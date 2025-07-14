#!/usr/bin/env python3

import time
import json
import random
import re
import os
from datetime import datetime, timedelta
import telnetlib

# Change the file paths based on your user/folder setup
LOG_FILE = "/home/7days/7days/output_log__*.txt"
DEBUG_LOG = "/home/7days/gimmie_debug.log"
ITEMS_CSV = "/home/7days/items.csv"
COOLDOWN_FILE = "/home/7days/gimmie_cooldowns.json"
# Change cooldown minutes if you want to allow the command more often, or less often
COOLDOWN_MINUTES = 60
TELNET_HOST = "localhost"
TELNET_PORT = 8081  # Change to your configured port
TELNET_TIMEOUT = 5

# Change these to change the chances of item spawning, rarity is defined in items.csv
RARITY_WEIGHTS = {
    "common": 65,
    "uncommon": 20,
    "rare": 10,
    "epic": 4,
    "legendary": 1
}

# Change these to determine item quality chances
QUALITY_WEIGHTS = {
    1: 30,
    2: 25,
    3: 20,
    4: 15,
    5: 9,
    6: 1
}


def load_items():
    items = []
    with open(ITEMS_CSV, "r") as f:
        for line in f:
            if line.strip().lower().startswith("name"):
                continue
            parts = line.strip().split(",")
            if len(parts) >= 3:
                item = {
                    "name": parts[0],
                    "type": parts[1],
                    "rarity": parts[2],
                    "maxQuantity": int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 1
                }
                items.append(item)
    return items


def load_cooldowns():
    if not os.path.exists(COOLDOWN_FILE):
        return {}
    with open(COOLDOWN_FILE, "r") as f:
        return json.load(f)


def save_cooldowns(cooldowns):
    with open(COOLDOWN_FILE, "w") as f:
        json.dump(cooldowns, f)


def weighted_random_choice(weight_dict):
    total = sum(weight_dict.values())
    rand_val = random.randint(1, total)
    for key, weight in weight_dict.items():
        rand_val -= weight
        if rand_val <= 0:
            return key
    return random.choice(list(weight_dict.keys()))


def send_telnet_command(command):
    try:
        with telnetlib.Telnet(TELNET_HOST, TELNET_PORT, timeout=3) as tn:
            time.sleep(0.5)
            tn.read_until(b"Press 'help' to get a list of all commands.", timeout=2)

            tn.write(command.encode('utf-8') + b"\n")
            time.sleep(0.5)
            output = tn.read_very_eager().decode('utf-8', errors='ignore')
            return output
    except Exception as e:
        with open("/home/7days/gimmie_debug.log", "a") as f:
            f.write(f"{datetime.utcnow().isoformat()} - Telnet error: {e}\n")
        raise

# Not used, made to debug give/say commands on top of eachother, didnt work
def send_multiple_telnet_commands(commands):
    try:
        with telnetlib.Telnet(TELNET_HOST, TELNET_PORT, TELNET_TIMEOUT) as tn:
            # Give the server time to send the banner
            time.sleep(0.5)
            tn.read_until(b"Press 'exit' to end session.", timeout=2)

            for cmd in commands:
                tn.write(cmd.encode('utf-8') + b"\n")
                time.sleep(0.2)  # slight delay between commands

            time.sleep(0.5)
            output = tn.read_very_eager().decode('utf-8', errors='ignore')
            with open("/home/7days/gimmie_debug.log", "a") as f:
                f.write(f"{datetime.utcnow().isoformat()} - [MULTI TELNET] Response: {output}\n")

            return output
    except Exception as e:
        with open("/home/7days/gimmie_debug.log", "a") as f:
            f.write(f"{datetime.utcnow().isoformat()} - Telnet error: {e}\n")
        raise

def log_debug(message):
    with open(DEBUG_LOG, "a") as f:
        f.write(f"{datetime.utcnow().isoformat()} - {message}\n")

def give_item(entity_id, player_name):
    items = load_items()
    rarity = weighted_random_choice(RARITY_WEIGHTS)
    eligible = [i for i in items if i['rarity'].lower() == rarity]
    if not eligible:
        print(f"No items with rarity: {rarity}")
        return

    item = random.choice(eligible)
    name = item['name']
    type_ = item['type'].lower()
    max_qty = item.get('maxQuantity', 1)

    if type_ == "material":
        amount = random.choice(range(100, 1100, 100))
        cmd = f"give {entity_id} {name} {amount}"
        message = f"{player_name} received {amount}x {name} - Check your feet!"
    elif type_ in ["food", "drink","resource"]:
        amount = random.randint(1, max(1, max_qty))
        cmd = f"give {entity_id} {name} {amount}"
        message = f"{player_name} received {amount}x {name} - Check your feet!"
    else:
        amount = 1
        quality = weighted_random_choice(QUALITY_WEIGHTS)
        cmd = f"give {entity_id} {name} {amount} {quality}"
        message = f"{player_name} received a quality {quality} {name} - Check your feet!"

    send_telnet_command(cmd)

    # Setting this lower will cause the 2nd command to never be sent to the server
    time.sleep(3)

    # Send the say message with error handling, outputs which player got which item in game chat
    try:
        say_command = f'say "{message}"'
        response = send_telnet_command(say_command)
        log_debug(f"[SAY] Sent message: {say_command}")
        log_debug(f"[SAY] Response: {response.strip()}")
    except Exception as e:
        log_debug(f"[SAY] Error: {e}")
        log_debug(f"[SAY] Failed message: {message}")

    log_debug(f"[GIVE] {player_name} -> {cmd}")


def process_line(line, cooldowns):
    match = re.search(r"Chat \(from 'Steam_(\d+)', entity id '(\d+)', to 'Global'\): '([^']+)': /gimmie", line)
    if not match:
        return

    steam_id, entity_id, player_name = match.groups()
    now = datetime.utcnow()

    last_used_str = cooldowns.get(steam_id)
    if last_used_str:
        last_used = datetime.strptime(last_used_str, "%Y-%m-%dT%H:%M:%S")
        diff = now - last_used
        if diff < timedelta(minutes=COOLDOWN_MINUTES):
            minutes_left = COOLDOWN_MINUTES - int(diff.total_seconds() // 60)
            send_telnet_command(f'say "{player_name}, try again in {minutes_left} minutes."')
            return

    give_item(entity_id, player_name)
    cooldowns[steam_id] = now.strftime("%Y-%m-%dT%H:%M:%S")
    save_cooldowns(cooldowns)


def get_latest_log():
    import glob
    logs = glob.glob(LOG_FILE)
    if not logs:
        return None
    return max(logs, key=os.path.getmtime)


def monitor_log():
    latest_log = get_latest_log()
    if not latest_log:
        print("[ERROR] No log file found.")
        return

    print(f"[INFO] Monitoring: {latest_log}")
    cooldowns = load_cooldowns()

    with open(latest_log, "r") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            process_line(line.strip(), cooldowns)


if __name__ == "__main__":
    monitor_log()
