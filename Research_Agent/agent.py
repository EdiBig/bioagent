"""
Research Agent — Main Agent Class.

The Research Agent is a postdoctoral-level AI research specialist
that integrates into the BioAgent multi-agent system.

It receives findings from other agents, conducts deep literature-backed
research, produces publication-quality reports with proper citations,
and generates presentation decks with data visualisations.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

from .config import ResearchAgentConfig
from .prompts.system import get_system_prompt
from .tools.definitions import get_research_tools, get_research_tool_names
from .workflows.study_planner import create_study_plan
from .inter_agent.protocols import (
    AgentMessage, ResearchRequest, ResearchOutput,
    AdvisoryMessage, ContextUpdate, MessageQueue,
    ResearchAgentMessageBuilder,
)


class ResearchAgent:
    """
    An agentic research specialist powered by Claude.

    Capabilities:
    - Deep literature search across PubMed, Semantic Scholar, Europe PMC,
      CrossRef, bioRxiv, Unpaywall
    - Citation management with multiple academic styles
    - Structured report generation with proper references
    - PowerPoint presentation creation with charts
    - Inter-agent advisory communication

    Usage:
        agent = ResearchAgent()
        response = agent.run("Review the role of TP53 in colorectal cancer progression")

    Integration with BioAgent Orchestrator:
        agent = ResearchAgent(config)
        result = agent.handle_research_request(request_message)
    """

    def __init__(self, config: ResearchAgentConfig | None = None):
        self.config = config or ResearchAgentConfig.from_env()

        # Validate
        issues = self.config.validate()
        if any("ANTHROPIC_API_KEY" in i for i in issues):
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "The Research Agent requires an Anthropic API key."
            )
        for issue in issues:
            self._log(f"⚠️  {issue}")

        # Anthropic client
        self.client = anthropic.Anthropic(api_key=self.config.anthropic_api_key)

        # Initialise literature clients (lazy — imported when first used)
        self._lit_orchestrator = None
        self._citation_manager = None

        # Message queue for inter-agent communication
        self.message_queue = MessageQueue()
        self.msg_builder = ResearchAgentMessageBuilder()

        # Conversation history for the agent loop
        self.messages: list[dict] = []

        # Session state
        self._session_log: list[dict] = []
        self._advisories_sent: list[AdvisoryMessage] = []

        # Workspace
        self.workspace = Path(self.config.workspace_dir)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ═══════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════

    def run(self, user_message: str,
            context: str = "",
            max_turns: int = 25) -> str:
        """
        Process a research request through the agentic loop.

        Args:
            user_message: The research question or task
            context: Optional context from other agents
            max_turns: Maximum agentic loop iterations

        Returns:
            Final response text from the agent
        """
        # Build the user message with optional context
        full_message = user_message
        if context:
            full_message = (
                f"{user_message}\n\n"
                f"--- Context from Other Agents ---\n{context}"
            )

        self.messages.append({"role": "user", "content": full_message})
        self._log(f"📨 User: {user_message[:100]}...")

        # Agentic loop
        for turn in range(max_turns):
            response = self._call_claude()

            # Check if we need to execute tools
            if response.stop_reason == "tool_use":
                # Extract tool calls and text
                assistant_content = response.content
                self.messages.append({"role": "assistant", "content": assistant_content})

                # Execute each tool call
                tool_results = []
                for block in assistant_content:
                    if block.type == "tool_use":
                        self._log(f"🔧 Tool: {block.name}")
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                self.messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "end_turn":
                # Final response
                final_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text += block.text

                self.messages.append({
                    "role": "assistant",
                    "content": response.content,
                })
                self._log(f"✅ Complete ({turn + 1} turns)")
                return final_text

            else:
                self._log(f"⚠️ Unexpected stop reason: {response.stop_reason}")
                break

        return "Research agent reached maximum turns without completing."

    def handle_research_request(self, request: ResearchRequest) -> ResearchOutput:
        """
        Handle a structured research request from the Orchestrator.

        This is the primary integration point for the multi-agent system.
        """
        # Build context from the request
        context_parts = []
        if request.agent_results:
            for agent_name, results in request.agent_results.items():
                context_parts.append(f"[{agent_name}]: {results}")

        context = "\n".join(context_parts)

        # Run the agent
        response = self.run(
            user_message=request.research_question,
            context=context,
        )

        # Build output message
        return self.msg_builder.research_output(
            conversation_id=request.conversation_id,
            summary=response,
            papers_cited=self._get_citation_count(),
            advisories=[a.to_dict() for a in self._advisories_sent],
        )

    def handle_context_update(self, update: ContextUpdate):
        """
        Receive a context update from another agent.

        This allows the Research Agent to incorporate new findings
        from other agents into its ongoing research.
        """
        context_msg = (
            f"New findings from {update.source_agent}:\n"
            f"Data type: {update.data_type}\n"
            f"Summary: {update.data_summary}\n"
        )
        if update.key_findings:
            context_msg += "Key findings:\n"
            for finding in update.key_findings:
                context_msg += f"  - {finding}\n"

        # Add to conversation as a system-like context injection
        self.messages.append({
            "role": "user",
            "content": (
                f"[SYSTEM: Context update from {update.source_agent}]\n"
                f"{context_msg}"
            )
        })
        self._log(f"📥 Context update from {update.source_agent}: {update.data_type}")

    def plan_study(self, research_question: str,
                   study_type: str = "literature_review",
                   scope: str = "comprehensive",
                   context: str = "") -> str:
        """
        Create a study plan without entering the full agent loop.

        Returns the plan as Markdown.
        """
        plan = create_study_plan(research_question, study_type, scope, context)
        return plan.to_markdown()

    def reset(self):
        """Reset conversation history and session state."""
        self.messages.clear()
        self._session_log.clear()
        self._advisories_sent.clear()
        self._citation_manager = None
        self._log("🔄 Session reset")

    # ═══════════════════════════════════════════════════════════
    # PRIVATE: CLAUDE API
    # ═══════════════════════════════════════════════════════════

    def _call_claude(self):
        """Call Claude API with current conversation."""
        return self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=get_system_prompt(
                citation_style=self.config.default_citation_style,
                focus_area="bioinformatics",
            ),
            tools=get_research_tools(),
            messages=self.messages,
        )

    # ═══════════════════════════════════════════════════════════
    # PRIVATE: TOOL EXECUTION
    # ═══════════════════════════════════════════════════════════

    def _execute_tool(self, name: str, input_data: dict) -> str:
        """Execute a tool and return the result as a string."""
        try:
            handler = self._tool_handlers.get(name)
            if handler:
                return handler(self, input_data)
            else:
                return f"Error: Unknown tool '{name}'"
        except Exception as e:
            self._log(f"❌ Tool error ({name}): {e}")
            return f"Error executing {name}: {str(e)}"

    def _handle_search_literature(self, input_data: dict) -> str:
        """Execute a multi-source literature search."""
        orchestrator = self._get_lit_orchestrator()
        query = input_data.get("query", "")
        sources = input_data.get("sources", ["pubmed", "semantic_scholar", "europe_pmc"])
        max_results = input_data.get("max_results_per_source", 20)
        year_from = input_data.get("year_from")
        year_to = input_data.get("year_to")

        result = orchestrator.search(
            query=query,
            sources=sources,
            max_per_source=max_results,
            year_from=year_from,
            year_to=year_to,
        )
        return result.to_agent_summary(max_papers=15)

    def _handle_get_paper_details(self, input_data: dict) -> str:
        """Fetch detailed metadata for a specific paper."""
        orchestrator = self._get_lit_orchestrator()
        identifier = input_data.get("identifier", "")
        id_type = input_data.get("identifier_type", "auto")

        paper = orchestrator.get_paper(identifier, id_type)
        if paper:
            details = paper.to_dict()
            details["abstract"] = paper.abstract  # Full abstract
            return json.dumps(details, indent=2)
        return f"Paper not found for identifier: {identifier}"

    def _handle_get_citation_network(self, input_data: dict) -> str:
        """Explore citation network of a paper."""
        orchestrator = self._get_lit_orchestrator()
        paper_id = input_data.get("paper_id", "")
        direction = input_data.get("direction", "both")
        max_results = input_data.get("max_results", 20)

        results = orchestrator.get_citation_network(
            paper_id, direction=direction, max_results=max_results
        )
        return results.to_agent_summary(max_papers=15)

    def _handle_get_recommendations(self, input_data: dict) -> str:
        """Get ML-based paper recommendations."""
        orchestrator = self._get_lit_orchestrator()
        paper_id = input_data.get("paper_id", "")
        max_results = input_data.get("max_results", 10)

        papers = orchestrator.get_recommendations(paper_id, max_results)
        if papers:
            lines = [f"**Recommended papers based on:** {paper_id}", ""]
            for i, p in enumerate(papers, 1):
                lines.append(
                    f"{i}. **{p.title}** ({p.author_et_al}, {p.year})\n"
                    f"   {p.journal} | Citations: {p.citation_count} | DOI: {p.doi}"
                )
            return "\n".join(lines)
        return "No recommendations found."

    def _handle_find_oa_pdf(self, input_data: dict) -> str:
        """Find open access PDF."""
        orchestrator = self._get_lit_orchestrator()
        doi = input_data.get("doi", "")
        url = orchestrator.find_open_access_pdf(doi)
        if url:
            return f"Open access PDF found: {url}"
        return f"No open access PDF found for DOI: {doi}"

    def _handle_add_citation(self, input_data: dict) -> str:
        """Register a paper in the citation manager."""
        manager = self._get_citation_manager()
        # Build a Paper object from the input
        from .literature.clients import Paper, Author

        authors = []
        for name in input_data.get("authors", []):
            authors.append(Author(name=name))

        paper = Paper(
            title=input_data.get("title", ""),
            authors=authors,
            year=input_data.get("year", 0),
            journal=input_data.get("journal", ""),
            doi=input_data.get("doi", ""),
            pmid=input_data.get("pmid", ""),
        )

        citation_text = manager.cite(paper)
        return f"Citation registered: {citation_text}"

    def _handle_format_references(self, input_data: dict) -> str:
        """Generate formatted reference list."""
        manager = self._get_citation_manager()
        style = input_data.get("style", self.config.default_citation_style)

        if style != manager.style.__class__.__name__.lower().replace("style", ""):
            # Switch style if different from current
            pass  # TODO: implement style switching

        return manager.get_reference_list()

    def _handle_export_bibtex(self, input_data: dict) -> str:
        """Export citations as BibTeX."""
        manager = self._get_citation_manager()
        bibtex = manager.get_bibtex()
        # Save to file
        path = self.output_dir / "references.bib"
        path.write_text(bibtex)
        return f"BibTeX exported to {path}\n\n{bibtex}"

    def _handle_plan_study(self, input_data: dict) -> str:
        """Create a structured study plan."""
        plan = create_study_plan(
            research_question=input_data.get("research_question", ""),
            study_type=input_data.get("study_type", "literature_review"),
            scope=input_data.get("scope", "comprehensive"),
            context=input_data.get("context_from_agents", ""),
        )
        markdown = plan.to_markdown()
        # Save to file
        path = self.output_dir / "study_plan.md"
        path.write_text(markdown)
        return f"Study plan saved to {path}\n\n{markdown}"

    def _handle_generate_report_section(self, input_data: dict) -> str:
        """
        Generate a report section.

        Note: The actual content is generated by Claude in the agent loop.
        This tool primarily provides structure and saves the section.
        """
        section_type = input_data.get("section_type", "")
        section_title = input_data.get("section_title", section_type.title())
        content = input_data.get("content_guidance", "")

        # Save section
        path = self.workspace / f"report_section_{section_type}.md"
        path.write_text(f"## {section_title}\n\n{content}")

        return (
            f"Section '{section_title}' guidance registered. "
            f"Write the section content using the literature you've gathered, "
            f"with proper inline citations."
        )

    def _handle_compile_report(self, input_data: dict) -> str:
        """Compile all sections into a complete report."""
        title = input_data.get("title", "Research Report")
        authors = input_data.get("authors", ["BioAgent Research Team"])
        citation_style = input_data.get("citation_style", "vancouver")

        # Collect all section files
        sections = sorted(self.workspace.glob("report_section_*.md"))

        report_lines = [
            f"# {title}",
            "",
            f"**Authors:** {', '.join(authors)}",
            f"**Date:** {datetime.now().strftime('%d %B %Y')}",
            f"**Citation Style:** {citation_style}",
            "",
            "---",
            "",
        ]

        for section_path in sections:
            report_lines.append(section_path.read_text())
            report_lines.append("")

        # Add references
        manager = self._get_citation_manager()
        if manager.count() > 0:
            report_lines.append(manager.get_reference_list())

        report = "\n".join(report_lines)
        path = self.output_dir / "research_report.md"
        path.write_text(report)

        return f"Report compiled and saved to {path} ({manager.count()} references)"

    def _handle_generate_presentation(self, input_data: dict) -> str:
        """Generate a PPTX presentation."""
        from .presentations.generator import (
            PresentationSpec, SlideContent, generate_pptxgenjs_code
        )

        slides = []
        for section in input_data.get("sections", []):
            slides.append(SlideContent(
                title=section.get("title", ""),
                key_points=section.get("key_points", []),
                speaker_notes=section.get("speaker_notes", ""),
                chart_data=section.get("chart_data"),
                chart_type=section.get("chart_type", "bar"),
                layout="chart" if section.get("chart_data") else "content",
            ))

        # Get references from citation manager
        refs = []
        manager = self._get_citation_manager()
        if manager.count() > 0:
            for paper in manager.get_all_papers():
                refs.append(f"{paper.author_et_al} ({paper.year}). {paper.title}. {paper.journal}.")

        spec = PresentationSpec(
            title=input_data.get("title", "Research Presentation"),
            subtitle=input_data.get("subtitle", ""),
            slides=slides,
            color_scheme=input_data.get("color_scheme", self.config.default_color_scheme),
            references=refs,
            include_references_slide=input_data.get("include_references_slide", True),
        )

        output_path = str(self.output_dir / "research_presentation.pptx")
        js_code = generate_pptxgenjs_code(spec, output_path)

        # Save JS file
        js_path = self.workspace / "generate_pptx.js"
        js_path.write_text(js_code)

        return (
            f"PptxGenJS code generated at {js_path}\n"
            f"Run with: node {js_path}\n"
            f"Output will be: {output_path}\n\n"
            f"Slides: {len(slides)} content + 1 title"
            + (" + 1 references" if spec.include_references_slide else "")
        )

    def _handle_add_chart_slide(self, input_data: dict) -> str:
        """Add a chart slide to the presentation."""
        # This stores chart data for later inclusion in the presentation
        chart_path = self.workspace / f"chart_{int(time.time())}.json"
        chart_path.write_text(json.dumps(input_data, indent=2))
        return f"Chart data saved to {chart_path}. Include in generate_presentation call."

    def _handle_advise_agent(self, input_data: dict) -> str:
        """Send an advisory message to another agent."""
        advisory = self.msg_builder.advisory(
            target_agent=input_data.get("target_agent", ""),
            advisory_type=input_data.get("advisory_type", ""),
            message=input_data.get("message", ""),
            priority=input_data.get("priority", "medium"),
            supporting_papers=input_data.get("supporting_papers", []),
        )

        # Send to message queue
        self.message_queue.send(advisory)
        self._advisories_sent.append(advisory)

        return (
            f"Advisory sent to {advisory.to_agent}:\n"
            f"Type: {advisory.advisory_type}\n"
            f"Priority: {advisory.priority}\n"
            f"Message: {advisory.message[:200]}..."
        )

    # Tool handler registry
    _tool_handlers = {
        "search_literature": _handle_search_literature,
        "get_paper_details": _handle_get_paper_details,
        "get_citation_network": _handle_get_citation_network,
        "get_paper_recommendations": _handle_get_recommendations,
        "find_open_access_pdf": _handle_find_oa_pdf,
        "add_citation": _handle_add_citation,
        "format_reference_list": _handle_format_references,
        "export_bibtex": _handle_export_bibtex,
        "plan_study": _handle_plan_study,
        "generate_report_section": _handle_generate_report_section,
        "compile_report": _handle_compile_report,
        "generate_presentation": _handle_generate_presentation,
        "add_chart_slide": _handle_add_chart_slide,
        "advise_agent": _handle_advise_agent,
    }

    # ═══════════════════════════════════════════════════════════
    # PRIVATE: LAZY INITIALISATION
    # ═══════════════════════════════════════════════════════════

    def _get_lit_orchestrator(self):
        """Lazy-init the literature search orchestrator."""
        if self._lit_orchestrator is None:
            from .literature.clients import LiteratureSearchOrchestrator
            self._lit_orchestrator = LiteratureSearchOrchestrator(
                ncbi_api_key=self.config.ncbi_api_key,
                ncbi_email=self.config.ncbi_email,
                s2_api_key=self.config.semantic_scholar_api_key,
            )
        return self._lit_orchestrator

    def _get_citation_manager(self):
        """Lazy-init the citation manager."""
        if self._citation_manager is None:
            from .citations.manager import CitationManager, VancouverStyle
            style_map = {
                "vancouver": VancouverStyle,
                # Add others as they're implemented
            }
            style_cls = style_map.get(
                self.config.default_citation_style, VancouverStyle
            )
            self._citation_manager = CitationManager(style=style_cls())
        return self._citation_manager

    def _get_citation_count(self) -> int:
        """Get number of citations registered."""
        if self._citation_manager:
            return self._citation_manager.count()
        return 0

    # ═══════════════════════════════════════════════════════════
    # LOGGING
    # ═══════════════════════════════════════════════════════════

    def _log(self, message: str):
        """Log a message to session log and stderr."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
        }
        self._session_log.append(entry)
        print(f"[ResearchAgent] {message}", file=sys.stderr)
