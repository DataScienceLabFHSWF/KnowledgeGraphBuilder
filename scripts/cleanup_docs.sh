#!/bin/bash
# cleanup_docs.sh - Archive old session docs and consolidate to MASTER_PLAN.md
# Run: bash scripts/cleanup_docs.sh

set -e

ARCHIVE_DIR="local-docs/archive"
mkdir -p "$ARCHIVE_DIR"

echo "📦 Archiving session-specific documentation..."

# Files to archive (superseded by Planning/MASTER_PLAN.md)
FILES_TO_ARCHIVE=(
    # Session summaries
    "SESSION_SUMMARY.md"
    "CURRENT_STATUS.md"
    
    # Phase completion docs (now in MASTER_PLAN.md)
    "PHASE_2_COMPLETION_CHECKLIST.md"
    "PHASE_2_SUMMARY.md"
    "PHASE_3A_EXTRACTION_COMPLETE.md"
    "PHASE_3B_COMPLETE.md"
    "PHASE_3B_TO_3C_TRANSITION.md"
    "PHASE_3C_ADVANCED_PROCESSOR.md"
    "PHASE_3C_PLAN.md"
    "PHASE_3C_QUICKSTART.md"
    "PHASE_3C_SPRINT1_COMPLETE.md"
    "PHASE_3_COMPLETE.md"
    "PHASE_3_COMPLETE_STATUS.md"
    "PHASE_4A_COMPLETE.md"
    "PHASE_4B_COMPLETE.md"
    "PHASE_4C_COMPLETE.md"
    "PHASE_4_FINAL_RESULTS.md"
    "PHASE_4_ROADMAP.md"
    "PHASE_5_CONFIDENCE_TUNING.md"
    "PHASE_5_INDEX.md"
    "PHASE_5_QUICK_START.md"
    "PHASE_5_READY_DOCUMENTATION.md"
    "PHASE_5_SESSION_SUMMARY.md"
    "PHASE_5_TASKS_1_3_COMPLETE.md"
    "PHASE_6_PLAN.md"
    "PHASES_1_5_COMPLETE.md"
    
    # Index files (superseded)
    "INDEX.md"
    "INDEX_OLD.md"
    
    # Implementation status (superseded)
    "IMPLEMENTATION_STATUS.md"
    "IMPLEMENTATION_STATUS_COMPLETE.md"
    "IMPLEMENTATION_GUIDE.md"
    
    # Quickstarts (merged into MASTER_PLAN)
    "QUICKSTART_DATA.md"
    "QUICK_START_ADVANCED_PROCESSOR.md"
    
    # Old readmes
    "README_PHASE_3B_COMPLETE.md"
    
    # Misc completion docs
    "SCAFFOLDING_COMPLETE.md"
    "PIPELINE_REFACTORING_COMPLETE.md"
    "RELEASE_0_1_0_SUMMARY.md"
    "FUSEKI_ONTOLOGY_COMPLETE.md"
    "DATA_INTEGRATION_COMPLETE.md"
    "ONTOLOGY_STATUS.md"
)

cd local-docs

for file in "${FILES_TO_ARCHIVE[@]}"; do
    if [ -f "$file" ]; then
        mv "$file" "archive/$file"
        echo "  ✓ Archived: $file"
    fi
done

echo ""
echo "✅ Archived ${#FILES_TO_ARCHIVE[@]} files to local-docs/archive/"
echo ""
echo "📚 Remaining documentation:"
echo "   - Planning/MASTER_PLAN.md (Single Source of Truth)"
echo "   - Planning/ARCHITECTURE.md (Detailed diagrams)"
echo "   - Planning/ISSUES_BACKLOG.md (Historical reference)"
echo "   - README.md (User quickstart)"
echo ""
echo "🗑️  To delete archived files permanently:"
echo "   rm -rf local-docs/archive/"
