#!/bin/bash
# Automatically restarts the main server and monitoring scripts via system services
# This script is meant to be called via cron job for daily/weekly restarts

# Change based on your telnet port
TELNET_PORT=8081

say() {
    local MESSAGE="$1"
    {
        echo "say $MESSAGE"
        echo "exit"
    } | telnet localhost $TELNET_PORT > /dev/null 2>&1
}

echo "$(date '+%F %T') Restarting 7DTD server..." >> /home/7days/restart.log

# Send warning messages to the in game chat
say "Server will restart in 5 minutes!"
sleep 240  # 4 minutes
say "Server will restart in 1 minute!"
sleep 60

# Stop the server services
systemctl stop log_monitor.service
systemctl stop gimmie.service
systemctl stop 7daystodie.service

# Wait 60 seconds to ensure clean shutdown
sleep 60

# Start the server service
systemctl start 7daystodie.service

# Optional: Wait 3-5 minutes for server to be ready before restarting the log monitor
sleep 240

# Restart log monitor and gimmie service
systemctl start log_monitor.service
systemctl start gimmie.service

# Change based on your user/folder structure
echo "$(date '+%F %T') Restart complete." >> /home/7days/restart.log
