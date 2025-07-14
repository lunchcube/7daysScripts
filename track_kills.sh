#!/bin/bash

# Change based on your user/folder structure
KILL_STATS_FILE="/home/7days/kill_stats.json"
KILLER="$1"
VICTIM="$2"

# Create file if it doesn't exist
if [[ ! -f "$KILL_STATS_FILE" ]]; then
    echo "{}" > "$KILL_STATS_FILE"
fi

# Update total kills and per-victim kills for the killer
UPDATED_JSON=$(jq --arg killer "$KILLER" --arg victim "$VICTIM" '
  .[$killer].total_kills = (.[$killer].total_kills // 0) + 1
  | .[$killer].kills[$victim] = (.[$killer].kills[$victim] // 0) + 1
' "$KILL_STATS_FILE")

# Creates and/or overwrites old file with new stats
echo "$UPDATED_JSON" > "$KILL_STATS_FILE"
