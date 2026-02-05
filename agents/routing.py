"""
Task routing for multi-agent architecture.

Routes incoming queries to the appropriate specialist agent(s) using
a hybrid approach: fast keyword pattern matching with LLM fallback
for ambiguous queries.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import anthropic

from .base import SpecialistType


# Routing patterns for each specialist
# Patterns are (regex_pattern, weight) tuples
ROUTING_PATTERNS: dict[SpecialistType, list[tuple[str, float]]] = {
    SpecialistType.PIPELINE_ENGINEER: [
        # Workflow/pipeline keywords
        (r"\b(pipeline|workflow|nextflow|snakemake|wdl|nf-core)\b", 1.0),
        # Code execution indicators
        (r"\b(run|execute|write|create|build|implement)\s+(code|script|pipeline|analysis)\b", 0.8),
        (r"\b(python|r\s+code|bash|script)\b", 0.7),
        # Data processing
        (r"\b(process|align|map|call\s+variants|trim|qc)\s+(samples?|reads?|data)\b", 0.8),
        # Tool execution
        (r"\b(fastqc|multiqc|star|bwa|samtools|gatk|bcftools|deseq2|edger)\b", 0.7),
        # File operations
        (r"\b(save|write|output|generate)\s+(file|results?|report)\b", 0.5),
    ],

    SpecialistType.STATISTICIAN: [
        # Statistical methods
        (r"\b(differential\s+expression|de\s+analysis|deg|dge)\b", 1.0),
        (r"\b(statistical|statistics|stats|p-value|fdr|significance)\b", 0.9),
        (r"\b(enrichment|gsea|pathway\s+analysis|go\s+enrichment|kegg\s+enrichment)\b", 0.9),
        (r"\benriched\b", 0.8),  # "pathways enriched"
        # Specific tests
        (r"\b(t-test|anova|regression|correlation|pca|clustering)\b", 0.8),
        (r"\b(deseq2|edger|limma|batch\s+effect|normali[sz]ation)\b", 1.0),
        # Data analysis
        (r"\b(analyz?[es]|compare|test|assess)\s+(expression|counts?|samples?)\b", 0.7),
        (r"\b(power\s+analysis|sample\s+size|effect\s+size)\b", 0.9),
        (r"\b(volcano|heatmap|ma\s+plot)\b", 0.6),
        # Run statistical tools
        (r"\brun\s+(deseq2|edger|limma)\b", 1.0),
    ],

    SpecialistType.LITERATURE_AGENT: [
        # Database queries
        (r"\b(search|query|find|look\s+up)\s+(pubmed|ncbi|literature|papers?|publications?)\b", 1.0),
        (r"\b(what\s+is\s+known|literature|published|papers?\s+on)\b", 0.9),
        # Information retrieval
        (r"\b(information|details?|data)\s+(about|on|for)\s+\w+\b", 0.6),
        # Specific databases
        (r"\b(uniprot|ensembl|kegg|reactome|string|pdb|alphafold|interpro|gnomad)\b", 0.8),
        # Gene/protein lookup
        (r"\b(gene|protein|variant|pathway)\s+(information|function|annotation)\b", 0.7),
        (r"\bwhat\s+(does|is)\s+\w+\s+(do|gene|protein)\b", 0.7),
        # Function queries
        (r"\b(function|role)\s+of\s+[A-Z][A-Z0-9]+\b", 0.9),  # "function of TP53"
        (r"\bwhat\s+is\s+the\s+function\b", 0.9),
    ],

    SpecialistType.QC_REVIEWER: [
        # QC keywords
        (r"\b(quality\s+control|qc|review|check|validate|verify)\b", 1.0),
        (r"\b(qc\s+metrics|quality\s+metrics|mapping\s+rate|duplication)\b", 0.9),
        # Review requests
        (r"\b(review|critique|assess|evaluate)\s+(results?|analysis|output)\b", 0.8),
        (r"\b(is\s+this\s+(correct|right|good)|look\s+ok|sanity\s+check)\b", 0.8),
        # Problem detection
        (r"\b(outlier|batch\s+effect|artifact|bias|problem|issue)\b", 0.6),
        (r"\b(fastqc|multiqc)\s+report\b", 0.7),
    ],

    SpecialistType.DOMAIN_EXPERT: [
        # Interpretation requests
        (r"\b(interpret|explain|meaning|significance|implication)\b", 1.0),
        (r"\b(biological|clinical)\s+(meaning|interpretation|significance|relevance)\b", 1.0),
        # Domain knowledge
        (r"\b(mechanism|pathway|function|role)\s+(of|in)\b", 0.8),
        (r"\b(disease|cancer|tumor|clinical|phenotype|therapeutic)\b", 0.7),
        # Context questions
        (r"\bwhy\s+(is|does|would)\b", 0.6),
        (r"\b(known\s+to|associated\s+with|implicated\s+in)\b", 0.7),
        # Biological reasoning
        (r"\b(what\s+does\s+this\s+mean|how\s+does\s+this|makes?\s+sense)\b", 0.8),
    ],
}


@dataclass
class RoutingResult:
    """
    Result of task routing.

    Attributes:
        primary: Primary specialist to handle the task
        secondary: Additional specialists that may contribute
        confidence: Confidence in the routing decision (0-1)
        reasoning: Explanation of why this routing was chosen
        requires_parallel: Whether secondary specialists should run in parallel
        execution_order: Ordered list of specialists for sequential execution
    """
    primary: SpecialistType
    secondary: list[SpecialistType] = field(default_factory=list)
    confidence: float = 1.0
    reasoning: str = ""
    requires_parallel: bool = False
    execution_order: list[SpecialistType] = field(default_factory=list)

    def __post_init__(self):
        # Build execution order if not provided
        if not self.execution_order:
            self.execution_order = [self.primary] + self.secondary

    @property
    def all_specialists(self) -> list[SpecialistType]:
        """Return all specialists involved in this routing."""
        return self.execution_order


class TaskRouter:
    """
    Routes tasks to appropriate specialist agents.

    Uses a hybrid approach:
    1. Fast keyword/pattern matching for clear cases
    2. LLM-based classification for ambiguous queries
    """

    # Confidence threshold below which we use LLM classification
    PATTERN_CONFIDENCE_THRESHOLD = 0.5

    # Classification prompt for LLM fallback
    CLASSIFICATION_PROMPT = """You are a task router for a bioinformatics AI assistant.
Given a user query, determine which specialist agent(s) should handle it.

Available specialists:
1. PIPELINE_ENGINEER: Executes code (Python, R, Bash), builds workflows, runs bioinformatics tools
2. STATISTICIAN: Statistical analysis, differential expression, enrichment, batch correction
3. LITERATURE_AGENT: Database queries (NCBI, UniProt, etc.), literature search, information retrieval
4. QC_REVIEWER: Quality control assessment, validation, reviewing analysis outputs
5. DOMAIN_EXPERT: Biological interpretation, explaining mechanisms, clinical significance

Respond in this exact format:
PRIMARY: <specialist_name>
SECONDARY: <comma-separated list or NONE>
CONFIDENCE: <0.0-1.0>
PARALLEL: <true or false>
REASONING: <one sentence explanation>

Query: {query}"""

    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        model: str = "claude-haiku-3-5-20241022",
        use_llm_fallback: bool = True,
    ):
        """
        Initialize the task router.

        Args:
            client: Anthropic client for LLM classification (optional)
            model: Model to use for LLM classification
            use_llm_fallback: Whether to use LLM for ambiguous cases
        """
        self.client = client
        self.model = model
        self.use_llm_fallback = use_llm_fallback and client is not None

    def route(self, query: str, max_specialists: int = 3) -> RoutingResult:
        """
        Route a query to appropriate specialist(s).

        Args:
            query: The user's query/task
            max_specialists: Maximum number of specialists to involve

        Returns:
            RoutingResult with routing decision
        """
        # First try pattern-based classification
        pattern_result = self._pattern_classify(query)

        # If confident enough, use pattern result
        if pattern_result.confidence >= self.PATTERN_CONFIDENCE_THRESHOLD:
            # Limit to max specialists
            if len(pattern_result.secondary) > max_specialists - 1:
                pattern_result.secondary = pattern_result.secondary[:max_specialists - 1]
                pattern_result.execution_order = [pattern_result.primary] + pattern_result.secondary
            return pattern_result

        # Otherwise, try LLM classification if available
        if self.use_llm_fallback:
            llm_result = self._llm_classify(query)
            if llm_result:
                if len(llm_result.secondary) > max_specialists - 1:
                    llm_result.secondary = llm_result.secondary[:max_specialists - 1]
                    llm_result.execution_order = [llm_result.primary] + llm_result.secondary
                return llm_result

        # Fall back to pattern result even if low confidence
        return pattern_result

    def _pattern_classify(self, query: str) -> RoutingResult:
        """Classify using regex patterns."""
        query_lower = query.lower()
        scores: dict[SpecialistType, float] = {st: 0.0 for st in SpecialistType if st != SpecialistType.COORDINATOR}

        # Score each specialist based on pattern matches
        for specialist, patterns in ROUTING_PATTERNS.items():
            for pattern, weight in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    scores[specialist] += weight

        # Normalize scores
        max_score = max(scores.values()) if scores else 0
        if max_score > 0:
            for specialist in scores:
                scores[specialist] /= max_score

        # Sort specialists by score
        sorted_specialists = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Get primary and secondary specialists
        primary = sorted_specialists[0][0]
        primary_score = sorted_specialists[0][1]

        # Include secondary specialists with score > 0.3
        secondary = [
            specialist for specialist, score in sorted_specialists[1:]
            if score > 0.3
        ]

        # Determine if parallel execution makes sense
        requires_parallel = self._should_parallelize(primary, secondary, query_lower)

        # Build execution order based on dependencies
        execution_order = self._determine_execution_order(primary, secondary, query_lower)

        return RoutingResult(
            primary=primary,
            secondary=secondary,
            confidence=primary_score if max_score > 0 else 0.2,
            reasoning=f"Pattern matching: {primary.value} scored {primary_score:.2f}",
            requires_parallel=requires_parallel,
            execution_order=execution_order,
        )

    def _llm_classify(self, query: str) -> RoutingResult | None:
        """Classify using LLM for ambiguous cases."""
        if not self.client:
            return None

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=256,
                temperature=0.0,
                messages=[{
                    "role": "user",
                    "content": self.CLASSIFICATION_PROMPT.format(query=query),
                }],
            )

            # Parse response
            text = response.content[0].text
            return self._parse_llm_response(text)

        except Exception:
            return None

    def _parse_llm_response(self, text: str) -> RoutingResult | None:
        """Parse the LLM classification response."""
        try:
            lines = text.strip().split("\n")
            result = {}

            for line in lines:
                if ":" in line:
                    key, value = line.split(":", 1)
                    result[key.strip().upper()] = value.strip()

            # Parse primary specialist
            primary_str = result.get("PRIMARY", "").upper().replace(" ", "_")
            primary = self._string_to_specialist(primary_str)
            if not primary:
                return None

            # Parse secondary specialists
            secondary_str = result.get("SECONDARY", "NONE")
            secondary = []
            if secondary_str.upper() != "NONE":
                for s in secondary_str.split(","):
                    specialist = self._string_to_specialist(s.strip().upper().replace(" ", "_"))
                    if specialist and specialist != primary:
                        secondary.append(specialist)

            # Parse confidence
            confidence = float(result.get("CONFIDENCE", "0.8"))

            # Parse parallel flag
            parallel = result.get("PARALLEL", "false").lower() == "true"

            # Get reasoning
            reasoning = result.get("REASONING", "LLM classification")

            return RoutingResult(
                primary=primary,
                secondary=secondary,
                confidence=confidence,
                reasoning=reasoning,
                requires_parallel=parallel,
            )

        except Exception:
            return None

    def _string_to_specialist(self, s: str) -> SpecialistType | None:
        """Convert string to SpecialistType."""
        mapping = {
            "PIPELINE_ENGINEER": SpecialistType.PIPELINE_ENGINEER,
            "STATISTICIAN": SpecialistType.STATISTICIAN,
            "LITERATURE_AGENT": SpecialistType.LITERATURE_AGENT,
            "QC_REVIEWER": SpecialistType.QC_REVIEWER,
            "DOMAIN_EXPERT": SpecialistType.DOMAIN_EXPERT,
        }
        return mapping.get(s)

    def _should_parallelize(
        self,
        primary: SpecialistType,
        secondary: list[SpecialistType],
        query: str,
    ) -> bool:
        """Determine if secondary specialists can run in parallel."""
        # Can't parallelize if only one specialist
        if not secondary:
            return False

        # Literature and Domain Expert can often run in parallel with others
        parallel_safe = {SpecialistType.LITERATURE_AGENT, SpecialistType.DOMAIN_EXPERT}

        # If all secondary are parallel-safe, allow parallelization
        if all(s in parallel_safe for s in secondary):
            return True

        # Don't parallelize if there are data dependencies
        dependency_indicators = [
            "then", "after", "use the results", "based on",
            "with the output", "using the",
        ]
        if any(ind in query for ind in dependency_indicators):
            return False

        return False

    def _determine_execution_order(
        self,
        primary: SpecialistType,
        secondary: list[SpecialistType],
        query: str,
    ) -> list[SpecialistType]:
        """Determine the order of specialist execution."""
        all_specialists = [primary] + secondary

        # Define natural ordering based on typical workflow
        # Lower number = run earlier
        priority = {
            SpecialistType.LITERATURE_AGENT: 1,  # Get info first
            SpecialistType.PIPELINE_ENGINEER: 2,  # Then run analysis
            SpecialistType.STATISTICIAN: 3,       # Then statistics
            SpecialistType.DOMAIN_EXPERT: 4,      # Interpret results
            SpecialistType.QC_REVIEWER: 5,        # Review at the end
        }

        # Check for explicit ordering in query
        if "then interpret" in query or "what does it mean" in query:
            # Move domain expert to end
            if SpecialistType.DOMAIN_EXPERT in all_specialists:
                all_specialists.remove(SpecialistType.DOMAIN_EXPERT)
                all_specialists.append(SpecialistType.DOMAIN_EXPERT)
            return all_specialists

        if "review" in query and "first" not in query:
            # Move QC reviewer to end
            if SpecialistType.QC_REVIEWER in all_specialists:
                all_specialists.remove(SpecialistType.QC_REVIEWER)
                all_specialists.append(SpecialistType.QC_REVIEWER)
            return all_specialists

        # Default: sort by priority but keep primary first
        primary_priority = priority.get(primary, 3)
        secondary_sorted = sorted(
            secondary,
            key=lambda s: priority.get(s, 3),
        )

        return [primary] + secondary_sorted


def quick_route(query: str) -> SpecialistType:
    """
    Quick routing for simple cases without full RoutingResult.

    Args:
        query: The user's query

    Returns:
        Primary specialist type
    """
    router = TaskRouter(use_llm_fallback=False)
    result = router.route(query)
    return result.primary
