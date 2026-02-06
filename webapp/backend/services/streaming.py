"""
Streaming service for real-time agent communication via Server-Sent Events (SSE)

This module handles the SSE protocol for streaming agent responses to the frontend.
"""

import json
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional, List
from datetime import datetime

from fastapi.responses import StreamingResponse


class StreamEvent:
    """Base streaming event"""

    def __init__(self, event: str, data: Dict[str, Any], timestamp: datetime = None):
        self.event = event
        self.data = data
        self.timestamp = timestamp or datetime.utcnow()

    def to_sse(self) -> str:
        """Format as Server-Sent Event"""
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


class ThinkingEvent(StreamEvent):
    """Agent is thinking/reasoning"""

    def __init__(self, data: Dict[str, Any], timestamp: datetime = None):
        super().__init__("thinking", data, timestamp)


class ToolStartEvent(StreamEvent):
    """Tool execution started"""

    def __init__(self, data: Dict[str, Any], timestamp: datetime = None):
        super().__init__("tool_start", data, timestamp)


class ToolResultEvent(StreamEvent):
    """Tool execution completed"""

    def __init__(self, data: Dict[str, Any], timestamp: datetime = None):
        super().__init__("tool_result", data, timestamp)


class CodeOutputEvent(StreamEvent):
    """Code execution output (stdout, stderr, plots)"""

    def __init__(self, data: Dict[str, Any], timestamp: datetime = None):
        super().__init__("code_output", data, timestamp)


class TextDeltaEvent(StreamEvent):
    """Text response chunk"""

    def __init__(self, data: Dict[str, Any], timestamp: datetime = None):
        super().__init__("text_delta", data, timestamp)


class ErrorEvent(StreamEvent):
    """Error occurred"""

    def __init__(self, data: Dict[str, Any], timestamp: datetime = None):
        super().__init__("error", data, timestamp)


class DoneEvent(StreamEvent):
    """Processing complete"""

    def __init__(self, data: Dict[str, Any], timestamp: datetime = None):
        super().__init__("done", data, timestamp)


class StreamingService:
    """
    Handles Server-Sent Events (SSE) streaming for agent responses.

    Features:
    - Tracks active streams for cancellation support
    - Formats events according to SSE protocol
    - Handles client disconnections gracefully
    """

    def __init__(self):
        self.active_streams: Dict[str, bool] = {}

    async def create_sse_response(
        self,
        generator: AsyncGenerator[StreamEvent, None]
    ) -> StreamingResponse:
        """
        Create a StreamingResponse for SSE.

        Args:
            generator: Async generator yielding StreamEvent objects

        Returns:
            StreamingResponse configured for SSE
        """
        return StreamingResponse(
            self._format_sse_stream(generator),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )

    async def _format_sse_stream(
        self,
        generator: AsyncGenerator[StreamEvent, None]
    ) -> AsyncGenerator[str, None]:
        """
        Format events for SSE protocol.

        SSE format:
        event: <event_type>
        data: <json_data>

        <empty line>

        Args:
            generator: Async generator yielding StreamEvent objects

        Yields:
            Formatted SSE strings
        """
        try:
            async for event in generator:
                # Format as SSE
                sse_data = f"event: {event.event}\n"
                sse_data += f"data: {json.dumps(event.data)}\n\n"
                yield sse_data

                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            # Client disconnected - send final event
            yield "event: disconnect\ndata: {}\n\n"
        except Exception as e:
            # Send error event and close
            error_event = ErrorEvent(data={"error": str(e)})
            yield f"event: {error_event.event}\n"
            yield f"data: {json.dumps(error_event.data)}\n\n"

    async def stream_agent_response(
        self,
        message: str,
        chat_session_id: int,
        user_id: int,
        attached_files: List[str] = None,
        analysis_context: Dict[str, Any] = None
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Main agent streaming function - delegates to BioAgent service.

        Args:
            message: User's message
            chat_session_id: ID of the chat session
            user_id: ID of the user
            attached_files: Optional list of attached file paths
            analysis_context: Optional analysis context with input files

        Yields:
            StreamEvent objects
        """
        stream_id = f"{user_id}_{chat_session_id}_{datetime.utcnow().isoformat()}"
        self.active_streams[stream_id] = True

        try:
            # Import here to avoid circular imports
            from services.agent_service import bioagent_service

            # Stream all events from the BioAgent service
            async for event in bioagent_service.process_message(
                message=message,
                chat_session_id=chat_session_id,
                user_id=user_id,
                attached_files=attached_files or [],
                analysis_context=analysis_context
            ):
                if not self.active_streams.get(stream_id, False):
                    break
                yield event

        except asyncio.CancelledError:
            # Client disconnected
            self.active_streams[stream_id] = False
            raise
        except Exception as e:
            yield ErrorEvent(data={
                "error": f"Agent execution failed: {str(e)}",
                "details": "Please try again or contact support if the issue persists"
            })
        finally:
            # Cleanup
            self.active_streams.pop(stream_id, None)

    def cancel_stream(self, stream_id: str) -> bool:
        """
        Cancel an active stream.

        Args:
            stream_id: ID of the stream to cancel

        Returns:
            True if stream was cancelled, False if not found
        """
        if stream_id in self.active_streams:
            self.active_streams[stream_id] = False
            return True
        return False


# Global streaming service instance
streaming_service = StreamingService()


# Helper functions for creating events
def create_thinking_event(content: str) -> ThinkingEvent:
    """Create a thinking event"""
    return ThinkingEvent(data={"content": content})


def create_tool_start_event(tool_name: str, tool_input: Dict[str, Any]) -> ToolStartEvent:
    """Create a tool start event"""
    return ToolStartEvent(data={"tool": tool_name, "input": tool_input})


def create_tool_result_event(
    tool_name: str,
    output: Any,
    execution_time: float,
    **metadata
) -> ToolResultEvent:
    """Create a tool result event"""
    return ToolResultEvent(data={
        "tool": tool_name,
        "output": output,
        "execution_time": execution_time,
        **metadata
    })


def create_code_output_event(
    stdout: str = "",
    stderr: str = "",
    plots: list = None,
    execution_time: float = 0
) -> CodeOutputEvent:
    """Create a code output event"""
    return CodeOutputEvent(data={
        "stdout": stdout,
        "stderr": stderr,
        "plots": plots or [],
        "execution_time": execution_time
    })


def create_text_delta_event(delta: str) -> TextDeltaEvent:
    """Create a text delta event"""
    return TextDeltaEvent(data={"delta": delta})


def create_error_event(error: str, details: str = "") -> ErrorEvent:
    """Create an error event"""
    return ErrorEvent(data={"error": error, "details": details})


def create_done_event(message_id: Optional[int] = None, **metadata) -> DoneEvent:
    """Create a completion event"""
    return DoneEvent(data={"message_id": message_id, **metadata})
