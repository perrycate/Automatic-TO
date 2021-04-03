#!/usr/bin/env python3
import asyncio
import os
import os.path
import pathlib
import shutil
import unittest
import unittest.mock
import uuid

import discord

import challonge
import main
import tournament
from bracket import _Bracket

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
        bracket = _Bracket(mock_challonge, state)

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
        p1_name, p2_name = "Alice", "Bob"
        p1_challonge_id, p2_challonge_id = "1001", "1002"  # Challonge IDs
        p1_discord_id, p2_discord_id = 1, 2  # Discord IDs

        # Mock response from challonge - Alice and Bob are created, yay!
        mock_challonge = unittest.mock.MagicMock(spec=challonge.Client)
        mock_challonge.add_players = unittest.mock.MagicMock(return_value={
            p1_name: p1_challonge_id,
            p2_name: p2_challonge_id,
        })

        state = tournament.State("arbitraryID12")
        bracket = _Bracket(mock_challonge, state)
        bracket.create_players({
            p1_discord_id: p1_name,
            p2_discord_id: p2_name,
        })
        match = challonge.Match(state.tournament_id, p1_challonge_id, p2_challonge_id)

        context = unittest.mock.MagicMock(spec=discord.ext.commands.Context)
        bot = _new_bot()

        # Ping the open match.
        _wait_for(bot._announce_match(context, match, bracket))

        # Players should have been pinged.
        context.send.assert_called_once()
        self.assertIn(f"<@!{p1_discord_id}>", context.send.call_args[0][0])
        self.assertIn(f"<@!{p2_discord_id}>", context.send.call_args[0][0])

        # Let's call this again. Because it's already been called once, the
        # players _should not_ be called.
        context.send.reset_mock()
        _wait_for(bot._announce_match(context, match, bracket))

        # No message should have been sent, since this match has been called
        # before.
        context.send.assert_not_called()


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
        s = tournament.State("arbitrary-tourney-id")
        s.mark_called("arbitrary-match")

        # pretend we crashed

        new_s = tournament.State("arbitrary-tourney-id")
        self.assertTrue(new_s.was_called("arbitrary-match"))

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


def _new_bot() -> main.Bot:
    mock_client = unittest.mock.MagicMock(spec=discord.ext.commands.Bot)
    return main.Bot(mock_client, "arbitrary challonge token")


if __name__ == '__main__':
    unittest.main()
