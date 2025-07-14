import discord
import json
import asyncio
import telnetlib

# Change this to whichever user/folder you are using
KILL_STATS_PATH = "/home/7days/kill_stats.json"
DISCORD_TOKEN = "SuperSecretToken"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def send_telnet_command(cmd):
    try:
        tn = telnetlib.Telnet("localhost", 8081, timeout=5)
        tn.write(cmd.encode('utf-8') + b"\n")
        tn.write(b"exit\n")
        tn.close()
        return True
    except Exception as e:
        print(f"Telnet error: {e}")
        return False

def send_telnet_and_get_output(cmd):
    try:
        tn = telnetlib.Telnet("localhost", 8081, timeout=5)
        tn.read_until(b">", timeout=1)  # Wait for prompt
        tn.write(cmd.encode('utf-8') + b"\n")
        # Wait for response (read until next prompt or timeout)
        output = tn.read_until(b">", timeout=2).decode("utf-8")
        tn.write(b"exit\n")
        #output = tn.read_all().decode('utf-8')
        tn.close()
        return output.strip()
    except Exception as e:
        return f"Telnet error: {e}"

# Deletes original message from user in Discord channel
async def delete_command_message(message):
    try:
        await message.delete()
    except discord.Forbidden:
        pass
    except discord.HTTPException:
        pass

# Helper function to split and send long content via DM
async def send_long_dm(user, title, content, max_chars=1900):
    """Split long content into multiple Discord DMs."""
    lines = content.splitlines()
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > max_chars:
            await user.send(f"{title}\n```{chunk}```")
            chunk = ""
        chunk += line + "\n"
    if chunk:
        await user.send(f"{title}\n```{chunk}```")

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # Shows top 10 players in terms of player kills
    if message.content.strip().lower() == "!leaderboard":
        try:
            with open(KILL_STATS_PATH, "r") as f:
                data = json.load(f)

            leaderboard = sorted(
                [(player, info.get("total_kills", 0)) for player, info in data.items()],
                key=lambda x: x[1],
                reverse=True
            )

            if not leaderboard:
                await message.channel.send("No kills recorded yet!")
                await delete_command_message(message)
                return

            output_lines = ["🏆 **Kill Leaderboard** 🏆"]
            for rank, (player, kills) in enumerate(leaderboard[:10], start=1):
                output_lines.append(f"{rank}. **{player}** - {kills} kill{'s' if kills != 1 else ''}")

            await message.channel.send("\n".join(output_lines))
            await delete_command_message(message)

        except Exception as e:
            await message.channel.send("⚠️ Failed to load leaderboard.")
            print("Error:", e)

    # Outputs the number of times a player has killed other players
    elif message.content.lower().startswith("!kills "):
        target = message.content[7:].strip().lower()

        try:
            with open(KILL_STATS_PATH, "r") as f:
                data = json.load(f)

            # Build a lowercase lookup map
            lowercased_data = {name.lower(): name for name in data.keys()}
            actual_name = lowercased_data.get(target)

            if not actual_name:
                await message.channel.send(f"🕵️ No kill data found for **{message.content[7:].strip()}**.")
                await delete_command_message(message)
                return

            player_data = data.get(actual_name, {})
            total_kills = player_data.get("total_kills", 0)
            kills = player_data.get("kills", {})

            response = [f"📊 **{actual_name}** has **{total_kills}** total kill{'s' if total_kills != 1 else ''}."]
            if kills:
                response.append("🧟 Kills by target:")
                for victim, count in sorted(kills.items(), key=lambda x: -x[1]):
                    response.append(f"- {victim}: {count}")
            else:
                response.append("No per-player kill breakdown available.")

            await message.channel.send("\n".join(response))
            await delete_command_message(message)

        except Exception as e:
            await message.channel.send("⚠️ Could not load kill data.")
            print("Error in !kills command:", e)

    # Allows admins to send server messages from Discord
    elif message.content.lower().startswith("!say "):
        allowed_roles = {"Admin", "Mods"}  # Customize these as needed
        user_roles = {role.name for role in message.author.roles}
        if not allowed_roles & user_roles:
            await message.channel.send("❌ You don't have permission to use this command.")
            await delete_command_message(message)
            return

        say_message = message.content[5:].strip()
        if not say_message:
            await message.channel.send("❗ You must provide a message.")
            await delete_command_message(message)
            return

        formatted_message = f"DISCORD | {message.author.display_name}: {say_message}"
        success = send_telnet_command(f'say "{formatted_message}"')
        if success:
            await message.channel.send("✅ Message sent to server.")
        else:
            await message.channel.send("⚠️ Failed to send message to server.")

        await delete_command_message(message)

    # Allows admin to run the 'lpi' command from Discord to get player list
    elif message.content.lower().startswith("!lpi"):
        allowed_roles = {"Admin", "Mods"}
        user_roles = {role.name for role in message.author.roles}

        if not allowed_roles & user_roles:
            await message.channel.send("❌ You don't have permission to use this command.")
            await delete_command_message(message)
            return

        output = send_telnet_and_get_output("lpi")

        if not output:
            await message.channel.send("⚠️ No output received.")
            await delete_command_message(message)
            return
        #print("RAW TELNET OUTPUT:\n", output)

        # Filter and clean output for Discord
        lines = output.splitlines()
        filtered_lines = [
            line for line in lines
            if not line.startswith("2025") and "Executing command" not in line
        ]

        result = "\n".join(filtered_lines)

        if not result:
            await message.channel.send("⚠️ No players online.")
        elif len(result) > 1900:
            await message.channel.send("⚠️ Output too long for Discord.")
        else:
            await message.channel.send(f"🧍 Players online:\n```{result}```")

        await delete_command_message(message)

    # Allows an admin to kick a player from Discord
    elif message.content.lower().startswith("!kick "):
        allowed_roles = {"Admin", "Mods"}
        user_roles = {role.name for role in message.author.roles}

        if not allowed_roles & user_roles:
            await message.channel.send("❌ You don't have permission to use this command.")
            await delete_command_message(message)
            return

        parts = message.content.strip().split(" ", 2)
        if len(parts) < 2:
            await message.channel.send("❗ Usage: `!kick <id> [reason]`")
            await delete_command_message(message)
            return

        entity_id = parts[1]
        reason = parts[2] if len(parts) == 3 else ""

        command = f"kick {entity_id} {reason}".strip()
        result = send_telnet_command(command)

        if result:
            await message.channel.send(f"✅ Kicked entity ID `{entity_id}`{' for reason: ' + reason if reason else ''}.")
        else:
            await message.channel.send("⚠️ Kick failed.")

        await delete_command_message(message)

    # Allows an admin to ban a player from Discord
    elif message.content.lower().startswith("!ban "):
        allowed_roles = {"Admin", "Mods"}
        user_roles = {role.name for role in message.author.roles}

        if not allowed_roles & user_roles:
            await message.channel.send("❌ You don't have permission to use this command.")
            await delete_command_message(message)
            return

        parts = message.content.strip().split(" ", 5)
        if len(parts) < 4:
            await message.channel.send("❗ Usage: `!ban <target> <duration> <unit> [reason]`")
            await delete_command_message(message)
            return

        target = parts[1]
        duration = parts[2]
        unit = parts[3]
        reason = parts[4] if len(parts) > 4 else ""

        command = f"ban add {target} {duration} {unit} {reason}".strip()
        result = send_telnet_command(command)

        if result:
            await message.channel.send(f"🔨 Banned `{target}` for {duration} {unit}{' (Reason: ' + reason + ')' if reason else ''}.")
        else:
            await message.channel.send("⚠️ Ban failed.")

        await delete_command_message(message)

    # Prints out a help message of available commands
    elif message.content.lower().startswith("!help"):
        user_roles = {role.name for role in message.author.roles}
        is_mod_or_admin = {"Admin", "Mods"} & user_roles

        public_help = (
            "**🛠️  7 Days to Die Bot Commands (Public Access):**\n\n"
            "`!help` - Show this help message\n"
            "`!kills <PlayerName>` - Show kill stats for the specified player (case-insensitive)\n"
            "`!leaderboard` - Show kill leaderboard\n"
            "`!gg` / `!getgamepref` - Show current game preferences (DM)\n"
            "`!ggs` / `!getgamestat` - Show current game stats (DM)\n"
            "`!gt` / `!gettime` - Show in-game day/time\n"
        )

        mod_help = (
            "**🔐 Additional Mod/Admin Commands:**\n\n"
            "`!lpi` - List players currently online\n"
            "`!kick <entity_id> [reason]` - Kick a player by entity ID\n"
            "`!ban <target> <duration> <unit> [reason]` - Ban a player by name, ID, or Steam ID\n"
            "  • Example: `!ban 171 10 hours griefing`\n"
            "`!say <message>` - Broadcast a message to in-game chat\n"
        )

        full_help = (
            "📬 **Based on your role, you can use the following commands:**\n\n"
            f"{public_help}\n"
            f"{mod_help if is_mod_or_admin else ''}"
        )

        try:
            await message.author.send(full_help)
        except discord.Forbidden:
            await message.channel.send("❗ I couldn't DM you. Please check your privacy settings.")

        await delete_command_message(message)

    # Game Preference Command (DM)
    elif message.content.lower() in ("!gg", "!getgamepref"):
        output = send_telnet_and_get_output("getgamepref")
        if output:
            filtered = "\n".join(line for line in output.splitlines() if line.startswith("GamePref"))
            try:
                await send_long_dm(message.author, "🛠️ Game Preferences", filtered)
                await message.channel.send("📬 Game preferences sent to your DM.")
            except discord.Forbidden:
                await message.channel.send("⚠️ I couldn't DM you. Please check your privacy settings.")
        else:
            await message.channel.send("⚠️ No output received.")
        await delete_command_message(message)

    # Game Stat Command (DM)
    elif message.content.lower() in ("!ggs", "!getgamestat"):
        output = send_telnet_and_get_output("getgamestat")
        if output:
            filtered = "\n".join(line for line in output.splitlines() if line.startswith("GameStat"))
            try:
                await send_long_dm(message.author, "📊 Game Stats", filtered)
                await message.channel.send("📬 Game stats sent to your DM.")
            except discord.Forbidden:
                await message.channel.send("⚠️ I couldn't DM you. Please check your privacy settings.")
        else:
            await message.channel.send("⚠️ No output received.")
        await delete_command_message(message)

    # Game Time Command (In channel)
    elif message.content.lower() in ("!gt", "!gettime"):
        output = send_telnet_and_get_output("gettime")
        if output:
            # Grab only the first line that looks like "Day XX, HH:MM"
            for line in output.splitlines():
                if line.strip().startswith("Day "):
                    await message.channel.send(f"🕓 In-Game Time:\n```{line.strip()}```")
                    break
            else:
                await message.channel.send("⚠️ Could not find game time in output.")
        else:
            await message.channel.send("⚠️ No output received.")
        await delete_command_message(message)

client.run(DISCORD_TOKEN)
