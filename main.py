#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Set, Tuple

import discord
from discord.ext import commands

import bracket as challonge_bracket
import util

DISCORD_TOKEN_VAR = 'DISCORD_BOT_TOKEN'
CHALLONGE_TOKEN_VAR = 'CHALLONGE_TOKEN'

PREFIX = '!'
CHALLONGE_POLLING_INTERVAL_IN_SECS = 10
BACKUP_FILE = 'in_progress_tournaments.txt'
DEFAULT_WARN_TIMER_IN_MINS = 5
DEFAULT_DQ_TIMER_IN_MINS = 10
DEFAULT_CHECK_IN_EMOJI = discord.PartialEmoji(name="👍")

CREATE_COMMAND = 'create'
PAIR_USERNAME_COMMAND = 'pair-challonge-account'
ADD_PLAYER_COMMAND = 'add-player'
GET_BRACKET_COMMAND = 'bracket'


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
            tournaments_and_channels.append(
                (tourney_id, int(announce_channel_id)))
    return tournaments_and_channels


def _format_name(u: discord.Member) -> str:
    return f'{u.name}#{u.discriminator}'


def _minutes_in(td: timedelta) -> float:
    return td.seconds / 60


def _get_emoji_id(emoji: discord.PartialEmoji) -> str:
    """
    Returns a useable string ID for the given emoji object.

    This is necessary because discord emojis have different semantics if
    they are a built-in emoji vs a custom one. Custom ones have an ID, but
    the name can be easily changed and is thus unreliable. Standard emojis
    have a name that is stable (in theory), but their ID is None.
    """
    if emoji.id is None:
        return emoji.name
    return emoji.id


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
                "It should have a dash in the middle.)")


@dataclass
class Options:
    # How many minutes after a match is called to wait before warning/DQing a player for no-showing.
    warn_timer_in_minutes: float = DEFAULT_WARN_TIMER_IN_MINS
    dq_timer_in_minutes: float = DEFAULT_DQ_TIMER_IN_MINS
    check_in_emoji: discord.PartialEmoji = DEFAULT_CHECK_IN_EMOJI


class Tournament(commands.Cog):
    def __init__(self,
                 bot: commands.Bot,
                 b: challonge_bracket.Bracket = None,
                 announce_channel_id: int = None,
                 announce_channel_override: discord.abc.Messageable = None,
                 options: Options = Options()):  # override is for testing.
        self._bot = bot
        self._bracket = b
        self._announce_channel_id = announce_channel_id
        self._announce_channel = announce_channel_override
        self._check_in_emoji = options.check_in_emoji
        self._warn_time_in_mins = options.warn_timer_in_minutes
        self._dq_time_in_mins = options.dq_timer_in_minutes

        self._players_by_discord_id = None
        if b is not None:
            self._players_by_discord_id = {p.discord_id: p for p in b.players}

        self._bot.add_listener(self.on_ready, 'on_ready')

    async def on_ready(self):
        # Fetch announce channel, unless one was injected (probably for testing.)
        # If announce channel id isn't set, we clearly don't have a channel to
        # announce to yet, and that's ok.
        if self._announce_channel is None and self._announce_channel_id:
            await self._configure_announce_channel(self._announce_channel_id)

        # Monitor bracket for changes.
        if self._bracket is not None:
            logging.info(
                f'Resuming bracket with ID {self._bracket.tourney_id}: {self._bracket.link}'
            )
            asyncio.create_task(self._monitor_matches())

        logging.info('Logged in and ready')

    async def _configure_announce_channel(self, channel_id: int):
        self._announce_channel_id = channel_id
        self._announce_channel = await self._bot.fetch_channel(
            self._announce_channel_id)
        logging.info(
            f'Using channel {self._announce_channel_id} "{self._announce_channel.name}" in'
            f'"{self._announce_channel.guild.name}" to call matches and warn players of DQs.'
        )

    @commands.command(name=GET_BRACKET_COMMAND)
    async def get_bracket_link(self, ctx):
        """Returns a link to the current tournament."""
        logging.info(
            f'Got request for bracket from member {ctx.author.id} "{ctx.author.name}".'
        )
        if self._bracket is None:
            await ctx.send(
                f"Sorry, no bracket exists yet. Ask your TO to run the {CREATE_COMMAND} command!"
            )
        else:
            await ctx.send(self._bracket.link)

    @commands.command(name='link')
    async def get_bracket_link_alt_def(self, ctx):
        """
        Returns a link to the current tournament.

        This exists because the devs couldn't figure out whether !link or !bracket was better.
        """
        await self.get_bracket_link(ctx)

    async def check_matches(self):
        for match in self._bracket.fetch_open_matches():
            # Call any matches that haven't been called yet.
            if match.call_time is None:
                logging.info(
                    f'Noticed new match with challonge ID {match.challonge_id} '
                    f'between players {match.p1.discord_id} (P1) and {match.p2.discord_id} (P2).'
                )

                # Tell players before updating state - in the event of a crash,
                # better they get pinged twice than someone gets DQ'd without being told about it.
                call_message = await self._announce_channel.send(
                    f"<@!{match.p1.discord_id}> <@!{match.p2.discord_id}> your match has been called!"
                    f" React with {self._check_in_emoji} in the next {self._dq_time_in_mins} minutes to check in!"
                )

                match.call_message_id = call_message.id
                match.call_time = datetime.now()
                self._bracket.save_metadata(match)

                # Pre-react to the message with the check-in emoji to make it easier for the players.
                # We do this after updating the metadata in case it fails for some reason.
                await call_message.add_reaction(self._check_in_emoji)
                logging.info(
                    f'Match {match.challonge_id} has been called. Call message ID: {match.call_message_id}'
                )
                continue

    async def _monitor_matches(self):
        """
        Poll for match updates indefinitely.

        If a match is "called" notify the players in discord.
        """
        while True:
            await self.check_matches()
            await asyncio.sleep(CHALLONGE_POLLING_INTERVAL_IN_SECS)

    def _warn_msg(self, player_challonge_id: str) -> str:
        return f"<@!{player_challonge_id}> it has been at least {self._warn_time_in_mins} minutes since your match " \
               f"was called. Please check in in the next {self._dq_time_in_mins - self._warn_time_in_mins} minutes or " \
               f"be disqualified."

    def _dq_msg(self, player_challonge_id: str) -> str:
        return f"<@!{player_challonge_id}> it has been at least {self._dq_time_in_mins} minutes since your match " \
               f"was called. You have been disqualified from that match."


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s:%(levelname)s:%(module)s: %(message)s')

    # Make sure our backup file exists
    if not os.path.exists(BACKUP_FILE):
        logging.warning(
            f"Tournament id backup file '{BACKUP_FILE}' does not exist. Creating."
        )
        open(BACKUP_FILE, 'w').close()

    # Check for auth token.
    if DISCORD_TOKEN_VAR not in os.environ:
        sys.exit(
            "{0} not found in system environment. "
            "Try running again with the prefix '{0}=<insert discord bot token here>'"
            .format(DISCORD_TOKEN_VAR))
    discord_auth = os.environ[DISCORD_TOKEN_VAR]
    if CHALLONGE_TOKEN_VAR not in os.environ:
        sys.exit(
            "{0} not found in system environment. "
            "Try running again with the prefix '{0}=<insert discord bot token here>'"
            .format(CHALLONGE_TOKEN_VAR))
    challonge_auth = os.environ[CHALLONGE_TOKEN_VAR]

    # Create bot instance.
    bot = commands.Bot(command_prefix=PREFIX)

    # Resume the last interrupted tournament.
    # For now, assume we only have one tournament running at any given time.
    # Resume the last tournament.
    # TODO support multiple tournaments.
    in_progress_tournaments = _reload_state()
    if len(in_progress_tournaments) > 0:
        tourney_id, announce_channel_id = in_progress_tournaments[-1]
        in_progress_bracket = challonge_bracket.resume(challonge_auth,
                                                       tourney_id)
        bot.add_cog(Tournament(bot, in_progress_bracket, announce_channel_id))
    else:
        bot.add_cog(Tournament(bot))

    # Connect to discord and start doing stuff.
    bot.run(discord_auth)


def _sanity_check():
    # discord_auth, challonge_auth
    pass
