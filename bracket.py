#!/usr/bin/env python3
import sys
from typing import List, Dict

import challonge
import data
import persistent


def create(api_token: str, name: str, admin_id: int, tournament_type=challonge.TourneyType.DOUBLE_ELIM,
           is_unlisted=True):
    """
    Creates a new tournament in Challonge owned by the user with the given API key.

    name can only contain letters, numbers, and underscores.
    Returns a new Tournament object corresponding to the created tournament.
    """
    challonge_client = challonge.Client(api_token)

    tourney_id, url = challonge_client.create_tournament(name, tournament_type, is_unlisted)
    state = persistent.State(tourney_id, url)
    state.set_admin(admin_id)

    return Bracket(challonge_client, state)


def resume(api_token: str, tournament_id: str):
    client = challonge.Client(api_token)
    return Bracket(client, persistent.State(tournament_id))


# Represents a bracket in Challonge.
class Bracket:
    def __init__(self, client: challonge.Client, state: persistent.State):
        self._challonge_client = client
        self._local_state = state

    @property
    def tourney_id(self) -> str:
        return self._local_state.tournament_id

    @property
    def link(self) -> str:
        return self._local_state.bracket_link

    @property
    def players(self) -> List[data.Player]:
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
    def create_players(self, names_by_discord_id) -> List[data.Player]:
        challonge_ids_by_discord_name = self._challonge_client.add_players(self.tourney_id,
                                                                           names_by_discord_id.values())

        players = []
        for discord_id, name in names_by_discord_id.items():
            challonge_id = challonge_ids_by_discord_name[name]
            players.append(data.new_player(discord_id, challonge_id))

        self._local_state.add_players(players)
        return self.players

    def update_username(self, player: data.Player, name: str) -> bool:
        """
        Updates a player's username in challonge.
        Returns true iff the user was present in the tournament.

        Note that the "username" is not the display name - it is the actual
        username of the account, so they can update their own scores.
        """
        return self._challonge_client.update_username(self.tourney_id, player, name)

    def fetch_open_matches(self):
        # Fetch open matches
        open_match_data = self._challonge_client.list_matches(self.tourney_id)

        # Register any matches we don't already know about.
        known_matches_by_id = self._known_matches_by_challonge_id()
        players_by_challonge_id = {p.challonge_id: p for p in self._local_state.players}
        for m in open_match_data:
            if m.id not in known_matches_by_id:
                p1 = players_by_challonge_id[m.p1_id]
                p2 = players_by_challonge_id[m.p2_id]
                known_matches_by_id[m.id] = data.new_match(p1, p2, m.id)

        self._local_state.set_matches(known_matches_by_id.values())

        return [known_matches_by_id[m.id] for m in open_match_data]

    def save_metadata(self, match: data.Match):
        # Wasteful, but fine.
        matches = self._known_matches_by_challonge_id()
        matches[match.challonge_id] = match
        self._local_state.set_matches(matches.values())

    def save_score(self, match: data.Match, p1_score: int, p2_score: int):
        winner_id = match.p1.challonge_id if p1_score >= p2_score else match.p2.challonge_id
        self._challonge_client.set_score(self.tourney_id, match.challonge_id, p1_score, p2_score, winner_id)

    def is_admin(self, player_id: int) -> bool:
        return player_id == self._local_state.admin_id

    def _known_matches_by_challonge_id(self) -> Dict[str, data.Match]:
        """
        Gets known matches from persistent state and indexes by challonge ID.
        A bit wasteful not to save it once we have it, but this makes it less
        likely that we get out of sync with our persistent state.
        """
        return {m.challonge_id: m for m in self._local_state.known_matches}


def _sanity_check():
    # Create a new tournament, and add 2 dummy players to it.
    auth_token = sys.argv[1]

    b = create(auth_token, "NEWEST_test_tourney_pls_ignore")
    print(f"bracket id: {b.tourney_id}")
    players = b.create_players({53190: "Alice", 3519: "Bob"})
    print(players)

    # Update challonge username.
    players_by_discord_id = {p.discord_id: p for p in players}
    print(b.update_username(players_by_discord_id[53190], "graviddd"))


if __name__ == '__main__':
    _sanity_check()
