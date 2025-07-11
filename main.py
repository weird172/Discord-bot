import os
import discord
from discord.ext import commands
from datetime import datetime, timezone
import asyncio

# === CONFIGURATION ===
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1229684302107774976
CHECK_INTERVAL_SECONDS = 600  # 10 minutes
MAX_AGE_MINUTES = 30
TARGET_CHANNEL_ID = 1229984677583126549
EMOJI = "<a:tick_mark:1391782025983426571>"

# === GAME STATE ===
target_text = None
counting_channel_id = None
revoke_task = None

# === BOT SETUP ===
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

client = commands.Bot(command_prefix="+", intents=intents)
tree = client.tree

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    print("✅ Slash commands synced.")

# === INVITE REVOKING LOGIC ===
async def invite_revoke_loop():
    await client.wait_until_ready()
    while True:
        await revoke_old_invites()
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

async def revoke_old_invites():
    try:
        guild = client.get_guild(GUILD_ID)
        if not guild:
            print("⚠️ Guild not found.")
            return

        invites = await guild.invites()
        now = datetime.now(timezone.utc)

        for invite in invites:
            if invite.created_at:
                age = (now - invite.created_at).total_seconds() / 60
                if age >= MAX_AGE_MINUTES:
                    try:
                        await invite.delete()
                        print(f"❌ Deleted invite {invite.code} (Age: {int(age)} mins)")
                    except Exception as e:
                        print(f"⚠️ Could not delete invite {invite.code}: {e}")
    except Exception as e:
        print(f"⚠️ Invite check failed: {e}")

# === START / STOP REVOKE SLASH ===
@tree.command(name="startrevoke", description="Start auto-invite revoking", guild=discord.Object(id=GUILD_ID))
async def startrevoke(interaction: discord.Interaction):
    global revoke_task
    if revoke_task and not revoke_task.done():
        await interaction.response.send_message("🚫 Invite revoking is already running.", ephemeral=True)
        return
    revoke_task = asyncio.create_task(invite_revoke_loop())
    await interaction.response.send_message("✅ Invite revoking started!", ephemeral=True)

@tree.command(name="stoprevoke", description="Stop auto-invite revoking", guild=discord.Object(id=GUILD_ID))
async def stoprevoke(interaction: discord.Interaction):
    global revoke_task
    if revoke_task and not revoke_task.done():
        revoke_task.cancel()
        await interaction.response.send_message("🛑 Invite revoking stopped.", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ No revoking task running.", ephemeral=True)

# === REACTSYNC SLASH ===
@tree.command(name="reactsync", description="React to recent messages", guild=discord.Object(id=GUILD_ID))
@discord.app_commands.describe(amount="How many messages to react to (max 200)")
async def reactsync(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    if amount < 1 or amount > 200:
        await interaction.followup.send("❌ Must be between 1 and 200.")
        return

    channel = client.get_channel(TARGET_CHANNEL_ID)
    if not channel:
        await interaction.followup.send("❌ Channel not found.")
        return

    count = 0
    async for msg in channel.history(limit=amount):
        if not msg.author.bot:
            try:
                await msg.add_reaction(EMOJI)
                count += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"⚠️ Couldn't react to {msg.id}: {e}")
    await interaction.followup.send(f"✅ Reacted to {count} messages.")

# === UNLOCK CHANNEL SLASH ===
@tree.command(name="unlock", description="Unlock the current channel", guild=discord.Object(id=GUILD_ID))
async def unlock(interaction: discord.Interaction):
    channel = interaction.channel
    overwrite = channel.overwrites_for(channel.guild.default_role)
    overwrite.send_messages = True
    await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message("🔓 Channel unlocked.")

# === +SETTARGET COMMAND (word or number) ===
@client.command(name="settarget")
@commands.has_permissions(administrator=True)
async def settarget(ctx, target: str, channel: discord.TextChannel):
    global target_text, counting_channel_id
    target_text = target.lower()
    counting_channel_id = channel.id
    await ctx.send(f"🎯 Target set to `{target}` in {channel.mention}. First one to type it wins!")

# === LOCK CHANNEL FUNCTION ===
async def lock_channel(channel):
    overwrite = channel.overwrites_for(channel.guild.default_role)
    overwrite.send_messages = False
    await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)
    await channel.send("🔒  **Locking channel since we have a winner**")

# === ON MESSAGE EVENT ===
@client.event
async def on_message(message):
    global target_text, counting_channel_id

    if message.author.bot:
        return

    if target_text and message.channel.id == counting_channel_id:
        if message.content.strip().lower() == target_text:
            await message.channel.send(f"🎉 {message.author.mention} typed the correct answer `{target_text}` and won!")
            await asyncio.sleep(1)
            await lock_channel(message.channel)
            target_text = None
            counting_channel_id = None
            return

    if message.channel.id == TARGET_CHANNEL_ID:
        try:
            await message.add_reaction(EMOJI)
        except Exception as e:
            print(f"⚠️ Failed to react: {e}")

    await client.process_commands(message)

# === RUN BOT ===
client.run(TOKEN)
