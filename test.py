#!/usr/bin/env python3
import asyncio
import os
import os.path
import pathlib
import shutil
import time
import unittest
import unittest.mock
import uuid
from datetime import datetime

import discord

import challonge
import data
import main
import persistent
import util
from bracket import Bracket

TEST_RUN_ID = uuid.uuid1()
persistent.STATE_BACKUP_DIR = BACKUP_DIR = f'/tmp/{TEST_RUN_ID}'
main.BACKUP_FILE = BACKUP_FILE = f'/tmp/{TEST_RUN_ID}-main-file'


class MyTest(unittest.TestCase):
    """
    Contains setup and teardown to ensure that backup files don't mix state
    between tests.
    """

    def setUp(self):
        super().setUp()

        # Nuke and recreate backups
        if os.path.exists(BACKUP_DIR):
            shutil.rmtree(BACKUP_DIR)
        if os.path.exists(BACKUP_FILE):
            os.remove(BACKUP_FILE)

        pathlib.Path(persistent.STATE_BACKUP_DIR).mkdir()
        # No need to recreate the backup file, it will be created automatically
        # when it is opened.


class TestAnnounceMatch(MyTest):

    def test_add_players_to_bracket(self):
        p1_name, p2_name = "Alice", "Bob"
        p1_challonge_id, p2_challonge_id = "1001", "1002"  # Challonge IDs
        p1_discord_id, p2_discord_id = 1, 2  # Discord IDs

        # Fake challonge call, will succeed
        mock_challonge = unittest.mock.MagicMock(spec=challonge.Client)
        mock_challonge.add_players = unittest.mock.MagicMock(return_value={
            p1_name: p1_challonge_id,
            p2_name: p2_challonge_id,
        })

        state = persistent.State("arbitraryID12")
        bracket = Bracket(mock_challonge, state)

        # Create the players.
        bracket.create_players({
            p1_discord_id: p1_name,
            p2_discord_id: p2_name,
        })

        self.assertEqual(2, len(bracket.players))
        self.assertEqual(p1_discord_id, bracket.players[0].discord_id)
        self.assertEqual(p1_challonge_id, bracket.players[0].challonge_id)
        self.assertEqual(p2_discord_id, bracket.players[1].discord_id)
        self.assertEqual(p2_challonge_id, bracket.players[1].challonge_id)

    def test_pings_uncalled_players_exactly_once(self):
        p1_name, p2_name = "Alice", "Bob"  # Discord names.
        p1_discord_id, p2_discord_id = 1, 2  # Discord IDs.
        p1_challonge_id, p2_challonge_id = "1001", "1002"  # Challonge IDs.

        # Set "challonge" up to add Alice and Bob.
        mock_challonge = unittest.mock.MagicMock(spec=challonge.Client)
        mock_challonge.add_players = unittest.mock.MagicMock(return_value={
            p1_name: p1_challonge_id,
            p2_name: p2_challonge_id,
        })

        # Set "challonge" up to have 1 in progress match.
        match = challonge.Match("arbitrary_match_id", p1_challonge_id, p2_challonge_id)
        mock_challonge.list_matches = unittest.mock.MagicMock(return_value=[match])

        # Not mocked, we're testing real logic here.
        state = persistent.State("arbitraryID12")
        bracket = Bracket(mock_challonge, state)

        # Mock out external dependencies.
        mock_discord_client = unittest.mock.MagicMock(spec=discord.ext.commands.Bot)
        output_channel = unittest.mock.MagicMock(spec=discord.TextChannel)
        output_channel.send.return_value.id = 1234

        # Add players to the bracket.
        bracket.create_players({
            p1_discord_id: p1_name,
            p2_discord_id: p2_name,
        })

        bot = main.Tournament(mock_discord_client, bracket, 4206969, output_channel)
        _wait_for(bot.check_matches())

        # Players should have been pinged, as there is 1 in-progress match that hasn't been called.
        output_channel.send.assert_called_once()
        self.assertIn(f"<@!{p1_discord_id}>", output_channel.send.call_args[0][0])
        self.assertIn(f"<@!{p2_discord_id}>", output_channel.send.call_args[0][0])

        # Check again. Because we already pinged the players once, they should not have been called again.
        output_channel.send.reset_mock()
        _wait_for(bot.check_matches())
        output_channel.send.assert_not_called()

    def test_warn_before_DQ_p1(self):
        """
        Scenario in which player one does not check into their match.

        Asserts:
        1. Player 1 is warned at the appropriate time.
        2. Player 1 is DQ'd at the appropriate time.
        3. No further messages are sent.
        """
        warn_timer_in_secs = 1
        dq_timer_in_secs = 2
        emoji = "😀"

        # 2 Players, Alice and Bob.
        p1_name, p2_name = "Alice", "Bob"  # Discord names.
        p1_discord_id, p2_discord_id = 1, 2  # Discord IDs.
        p1_challonge_id, p2_challonge_id = "1001", "1002"  # Challonge IDs.
        tourney_id = "tourneyID12"

        # Set "challonge" up to add Alice and Bob.
        mock_challonge = unittest.mock.MagicMock(spec=challonge.Client)
        mock_challonge.add_players = unittest.mock.MagicMock(return_value={
            p1_name: p1_challonge_id,
            p2_name: p2_challonge_id,
        })

        # Set "challonge" up to have 1 in progress match (Alice vs Bob).
        match_id = "arbitrary_match_id"
        match = challonge.Match(match_id, p1_challonge_id, p2_challonge_id)
        mock_challonge.list_matches = unittest.mock.MagicMock(return_value=[match])

        # Not mocked, we're testing real logic here.
        state = persistent.State(tourney_id)
        bracket = Bracket(mock_challonge, state)

        # Mock out external dependencies.
        mock_discord_client = unittest.mock.MagicMock(spec=discord.ext.commands.Bot)
        output_channel = unittest.mock.MagicMock(spec=discord.TextChannel)

        # Add players to the bracket.
        bracket.create_players({
            p1_discord_id: p1_name,
            p2_discord_id: p2_name,
        })

        bot = main.Tournament(mock_discord_client, bracket, 4206969, output_channel,
                              options=main.Options(
                                  warn_timer_in_minutes=warn_timer_in_secs / 60,
                                  dq_timer_in_minutes=dq_timer_in_secs / 60,
                                  check_in_emoji=discord.PartialEmoji(name=emoji)
                              ))

        # Call the match. Set the ID to be returned from the sent message, so we can reference it later.
        match_call_message = unittest.mock.MagicMock(spec=discord.Message)
        match_call_message.id = 6942096
        output_channel.send.return_value = match_call_message
        _wait_for(bot.check_matches())
        output_channel.send.assert_called_once()
        self.assertIn(f"<@!{p1_discord_id}>", output_channel.send.call_args[0][0])
        self.assertIn(f"<@!{p2_discord_id}>", output_channel.send.call_args[0][0])

        # Check p2 in, but not p1
        match_call_message.reactions = [_reaction(emoji)]
        util.get_user_ids = lambda _: _future({p2_discord_id})
        output_channel.fetch_message.return_value = match_call_message

        # 1. p1 (and only p1!) should be warned.
        output_channel.send.reset_mock()
        time.sleep(warn_timer_in_secs)
        _wait_for(bot.check_matches())
        output_channel.fetch_message.assert_called_with(match_call_message.id)
        output_channel.send.assert_called_once()
        self.assertNotIn(f"<@!{p2_discord_id}>", output_channel.send.call_args[0][0])
        self.assertIn(f"<@!{p1_discord_id}>", output_channel.send.call_args[0][0])

        # Nobody should have been DQ'd yet.
        mock_challonge.set_score.assert_not_called()

        # Wait until player should be DQ'd.
        time.sleep(dq_timer_in_secs - warn_timer_in_secs + 1)
        output_channel.send.reset_mock()
        _wait_for(bot.check_matches())

        # 2. Assert p1 (and only p1!) was DQ'd.
        output_channel.send.assert_called_once()
        self.assertNotIn(f"<@!{p2_discord_id}>", output_channel.send.call_args[0][0])
        self.assertIn(f"<@!{p1_discord_id}>", output_channel.send.call_args[0][0])
        mock_challonge.set_score.assert_called_with(tourney_id, match_id, -1, 0, p2_challonge_id)

        # Let's assume that set_score failed, and so the match is still
        # returned by challonge.list_matches.
        # 3. Make sure we don't message the players again.
        output_channel.send.reset_mock()
        _wait_for(bot.check_matches())
        output_channel.send.assert_not_called()

    def test_warn_before_DQ_p2(self):
        """
        Scenario in which player two does not check in for their match.

        Asserts:
        1. p2 is warned at the appropriate time.
        2. p2 is DQ'd at the appropriate time.
        3. No further messages are sent.
        """
        warn_timer_in_secs = 1
        dq_timer_in_secs = 2
        emoji = "😀"

        # 2 Players, Alice and Bob.
        p1_name, p2_name = "Alice", "Bob"  # Discord names.
        p1_discord_id, p2_discord_id = 1, 2  # Discord IDs.
        p1_challonge_id, p2_challonge_id = "1001", "1002"  # Challonge IDs.
        tourney_id = "tourneyID12"

        # Set "challonge" up to add Alice and Bob.
        mock_challonge = unittest.mock.MagicMock(spec=challonge.Client)
        mock_challonge.add_players = unittest.mock.MagicMock(return_value={
            p1_name: p1_challonge_id,
            p2_name: p2_challonge_id,
        })

        # Set "challonge" up to have 1 in progress match (Alice vs Bob).
        match_id = "arbitrary_match_id"
        match = challonge.Match(match_id, p1_challonge_id, p2_challonge_id)
        mock_challonge.list_matches = unittest.mock.MagicMock(return_value=[match])

        # Not mocked, we're testing real logic here.
        state = persistent.State(tourney_id)
        bracket = Bracket(mock_challonge, state)

        # Mock out external dependencies.
        mock_discord_client = unittest.mock.MagicMock(spec=discord.ext.commands.Bot)
        output_channel = unittest.mock.MagicMock(spec=discord.TextChannel)

        # Add players to the bracket.
        bracket.create_players({
            p1_discord_id: p1_name,
            p2_discord_id: p2_name,
        })

        bot = main.Tournament(mock_discord_client, bracket, 4206969, output_channel,
                              options=main.Options(
                                  warn_timer_in_minutes=warn_timer_in_secs / 60,
                                  dq_timer_in_minutes=dq_timer_in_secs / 60,
                                  check_in_emoji=discord.PartialEmoji(name=emoji)
                              ))

        # Call the match. Set the ID to be returned from the sent message, so we can reference it later.
        match_call_message = unittest.mock.MagicMock(spec=discord.Message)
        match_call_message.id = 6942096
        output_channel.send.return_value = match_call_message
        _wait_for(bot.check_matches())
        output_channel.send.assert_called_once()
        self.assertIn(f"<@!{p1_discord_id}>", output_channel.send.call_args[0][0])
        self.assertIn(f"<@!{p2_discord_id}>", output_channel.send.call_args[0][0])

        # Check p1 in, but not p2.
        match_call_message.reactions = [_reaction(emoji)]
        util.get_user_ids = lambda _: _future({p1_discord_id})
        output_channel.fetch_message.return_value = match_call_message

        # p2 (and only p2!) should be warned.
        output_channel.send.reset_mock()
        time.sleep(warn_timer_in_secs)
        _wait_for(bot.check_matches())
        output_channel.fetch_message.assert_called_with(match_call_message.id)
        output_channel.send.assert_called_once()
        self.assertNotIn(f"<@!{p1_discord_id}>", output_channel.send.call_args[0][0])
        self.assertIn(f"<@!{p2_discord_id}>", output_channel.send.call_args[0][0])

        # Nobody should have been DQ'd yet.
        output_channel.send.reset_mock()
        _wait_for(bot.check_matches())
        output_channel.send.assert_not_called()
        mock_challonge.set_score.assert_not_called()

        # Wait until player should be DQ'd.
        time.sleep(dq_timer_in_secs - warn_timer_in_secs + 1)
        output_channel.send.reset_mock()
        _wait_for(bot.check_matches())

        # Assert p2 (and only p2!) was DQ'd.
        output_channel.send.assert_called_once()
        self.assertNotIn(f"<@!{p1_discord_id}>", output_channel.send.call_args[0][0])
        self.assertIn(f"<@!{p2_discord_id}>", output_channel.send.call_args[0][0])
        mock_challonge.set_score.assert_called_with(tourney_id, match_id, 0, -1, p1_challonge_id)

        # Let's assume that set_score failed, and so the match is still
        # returned by challonge.list_matches. Make sure we don't message the
        # players again.
        output_channel.send.reset_mock()
        _wait_for(bot.check_matches())
        output_channel.send.assert_not_called()

    def test_dq_both_players(self):
        """
        Scenario in which neither player checks into their match.

        Asserts:
        1. Both players are warned.
        2. A score is set after the DQ interval.
        3. No further messages are sent after that.
        """
        warn_timer_in_secs = 1
        dq_timer_in_secs = 2
        emoji = "😀"

        # 2 Players, Alice and Bob.
        p1_name, p2_name = "Alice", "Bob"  # Discord names.
        p1_discord_id, p2_discord_id = 1, 2  # Discord IDs.
        p1_challonge_id, p2_challonge_id = "1001", "1002"  # Challonge IDs.
        tourney_id = "tourneyID12"

        # Set "challonge" up to add Alice and Bob.
        mock_challonge = unittest.mock.MagicMock(spec=challonge.Client)
        mock_challonge.add_players = unittest.mock.MagicMock(return_value={
            p1_name: p1_challonge_id,
            p2_name: p2_challonge_id,
        })

        # Set "challonge" up to have 1 in progress match (Alice vs Bob).
        match_id = "arbitrary_match_id"
        match = challonge.Match(match_id, p1_challonge_id, p2_challonge_id)
        mock_challonge.list_matches = unittest.mock.MagicMock(return_value=[match])

        # Not mocked, we're testing real logic here.
        state = persistent.State(tourney_id)
        bracket = Bracket(mock_challonge, state)

        # Mock out external dependencies.
        mock_discord_client = unittest.mock.MagicMock(spec=discord.ext.commands.Bot)
        output_channel = unittest.mock.MagicMock(spec=discord.TextChannel)

        # Add players to the bracket.
        bracket.create_players({
            p1_discord_id: p1_name,
            p2_discord_id: p2_name,
        })

        bot = main.Tournament(mock_discord_client, bracket, 4206969, output_channel,
                              options=main.Options(
                                  warn_timer_in_minutes=warn_timer_in_secs / 60,
                                  dq_timer_in_minutes=dq_timer_in_secs / 60,
                                  check_in_emoji=discord.PartialEmoji(name=emoji)
                              ))

        # Call the match. Set the ID to be returned from the sent message, so we can reference it later.
        match_call_message = unittest.mock.MagicMock(spec=discord.Message)
        match_call_message.id = 6942096
        output_channel.send.return_value = match_call_message
        _wait_for(bot.check_matches())
        output_channel.send.assert_called_once()
        self.assertIn(f"<@!{p1_discord_id}>", output_channel.send.call_args[0][0])
        self.assertIn(f"<@!{p2_discord_id}>", output_channel.send.call_args[0][0])

        # Neither player checks in.
        match_call_message.reactions = [_reaction(emoji)]
        util.get_user_ids = lambda _: _future({})
        output_channel.fetch_message.return_value = match_call_message

        # 1. Both players should be warned.
        output_channel.send.reset_mock()
        time.sleep(warn_timer_in_secs)
        _wait_for(bot.check_matches())
        output_channel.fetch_message.assert_called_with(match_call_message.id)
        self.assertGreaterEqual(output_channel.send.call_count, 2)
        self.assertIn(f"<@!{p1_discord_id}>", output_channel.send.call_args_list[0][0][0])
        self.assertIn(f"<@!{p2_discord_id}>", output_channel.send.call_args_list[1][0][0])

        # Nobody should have been DQ'd yet.
        mock_challonge.set_score.assert_not_called()

        # Wait until DQ deadline, nobody checks in still.
        time.sleep(dq_timer_in_secs - warn_timer_in_secs + 1)
        output_channel.send.reset_mock()
        _wait_for(bot.check_matches())

        # 2. Make sure a score was set for the match so it doesn't hold up the bracket.
        output_channel.send.assert_called_once()
        mock_challonge.set_score.assert_called()

        # Let's assume that set_score failed, and so the match is still
        # returned by challonge.list_matches.
        # 3. Make sure we don't message the players again.
        output_channel.send.reset_mock()
        _wait_for(bot.check_matches())
        output_channel.send.assert_not_called()


class TestReloadsState(MyTest):
    def test_resumes_main_state(self):
        main._save_state("some_tournament_id", 1234)

        # Pretend the bot crashed.
        recovered = main._reload_state()

        self.assertEqual(1, len(recovered))
        tourney_id, channel_id = recovered[0]
        self.assertEqual("some_tournament_id", tourney_id)
        self.assertEqual(1234, channel_id)

    def test_resumes_called_matches(self):
        tourney_id = "some-tourney-id"
        match_id = "some-match-id"

        # State with 1 match called.
        m = data.new_match(
            data.new_player(0, "arbitrary-id1"),
            data.new_player(1, "arbitrary-id2"),
            match_id)
        m.call_time = datetime.now()
        s = persistent.State(tourney_id)
        s.set_matches([m])

        # pretend we crashed

        new_s = persistent.State(tourney_id)  # Same tourney ID as before.
        self.assertEqual(1, len(new_s.known_matches))
        self.assertIsNotNone(new_s.known_matches[0].call_time)

    def test_resumes_players(self):
        s = persistent.State("arbitrary-tourney-id")
        p = data.Player(123, "challonge_id", 1)
        s.add_players([p])

        # pretend we crashed, this is the "reloaded" one.
        new_s = persistent.State("arbitrary-tourney-id")

        self.assertEqual(1, len(new_s.players))
        self.assertEqual(p, new_s.players[0])


def _reaction(emoji_unicode: str) -> discord.Reaction:
    mock_reaction = unittest.mock.MagicMock(spec=discord.Reaction)
    mock_reaction.emoji = emoji_unicode
    return mock_reaction


def _wait_for(func):
    l = asyncio.get_event_loop()
    l.run_until_complete(func)


def _future(value):
    f = asyncio.Future()
    f.set_result(value)
    return f


if __name__ == '__main__':
    unittest.main()
