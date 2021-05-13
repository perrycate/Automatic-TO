#!/usr/bin/env python3
import asyncio
import os
import os.path
import pathlib
import shutil
import unittest
import unittest.mock
import uuid
from datetime import datetime

import discord

import bracket
import challonge
import main
import tournament
from bracket import Bracket

TEST_RUN_ID = uuid.uuid1()
tournament.STATE_BACKUP_DIR = BACKUP_DIR = f'/tmp/{TEST_RUN_ID}'
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

        pathlib.Path(tournament.STATE_BACKUP_DIR).mkdir()
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

        state = tournament.State("arbitraryID12")
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
        p1_name, p2_name = "Alice", "Bob"                  # Discord names.
        p1_discord_id, p2_discord_id = 1, 2                # Discord IDs.
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
        state = tournament.State("arbitraryID12")
        bracket = Bracket(mock_challonge, state)

        # Mock out external dependencies.
        mock_discord_client = unittest.mock.MagicMock(spec=discord.ext.commands.Bot)
        output_channel = unittest.mock.MagicMock(spec=discord.TextChannel)

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
        m = tournament.new_match(
            tournament.new_player(0, "arbitrary-id1"),
            tournament.new_player(1, "arbitrary-id2"),
            match_id)
        m.call_time = datetime.now()
        s = tournament.State(tourney_id)
        s.set_matches([m])

        # pretend we crashed

        new_s = tournament.State(tourney_id)  # Same tourney ID as before.
        self.assertEqual(1, len(new_s.known_matches))
        self.assertIsNotNone(new_s.known_matches[0].call_time)

    def test_resumes_players(self):
        s = tournament.State("arbitrary-tourney-id")
        p = tournament.Player(123, "challonge_id", 1)
        s.add_players([p])

        # pretend we crashed, this is the "reloaded" one.
        new_s = tournament.State("arbitrary-tourney-id")

        self.assertEqual(1, len(new_s.players))
        self.assertEqual(p, new_s.players[0])


def _wait_for(func):
    l = asyncio.get_event_loop()
    l.run_until_complete(func)


def _new_bot() -> main.Tournament:
    mock_challonge_client = challonge.Client('arbitrary "token"')
    mock_bracket = bracket.Bracket(mock_challonge_client, tournament.State('arbitrary tourney ID'))
    return main.Tournament(mock_discord_client, mock_bracket, 4206969)


if __name__ == '__main__':
    unittest.main()
