"""Example: Using the Build Pipeline with Stopping Criteria.

This example demonstrates how to use the BuildPipeline with intelligent
stopping criteria to automatically stop KG building when quality gates are met.

Run this example with:
    python examples/build_pipeline_example.py
"""

from kgbuilder.pipeline import (
    BuildPipeline,
    BuildPipelineConfig,
    StoppingCriteria,
)


def example_basic_usage():
    """Basic usage: Run pipeline with default stopping criteria."""
    print("=" * 70)
    print("EXAMPLE 1: Basic Pipeline with Default Criteria")
    print("=" * 70)

    # Create sample competency questions
    cqs = [
        {"id": "CQ-1", "question": "What entities exist?", "sparql": "SELECT ?x ..."},
        {"id": "CQ-2", "question": "What relations exist?", "sparql": "SELECT ?x ?y ..."},
        {"id": "CQ-3", "question": "What is entity X?", "sparql": "SELECT ?prop ..."},
    ]

    # Create sample documents (empty list for demo)
    docs = ["doc1", "doc2", "doc3"]

    # Create pipeline with default criteria
    pipeline = BuildPipeline(BuildPipelineConfig())

    # Run pipeline
    result = pipeline.run(documents=docs, competency_questions=cqs)

    # Print results
    print(result.get_summary_string())
    print()


def example_custom_criteria():
    """Custom criteria: Strict quality requirements."""
    print("=" * 70)
    print("EXAMPLE 2: Custom Stopping Criteria (Strict)")
    print("=" * 70)

    cqs = [
        {"id": "CQ-1", "question": "What entities exist?", "sparql": "SELECT ?x ..."},
        {"id": "CQ-2", "question": "What relations exist?", "sparql": "SELECT ?x ?y ..."},
    ]
    docs = ["doc1", "doc2"]

    # Define strict criteria
    criteria = StoppingCriteria(
        min_cq_coverage=0.95,           # 95% CQs must be answerable
        min_validation_pass_rate=0.90,  # 90% validation must pass
        min_avg_confidence=0.80,        # High confidence requirement
        min_entity_count=150,           # At least 150 entities
        max_iterations=8,               # Max 8 iterations
        require_all=True                # ALL criteria must be met
    )

    config = BuildPipelineConfig(
        stopping_criteria=criteria,
        validate_at_each_iteration=True
    )
    pipeline = BuildPipeline(config)

    result = pipeline.run(documents=docs, competency_questions=cqs)

    print(result.get_summary_string())
    print()

    # Show detailed criteria checks
    print("Detailed Criteria Checks:")
    print(pipeline.get_checker_summary())
    print()


def example_cq_coverage_focus():
    """CQ-focused: Stop when CQs are well covered."""
    print("=" * 70)
    print("EXAMPLE 3: Focus on CQ Coverage")
    print("=" * 70)

    cqs = [
        {"id": "CQ-1", "question": "Q1", "sparql": "..."},
        {"id": "CQ-2", "question": "Q2", "sparql": "..."},
        {"id": "CQ-3", "question": "Q3", "sparql": "..."},
    ]
    docs = ["doc1"]

    # CQ-focused criteria
    criteria = StoppingCriteria(
        min_cq_coverage=0.98,           # 98% CQs answered!
        min_validation_pass_rate=0.75,  # Lower validation bar
        min_avg_confidence=0.70,        # Lower confidence bar
        min_entity_count=50,            # Fewer entities okay
        require_all=True
    )

    config = BuildPipelineConfig(stopping_criteria=criteria)
    pipeline = BuildPipeline(config)

    result = pipeline.run(documents=docs, competency_questions=cqs)

    print(result.get_summary_string())
    if result.cq_summary:
        print(f"\nCQ Details:")
        print(f"  Answerable: {result.cq_summary.answerable_questions}/{result.cq_summary.total_questions}")
        print(f"  Coverage: {result.cq_summary.coverage_percentage:.1f}%")
        if result.cq_summary.unanswerable:
            print(f"  Unanswerable: {result.cq_summary.unanswerable}")
    print()


def example_fast_build():
    """Fast mode: Stop as soon as quality is acceptable."""
    print("=" * 70)
    print("EXAMPLE 4: Fast Build Mode (Any Criterion)")
    print("=" * 70)

    cqs = [
        {"id": "CQ-1", "question": "Q1", "sparql": "..."},
    ]
    docs = ["doc1"]

    # Fast criteria: ANY criterion triggers stop
    criteria = StoppingCriteria(
        min_cq_coverage=0.80,           # 80% CQs
        min_validation_pass_rate=0.80,  # 80% validation
        min_avg_confidence=0.70,        # 70% confidence
        require_all=False               # Any can trigger stop!
    )

    config = BuildPipelineConfig(stopping_criteria=criteria)
    pipeline = BuildPipeline(config)

    result = pipeline.run(documents=docs, competency_questions=cqs)

    print(result.get_summary_string())
    print()


def example_iteration_details():
    """Show iteration-by-iteration progress."""
    print("=" * 70)
    print("EXAMPLE 5: Iteration-by-Iteration Progress")
    print("=" * 70)

    cqs = [
        {"id": "CQ-1", "question": "Q1", "sparql": "..."},
        {"id": "CQ-2", "question": "Q2", "sparql": "..."},
    ]
    docs = ["doc1"]

    criteria = StoppingCriteria(min_cq_coverage=0.95)
    config = BuildPipelineConfig(stopping_criteria=criteria)
    pipeline = BuildPipeline(config)

    result = pipeline.run(documents=docs, competency_questions=cqs)

    print(f"Pipeline completed in {result.total_iterations} iterations\n")

    # Show each iteration
    for iteration in result.iterations:
        print(f"Iteration {iteration.iteration_num}:")
        print(f"  Entities extracted: {iteration.entities_extracted}")
        print(f"  Relations extracted: {iteration.relations_extracted}")
        print(f"  Duration: {iteration.duration_ms:.0f}ms")
        if iteration.cq_results:
            print(f"  CQ Coverage: {iteration.cq_results.coverage_percentage:.1f}%")
        if iteration.validation_result:
            print(f"  Validation Pass Rate: {iteration.validation_result.get('pass_rate', 0):.1f}%")
        print()

    print(f"Final Result: {result.stopping_reason.value}")
    print()


def main():
    """Run all examples."""
    try:
        example_basic_usage()
        example_custom_criteria()
        example_cq_coverage_focus()
        example_fast_build()
        example_iteration_details()

        print("=" * 70)
        print("All examples completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
