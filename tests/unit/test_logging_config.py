import logging
import os
import time
from pathlib import Path

import pytest

from kgbuilder import logging_config


class DummyLogger:
    def __init__(self):
        self.records = []

    def info(self, msg, **kwargs):
        self.records.append(("info", msg, kwargs))

    def error(self, msg, **kwargs):
        self.records.append(("error", msg, kwargs))

    def warning(self, msg, **kwargs):
        self.records.append(("warning", msg, kwargs))


def test_setup_logging_creates_directory(tmp_path, caplog):
    logdir = tmp_path / "logs"
    # nothing exists initially
    assert not logdir.exists()
    logging_config.setup_logging(log_dir=logdir, log_level="DEBUG", enable_json=False)
    # directory should now exist
    assert logdir.is_dir()
    # there should be at least one file created
    files = list(logdir.iterdir())
    assert files, "no log file created"
    # cleanup logger handlers so other tests unaffected
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)


def test_estimate_tokens():
    text = "hello world this is a test"
    est = logging_config.LLMCallTracker._estimate_tokens(text)
    # word count 6 -> ~7 or 8 tokens
    assert est >= 6
    assert est <= 10


def test_llm_call_tracker_basic(monkeypatch):
    dummy = DummyLogger()
    tracker = logging_config.LLMCallTracker(logger=dummy)
    tracker.track_call(
        model="m1",
        prompt="hi",
        response="bye",
        input_tokens=2,
        output_tokens=3,
        latency_seconds=0.5,
    )
    assert tracker.call_count == 1
    assert tracker.total_input_tokens == 2
    assert tracker.total_output_tokens == 3
    assert tracker.total_latency_seconds == pytest.approx(0.5)
    summary = tracker.get_summary()
    assert summary["total_calls"] == 1
    assert summary["average_latency_seconds"] == pytest.approx(0.5)
    # should have logged info entry
    assert any(r[0] == "info" and r[1] == "llm_call" for r in dummy.records)

    # track failure with error message
    dummy.records.clear()
    tracker.track_call(
        model="m2",
        prompt="x",
        response="y",
        latency_seconds=0.1,
        success=False,
        error_message="err",
    )
    assert tracker.call_count == 2
    assert any(r[0] == "error" and r[1] == "llm_call_failed" for r in dummy.records)


def test_pipeline_health_monitor():
    dummy = DummyLogger()
    mon = logging_config.PipelineHealthMonitor(logger=dummy)
    mon.log_phase_start("phase1")
    time.sleep(0.01)
    mon.log_phase_complete("phase1", entity_count=5, relation_count=2, errors=1)
    mon.log_warning("warn1", foo=1)
    mon.log_error("err1", bar=2)
    summary = mon.get_summary()
    # one error from phase_complete plus one logged explicitly
    assert summary["total_errors"] == 2
    assert summary["total_warnings"] == 1
    assert "phase1_duration" in summary["phase_durations"]
    # log_pipeline_summary should add an info record
    dummy.records.clear()
    mon.log_pipeline_summary()
    assert any(r[0] == "info" and r[1] == "pipeline_summary" for r in dummy.records)
