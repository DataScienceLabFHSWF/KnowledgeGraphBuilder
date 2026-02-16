"""Tests for QA evaluation module."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kgbuilder.evaluation.metrics import EvaluationMetrics, MetricsComputer
from kgbuilder.evaluation.qa_dataset import QADataset, QAQuestion
from kgbuilder.evaluation.query_executor import QueryExecutor, QueryResult
from kgbuilder.evaluation.reporter import EvaluationReport, EvaluationReporter


class TestQAQuestion:
    """Tests for QAQuestion dataclass."""

    def test_qa_question_creation(self) -> None:
        """Test creating a QAQuestion."""
        q = QAQuestion(
            id="q1",
            question="What is X?",
            expected_answers=["answer1"],
            query_type="entity",
            difficulty="easy",
        )
        assert q.id == "q1"
        assert q.question == "What is X?"
        assert q.expected_answers == ["answer1"]

    def test_qa_question_to_dict(self) -> None:
        """Test QAQuestion.to_dict()."""
        q = QAQuestion(
            id="q1",
            question="What is X?",
            expected_answers=["answer1", "answer2"],
            query_type="relation",
            difficulty="hard",
            tags=["test"],
        )
        d = q.to_dict()
        assert d["id"] == "q1"
        assert d["question"] == "What is X?"
        assert len(d["expected_answers"]) == 2
        assert d["tags"] == ["test"]

    def test_qa_question_from_dict(self) -> None:
        """Test QAQuestion.from_dict()."""
        data = {
            "id": "q1",
            "question": "What is X?",
            "expected_answers": ["answer1"],
            "query_type": "entity",
            "difficulty": "medium",
        }
        q = QAQuestion.from_dict(data)
        assert q.id == "q1"
        assert q.question == "What is X?"
        assert q.difficulty == "medium"


class TestQADataset:
    """Tests for QADataset class."""

    @pytest.fixture
    def sample_questions(self) -> list[QAQuestion]:
        """Create sample questions."""
        return [
            QAQuestion(
                id="q1",
                question="What is entity A?",
                expected_answers=["A"],
                query_type="entity",
                difficulty=1,  # Easy
                tags=["basic"],
            ),
            QAQuestion(
                id="q2",
                question="What is the relation?",
                expected_answers=["relates_to"],
                query_type="relation",
                difficulty=2,  # Medium
                tags=["advanced"],
            ),
            QAQuestion(
                id="q3",
                question="How many entities?",
                expected_answers=["42"],
                query_type="count",
                difficulty=3,  # Hard
                tags=["counting"],
            ),
        ]

    def test_dataset_creation(self, sample_questions: list[QAQuestion]) -> None:
        """Test creating a QADataset."""
        dataset = QADataset(
            name="test_dataset",
            description="Test dataset",
            questions=sample_questions,
        )
        assert dataset.name == "test_dataset"
        assert len(dataset.questions) == 3

    def test_dataset_filter_by_type(self, sample_questions: list[QAQuestion]) -> None:
        """Test filtering by query type."""
        dataset = QADataset(
            name="test",
            description="Test",
            questions=sample_questions
        )
        entity_questions = dataset.filter_by_type("entity")
        assert len(entity_questions.questions) == 1
        assert entity_questions.questions[0].id == "q1"

    def test_dataset_filter_by_difficulty(
        self, sample_questions: list[QAQuestion]
    ) -> None:
        """Test filtering by difficulty."""
        dataset = QADataset(
            name="test",
            description="Test",
            questions=sample_questions
        )
        easy_questions = dataset.filter_by_difficulty(1, 1)
        assert len(easy_questions.questions) == 1
        assert easy_questions.questions[0].difficulty == 1

    def test_dataset_filter_by_tags(self, sample_questions: list[QAQuestion]) -> None:
        """Test filtering by tags."""
        dataset = QADataset(
            name="test",
            description="Test",
            questions=sample_questions
        )
        advanced = dataset.filter_by_tags(["advanced"])
        assert len(advanced.questions) == 1
        assert "advanced" in advanced.questions[0].tags

    def test_dataset_statistics(self, sample_questions: list[QAQuestion]) -> None:
        """Test getting dataset statistics."""
        dataset = QADataset(
            name="test",
            description="Test",
            questions=sample_questions
        )
        stats = dataset.get_statistics()
        assert stats["total_questions"] == 3
        assert "query_types" in stats
        assert "difficulties" in stats

    def test_dataset_split_train_test(
        self, sample_questions: list[QAQuestion]
    ) -> None:
        """Test train/test split."""
        dataset = QADataset(
            name="test",
            description="Test",
            questions=sample_questions
        )
        train, test = dataset.split_train_test(split_ratio=0.67)
        assert len(train.questions) + len(test.questions) == 3
        assert len(train.questions) >= len(test.questions)

    def test_dataset_to_dict(self, sample_questions: list[QAQuestion]) -> None:
        """Test dataset.to_dict()."""
        dataset = QADataset(
            name="test",
            description="Test",
            questions=sample_questions
        )
        d = dataset.to_dict()
        assert d["name"] == "test"
        assert len(d["questions"]) == 3

    def test_dataset_save_and_load_json(
        self, sample_questions: list[QAQuestion]
    ) -> None:
        """Test saving and loading JSON."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            filepath = Path(tmp_dir) / "dataset.json"

            # Save
            dataset = QADataset(
                name="test",
                description="Test",
                questions=sample_questions
            )
            dataset.save(str(filepath), format="json")
            assert filepath.exists()

            # Load
            loaded = QADataset.load(str(filepath))
            assert loaded.name == "test"
            assert len(loaded.questions) == 3

    def test_dataset_save_and_load_csv(
        self, sample_questions: list[QAQuestion]
    ) -> None:
        """Test saving and loading CSV."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            filepath = Path(tmp_dir) / "dataset.csv"

            # Save
            dataset = QADataset(
                name="test",
                description="Test",
                questions=sample_questions
            )
            dataset.save(str(filepath), format="csv")
            assert filepath.exists()

            # Load
            loaded = QADataset.load(str(filepath))
            assert len(loaded.questions) == 3


class TestQueryResult:
    """Tests for QueryResult class."""

    def test_query_result_creation(self) -> None:
        """Test creating a QueryResult."""
        result = QueryResult(
            question_id="q1",
            question_text="What is X?",
            query_type="entity",
            retrieved_answers=["answer1"],
        )
        assert result.question_id == "q1"
        assert result.retrieved_answers == ["answer1"]

    def test_query_result_is_correct_exact_match(self) -> None:
        """Test is_correct with exact match."""
        result = QueryResult(
            question_id="q1",
            question_text="What is X?",
            query_type="entity",
            retrieved_answers=["answer1"],
        )
        assert result.is_correct(["answer1"])

    def test_query_result_is_correct_no_match(self) -> None:
        """Test is_correct with no match."""
        result = QueryResult(
            question_id="q1",
            question_text="What is X?",
            query_type="entity",
            retrieved_answers=["wrong"],
        )
        assert not result.is_correct(["correct"])

    def test_query_result_is_correct_empty_answers(self) -> None:
        """Test is_correct with empty retrieved answers."""
        result = QueryResult(
            question_id="q1",
            question_text="What is X?",
            query_type="entity",
            retrieved_answers=[],
        )
        assert not result.is_correct(["answer1"])

    def test_query_result_to_dict(self) -> None:
        """Test result.to_dict()."""
        result = QueryResult(
            question_id="q1",
            question_text="What is X?",
            query_type="entity",
            retrieved_answers=["answer1"],
            execution_time_ms=10.5,
        )
        d = result.to_dict()
        assert d["question_id"] == "q1"
        assert d["retrieved_answers"] == ["answer1"]


class TestQueryExecutor:
    """Tests for QueryExecutor class."""

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        """Create a mock GraphStore."""
        store = MagicMock()

        # Mock nodes
        node1 = MagicMock()
        node1.id = "node1"
        node1.label = "Entity A"
        node1.node_type = "Entity"

        store.get_all_nodes.return_value = [node1]

        # Mock edges
        edge1 = MagicMock()
        edge1.source_id = "node1"
        edge1.edge_type = "related_to"
        edge1.target_id = "node2"

        store.get_all_edges.return_value = [edge1]

        return store

    def test_executor_creation(self, mock_store: MagicMock) -> None:
        """Test creating a QueryExecutor."""
        executor = QueryExecutor(mock_store)
        assert executor.store == mock_store

    def test_execute_entity_query(self, mock_store: MagicMock) -> None:
        """Test executing an entity query."""
        executor = QueryExecutor(mock_store)
        result = executor.execute(
            question_id="q1",
            question_text="What is Entity A?",
            query_type="entity",
        )
        assert result.question_id == "q1"
        assert result.query_type == "entity"

    def test_execute_relation_query(self, mock_store: MagicMock) -> None:
        """Test executing a relation query."""
        executor = QueryExecutor(mock_store)
        result = executor.execute(
            question_id="q1",
            question_text="What relates to X?",
            query_type="relation",
        )
        assert result.question_id == "q1"
        assert result.query_type == "relation"

    def test_execute_count_query(self, mock_store: MagicMock) -> None:
        """Test executing a count query."""
        executor = QueryExecutor(mock_store)
        result = executor.execute(
            question_id="q1",
            question_text="How many entities?",
            query_type="count",
        )
        assert result.question_id == "q1"
        assert result.query_type == "count"

    def test_execute_boolean_query(self, mock_store: MagicMock) -> None:
        """Test executing a boolean query."""
        executor = QueryExecutor(mock_store)
        result = executor.execute(
            question_id="q1",
            question_text="Does X relate to Y?",
            query_type="boolean",
            subject="node1",
            relation="related_to",
            object="node2",
        )
        assert result.question_id == "q1"
        assert result.query_type == "boolean"

    def test_execute_unknown_query_type(self, mock_store: MagicMock) -> None:
        """Test executing unknown query type."""
        executor = QueryExecutor(mock_store)
        result = executor.execute(
            question_id="q1",
            question_text="Question",
            query_type="unknown",
        )
        assert result.retrieved_answers == []


class TestMetricsComputer:
    """Tests for MetricsComputer class."""

    @pytest.fixture
    def sample_qa_pairs(self) -> list[tuple[dict, list[str]]]:
        """Create sample QA pairs."""
        return [
            (
                {
                    "id": "q1",
                    "question": "Q1",
                    "query_type": "entity",
                    "difficulty": "easy",
                },
                ["answer1"],
            ),
            (
                {
                    "id": "q2",
                    "question": "Q2",
                    "query_type": "relation",
                    "difficulty": "hard",
                },
                ["answer2"],
            ),
            (
                {
                    "id": "q3",
                    "question": "Q3",
                    "query_type": "count",
                    "difficulty": "medium",
                },
                ["42"],
            ),
        ]

    @pytest.fixture
    def sample_results(self) -> list[dict]:
        """Create sample query results."""
        return [
            {
                "question_id": "q1",
                "question_text": "Q1",
                "query_type": "entity",
                "retrieved_answers": ["answer1"],
                "execution_time_ms": 10.0,
            },
            {
                "question_id": "q2",
                "question_text": "Q2",
                "query_type": "relation",
                "retrieved_answers": ["wrong_answer"],
                "execution_time_ms": 20.0,
            },
            {
                "question_id": "q3",
                "question_text": "Q3",
                "query_type": "count",
                "retrieved_answers": [],
                "execution_time_ms": 15.0,
            },
        ]

    def test_metrics_computer_creation(self) -> None:
        """Test creating MetricsComputer."""
        computer = MetricsComputer()
        assert computer is not None

    def test_compute_metrics(
        self,
        sample_qa_pairs: list[tuple[dict, list[str]]],
        sample_results: list[dict],
    ) -> None:
        """Test computing metrics."""
        computer = MetricsComputer()
        metrics = computer.compute(sample_qa_pairs, sample_results)

        assert metrics.total_questions == 3
        assert metrics.accuracy >= 0.0
        assert metrics.accuracy <= 1.0
        assert metrics.f1_score >= 0.0

    def test_compute_metrics_empty_results(
        self, sample_qa_pairs: list[tuple[dict, list[str]]]
    ) -> None:
        """Test computing metrics with empty results."""
        computer = MetricsComputer()
        metrics = computer.compute(sample_qa_pairs, [])

        assert metrics.total_questions == 0
        assert metrics.accuracy == 0.0

    def test_metrics_to_dict(
        self,
        sample_qa_pairs: list[tuple[dict, list[str]]],
        sample_results: list[dict],
    ) -> None:
        """Test metrics.to_dict()."""
        computer = MetricsComputer()
        metrics = computer.compute(sample_qa_pairs, sample_results)
        d = metrics.to_dict()

        assert "accuracy" in d
        assert "f1_score" in d
        assert "total_questions" in d


class TestEvaluationReporter:
    """Tests for EvaluationReporter class."""

    @pytest.fixture
    def sample_report(self) -> EvaluationReport:
        """Create a sample report."""
        metrics = EvaluationMetrics(
            total_questions=10,
            correct_answers=8,
            accuracy=0.8,
            precision=0.9,
            recall=0.85,
            f1_score=0.87,
            coverage=0.95,
            completeness=0.88,
            average_response_time=15.5,
        )
        return EvaluationReport(
            title="Sample Evaluation Report",
            metrics=metrics,
            timestamp="2024-01-01T12:00:00",
        )

    def test_reporter_creation(self) -> None:
        """Test creating EvaluationReporter."""
        reporter = EvaluationReporter()
        assert reporter is not None

    def test_generate_markdown(self, sample_report: EvaluationReport) -> None:
        """Test generating Markdown report."""
        reporter = EvaluationReporter()
        md = reporter.generate_markdown(sample_report)

        assert "Sample Evaluation Report" in md
        assert "Accuracy" in md
        assert "80.0%" in md

    def test_generate_json(self, sample_report: EvaluationReport) -> None:
        """Test generating JSON report."""
        reporter = EvaluationReporter()
        json_str = reporter.generate_json(sample_report)

        assert "Sample Evaluation Report" in json_str
        assert "accuracy" in json_str
        assert "0.8" in json_str

    def test_generate_html(self, sample_report: EvaluationReport) -> None:
        """Test generating HTML report."""
        reporter = EvaluationReporter()
        html = reporter.generate_html(sample_report)

        assert "<html>" in html
        assert "Sample Evaluation Report" in html
        assert "80" in html  # 80%

    def test_save_report_json(self, sample_report: EvaluationReport) -> None:
        """Test saving JSON report."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            filepath = Path(tmp_dir) / "report.json"
            reporter = EvaluationReporter()
            reporter.save_report(sample_report, str(filepath), format="json")
            assert filepath.exists()

    def test_save_report_markdown(self, sample_report: EvaluationReport) -> None:
        """Test saving Markdown report."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            filepath = Path(tmp_dir) / "report.md"
            reporter = EvaluationReporter()
            reporter.save_report(sample_report, str(filepath), format="markdown")
            assert filepath.exists()

    def test_save_report_html(self, sample_report: EvaluationReport) -> None:
        """Test saving HTML report."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            filepath = Path(tmp_dir) / "report.html"
            reporter = EvaluationReporter()
            reporter.save_report(sample_report, str(filepath), format="html")
            assert filepath.exists()

    def test_save_report_invalid_format(
        self, sample_report: EvaluationReport
    ) -> None:
        """Test saving report with invalid format."""
        reporter = EvaluationReporter()
        with pytest.raises(ValueError):
            with tempfile.TemporaryDirectory() as tmp_dir:
                filepath = Path(tmp_dir) / "report.txt"
                reporter.save_report(sample_report, str(filepath), format="invalid")
