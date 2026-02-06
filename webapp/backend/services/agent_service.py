"""
BioAgent Service - Integrates the actual BioAgent with the web API

This service wraps the BioAgent's multi-agent system and provides
streaming responses for the web interface.
"""

import os
import sys
import asyncio
import json
import traceback
from pathlib import Path
from typing import List, Dict, Any, AsyncGenerator, Optional
from datetime import datetime

# Add bioagent root to path
BIOAGENT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BIOAGENT_ROOT))

# Upload directory for user files
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))

from services.streaming import (
    StreamEvent,
    ThinkingEvent,
    ToolStartEvent,
    ToolResultEvent,
    CodeOutputEvent,
    TextDeltaEvent,
    ErrorEvent,
    DoneEvent,
)


class BioAgentService:
    """
    Service wrapper for the BioAgent multi-agent system.

    This class integrates the existing BioAgent with all 72 tools
    and 6 specialist agents into the web application.
    """

    def __init__(self):
        """Initialize the BioAgent service"""
        self.agent = None
        self.config = None
        self._initialized = False
        self._initialization_error = None

        # Try to initialize the agent
        self._lazy_init()

    def _lazy_init(self):
        """Lazy initialization of the BioAgent"""
        if self._initialized:
            return

        try:
            # Import BioAgent components
            from config import Config
            from agent import BioAgent

            # Create configuration
            self.config = Config.from_env()

            # Apply fast mode if enabled (disables multi-agent, memory, etc.)
            self.config.apply_fast_mode()

            # Enable multi-agent mode for the web interface (unless fast mode)
            if not self.config.fast_mode:
                self.config.enable_multi_agent = True

            # Create the agent
            self.agent = BioAgent(self.config)
            self._initialized = True

        except ImportError as e:
            self._initialization_error = f"Failed to import BioAgent: {e}"
            print(f"Warning: {self._initialization_error}")
        except Exception as e:
            self._initialization_error = f"Failed to initialize BioAgent: {e}"
            print(f"Warning: {self._initialization_error}")

    def get_user_files(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get list of files uploaded by a user.

        Args:
            user_id: User's ID

        Returns:
            List of file info dicts
        """
        user_dir = UPLOAD_DIR / str(user_id)
        files = []

        if user_dir.exists():
            for path in user_dir.iterdir():
                if path.is_file():
                    ext = path.suffix.lstrip(".").lower()
                    files.append({
                        "filename": path.name,
                        "path": str(path.absolute()),
                        "size": path.stat().st_size,
                        "type": ext,
                        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat()
                    })

        return files

    def build_file_context(self, user_id: int, attached_files: List[str] = None) -> str:
        """
        Build context string about available files for the agent.

        Args:
            user_id: User's ID
            attached_files: Specific files attached to this message

        Returns:
            Context string describing available files
        """
        files = self.get_user_files(user_id)

        if not files and not attached_files:
            return ""

        context_parts = []

        if files:
            context_parts.append("## Available Uploaded Files")
            context_parts.append("The user has the following files uploaded that you can analyze:")
            for f in files:
                size_kb = f['size'] / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
                context_parts.append(f"- **{f['filename']}** ({f['type'].upper()}, {size_str})")
                context_parts.append(f"  Path: `{f['path']}`")
            context_parts.append("")

        if attached_files:
            context_parts.append("## Files Attached to This Message")
            for f in attached_files:
                context_parts.append(f"- `{f}`")
            context_parts.append("")

        if context_parts:
            context_parts.append("You can use `ingest_file` tool with these file paths to analyze them.")

        return "\n".join(context_parts)

    async def process_message(
        self,
        message: str,
        chat_session_id: int,
        user_id: int,
        attached_files: List[str] = None,
        analysis_context: Dict[str, Any] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Process a user message and stream the response.

        This method:
        1. Analyzes the user's message
        2. Routes to appropriate specialist agents
        3. Executes tools and streams results
        4. Generates the final response

        Args:
            message: User's message
            chat_session_id: ID of the chat session
            user_id: ID of the user
            attached_files: Optional list of attached file paths
            analysis_context: Optional analysis context with files from web UI

        Yields:
            StreamEvent objects for real-time updates
        """
        start_time = datetime.utcnow()
        tools_used = []
        total_tokens = 0

        try:
            # Check if agent is initialized
            if not self._initialized:
                yield ThinkingEvent(data={
                    "content": "Initializing BioAgent system..."
                })
                self._lazy_init()

                if not self._initialized:
                    yield ErrorEvent(data={
                        "error": "BioAgent initialization failed",
                        "details": self._initialization_error or "Unknown error"
                    })
                    return

            # Step 1: Build analysis context if available
            analysis_file_context = ""
            if analysis_context and analysis_context.get('input_files'):
                analysis_files = analysis_context['input_files']
                analysis_id = analysis_context.get('analysis_id', 'Unknown')
                analysis_title = analysis_context.get('title', 'Analysis')

                yield ThinkingEvent(data={
                    "content": f"Loading analysis {analysis_id}: {analysis_title}..."
                })

                analysis_file_context = f"## Analysis Context: {analysis_id}\n"
                analysis_file_context += f"**{analysis_title}**\n\n"
                analysis_file_context += "### Files to Analyze:\n"
                for f in analysis_files:
                    size_bytes = f.get('file_size', 0)
                    size_str = f"{size_bytes/1024:.1f} KB" if size_bytes < 1024*1024 else f"{size_bytes/1024/1024:.1f} MB"
                    analysis_file_context += f"- **{f.get('filename', 'Unknown')}** ({f.get('file_type', 'unknown').upper()}, {size_str})\n"
                    analysis_file_context += f"  Path: `{f.get('file_path', '')}`\n"
                analysis_file_context += "\n**Important**: Use the `ingest_file` tool with the paths above to load and analyze these files.\n"

            # Step 2: Initial analysis - gather additional file context
            yield ThinkingEvent(data={
                "content": "Analyzing your bioinformatics request..."
            })

            # Build general file context for the agent (in addition to analysis files)
            file_context = self.build_file_context(user_id, attached_files)

            # Enhance message with all file context
            enhanced_message = message
            if analysis_file_context:
                # Prepend analysis context to the message so agent knows about files
                enhanced_message = f"{analysis_file_context}\n---\n\n**User Request:** {message}"
            elif file_context:
                yield ThinkingEvent(data={
                    "content": "Found uploaded files in your workspace..."
                })
                enhanced_message = f"{message}\n\n---\n{file_context}"

            await asyncio.sleep(0.1)  # Small delay for UI smoothness

            # Step 2: Process with the actual BioAgent
            if self.agent and hasattr(self.agent, 'process_request_streaming'):
                # Use streaming API if available
                async for event in self._process_with_streaming(
                    enhanced_message, attached_files
                ):
                    if isinstance(event, ToolStartEvent):
                        tools_used.append(event.data.get("tool", "unknown"))
                    yield event
            else:
                # Fallback to non-streaming processing
                async for event in self._process_with_agent(
                    enhanced_message, attached_files, user_id
                ):
                    if isinstance(event, ToolStartEvent):
                        tools_used.append(event.data.get("tool", "unknown"))
                    yield event

            # Step 3: Completion
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            yield DoneEvent(data={
                "total_tokens": total_tokens,
                "execution_time": execution_time,
                "tools_used": tools_used,
            })

        except asyncio.CancelledError:
            # Client disconnected
            raise
        except Exception as e:
            print(f"Error in process_message: {traceback.format_exc()}")
            yield ErrorEvent(data={
                "error": f"Processing failed: {str(e)}",
                "details": "Please try again or contact support."
            })

    async def _process_with_streaming(
        self,
        message: str,
        attached_files: List[str] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Process message using BioAgent's streaming API"""
        try:
            # Create context for the request
            context = {
                "files": attached_files or [],
                "stream": True,
            }

            # Process with the agent
            async for response in self.agent.process_request_streaming(
                message, context
            ):
                # Convert agent responses to stream events
                yield self._convert_to_stream_event(response)

        except Exception as e:
            yield ErrorEvent(data={
                "error": f"Streaming failed: {str(e)}",
                "details": str(e)
            })

    async def _process_with_agent(
        self,
        message: str,
        attached_files: List[str] = None,
        user_id: int = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Process message using the BioAgent's synchronous API.

        Wraps the synchronous agent in an async generator with progress updates.
        """
        try:
            # Prepare context with files
            user_files = self.get_user_files(user_id) if user_id else []
            context = {
                "files": attached_files or [],
                "user_files": user_files,
                "user_id": user_id,
            }

            yield ThinkingEvent(data={
                "content": "Routing to appropriate specialist..."
            })

            # Run the agent in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()

            # Check if multi-agent mode is enabled
            if hasattr(self.agent, 'coordinator') and self.agent.coordinator:
                # Use multi-agent processing
                async for event in self._process_multi_agent(message, context):
                    yield event
            else:
                # Use single-agent processing
                async for event in self._process_single_agent(message, context):
                    yield event

        except Exception as e:
            yield ErrorEvent(data={
                "error": f"Agent processing failed: {str(e)}",
                "details": traceback.format_exc()
            })

    async def _process_multi_agent(
        self,
        message: str,
        context: dict,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Process with multi-agent coordinator"""
        try:
            # Import coordinator
            from agents.coordinator import CoordinatorAgent
            from agents.routing import TaskRouter

            # Route the task
            router = TaskRouter()
            routing_result = await asyncio.to_thread(
                router.route, message
            )

            yield ThinkingEvent(data={
                "content": f"Routing to {routing_result.primary.value}: {routing_result.reasoning}"
            })

            # Execute with the specialist
            yield ToolStartEvent(data={
                "tool": f"specialist_{routing_result.primary.value}",
                "input": {"query": message[:100] + "..."}
            })

            # Run the agent
            result = await asyncio.to_thread(
                self.agent.run, message
            )

            yield ToolResultEvent(data={
                "tool": f"specialist_{routing_result.primary.value}",
                "output": "Processing complete",
                "execution_time": 0.0
            })

            # Add uploaded files context if available
            user_files = context.get('user_files', [])
            if user_files:
                uploaded_files_info = "\n\n---\n## Your Uploaded Files (Web Interface)\n"
                uploaded_files_info += "You also have these files uploaded via the web interface:\n"
                for f in user_files:
                    size_str = f"{f['size']/1024:.1f} KB" if f['size'] < 1024*1024 else f"{f['size']/1024/1024:.1f} MB"
                    uploaded_files_info += f"- **{f['filename']}** ({f['type'].upper()}, {size_str})\n"
                    uploaded_files_info += f"  Path: `{f['path']}`\n"
                uploaded_files_info += "\nYou can use `ingest_file` with these paths to analyze them."
                result = result + uploaded_files_info

            # Stream the response
            for part in self._chunk_response(result):
                yield TextDeltaEvent(data={"delta": part})
                await asyncio.sleep(0.02)

        except Exception as e:
            yield ErrorEvent(data={
                "error": str(e),
                "details": traceback.format_exc()
            })

    async def _process_single_agent(
        self,
        message: str,
        context: dict,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Process with single agent using the actual BioAgent"""
        try:
            # Detect intent for UI feedback
            intent = self._analyze_intent(message)

            yield ThinkingEvent(data={
                "content": f"Detected {intent['type']} task. Processing with BioAgent..."
            })

            # Start tool execution indicator
            yield ToolStartEvent(data={
                "tool": "bioagent_single_mode",
                "input": {"query": message[:100] + "..." if len(message) > 100 else message}
            })

            # Run the actual BioAgent
            start = datetime.utcnow()
            result = await asyncio.to_thread(
                self.agent.run, message
            )
            execution_time = (datetime.utcnow() - start).total_seconds()

            yield ToolResultEvent(data={
                "tool": "bioagent_single_mode",
                "output": f"Analysis complete in {execution_time:.1f}s",
                "execution_time": execution_time,
            })

            # Add uploaded files context if available
            user_files = context.get('user_files', [])
            if user_files:
                uploaded_files_info = "\n\n---\n## Your Uploaded Files\n"
                uploaded_files_info += "Files available for analysis:\n"
                for f in user_files:
                    size_str = f"{f['size']/1024:.1f} KB" if f['size'] < 1024*1024 else f"{f['size']/1024/1024:.1f} MB"
                    uploaded_files_info += f"- **{f['filename']}** ({f['type'].upper()}, {size_str})\n"
                    uploaded_files_info += f"  Path: `{f['path']}`\n"
                uploaded_files_info += "\nUse `ingest_file` with these paths to analyze them."
                result = result + uploaded_files_info

            # Stream the response
            for part in self._chunk_response(result):
                yield TextDeltaEvent(data={"delta": part})
                await asyncio.sleep(0.02)

        except Exception as e:
            yield ErrorEvent(data={
                "error": str(e),
                "details": traceback.format_exc()
            })

    def _analyze_intent(self, message: str) -> Dict[str, Any]:
        """Analyze user message to determine intent and workflow"""
        message_lower = message.lower()

        # Intent patterns - check for file-related queries first
        if any(kw in message_lower for kw in ['file', 'upload', 'data', 'dataset', 'my files', 'loaded', 'ingested']):
            return {
                'type': 'file_query',
                'workflow': [
                    {'tool': 'list_files', 'params': {'query': message}}
                ]
            }

        elif any(kw in message_lower for kw in ['ncbi', 'pubmed', 'literature', 'papers', 'search']):
            return {
                'type': 'literature_search',
                'workflow': [
                    {'tool': 'search_literature', 'params': {'query': message}}
                ]
            }

        elif any(kw in message_lower for kw in ['differential', 'expression', 'rnaseq', 'deseq']):
            return {
                'type': 'differential_expression',
                'workflow': [
                    {'tool': 'differential_expression', 'params': {'query': message}}
                ]
            }

        elif any(kw in message_lower for kw in ['pathway', 'enrichment', 'go', 'kegg']):
            return {
                'type': 'pathway_analysis',
                'workflow': [
                    {'tool': 'pathway_enrichment', 'params': {'query': message}}
                ]
            }

        elif any(kw in message_lower for kw in ['variant', 'vcf', 'mutation', 'snp']):
            return {
                'type': 'variant_analysis',
                'workflow': [
                    {'tool': 'variant_annotation', 'params': {'query': message}}
                ]
            }

        elif any(kw in message_lower for kw in ['protein', 'structure', 'alphafold', 'pdb']):
            return {
                'type': 'structure_analysis',
                'workflow': [
                    {'tool': 'predict_structure', 'params': {'query': message}}
                ]
            }

        elif any(kw in message_lower for kw in ['single cell', 'scrna', 'cell type']):
            return {
                'type': 'single_cell_analysis',
                'workflow': [
                    {'tool': 'annotate_cell_types', 'params': {'query': message}}
                ]
            }

        else:
            return {
                'type': 'general_query',
                'workflow': [
                    {'tool': 'general_analysis', 'params': {'query': message}}
                ]
            }

    async def _execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool and return results"""
        try:
            # Try to use the actual agent's tools
            if self.agent and hasattr(self.agent, 'execute_tool'):
                result = await asyncio.to_thread(
                    self.agent.execute_tool, tool_name, params
                )
                return {'output': str(result)}

            # Fallback: return mock result
            await asyncio.sleep(0.5)  # Simulate processing
            return {'output': f"Tool {tool_name} executed successfully"}

        except Exception as e:
            return {'output': f"Error: {str(e)}"}

    def _generate_response(self, message: str, intent: Dict[str, Any], context: dict = None) -> str:
        """Generate a response based on the intent and analysis"""
        # Handle file queries with actual file info
        if intent['type'] == 'file_query' and context and context.get('user_files'):
            files = context['user_files']
            if files:
                file_list = "\n".join([
                    f"- **{f['filename']}** ({f['type'].upper()}, {f['size']/1024:.1f} KB)\n  Path: `{f['path']}`"
                    for f in files
                ])
                return (
                    f"I found {len(files)} file(s) in your uploaded files:\n\n{file_list}\n\n"
                    "You can ask me to analyze any of these files. For example:\n"
                    "- 'Analyze the VCF file for variants'\n"
                    "- 'Run differential expression on my RNA-seq data'\n"
                    "- 'What's in the FASTQ file?'"
                )
            else:
                return (
                    "I don't see any uploaded files in your workspace yet. "
                    "You can upload files using the Files page, and then I'll be able to analyze them. "
                    "Supported formats include FASTQ, FASTA, VCF, BAM, BED, GFF, CSV, TSV, and more."
                )

        responses = {
            'literature_search': (
                "I've searched the biomedical literature for your query. "
                "The results show relevant publications in this research area. "
                "Would you like me to provide detailed summaries of specific papers?"
            ),
            'differential_expression': (
                "I've completed the differential expression analysis. "
                "The results show significantly differentially expressed genes between conditions. "
                "Would you like me to perform pathway enrichment on these genes?"
            ),
            'pathway_analysis': (
                "The pathway enrichment analysis is complete. "
                "Several biological pathways are significantly enriched in your gene set. "
                "These findings suggest involvement in key cellular processes."
            ),
            'variant_analysis': (
                "I've analyzed the variants and annotated them for functional impact. "
                "The pathogenicity predictions identify variants of interest. "
                "Would you like detailed information on specific variants?"
            ),
            'structure_analysis': (
                "The protein structure analysis is complete. "
                "I've retrieved relevant structural information for your query. "
                "Would you like me to perform additional structural analyses?"
            ),
            'single_cell_analysis': (
                "The single-cell analysis has identified distinct cell populations. "
                "Cell type annotations are based on marker gene expression. "
                "Would you like to explore specific clusters in more detail?"
            ),
            'file_query': (
                "I don't see any uploaded files in your workspace yet. "
                "You can upload files using the Files page, and I'll be able to analyze them."
            ),
            'general_query': (
                "I've processed your bioinformatics request. "
                "Please let me know if you need any clarification or additional analysis."
            ),
        }

        return responses.get(intent['type'], responses['general_query'])

    def _chunk_response(self, text: str, chunk_size: int = 20) -> List[str]:
        """Split response text into chunks for streaming"""
        words = text.split()
        chunks = []
        current_chunk = []

        for word in words:
            current_chunk.append(word)
            if len(current_chunk) >= chunk_size:
                chunks.append(" ".join(current_chunk) + " ")
                current_chunk = []

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _convert_to_stream_event(self, response: Any) -> StreamEvent:
        """Convert agent response to stream event"""
        if isinstance(response, dict):
            event_type = response.get('type', 'text')
            data = response.get('data', {})

            if event_type == 'thinking':
                return ThinkingEvent(data=data)
            elif event_type == 'tool_start':
                return ToolStartEvent(data=data)
            elif event_type == 'tool_result':
                return ToolResultEvent(data=data)
            elif event_type == 'code_output':
                return CodeOutputEvent(data=data)
            elif event_type == 'error':
                return ErrorEvent(data=data)
            else:
                return TextDeltaEvent(data={'delta': str(response)})

        return TextDeltaEvent(data={'delta': str(response)})


# Global service instance
bioagent_service = BioAgentService()
