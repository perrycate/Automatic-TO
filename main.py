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

@bot.event
async def on_ready():
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
            await ctx.send(f"Unable to find message {argument}. (Remember to hold shift when clicking 'Copy ID' to get the FULL ID. It should have a dash in the middle.)")

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
    bracket = challonge_bracket.create(challonge_auth, tourney_name)
    bracket.add_players(names_by_discord_id.values())

    await ctx.send(f"Bracket has been created! View it here: {bracket.link}")


# Log in and begin reading and responding to messages.
# Nothing else will run below this line.
bot.run(discord_auth)


def _sanity_check():
    # discord_auth, challonge_auth
    pass
