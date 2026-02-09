"""Structured logging configuration for Knowledge Graph Builder.

Provides:
- JSON-formatted structured logs
- LLM call tracking (prompt, response, tokens, latency)
- Pipeline health monitoring
- wandb integration for experiment tracking
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        # Add context like request IDs, etc.
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


def setup_logging(
    log_dir: Path | None = None,
    log_level: str = "INFO",
    enable_json: bool = True,
) -> None:
    """Configure structured logging for the application.
    
    Args:
        log_dir: Directory for log files (optional)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        enable_json: Enable JSON-formatted logs
    """
    # Create log directory if specified
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure stderr handler (console output)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(getattr(logging, log_level))
    
    if enable_json:
        console_formatter = logging.Formatter('%(message)s')
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s - %(message)s'
        )
    
    console_handler.setFormatter(console_formatter)
    
    # Configure file handler if log_dir provided
    file_handler = None
    if log_dir:
        log_file = log_dir / f"kg_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(console_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add handlers
    root_logger.addHandler(console_handler)
    if file_handler:
        root_logger.addHandler(file_handler)
    
    # Get structlog logger
    logger = structlog.get_logger(__name__)
    logger.info("logging_configured", level=log_level, json_enabled=enable_json)


class LLMCallTracker:
    """Tracks LLM API calls for monitoring and analytics.
    
    Logs:
    - Model name
    - Prompt size (tokens)
    - Response size (tokens)
    - Latency
    - Success/failure status
    - Error messages (if failed)
    """

    def __init__(self, logger: Any = None) -> None:
        """Initialize tracker.
        
        Args:
            logger: structlog logger instance
        """
        self.logger = logger or structlog.get_logger(__name__)
        self.call_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_latency_seconds = 0.0

    def track_call(
        self,
        model: str,
        prompt: str,
        response: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        latency_seconds: float = 0.0,
        success: bool = True,
        error_message: str | None = None,
        call_type: str = "generate",  # "generate", "generate_structured", "embed", etc.
    ) -> None:
        """Record an LLM API call.
        
        Args:
            model: Model name
            prompt: Input prompt
            response: LLM response
            input_tokens: Number of input tokens (estimated if None)
            output_tokens: Number of output tokens (estimated if None)
            latency_seconds: API call latency
            success: Whether call succeeded
            error_message: Error message if failed
            call_type: Type of call (for filtering)
        """
        self.call_count += 1
        
        # Estimate tokens if not provided
        if input_tokens is None:
            input_tokens = self._estimate_tokens(prompt)
        if output_tokens is None:
            output_tokens = self._estimate_tokens(response)
        
        # Update aggregates
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_latency_seconds += latency_seconds
        
        # Log the call
        log_data = {
            "model": model,
            "call_type": call_type,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "latency_seconds": latency_seconds,
            "prompt_length": len(prompt),
            "response_length": len(response),
            "success": success,
            "call_number": self.call_count,
        }
        
        if not success and error_message:
            log_data["error"] = error_message
        
        if success:
            self.logger.info("llm_call", **log_data)
        else:
            self.logger.error("llm_call_failed", **log_data)

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics of tracked calls.
        
        Returns:
            Dict with aggregated metrics
        """
        return {
            "total_calls": self.call_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_latency_seconds": self.total_latency_seconds,
            "average_latency_seconds": (
                self.total_latency_seconds / max(1, self.call_count)
            ),
        }

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimation (words + punctuation).
        
        For accurate estimates, would use tiktoken or similar.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        # Rough heuristic: ~1.3 tokens per word
        word_count = len(text.split())
        return int(word_count * 1.3)


class PipelineHealthMonitor:
    """Monitors pipeline health and logs key metrics.
    
    Tracks:
    - Phase completion times
    - Entity/relation discovery rates
    - Error/warning counts
    - Resource usage
    """

    def __init__(self, logger: Any = None) -> None:
        """Initialize monitor.
        
        Args:
            logger: structlog logger instance
        """
        self.logger = logger or structlog.get_logger(__name__)
        self.phase_times: dict[str, float] = {}
        self.error_count = 0
        self.warning_count = 0
        self.start_time = time.time()

    def log_phase_start(self, phase_name: str) -> None:
        """Log start of a pipeline phase.
        
        Args:
            phase_name: Name of the phase
        """
        self.logger.info("phase_start", phase=phase_name)
        self.phase_times[f"{phase_name}_start"] = time.time()

    def log_phase_complete(
        self,
        phase_name: str,
        entity_count: int | None = None,
        relation_count: int | None = None,
        errors: int = 0,
    ) -> None:
        """Log completion of a pipeline phase.
        
        Args:
            phase_name: Name of the phase
            entity_count: Entities discovered/processed in this phase
            relation_count: Relations discovered/processed in this phase
            errors: Error count in this phase
        """
        start_key = f"{phase_name}_start"
        if start_key in self.phase_times:
            duration = time.time() - self.phase_times[start_key]
        else:
            duration = 0.0
        
        self.phase_times[f"{phase_name}_duration"] = duration
        self.error_count += errors
        
        log_data = {
            "phase": phase_name,
            "duration_seconds": duration,
        }
        
        if entity_count is not None:
            log_data["entities"] = entity_count
        
        if relation_count is not None:
            log_data["relations"] = relation_count
        
        if errors > 0:
            log_data["errors"] = errors
        
        self.logger.info("phase_complete", **log_data)

    def log_warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning.
        
        Args:
            message: Warning message
            **kwargs: Additional context
        """
        self.warning_count += 1
        self.logger.warning(message, warning_count=self.warning_count, **kwargs)

    def log_error(self, message: str, **kwargs: Any) -> None:
        """Log an error.
        
        Args:
            message: Error message
            **kwargs: Additional context
        """
        self.error_count += 1
        self.logger.error(message, error_count=self.error_count, **kwargs)

    def get_summary(self) -> dict[str, Any]:
        """Get summary of pipeline health.
        
        Returns:
            Dict with metrics
        """
        total_time = time.time() - self.start_time
        
        return {
            "total_execution_seconds": total_time,
            "total_errors": self.error_count,
            "total_warnings": self.warning_count,
            "phase_durations": {
                k: v for k, v in self.phase_times.items()
                if k.endswith("_duration")
            },
        }

    def log_pipeline_summary(self) -> None:
        """Log comprehensive pipeline summary.
        """
        summary = self.get_summary()
        self.logger.info("pipeline_summary", **summary)
