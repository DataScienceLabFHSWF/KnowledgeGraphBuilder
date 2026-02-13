"""Structured generation benchmarking and reliability metrics.

Measures and tracks success rates of LLM structured output generation,
providing insights into reliability and suggesting improvements.
"""

from __future__ import annotations

import json
import structlog
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = structlog.get_logger(__name__)


@dataclass
class StructuredGenerationMetrics:
    """Metrics for structured generation performance."""

    total_attempts: int = 0
    successful_generations: int = 0
    validation_failures: int = 0
    json_parse_failures: int = 0
    retries_exhausted: int = 0
    
    # Success rates
    first_attempt_success_rate: float = 0.0  # % succeeding on first try
    overall_success_rate: float = 0.0  # % eventually succeeding
    
    # Average metrics
    average_retries_on_success: float = 0.0
    average_retries_on_failure: float = 0.0
    
    # Per-schema tracking
    schema_stats: dict[str, dict] = field(default_factory=dict)
    
    # Time series (for trending)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def compute_rates(self) -> None:
        """Compute derived metrics from raw counters."""
        if self.total_attempts == 0:
            return
        
        self.overall_success_rate = 100 * self.successful_generations / self.total_attempts
        
        # First attempt success = total - retries_needed
        # Approximated as successful - those that needed retries
        # For simplicity: assume some succeeded on first try
        if self.successful_generations > 0:
            self.first_attempt_success_rate = 100 * max(0, 
                self.successful_generations - self.validation_failures - self.json_parse_failures
            ) / self.total_attempts


@dataclass
class GenerationAttemptRecord:
    """Record of a single structured generation attempt."""

    timestamp: datetime = field(default_factory=datetime.now)
    schema_name: str = ""
    attempt_number: int = 1
    
    # Input
    prompt_length: int = 0
    
    # Execution
    duration_seconds: float = 0.0
    
    # Outcome
    status: str = ""  # "" | "success" | "validation_failure" | "json_error"
    raw_output: str = ""
    error_message: str = ""
    
    # Retry info
    total_retries: int = 0
    was_recovered: bool = False  # Did error recovery succeed?


class StructuredGenerationBenchmark:
    """Tracks and analyzes structured generation reliability.
    
    Provides:
    - Success rate tracking across multiple runs
    - Per-schema performance analysis
    - Identification of problematic patterns
    - Recommendations for improvement
    """

    def __init__(self, name: str = "default") -> None:
        """Initialize benchmarker.
        
        Args:
            name: Name for this benchmark session
        """
        self.name = name
        self.metrics = StructuredGenerationMetrics()
        self.records: list[GenerationAttemptRecord] = []

    def record_attempt(
        self,
        schema_name: str,
        success: bool,
        duration_seconds: float,
        prompt_length: int,
        attempt_number: int = 1,
        total_retries: int = 0,
        error_type: str | None = None,
        was_recovered: bool = False,
        raw_output: str = "",
        error_message: str = "",
    ) -> None:
        """Record a single generation attempt.
        
        Args:
            schema_name: Name of the Pydantic schema used
            success: Whether generation succeeded
            duration_seconds: How long the attempt took
            prompt_length: Size of input prompt
            attempt_number: Which attempt in the sequence
            total_retries: How many retries were needed
            error_type: Type of error ("json_error", "validation_error", etc.)
            was_recovered: Whether error recovery succeeded
            raw_output: Raw LLM output (for analysis)
            error_message: Error message if failed
        """
        record = GenerationAttemptRecord(
            schema_name=schema_name,
            attempt_number=attempt_number,
            prompt_length=prompt_length,
            duration_seconds=duration_seconds,
            status="success" if success else error_type or "unknown_error",
            raw_output=raw_output[:200],  # Truncate for storage
            error_message=error_message[:100],
            total_retries=total_retries,
            was_recovered=was_recovered,
        )
        
        self.records.append(record)
        
        # Update aggregate metrics
        if success:
            self.metrics.successful_generations += 1
        elif error_type == "json_error":
            self.metrics.json_parse_failures += 1
        elif error_type == "validation_error":
            self.metrics.validation_failures += 1
        
        if total_retries >= 3:  # Assuming max_retries=3
            self.metrics.retries_exhausted += 1
        
        self.metrics.total_attempts += 1
        
        # Update per-schema stats
        if schema_name not in self.metrics.schema_stats:
            self.metrics.schema_stats[schema_name] = {
                "attempts": 0,
                "successes": 0,
                "failures": 0,
            }
        
        stats = self.metrics.schema_stats[schema_name]
        stats["attempts"] += 1
        if success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1
        
        # Compute derived metrics
        self.metrics.compute_rates()
        
        # Log if success rate is poor
        if self.metrics.overall_success_rate < 0.85 and self.metrics.total_attempts > 10:
            logger.warning(
                "low_structured_generation_success",
                schema=schema_name,
                success_rate=self.metrics.overall_success_rate,
                attempts=self.metrics.total_attempts,
            )

    def get_success_rate(self, schema_name: str | None = None) -> float:
        """Get success rate for a schema or overall.
        
        Args:
            schema_name: Optional specific schema, or None for overall
            
        Returns:
            Success rate as percentage (0-100)
        """
        if schema_name is None:
            return self.metrics.overall_success_rate
        
        if schema_name not in self.metrics.schema_stats:
            return 0.0
        
        stats = self.metrics.schema_stats[schema_name]
        if stats["attempts"] == 0:
            return 0.0
        
        return 100 * stats["successes"] / stats["attempts"]

    def identify_problem_patterns(self) -> dict[str, ANY]:
        """Identify patterns in generation failures.
        
        Returns:
            Dict with findings and recommendations
        """
        findings = {
            "high_json_error_rate": False,
            "high_validation_error_rate": False,
            "specific_schemas_failing": [],
            "common_error_patterns": [],
            "recommendations": [],
        }
        
        # Check error type distribution
        json_error_pct = 100 * self.metrics.json_parse_failures / max(1, self.metrics.total_attempts)
        validation_error_pct = 100 * self.metrics.validation_failures / max(1, self.metrics.total_attempts)
        
        if json_error_pct > 10:
            findings["high_json_error_rate"] = True
            findings["recommendations"].append(
                "High JSON parse errors: Ensure `format=\"json\"` is used in Ollama calls"
            )
        
        if validation_error_pct > 10:
            findings["high_validation_error_rate"] = True
            findings["recommendations"].append(
                "High validation errors: Add more detailed field descriptions to schema, use few-shot examples"
            )
        
        # Schema-specific analysis
        for schema_name, stats in self.metrics.schema_stats.items():
            success_rate = 100 * stats["successes"] / max(1, stats["attempts"])
            if success_rate < 80:
                findings["specific_schemas_failing"].append({
                    "schema": schema_name,
                    "success_rate": success_rate,
                    "attempts": stats["attempts"],
                })
        
        return findings

    def generate_report(self, output_path: str | None = None) -> str:
        """Generate benchmark report.
        
        Args:
            output_path: Optional file path to save report
            
        Returns:
            Formatted report string
        """
        report = f"""# Structured Generation Benchmark Report

**Session**: {self.name}
**Generated**: {self.metrics.timestamp.isoformat()}
**Total Attempts**: {self.metrics.total_attempts}

## Overall Success Rates

- **Overall Success Rate**: {self.metrics.overall_success_rate:.1f}%
- **First-Attempt Success Rate**: {self.metrics.first_attempt_success_rate:.1f}%
- **Successful Generations**: {self.metrics.successful_generations}

## Failure Analysis

- **Validation Failures**: {self.metrics.validation_failures} ({100*self.metrics.validation_failures/max(1, self.metrics.total_attempts):.1f}%)
- **JSON Parse Failures**: {self.metrics.json_parse_failures} ({100*self.metrics.json_parse_failures/max(1, self.metrics.total_attempts):.1f}%)
- **Retries Exhausted**: {self.metrics.retries_exhausted}

## Per-Schema Performance

"""
        for schema_name, stats in self.metrics.schema_stats.items():
            success_rate = 100 * stats["successes"] / max(1, stats["attempts"])
            report += f"- **{schema_name}**: {success_rate:.1f}% ({stats['successes']}/{stats['attempts']})\n"

        # Problem patterns
        patterns = self.identify_problem_patterns()
        if patterns["recommendations"]:
            report += "\n## Recommendations\n\n"
            for rec in patterns["recommendations"]:
                report += f"- {rec}\n"

        report += f"\n## Target Success Rate\n\n"
        report += f"- **Target**: ≥95% success rate\n"
        report += f"- **Current**: {self.metrics.overall_success_rate:.1f}%\n"
        report += f"- **Gap**: {max(0, 95 - self.metrics.overall_success_rate):.1f}%\n"

        if output_path:
            try:
                with open(output_path, "w") as f:
                    f.write(report)
                logger.info(f"benchmark_report_written path={output_path}")
            except Exception as e:
                logger.warning(f"Failed to write benchmark report: {e}")

        return report
