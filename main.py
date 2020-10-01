#!/usr/bin/env python3
import discord
import os
import sys

from tournament import Tournament

from discord.ext import commands


TOKEN_ENV_VAR = 'DISCORD_BOT_TOKEN'


# Create bot instance.
bot = commands.Bot(command_prefix='!')
tournaments_by_guild_id = {}


@bot.event
async def on_ready():
    print('sup')


@bot.command()
async def open(ctx, dest_channel, message="Registration is open! React to this message to register."):
    guild = ctx.message.channel.guild

    # To keep things simple, only allow one tournament per guild for now.
    if guild.id in tournaments_by_guild_id:
        # TODO give option of cancelling. Eventually allow many tournaments per 'cord.
        await ctx.message.channel.send("Sorry, a tournament is already being run from this discord.")
        return

    dest = ctx.message.channel
    for c in guild.channels:
        if c.name == dest_channel and isinstance(c, discord.TextChannel):
            dest = c
            break

    sent_msg = await dest.send(message)
    tournaments_by_guild_id[guild.id] = Tournament(
        guild.id, sent_msg.channel.id, sent_msg.id)

    await ctx.send("Registration message posted!")


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
