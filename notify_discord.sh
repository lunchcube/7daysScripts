#!/bin/bash
# Used to notify Discord for server restarts

DISCORD_WEBHOOK="https://discord.com/api/webhooks/Your/Webhook"
SERVICE_NAME="7 Days to Die Server"
STATUS="$1"

MESSAGE="⚠️ **$SERVICE_NAME has $STATUS!**"

curl -H "Content-Type: application/json" -X POST -d "{\"content\": \"$MESSAGE\"}" "$DISCORD_WEBHOOK"
