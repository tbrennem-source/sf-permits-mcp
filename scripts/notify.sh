#!/bin/bash
# Differentiated notification sounds for CC workflow events
# Usage: scripts/notify.sh <event_type> [message]
#
# Event types:
#   agent-done      - Single agent completed (Tink — light, brief)
#   terminal-done   - Full terminal (T1-T4) completed (Glass — clear, ringing)
#   sprint-done     - Full sprint complete (Hero — triumphant)
#   qa-fail         - QA FAIL detected (Basso — deep, attention-getting)
#   prod-promoted   - Promoted to prod (Funk — celebratory)
#   [anything else] - Generic notification (Pop — neutral)
#
# Disable: NOTIFY_ENABLED=0 scripts/notify.sh agent-done

EVENT="$1"
MESSAGE="${2:-$EVENT}"

# Allow disabling all notifications via environment variable
[ "${NOTIFY_ENABLED:-1}" = "0" ] && exit 0

case "$EVENT" in
  agent-done)
    afplay /System/Library/Sounds/Tink.aiff &
    ;;
  terminal-done)
    afplay /System/Library/Sounds/Glass.aiff &
    ;;
  sprint-done)
    afplay /System/Library/Sounds/Hero.aiff &
    ;;
  qa-fail)
    afplay /System/Library/Sounds/Basso.aiff &
    ;;
  prod-promoted)
    afplay /System/Library/Sounds/Funk.aiff &
    ;;
  *)
    afplay /System/Library/Sounds/Pop.aiff &
    ;;
esac

# macOS notification center
osascript -e "display notification \"$MESSAGE\" with title \"sfpermits.ai\" subtitle \"$EVENT\"" 2>/dev/null

exit 0
