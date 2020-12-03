#!/usr/bin/env python3
import discord
import os
import sys

from discord.ext import commands

import bracket as challonge_bracket

from tournament import Tournament


DISCORD_TOKEN_VAR = 'DISCORD_BOT_TOKEN'
CHALLONGE_TOKEN_VAR = 'CHALLONGE_TOKEN'
PREFIX = '!'

# Check for auth token.
if DISCORD_TOKEN_VAR not in os.environ:
    sys.exit("{0} not found in system environment. Try running again with the prefix '{0}=<insert discord bot token here>'".format(
        DISCORD_TOKEN_VAR))
discord_auth = os.environ[DISCORD_TOKEN_VAR]
if CHALLONGE_TOKEN_VAR not in os.environ:
    sys.exit("{0} not found in system environment. Try running again with the prefix '{0}=<insert discord bot token here>'".format(
        CHALLONGE_TOKEN_VAR))
challonge_auth = os.environ[CHALLONGE_TOKEN_VAR]


# Create bot instance.
bot = commands.Bot(command_prefix=PREFIX)
tournaments_by_guild_id = {}


@bot.event
async def on_ready():
    print('sup')


@bot.command()
async def open(ctx, dest_channel=None, message="Registration is open! React to this message to register."):
    guild = ctx.message.channel.guild

    # To keep things simple, only allow one tournament per guild for now.
    if guild.id in tournaments_by_guild_id:
        # TODO give option of cancelling. Eventually allow many tournaments per 'cord.
        await ctx.message.channel.send("Sorry, a tournament is already being run from this discord.")
        return

    # If the destination channel is invalid, just send the message to the
    # channel the message was received from.
    dest = ctx.message.channel
    for c in guild.channels:
        if c.name == dest_channel and isinstance(c, discord.TextChannel):
            dest = c
            break

    sent_msg = await dest.send(message)
    tournaments_by_guild_id[guild.id] = Tournament(
        guild.id, sent_msg.channel.id, sent_msg.id)

    await ctx.send("Registration message posted!")


@bot.command()
async def begin(ctx, tourney_name="Tournament"):
    guild = ctx.message.channel.guild
    tournament = tournaments_by_guild_id.get(guild.id)
    if tournament is None:
        await ctx.send(f"No tournament to begin! Start a tournament with {PREFIX}open <channel> <message>")
        return

    # Collect all the users who reacted to the registration message.
    reg_message = await guild.get_channel(tournament.channel_id).fetch_message(tournament.registration_message_id)
    names_by_discord_id = {}
    for r in reg_message.reactions:
        async for u in r.users():
            names_by_discord_id[u.id] = f'{u.name}#{u.discriminator}'

    # Create a challonge bracket, and match challonge IDs to discord IDs.
    bracket = challonge_bracket.create(challonge_auth, tourney_name)
    bracket.add_players(names_by_discord_id.values())

    await ctx.send(f"Bracket has been created! View it here: {bracket.link}")

# Log in and begin reading and responding to messages.
# Nothing else will run below this line.
bot.run(discord_auth)


def _sanity_check():
    # discord_auth, challonge_auth
    pass
