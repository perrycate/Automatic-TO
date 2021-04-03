#!/usr/bin/env python3
import asyncio
import os
import sys
from typing import Tuple, List

import discord
from discord.ext import commands

import bracket
import bracket as challonge_bracket
import challonge

DISCORD_TOKEN_VAR = 'DISCORD_BOT_TOKEN'
CHALLONGE_TOKEN_VAR = 'CHALLONGE_TOKEN'
PREFIX = '!'
CHALLONGE_POLLING_INTERVAL_IN_SECS = 10
BACKUP_FILE = 'in_progress_tournaments.txt'


def _save_state(tourney_id, channel_id):
    with open(BACKUP_FILE, 'a') as ids:
        ids.write(f'{tourney_id} {channel_id}\n')


def _reload_state() -> List[Tuple[str, int]]:
    """
    Reload any tournaments that were in progress.
    Returns a list of (tourney_id, announce_channel_id)
    """
    tournaments_and_channels = []
    with open(BACKUP_FILE, 'r') as ids:
        for line in ids.readlines():
            tourney_id, announce_channel_id = line.split()
            tournaments_and_channels.append((tourney_id, int(announce_channel_id)))
    return tournaments_and_channels


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
                f"Unable to find message {argument}. "
                "(Remember to hold shift when clicking 'Copy ID' to get the FULL ID. "
                "It should have a dash in the middle.)"
            )


class Bot(commands.Cog):
    def __init__(self, bot: commands.Bot, challonge_token: str):
        self._bot = bot
        self._challonge_token = challonge_token

    @commands.Cog.listener()
    async def on_ready(self):
        for tourney_id, announce_channel_id in _reload_state():
            resumed_bracket = bracket.resume(self._challonge_token, tourney_id)
            announce_channel = await self._bot.fetch_channel(announce_channel_id)
            asyncio.create_task(self._monitor_matches(announce_channel, resumed_bracket))
        print('sup')

    @commands.command(name='set-challonge-username')
    async def set_challonge_username(self, ctx, username: str):
        pass  # TODO after refactor.

    @commands.command()
    async def begin(self, ctx, reg_msg: WrappedMessage, tourney_name="Tournament"):
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

        _save_state(bracket.tourney_id, ctx.channel.id)

        asyncio.create_task(self._monitor_matches(ctx, bracket))

    @staticmethod
    async def _announce_match(channel: discord.abc.Messageable, match: challonge.Match, bracket):
        # TODO tomorrow go back to passing players in for now, see if that fixes test.
        # Finish refactor, then remove extraneous param.
        players_by_challonge_id = {p.challonge_id: p for p in bracket.players}

        # Don't call matches more than once.
        if bracket.was_called(match.id):
            return

        p1_discord_id = players_by_challonge_id[match.p1_id].discord_id
        p2_discord_id = players_by_challonge_id[match.p2_id].discord_id

        await channel.send(
            f"<@!{p1_discord_id}> <@!{p2_discord_id}> your match has been called!")

        bracket.mark_called(match.id)

    async def _monitor_matches(self, ctx, bracket):
        """
        Poll for match updates indefinitely.

        If a match is "called" notify the players in discord.
        """

        while True:
            for match_info in bracket.fetch_open_matches():
                await self._announce_match(ctx, match_info, bracket)
            await asyncio.sleep(CHALLONGE_POLLING_INTERVAL_IN_SECS)


if __name__ == '__main__':

    # Make sure our backup file exists
    if not os.path.exists(BACKUP_FILE):
        print(
            f"WARNING: tournament id backup file '{BACKUP_FILE}' does not exist. Creating."
        )
        open(BACKUP_FILE, 'w').close()

    # Check for auth token.
    if DISCORD_TOKEN_VAR not in os.environ:
        sys.exit(
            "{0} not found in system environment. "
            "Try running again with the prefix '{0}=<insert discord bot token here>'".format(
                DISCORD_TOKEN_VAR))
    discord_auth = os.environ[DISCORD_TOKEN_VAR]
    if CHALLONGE_TOKEN_VAR not in os.environ:
        sys.exit(
            "{0} not found in system environment. "
            "Try running again with the prefix '{0}=<insert discord bot token here>'".format(
                CHALLONGE_TOKEN_VAR))
    challonge_auth = os.environ[CHALLONGE_TOKEN_VAR]

    # Create bot instance.
    bot = commands.Bot(command_prefix=PREFIX)
    bot.run(discord_auth)


def _sanity_check():
    # discord_auth, challonge_auth
    pass
