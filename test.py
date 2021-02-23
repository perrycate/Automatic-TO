#!/usr/bin/env python3
import unittest
import unittest.mock
import discord
import asyncio

import tournament
import main

from bracket import _Bracket  # TODO


class PingMatchesTest(unittest.TestCase):
    def _wait_for(self, func):
        l = asyncio.get_event_loop()
        l.run_until_complete(func)

    def test_pings_uncalled_players_exactly_once(self):
        p1_challonge_id, p2_challonge_id = "1001", "1002"  # Challonge IDs
        p1_discord_id, p2_discord_id = 1, 2  # Discord IDs

        state = tournament.State("arbitraryID123")
        bracket = _Bracket("arbitraryToken", state,
                           "https://www.youtube.com/watch?v=oHg5SJYRHA0")
        players = {
            p1_challonge_id: tournament.Player(p1_discord_id, p1_challonge_id),
            p2_challonge_id: tournament.Player(p2_discord_id, p2_challonge_id),
        }
        match = {
            'id': state.tournament_id,
            'player1_id': p1_challonge_id,
            'player2_id': p2_challonge_id,
            'state': "open",
        }
        context = unittest.mock.MagicMock(spec=discord.ext.commands.Context)

        # Ping the open match.
        self._wait_for(main.ping_open_match(context, match, bracket, players))

        # Players should have been pinged.
        context.send.assert_called_once()
        self.assertIn(f"<@!{p1_discord_id}>", context.send.call_args[0][0])
        self.assertIn(f"<@!{p2_discord_id}>", context.send.call_args[0][0])

        # Let's call this again. Because it's already been called once, the
        # players _should not_ be called.
        context.send.reset_mock()
        self._wait_for(main.ping_open_match(context, match, bracket, players))

        # No message should have been sent, since this match has been called
        # before.
        context.send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
