"""
Session Summarization for conversation compression.

This module provides automatic summarization of conversation segments
using Claude to preserve key information while reducing token count.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .types import SessionSummary, estimate_tokens

if TYPE_CHECKING:
    import anthropic


class SummaryResult:
    """Result of a summarization operation."""

    def __init__(
        self,
        success: bool,
        message: str,
        summary: SessionSummary | None = None,
        summaries: list[SessionSummary] | None = None,
    ):
        self.success = success
        self.message = message
        self.summary = summary
        self.summaries = summaries or []

    def to_string(self) -> str:
        """Format for display."""
        if not self.success:
            return f"Summarization error: {self.message}"

        if self.summary:
            return (
                f"Session summarized:\n"
                f"  Rounds: {self.summary.start_round}-{self.summary.end_round}\n"
                f"  Compression: {self.summary.compression_ratio:.1%}\n"
                f"  Key findings: {len(self.summary.key_findings)}\n"
            )

        if self.summaries:
            lines = [f"Retrieved {len(self.summaries)} session summaries:"]
            for s in self.summaries:
                lines.append(
                    f"  - Rounds {s.start_round}-{s.end_round}: "
                    f"{s.summary[:100]}..."
                )
            return "\n".join(lines)

        return self.message


class SessionSummarizer:
    """Summarizes conversation segments using Claude.

    Triggers summarization after N rounds to compress conversation
    history while preserving key information, findings, and context.
    """

    def __init__(
        self,
        summaries_file: str,
        client: "anthropic.Anthropic",
        summary_after_rounds: int = 5,
        summary_model: str = "claude-sonnet-4-20250514",
        max_summary_tokens: int = 1000,
    ):
        """Initialize summarizer.

        Args:
            summaries_file: Path to JSON file for storing summaries
            client: Anthropic client for Claude API
            summary_after_rounds: Number of rounds between summaries
            summary_model: Model to use for summarization
            max_summary_tokens: Maximum tokens per summary
        """
        self.summaries_file = Path(summaries_file)
        self.summaries_file.parent.mkdir(parents=True, exist_ok=True)
        self.client = client
        self.summary_after_rounds = summary_after_rounds
        self.summary_model = summary_model
        self.max_summary_tokens = max_summary_tokens

        self._summaries: dict[str, SessionSummary] = {}
        self._last_summarized_round: int = 0
        self._load_summaries()

    def _load_summaries(self) -> None:
        """Load summaries from disk."""
        if self.summaries_file.exists():
            try:
                with open(self.summaries_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._summaries = {
                        k: SessionSummary.from_dict(v)
                        for k, v in data.get("summaries", {}).items()
                    }
                    self._last_summarized_round = data.get(
                        "last_summarized_round", 0
                    )
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load summaries: {e}")
                self._summaries = {}

    def _save_summaries(self) -> None:
        """Save summaries to disk."""
        data = {
            "summaries": {k: v.to_dict() for k, v in self._summaries.items()},
            "last_summarized_round": self._last_summarized_round,
        }
        with open(self.summaries_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def should_summarize(self, current_round: int) -> bool:
        """Check if summarization should be triggered.

        Args:
            current_round: Current conversation round

        Returns:
            True if summarization should be triggered
        """
        rounds_since_last = current_round - self._last_summarized_round
        return rounds_since_last >= self.summary_after_rounds

    def summarize_segment(
        self,
        messages: list[dict],
        start_round: int,
        end_round: int,
        session_id: str,
        tools_used: list[str] | None = None,
    ) -> SummaryResult:
        """Summarize a segment of conversation.

        Args:
            messages: Conversation messages to summarize
            start_round: Starting round number
            end_round: Ending round number
            session_id: Current session identifier
            tools_used: List of tools used in this segment

        Returns:
            SummaryResult with the generated summary
        """
        if not messages:
            return SummaryResult(
                success=False,
                message="No messages to summarize",
            )

        # Build conversation text for summarization
        conversation_text = self._format_messages_for_summary(messages)
        original_tokens = estimate_tokens(conversation_text)

        if original_tokens < 500:
            return SummaryResult(
                success=False,
                message="Conversation too short to summarize",
            )

        # Create summarization prompt
        prompt = self._build_summary_prompt(
            conversation_text, tools_used or []
        )

        try:
            # Call Claude for summarization
            response = self.client.messages.create(
                model=self.summary_model,
                max_tokens=self.max_summary_tokens,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            summary_text = response.content[0].text
            summary_data = self._parse_summary_response(summary_text)

            # Create summary object
            summary_id = str(uuid.uuid4())
            summary = SessionSummary(
                id=summary_id,
                session_id=session_id,
                start_round=start_round,
                end_round=end_round,
                summary=summary_data.get("summary", summary_text),
                key_findings=summary_data.get("key_findings", []),
                tools_used=tools_used or [],
                entities_mentioned=summary_data.get("entities", []),
                artifacts_created=summary_data.get("artifacts", []),
                token_count_original=original_tokens,
                token_count_summary=estimate_tokens(summary_text),
            )

            # Store and save
            self._summaries[summary_id] = summary
            self._last_summarized_round = end_round
            self._save_summaries()

            return SummaryResult(
                success=True,
                message="Segment summarized successfully",
                summary=summary,
            )

        except Exception as e:
            return SummaryResult(
                success=False,
                message=f"Summarization failed: {e}",
            )

    def _format_messages_for_summary(self, messages: list[dict]) -> str:
        """Format messages into text for summarization."""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # Handle content blocks
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            text_parts.append(
                                f"[Tool: {block.get('name')}]"
                            )
                        elif block.get("type") == "tool_result":
                            result = block.get("content", "")
                            if len(result) > 500:
                                result = result[:500] + "..."
                            text_parts.append(f"[Result: {result}]")
                    elif hasattr(block, "type"):
                        if block.type == "text":
                            text_parts.append(block.text)
                        elif block.type == "tool_use":
                            text_parts.append(f"[Tool: {block.name}]")
                content = "\n".join(text_parts)

            if isinstance(content, str) and content.strip():
                lines.append(f"{role.upper()}: {content}")

        return "\n\n".join(lines)

    def _build_summary_prompt(
        self, conversation: str, tools_used: list[str]
    ) -> str:
        """Build the summarization prompt."""
        return f"""Summarize this bioinformatics analysis conversation segment.

CONVERSATION:
{conversation}

TOOLS USED: {', '.join(tools_used) if tools_used else 'None'}

Provide a structured summary with:
1. SUMMARY: A concise 2-3 paragraph summary of what was accomplished
2. KEY_FINDINGS: Bullet points of important discoveries or results
3. ENTITIES: Any biological entities mentioned (genes, proteins, pathways, etc.)
4. ARTIFACTS: Any files or data created

Format your response as:
SUMMARY:
[Your summary here]

KEY_FINDINGS:
- [Finding 1]
- [Finding 2]
...

ENTITIES:
- [Entity 1]
- [Entity 2]
...

ARTIFACTS:
- [Artifact 1]
...

Be concise but preserve all important scientific findings and context."""

    def _parse_summary_response(self, response: str) -> dict[str, Any]:
        """Parse structured summary response."""
        result = {
            "summary": "",
            "key_findings": [],
            "entities": [],
            "artifacts": [],
        }

        current_section = None
        lines = response.strip().split("\n")

        for line in lines:
            line_stripped = line.strip()

            if line_stripped.startswith("SUMMARY:"):
                current_section = "summary"
                remainder = line_stripped[8:].strip()
                if remainder:
                    result["summary"] = remainder
            elif line_stripped.startswith("KEY_FINDINGS:"):
                current_section = "key_findings"
            elif line_stripped.startswith("ENTITIES:"):
                current_section = "entities"
            elif line_stripped.startswith("ARTIFACTS:"):
                current_section = "artifacts"
            elif current_section:
                if current_section == "summary":
                    if result["summary"]:
                        result["summary"] += "\n" + line_stripped
                    else:
                        result["summary"] = line_stripped
                elif line_stripped.startswith("- "):
                    item = line_stripped[2:].strip()
                    if item:
                        result[current_section].append(item)

        # If no structured response, use whole text as summary
        if not result["summary"]:
            result["summary"] = response

        return result

    def get_context_summaries(
        self,
        session_id: str | None = None,
        max_summaries: int = 10,
    ) -> list[SessionSummary]:
        """Get summaries for context injection.

        Args:
            session_id: Filter by session ID (None for all)
            max_summaries: Maximum number of summaries to return

        Returns:
            List of summaries, most recent first
        """
        summaries = list(self._summaries.values())

        # Filter by session if specified
        if session_id:
            summaries = [s for s in summaries if s.session_id == session_id]

        # Sort by end_round descending (most recent first)
        summaries.sort(key=lambda s: s.end_round, reverse=True)

        return summaries[:max_summaries]

    def format_summaries_for_context(
        self,
        summaries: list[SessionSummary],
        max_tokens: int = 10000,
    ) -> str:
        """Format summaries for context injection.

        Args:
            summaries: Summaries to format
            max_tokens: Maximum tokens for formatted output

        Returns:
            Formatted summary text
        """
        if not summaries:
            return ""

        lines = ["## Previous Session Summaries\n"]
        current_tokens = estimate_tokens(lines[0])

        for summary in summaries:
            summary_text = (
                f"### Rounds {summary.start_round}-{summary.end_round}\n"
                f"{summary.summary}\n"
            )

            if summary.key_findings:
                summary_text += "\n**Key Findings:**\n"
                for finding in summary.key_findings[:5]:
                    summary_text += f"- {finding}\n"

            summary_tokens = estimate_tokens(summary_text)
            if current_tokens + summary_tokens > max_tokens:
                break

            lines.append(summary_text)
            current_tokens += summary_tokens

        return "\n".join(lines)

    def get_all_summaries(self) -> SummaryResult:
        """Get all stored summaries.

        Returns:
            SummaryResult with all summaries
        """
        summaries = list(self._summaries.values())
        summaries.sort(key=lambda s: s.created_at, reverse=True)

        return SummaryResult(
            success=True,
            message=f"Found {len(summaries)} summaries",
            summaries=summaries,
        )

    def delete_summary(self, summary_id: str) -> SummaryResult:
        """Delete a summary.

        Args:
            summary_id: Summary identifier

        Returns:
            SummaryResult with status
        """
        if summary_id not in self._summaries:
            return SummaryResult(
                success=False,
                message=f"Summary not found: {summary_id}",
            )

        del self._summaries[summary_id]
        self._save_summaries()

        return SummaryResult(
            success=True,
            message="Summary deleted",
        )

    def clear_session(self, session_id: str) -> SummaryResult:
        """Clear all summaries for a session.

        Args:
            session_id: Session identifier

        Returns:
            SummaryResult with status
        """
        to_delete = [
            sid for sid, s in self._summaries.items()
            if s.session_id == session_id
        ]

        for sid in to_delete:
            del self._summaries[sid]

        self._save_summaries()

        return SummaryResult(
            success=True,
            message=f"Cleared {len(to_delete)} summaries for session",
        )

    def get_stats(self) -> dict[str, Any]:
        """Get summarizer statistics.

        Returns:
            Dictionary with stats
        """
        total_original = sum(s.token_count_original for s in self._summaries.values())
        total_summary = sum(s.token_count_summary for s in self._summaries.values())

        return {
            "total_summaries": len(self._summaries),
            "last_summarized_round": self._last_summarized_round,
            "summary_after_rounds": self.summary_after_rounds,
            "total_original_tokens": total_original,
            "total_summary_tokens": total_summary,
            "overall_compression": (
                1 - (total_summary / total_original) if total_original > 0 else 0
            ),
        }
