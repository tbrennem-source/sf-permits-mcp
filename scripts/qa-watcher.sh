#!/bin/bash
# qa-watcher.sh
# Watches qa-drop/ folder and notifies when CC deposits a new QA script
# Usage: bash scripts/qa-watcher.sh
# Requires: brew install fswatch

QA_DROP_DIR="$(git rev-parse --show-toplevel)/qa-drop"
mkdir -p "$QA_DROP_DIR"

echo "👀 Watching $QA_DROP_DIR for new QA scripts..."
echo "Press Ctrl+C to stop."

fswatch -o "$QA_DROP_DIR" | while read -r event; do
  LATEST=$(ls -t "$QA_DROP_DIR"/*.md 2>/dev/null | head -1)

  if [ -n "$LATEST" ]; then
    FILENAME=$(basename "$LATEST")
    cat "$LATEST" | pbcopy
    osascript -e "display notification \"$FILENAME copied to clipboard — paste into Cowork\" \
      with title \"QA Script Ready\" \
      sound name \"Glass\""
    echo "✅ $(date '+%H:%M:%S') — $FILENAME copied to clipboard"
  fi
done
