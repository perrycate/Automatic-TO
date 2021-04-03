#!/usr/bin/env python3
import sys
from typing import List

import tournament
import challonge


def create(api_token, name, tournament_type=challonge.TourneyType.DOUBLE_ELIM, is_unlisted=True):
    """
    Creates a new tournament in Challonge owned by the user with the given API key.

    name can only contain letters, numbers, and underscores.
    Returns a new Tournament object corresponding to the created tournament.
    """
    challonge_client = challonge.Client(api_token)

    tourney_id, url = challonge_client.create_tournament(name, tournament_type, is_unlisted)

    return _Bracket(challonge_client, tournament.State(tourney_id)), url


def resume(api_token: str, tournament_id: str):
    client = challonge.Client(api_token)
    return _Bracket(client, tournament.State(tournament_id))


# Represents a bracket in Challonge.
class _Bracket:
    def __init__(self, client: challonge.Client, state: tournament.State):
        self._challonge_client = client
        self._local_state = state

    @property
    def tourney_id(self):
        return self._local_state.tournament_id

    @property
    def players(self) -> List[tournament.Player]:
        # Note that we do not contact challonge to see if any players have been
        # added or removed manually. This is ok because:
        # * If players were added, we have no idea how to relate it to their
        #       discord ids yet anyway.
        # * If players were removed, they won't have any matches, so it doesn't
        #       really matter if we have a little extra data.
        return self._local_state.players

    # Adds the given players to the tournament bracket.
    # Returns a list of Player objects.
    # NOTE: discord names must be unique! (include the discriminator)
    def create_players(self, names_by_discord_id):
        challonge_ids_by_discord_name = self._challonge_client.add_players(self.tourney_id, names_by_discord_id.values())

        players = []
        for discord_id, name in names_by_discord_id.items():
            challonge_id = challonge_ids_by_discord_name[name]
            players.append(tournament.new_player(discord_id, challonge_id))

        self._local_state.add_players(players)
        return self.players

    def fetch_open_matches(self):
        return self._challonge_client.list_matches(self.tourney_id)

    def mark_called(self, mid):
        return self._local_state.mark_called(mid)

    def was_called(self, mid):
        return self._local_state.was_called(mid)


def _sanity_check():
    # Create a new tournament, and add 2 dummy players to it.
    auth_token = sys.argv[1]

    b, _ = create(auth_token, "NEWER_test_tourney_pls_ignore")
    print(f"bracket id: {b.tourney_id}")
    players = b.create_players({53190: "Alice", 3519: "Bob"})
    print(players)

    # Update challonge username.
    players_by_discord_id = {p.discord_id: p for p in players}
    print(b.update_username(players_by_discord_id[53190], "graviddd"))


if __name__ == '__main__':
    _sanity_check()
