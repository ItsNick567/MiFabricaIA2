#!/usr/bin/env bash
set -euo pipefail

echo "Starting Tutorial Pipeline Autonomous Mode..."
echo ""
echo "This process will generate and publish tutorials automatically."
echo "Press Ctrl+C to stop."
echo ""
cd tutorial_pipeline_v2
python autonomous_pipeline.py
