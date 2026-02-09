#!/bin/bash
# Run full KG pipeline in background with venv and PYTHONPATH

cd /home/fneubuerger/KnowledgeGraphBuilder

nohup bash -c 'source .venv/bin/activate && export PYTHONPATH=/home/fneubuerger/KnowledgeGraphBuilder/src:$PYTHONPATH && python scripts/full_kg_pipeline.py --max-iterations 1' > /tmp/kg_pipeline_$(date +%Y%m%d_%H%M%S).log 2>&1 &

echo "Pipeline started in background"
sleep 1
echo "View log with: tail -f /tmp/kg_pipeline_*.log"
