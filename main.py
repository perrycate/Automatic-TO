#!/usr/bin/env python3
import discord
import os
import sys

TOKEN_ENV_VAR = 'DISCORD_BOT_TOKEN'


# Create bot instance.
bot = discord.Client()


@bot.event
async def on_ready():
    print('sup')


@bot.event
async def on_raw_reaction_add(payload):
    user = payload.member
    reaction = payload.emoji
    channel = bot.get_channel(payload.channel_id)
    await channel.send(f"{user} reacted with {reaction}")

# Check for auth token.
if TOKEN_ENV_VAR not in os.environ:
    sys.exit("{0} not found in system environment. Try running again with the prefix '{0}=<insert discord bot token here>'".format(
        TOKEN_ENV_VAR))
auth = os.environ[TOKEN_ENV_VAR]

# Log in and begin reading and responding to messages.
# Nothing else will run below this line.
bot.run(auth)
