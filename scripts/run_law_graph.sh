#!/bin/bash
# Law Graph Pipeline Runner
# This script properly sets up the environment and runs the law graph pipeline

set -e  # Exit on any error

echo "================================================================================"
echo "Law Graph Pipeline Runner"
echo "================================================================================"
echo ""

# Check if we're in the right directory
if [ ! -f "data/profiles/legal.json" ]; then
    echo "Error: data/profiles/legal.json not found. Are you in the KnowledgeGraphBuilder directory?"
    exit 1
fi

# Activate virtual environment
if [ ! -d ".venv" ]; then
    echo "Error: .venv directory not found. Please run 'python -m venv .venv' first."
    exit 1
fi

echo "Activating virtual environment..."
source .venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH="$PWD/src:$PYTHONPATH"
echo "PYTHONPATH set to: $PYTHONPATH"

# Generate log filename with timestamp
LOG_FILE="law_graph_$(date +%Y%m%d_%H%M%S).log"
echo "Log file: $LOG_FILE"
echo ""

# Run the pipeline
echo "Starting law graph pipeline..."
echo "Command: python scripts/build_law_graph.py $EXTRA_ARGS"
echo "Log: $LOG_FILE"
echo ""

if [ "$1" = "--background" ] || [ "$1" = "-b" ]; then
    shift  # remove --background/-b from args so remaining args pass through
    echo "Running in background with nohup..."
    nohup python scripts/build_law_graph.py "$@" > "$LOG_FILE" 2>&1 &
    PID=$!
    echo "Pipeline started in background with PID: $PID"
    echo "Monitor with: tail -f $LOG_FILE"
    echo "Kill with: kill $PID"
else
    echo "Running interactively (press Ctrl+C to stop)..."
    python scripts/build_law_graph.py "$@"
fi

echo ""
echo "================================================================================"
echo "Pipeline execution complete"
echo "================================================================================"