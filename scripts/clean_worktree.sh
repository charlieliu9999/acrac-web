#!/usr/bin/env bash
set -e
echo "[clean] Removing transient artifacts..."
rm -f ab_test_show_reasoning_*.json || true
rm -f ragas_results_*.json || true
rm -f *.log || true
find logs -type f -name "*.log" -delete 2>/dev/null || true
echo "[clean] Done."

