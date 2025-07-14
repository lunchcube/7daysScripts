#!/bin/bash

LOG_DIR="/home/7days/7days/"  # Change this to your log directory
DISCORD_WEBHOOK="https://discord.com/api/webhooks/Your/Webhook" # Only used to send messages to a 2nd channel, used for admin specific messages, yes I know its backwards
DISCORD_WEBHOOK2="https://discord.com/api/webhooks/Your/Webhook" 
SCRIPT_DIR="$(dirname "$(realpath "$0")")"
LOG_OUTPUT="$SCRIPT_DIR/log_monitor_output.txt"

blood_moon_active=false
declare -A bloodmoon_kills

# Function to find the latest log file based on modification time
get_latest_log_file() {
    ls -t "$LOG_DIR"/output_log__*.txt 2>/dev/null | head -n 1
}

log_message() {
    local MESSAGE="$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $MESSAGE" | tee -a "$LOG_OUTPUT"
}

# Remove all mentions of this function if you only want messages to 1 Discord channel, this used for admin only messages
send_discord_message() {
    local MESSAGE="$1"
    curl -H "Content-Type: application/json" -X POST -d "{\"content\": \"$MESSAGE\"}" "$DISCORD_WEBHOOK" 2>>"$LOG_OUTPUT"
    log_message "Sent to Discord: $MESSAGE"
}

send_discord_message2() {
    local MESSAGE="$1"
    curl -H "Content-Type: application/json" -X POST -d "{\"content\": \"$MESSAGE\"}" "$DISCORD_WEBHOOK2" 2>>"$LOG_OUTPUT"
}

send_server_chat() {
    local CHAT_MESSAGE="$1"
    {
        echo "say $CHAT_MESSAGE"
        sleep 1
    } | telnet 127.0.0.1 8081 > /dev/null 2>&1
}

# Get the latest log file once at startup, if the server restarts this script will also need to be restarted
LOG_FILE=$(get_latest_log_file)

if [[ -z "$LOG_FILE" ]]; then
    log_message "ERROR: No log files found in $LOG_DIR."
    exit 1
fi

log_message "Monitoring log file: $LOG_FILE"

# Start monitoring the log file
# Detects certain events in the log file and sends a message to Discord
tail -F "$LOG_FILE" | while read -r line; do
    # Watch for players logging in
    if [[ "$line" =~ PlayerLogin:\ ([^/]+) ]]; then
        PLAYER_NAME="${BASH_REMATCH[1]}"
        send_discord_message "🚀 **$PLAYER_NAME has logged in!**"
        send_discord_message2 "🚀 **$PLAYER_NAME has logged in!**"

    # Watch for players leaving the game
    elif [[ "$line" =~ Player\ \'([^\']+)\'\ left\ the\ game ]]; then
        PLAYER_NAME="${BASH_REMATCH[1]}"
        send_discord_message "👋 **$PLAYER_NAME has left the game!**"
        send_discord_message2 "👋 **$PLAYER_NAME has left the game!**"

    # Log Global chat messages to Discord
    elif [[ $line =~ Chat\ \(from\ .+,\ to\ \'Global\'\):\ \'([^\']+)\'\:\ (.+) ]]; then
        USERNAME="${BASH_REMATCH[1]}"
        CHAT_MESSAGE="${BASH_REMATCH[2]}"
        MESSAGE="💬 **$USERNAME**: $CHAT_MESSAGE"
        send_discord_message "Global Chat:  $MESSAGE"
        send_discord_message2 "Global Chat:  $MESSAGE"

    # Log player deaths to Discord
    elif [[ "$line" =~ GMSG:\ Player\ \'([^\']+)\'\ died ]]; then
        PLAYER_NAME="${BASH_REMATCH[1]}"
        send_discord_message "💀 **$PLAYER_NAME has died!**"
        send_discord_message2 "💀 **$PLAYER_NAME has died!**"

    # Sends coordinates that a player spawned in at to a Discord channel (Admins only)
    elif [[ "$line" =~ PlayerSpawnedInWorld\ \(reason:\ ([^,]+),\ position:\ (-?[0-9]+),\ (-?[0-9]+),\ (-?[0-9]+)\):.*PlayerName=\'([^\']+)\' ]]; then
        REASON="${BASH_REMATCH[1]}"
        X="${BASH_REMATCH[2]}"
        Y="${BASH_REMATCH[3]}"
        Z="${BASH_REMATCH[4]}"
        PLAYER_NAME="${BASH_REMATCH[5]}"

        # Format X coordinate
        if (( X < 0 )); then
            X_DIR="W ${X#-}"
        else
            X_DIR="E $X"
        fi

        # Format Z coordinate
        if (( Z < 0 )); then
            Z_DIR="S ${Z#-}"
        else
            Z_DIR="N $Z"
        fi

        Y_VAL="$Y"

        if [[ "$REASON" == "Teleport" ]]; then
            send_discord_message "🧭 **$PLAYER_NAME** spawned at: $X_DIR Y $Y_VAL $Z_DIR"
        elif [[ "$REASON" == "Died" ]]; then
            send_discord_message "☠️ **$PLAYER_NAME** re-spawned at: $X_DIR Y $Y_VAL $Z_DIR"
        else
            send_discord_message "🔄 **$PLAYER_NAME** spawned (reason: $REASON) at: $X_DIR Y $Y_VAL $Z_DIR"
        fi

    # Logs when a blood moon starts to a Discord channel
    elif [[ "$line" =~ BloodMoon\ starting\ for\ day\ ([0-9]+) ]]; then
        BLOOD_DAY="${BASH_REMATCH[1]}"
        send_discord_message "🌕 Blood moon started for day $BLOOD_DAY"
        send_discord_message2 "🌕 Blood moon started for day $BLOOD_DAY"

        # Sets blood moon kill tracker to active
        blood_moon_active=true
        declare -A bloodmoon_kills=()  # Reset zombie kill tracker
        log_message "🟥 Blood Moon started - tracking zombie kills."

    # Logs when a blood moon is over and prints out top 3 kills in game chat and full list to Discord
    elif [[ "$line" =~ Blood\ moon\ is\ over! ]]; then
        send_discord_message "🌤️ Blood moon is over!"
        send_discord_message2 "🌤 Blood moon is over!"

        # Stops blood moon kill tracker
        blood_moon_active=false
        log_message "⬛ Blood Moon ended - summarizing kills..."

        if [ ${#bloodmoon_kills[@]} -eq 0 ]; then
            send_server_chat "No zombie kills recorded during Blood Moon."
            send_discord_message "🧟♂️ Blood Moon ended - no kills recorded."
            send_discord_message2 "🧟♂ Blood Moon ended - no kills recorded."
        else
            sorted_report=$(for player in "${!bloodmoon_kills[@]}"; do
                echo "${bloodmoon_kills[$player]}:$player"
            done | sort -rn | awk -F: '{ printf "%d. %s - %d kills\n", NR, $2, $1 }')

            top_three=$(echo "$sorted_report" | head -n 3 | sed 's/^[0-9]\+\. //' | paste -sd ", " -)

            send_server_chat "🧟‍♂️ Blood Moon MVPs: $top_three"
            send_discord_message "🧟‍♂️ **Blood Moon Kill Report:**\n$sorted_report"
            send_discord_message2 "🧟<200d>♂ **Blood Moon Kill Report:**\n$sorted_report"
        fi

    # Logs PvP kills to a Discord channel, you must also havve track_kills.sh in order for this to work
    elif [[ "$line" =~ GMSG:\ Player\ \'([^\']+)\'\ killed\ by\ \'([^\']+)\' ]]; then
        VICTIM="${BASH_REMATCH[1]}"
        KILLER="${BASH_REMATCH[2]}"
        send_discord_message "⚔️ **$KILLER** killed **$VICTIM**"
        send_discord_message2 "⚔ **$KILLER** killed **$VICTIM**"
        /home/7days/track_kills.sh "$KILLER" "$VICTIM"
    fi
done
