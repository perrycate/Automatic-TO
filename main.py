#!/usr/bin/env python3
import asyncio
import os
import pickle
import sys
import time

import discord
from discord.ext import commands

import bracket as challonge_bracket
from tournament import State

DISCORD_TOKEN_VAR = 'DISCORD_BOT_TOKEN'
CHALLONGE_TOKEN_VAR = 'CHALLONGE_TOKEN'
PREFIX = '!'
CHALLONGE_POLLING_INTERVAL_IN_SECS = 10
BACKUP_FILE = 'in_progress_tournaments.txt'

# Check for auth token.
if DISCORD_TOKEN_VAR not in os.environ:
    sys.exit(
        "{0} not found in system environment. Try running again with the prefix '{0}=<insert discord bot token here>'"
        .format(DISCORD_TOKEN_VAR))
discord_auth = os.environ[DISCORD_TOKEN_VAR]
if CHALLONGE_TOKEN_VAR not in os.environ:
    sys.exit(
        "{0} not found in system environment. Try running again with the prefix '{0}=<insert discord bot token here>'"
        .format(CHALLONGE_TOKEN_VAR))
challonge_auth = os.environ[CHALLONGE_TOKEN_VAR]

# Create bot instance.
bot = commands.Bot(command_prefix=PREFIX)


def save_state(tourney_id, channel_id):
    with open(BACKUP_FILE, 'a') as ids:
        ids.write(f'{tourney_id} {channel_id}\n')


def reload_state():
    """Reload any tournaments that were in progress."""
    tournaments_and_channels = []
    with open(BACKUP_FILE, 'r') as ids:
        for line in ids.readlines():
            tourney_id, announce_channel_id = line.split()
            b = challonge_bracket.resume(challonge_auth, tourney_id)
            tournaments_and_channels.append((b, int(announce_channel_id)))
    return tournaments_and_channels


@bot.event
async def on_ready():
    for bracket, announce_channel_id in reload_state():
        announce_channel = await bot.fetch_channel(announce_channel_id)
        asyncio.create_task(monitor_matches(announce_channel, bracket))
    print('sup')


class WrappedMessage(discord.ext.commands.MessageConverter):
    """
    Behaves exactly the same as discord.py's MessageConverter,
    but sends back an error message if the message cannot be found.
    """
    async def convert(self, ctx, argument):
        try:
            return await super().convert(ctx, argument)
        except discord.ext.commands.MessageNotFound:
            await ctx.send(
                f"Unable to find message {argument}. (Remember to hold shift when clicking 'Copy ID' to get the FULL ID. It should have a dash in the middle.)"
            )


async def announce_match(channel: discord.abc.Messageable, match, bracket,
                         players_by_challonge_id):
    # Don't call matches more than once.
    mid = match['id']
    if bracket.was_called(mid):
        return

    p1_id = match['player1_id']
    p2_id = match['player2_id']

    p1_discord_id = players_by_challonge_id[p1_id].discord_id
    p2_discord_id = players_by_challonge_id[p2_id].discord_id

    await channel.send(
        f"<@!{p1_discord_id}> <@!{p2_discord_id}> your match has been called!")

    bracket.mark_called(mid)


async def monitor_matches(ctx, bracket):
    """
    Poll for match updates indefinitely.

    If a match is "called" notify the players in discord.
    """
    players_by_challonge_id = {p.challonge_id: p for p in bracket.players}

    while True:
        for match_info in bracket.fetch_open_matches():
            await announce_match(ctx, match_info, bracket,
                                 players_by_challonge_id)
        await asyncio.sleep(CHALLONGE_POLLING_INTERVAL_IN_SECS)


@bot.command()
async def begin(ctx, reg_msg: WrappedMessage, tourney_name="Tournament"):
    """
    Creates a bracket containing every member that reacted to the specified reg_msg.
    Responds with a link to the new bracket.

    Args:
        reg_msg: The message to check for reactions.
            If it is not in the same channel as the begin command was run in,
            it must be in the <channel ID>-<msg ID> format.
        tourney_name: The title of the tournament.
    """

    # Collect all the users who reacted to the registration message.
    names_by_discord_id = {}
    for r in reg_msg.reactions:
        async for u in r.users():
            names_by_discord_id[u.id] = f'{u.name}#{u.discriminator}'

    # Create a challonge bracket, and match challonge IDs to discord IDs.
    bracket, link = challonge_bracket.create(challonge_auth, tourney_name)
    bracket.create_players(names_by_discord_id)

    await ctx.send(f"Bracket has been created! View it here: {link}")

    save_state(bracket.tourney_id, ctx.channel.id)

    asyncio.create_task(monitor_matches(ctx, bracket))


if __name__ == '__main__':

    # Make sure our backup file exists
    if not os.path.exists(BACKUP_FILE):
        print(
            f"WARNING: tournament id backup file '{BACKUP_FILE}' does not exist. Creating."
        )
        open(BACKUP_FILE, 'w').close()

    bot.run(discord_auth)


def _sanity_check():
    # discord_auth, challonge_auth
    pass
