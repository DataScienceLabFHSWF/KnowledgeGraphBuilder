"""QA Dataset management for evaluation.

Supports loading and managing QA question datasets in multiple formats
(JSON, CSV, SPARQL). Used for evaluating knowledge graph quality.

Features:
- Load QA questions from files
- Filter by question type, difficulty, tags
- Compute dataset statistics
- Support multiple answer formats
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class QAQuestion:
    """Single QA question with expected answers.

    Represents one evaluation question with expected answer(s) and metadata.

    Attributes:
        id: Unique question identifier
        question: Question text
        expected_answers: List of valid answers (supports multiple correct answers)
        query_type: Type of query ("entity", "relation", "count", "boolean", "complex")
        difficulty: Difficulty level (1-5, where 1=easy, 5=hard)
        tags: Topic/category tags for filtering
        metadata: Additional metadata (source, context, etc.)
    """

    id: str
    question: str
    expected_answers: list[str]
    query_type: str = "entity"
    difficulty: int = 1
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "question": self.question,
            "expected_answers": self.expected_answers,
            "query_type": self.query_type,
            "difficulty": self.difficulty,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> QAQuestion:
        """Create from dictionary (JSON deserialization)."""
        return QAQuestion(
            id=data["id"],
            question=data["question"],
            expected_answers=data.get("expected_answers", []),
            query_type=data.get("query_type", "entity"),
            difficulty=data.get("difficulty", 1),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class QADataset:
    """Collection of QA questions for evaluation.

    Represents a complete QA dataset with questions, metadata, and utilities
    for filtering and analysis.

    Attributes:
        name: Dataset name
        description: Dataset description
        questions: List of QAQuestion objects
        version: Dataset version
        source: Original source of dataset
    """

    name: str
    description: str
    questions: list[QAQuestion]
    version: str = "1.0"
    source: str = "unknown"

    def __post_init__(self) -> None:
        """Validate dataset after initialization."""
        if not self.questions:
            logger.warning("empty_dataset", name=self.name)

    @classmethod
    def load(cls, path: Path) -> QADataset:
        """Load dataset from file.

        Supports JSON and CSV formats. Returns new dataset instance.

        Args:
            path: Path to dataset file

        Returns:
            New QADataset instance

        Raises:
            ValueError: If file format not supported
            FileNotFoundError: If file doesn't exist
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {path}")

        try:
            if path.suffix == ".json":
                return cls._load_json(path)
            elif path.suffix == ".csv":
                return cls._load_csv(path)
            else:
                raise ValueError(f"Unsupported format: {path.suffix}")

        except Exception as e:
            logger.error("dataset_load_failed", path=str(path), error=str(e))
            raise

    @staticmethod
    def _load_json(path: Path) -> QADataset:
        """Load dataset from JSON file."""
        with open(path) as f:
            data = json.load(f)

        questions = [QAQuestion.from_dict(q) for q in data.get("questions", [])]

        dataset = QADataset(
            name=data.get("name", "unknown"),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            source=data.get("source", "unknown"),
            questions=questions,
        )

        logger.info("dataset_loaded_json", path=str(path), question_count=len(questions))
        return dataset

    @staticmethod
    def _load_csv(path: Path) -> QADataset:
        """Load dataset from CSV file.

        Expected CSV columns: id, question, expected_answers, query_type, difficulty
        """
        questions = []

        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row.get("id"):
                    continue

                answers = row.get("expected_answers", "").split("|")
                answers = [a.strip() for a in answers if a.strip()]

                question = QAQuestion(
                    id=row["id"],
                    question=row.get("question", ""),
                    expected_answers=answers,
                    query_type=row.get("query_type", "entity"),
                    difficulty=int(row.get("difficulty", 1)),
                    tags=row.get("tags", "").split("|") if row.get("tags") else [],
                )
                questions.append(question)

        dataset = QADataset(
            name=path.stem,
            description=f"Dataset from {path.name}",
            questions=questions,
            source="CSV",
        )

        logger.info("dataset_loaded_csv", path=str(path), question_count=len(questions))
        return dataset

    def save(self, path: Path, format: str = "json") -> None:
        """Save dataset to file.

        Args:
            path: Output file path
            format: Output format ("json" or "csv")

        Raises:
            ValueError: If format not supported
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if format == "json":
                self._save_json(path)
            elif format == "csv":
                self._save_csv(path)
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info("dataset_saved", path=str(path), format=format)

        except Exception as e:
            logger.error("dataset_save_failed", path=str(path), error=str(e))
            raise

    def _save_json(self, path: Path) -> None:
        """Save dataset as JSON."""
        data = {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "source": self.source,
            "questions": [q.to_dict() for q in self.questions],
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _save_csv(self, path: Path) -> None:
        """Save dataset as CSV."""
        if not self.questions:
            return

        fieldnames = [
            "id",
            "question",
            "expected_answers",
            "query_type",
            "difficulty",
            "tags",
        ]

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for q in self.questions:
                writer.writerow(
                    {
                        "id": q.id,
                        "question": q.question,
                        "expected_answers": "|".join(q.expected_answers),
                        "query_type": q.query_type,
                        "difficulty": q.difficulty,
                        "tags": "|".join(q.tags),
                    }
                )

    def get_statistics(self) -> dict[str, Any]:
        """Get dataset statistics.

        Returns:
            Dictionary with statistics (size, type distribution, difficulty, etc.)
        """
        if not self.questions:
            return {
                "total_questions": 0,
                "avg_difficulty": 0,
                "query_types": {},
                "difficulty_distribution": {},
            }

        # Count by query type
        type_counts: dict[str, int] = {}
        for q in self.questions:
            type_counts[q.query_type] = type_counts.get(q.query_type, 0) + 1

        # Count by difficulty
        difficulty_counts: dict[int, int] = {}
        for q in self.questions:
            difficulty_counts[q.difficulty] = difficulty_counts.get(q.difficulty, 0) + 1

        # Calculate average difficulty
        avg_difficulty = sum(q.difficulty for q in self.questions) / len(
            self.questions
        )

        return {
            "total_questions": len(self.questions),
            "avg_difficulty": round(avg_difficulty, 2),
            "query_types": type_counts,
            "difficulty_distribution": difficulty_counts,
            "difficulties": difficulty_counts,
            "avg_answers_per_question": round(
                sum(len(q.expected_answers) for q in self.questions) / len(self.questions),
                2,
            ),
        }

    def filter_by_type(self, query_type: str) -> QADataset:
        """Filter dataset by question type.

        Args:
            query_type: Query type to filter by ("entity", "relation", etc.)

        Returns:
            New QADataset with filtered questions
        """
        filtered = [q for q in self.questions if q.query_type == query_type]

        logger.debug(
            "dataset_filtered_by_type",
            query_type=query_type,
            original_count=len(self.questions),
            filtered_count=len(filtered),
        )

        return QADataset(
            name=f"{self.name}_{query_type}",
            description=f"{self.description} (filtered by type: {query_type})",
            questions=filtered,
            version=self.version,
            source=self.source,
        )

    def filter_by_difficulty(self, min_difficulty: int, max_difficulty: int) -> QADataset:
        """Filter dataset by difficulty range.

        Args:
            min_difficulty: Minimum difficulty level (inclusive)
            max_difficulty: Maximum difficulty level (inclusive)

        Returns:
            New QADataset with filtered questions
        """
        filtered = [
            q
            for q in self.questions
            if min_difficulty <= q.difficulty <= max_difficulty
        ]

        logger.debug(
            "dataset_filtered_by_difficulty",
            min=min_difficulty,
            max=max_difficulty,
            original_count=len(self.questions),
            filtered_count=len(filtered),
        )

        return QADataset(
            name=f"{self.name}_diff{min_difficulty}-{max_difficulty}",
            description=f"{self.description} (difficulty {min_difficulty}-{max_difficulty})",
            questions=filtered,
            version=self.version,
            source=self.source,
        )

    def filter_by_tags(self, tags: list[str]) -> QADataset:
        """Filter dataset by tags (OR logic - any tag match).

        Args:
            tags: Tags to filter by

        Returns:
            New QADataset with filtered questions
        """
        filtered = [q for q in self.questions if any(t in q.tags for t in tags)]

        logger.debug(
            "dataset_filtered_by_tags",
            tags=tags,
            original_count=len(self.questions),
            filtered_count=len(filtered),
        )

        return QADataset(
            name=f"{self.name}_tags",
            description=f"{self.description} (filtered by tags: {', '.join(tags)})",
            questions=filtered,
            version=self.version,
            source=self.source,
        )

    def split_train_test(
        self, train_ratio: float = 0.8, split_ratio: float | None = None,
    ) -> tuple[QADataset, QADataset]:
        """Split dataset into train and test sets.

        Args:
            train_ratio: Ratio for training set (0.0-1.0)
            split_ratio: Legacy alias for train_ratio

        Returns:
            Tuple of (train_dataset, test_dataset)
        """
        if split_ratio is not None:
            train_ratio = split_ratio
        split_idx = int(len(self.questions) * train_ratio)
        train_questions = self.questions[:split_idx]
        test_questions = self.questions[split_idx:]

        train_dataset = QADataset(
            name=f"{self.name}_train",
            description=f"{self.description} (training set)",
            questions=train_questions,
            version=self.version,
            source=self.source,
        )

        test_dataset = QADataset(
            name=f"{self.name}_test",
            description=f"{self.description} (test set)",
            questions=test_questions,
            version=self.version,
            source=self.source,
        )

        logger.info(
            "dataset_split",
            train_count=len(train_questions),
            test_count=len(test_questions),
            train_ratio=train_ratio,
        )

        return train_dataset, test_dataset

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "source": self.source,
            "questions": [q.to_dict() for q in self.questions],
        }
