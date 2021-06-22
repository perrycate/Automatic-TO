#!/usr/bin/env python3
import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Tuple, List, Set

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
            tournaments_and_channels.append((tourney_id, int(announce_channel_id)))
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
                "It should have a dash in the middle.)"
            )


@dataclass
class Options:
    # How many minutes after a match is called to wait before warning/DQing a player for no-showing.
    warn_timer_in_minutes: float = DEFAULT_WARN_TIMER_IN_MINS
    dq_timer_in_minutes: float = DEFAULT_DQ_TIMER_IN_MINS
    check_in_emoji: discord.PartialEmoji = DEFAULT_CHECK_IN_EMOJI


class Tournament(commands.Cog):
    def __init__(self, bot: commands.Bot, b: challonge_bracket.Bracket = None, announce_channel_id: int = None,
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
            asyncio.create_task(self._monitor_matches())
        print('sup')

    async def _configure_announce_channel(self, channel_id: int):
        self._announce_channel_id = channel_id
        self._announce_channel = await self._bot.fetch_channel(self._announce_channel_id)

    @commands.command(name=CREATE_COMMAND)
    async def create(self, ctx: commands.Context, reg_msg: WrappedMessage, tourney_name="Tournament"):
        """
        Creates a bracket with every member that reacted to the specified message.
        Responds with a link to the new bracket.

        Anyone can run this command if there isn't a tournament already in progress, so choose permissions wisely.
        The admin of the challonge bracket is the one specified when the bot is turned up.
        If you don't know what that means, it isn't you.

        Args:
            reg_msg: The message to check for reactions.
                If it is not in the same channel as the begin command was run in,
                it must be in the <channel ID>-<msg ID> format.
            tourney_name: The title of the tournament.
        """

        if self._bracket is not None:
            await ctx.send("A bracket has already been created, sorry!")
            return

        # Collect all the users who reacted to the registration message.
        names_by_discord_id = {}
        for r in reg_msg.reactions:
            async for u in r.users():
                names_by_discord_id[u.id] = _format_name(u)

        # Create a challonge bracket, and match challonge IDs to discord IDs.
        await self._configure_announce_channel(ctx.channel.id)
        self._bracket = challonge_bracket.create(challonge_auth, tourney_name, ctx.author.id)
        self._bracket.create_players(names_by_discord_id)
        self._players_by_discord_id = {p.discord_id: p for p in self._bracket.players}

        _save_state(self._bracket.tourney_id, self._announce_channel_id)
        asyncio.create_task(self._monitor_matches())

        # Ping the players letting them know the bracket was created.
        message = ""
        for player_id in self._players_by_discord_id.keys():
            message += f"<@!{player_id}> "
        message += f"\nBracket has been created! View it here: {self._bracket.link}" \
                   "\n\n If you have a challonge account, you can pair it using the command" \
                   f"\n`{self._bot.command_prefix}{PAIR_USERNAME_COMMAND} your-challonge-username`"

        await ctx.send(message)

    @commands.command(name=ADD_PLAYER_COMMAND)
    async def add_player(self, ctx: commands.Context, player: discord.Member):
        """
        Adds the given player to the ongoing tournament.

        Only the person who created the bracket can run this command.

        args:
            player: The player to add.
        """
        if not self._bracket.is_admin(ctx.author.id):
            await ctx.send("Sorry, you are not the person that created this tournament. "
                           "Ask them _nicely_ if they can still add people.")
            return
        self._bracket.create_players({player.id: _format_name(player)})
        await ctx.send("Player added successfully!")

    @commands.command(name=PAIR_USERNAME_COMMAND)
    async def set_challonge_username(self, ctx: commands.Context, username: str):
        """
        Pairs yourself with the given challonge username.

        This allows the specified challonge user to report scores for the player that ran this.
        After running this command, that user should get a notification in challonge to accept being added.
        Any player can run this command, as it only affects the caller.
        """
        if ctx.author.id not in self._players_by_discord_id.keys():
            await ctx.send("Unfortunately you are not in the tournament."
                           " Contact your TO and ask nicely, maybe they can fix it.")
            return
        self._bracket.update_username(self._players_by_discord_id[ctx.author.id], username)
        await ctx.send("Update Successful! Log into challonge, you should have received an invitation.")

    @commands.command(name=GET_BRACKET_COMMAND)
    async def get_bracket_link(self, ctx):
        """Returns a link to the current tournament."""
        if self._bracket is None:
            await ctx.send(f"Sorry, no bracket exists yet. Ask your TO to run the {CREATE_COMMAND} command!")
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
                # Tell players before updating state - in the event of a crash,
                # better they get pinged twice than someone gets DQ'd without being told about it.
                call_message = await self._announce_channel.send(
                    f"<@!{match.p1.discord_id}> <@!{match.p2.discord_id}> your match has been called!"
                    f" React with {self._check_in_emoji} in the next {self._dq_time_in_mins} minutes to check in!")

                match.call_message_id = call_message.id
                match.call_time = datetime.now()
                self._bracket.save_metadata(match)
                continue

            # Warn players that haven't checked in.
            if _minutes_in(datetime.now() - match.call_time) >= self._warn_time_in_mins and match.warn_time is None:

                checked_in_ids = await self._get_checkins(match.call_message_id)

                # Ping players that didn't check-in to this match.
                if match.p1.discord_id not in checked_in_ids:
                    await self._announce_channel.send(self._warn_msg(match.p1.discord_id))
                if match.p2.discord_id not in checked_in_ids:
                    await self._announce_channel.send(self._warn_msg(match.p2.discord_id))

                # Mark this match as warned, so we don't ping them again.
                match.warn_time = datetime.now()
                self._bracket.save_metadata(match)
                continue

            # DQ players if they took too long to check in.
            if _minutes_in((datetime.now() - match.call_time)) > self._dq_time_in_mins and match.dq_time is None:
                # Make sure that if something fails (for example, interacting
                # with challonge), we don't ping players multiple times.
                match.dq_time = datetime.now()
                self._bracket.save_metadata(match)

                checked_in_ids = await self._get_checkins(match.call_message_id)
                p1_checked_in = match.p1.discord_id in checked_in_ids
                p2_checked_in = match.p2.discord_id in checked_in_ids

                if p1_checked_in:
                    if not p2_checked_in:
                        # Only P2 gets DQ'd
                        self._bracket.save_score(match, 0, -1)
                        await self._announce_channel.send(self._dq_msg(match.p2.discord_id))
                else:
                    if p2_checked_in:
                        # Only P1 gets DQ'd
                        self._bracket.save_score(match, -1, 0)
                        await self._announce_channel.send(self._dq_msg(match.p1.discord_id))
                    else:
                        # If neither player checks in, only P2 gets DQ'd
                        # TODO tomorrow: save score isn't working.
                        # Also let's not ping them every 10 seconds if challonge has an issue.
                        self._bracket.save_score(match, -1, -2)
                        await self._announce_channel.send(f"Wow, neither player checked in. Unfortunately I can only DQ"
                                                          f" one of you, so I'm DQing <@!{match.p2.discord_id}>."
                                                          f" <@!{match.p1.discord_id}>, I'm watching you...")

    async def _get_checkins(self, mid: int) -> Set[int]:
        message = await self._announce_channel.fetch_message(mid)
        for r in message.reactions:
            # Assuming r.emoji is a built-in emoji.
            # TODO support custom emojis as well as built-in emojis.
            if r.emoji == self._check_in_emoji.name:
                return await util.get_user_ids(r)
        return set()

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

    # Resume the last interrupted tournament.
    # For now, assume we only have one tournament running at any given time.
    # Resume the last tournament.
    # TODO support multiple tournaments.
    in_progress_tournaments = _reload_state()
    if len(in_progress_tournaments) > 0:
        tourney_id, announce_channel_id = in_progress_tournaments[-1]
        in_progress_bracket = challonge_bracket.resume(challonge_auth, tourney_id)
        bot.add_cog(Tournament(bot, in_progress_bracket, announce_channel_id))
    else:
        bot.add_cog(Tournament(bot))

    # Connect to discord and start doing stuff.
    bot.run(discord_auth)


def _sanity_check():
    # discord_auth, challonge_auth
    pass
