#!/usr/bin/env python3
import util
import sys
import pprint
import uuid

from tournament import Player

CHALLONGE_API = 'https://api.challonge.com/v1'

SINGLE_ELIM = 'single elimination'
DOUBLE_ELIM = 'double elimination'
ROUND_ROBIN = 'round robin'
SWISS = 'swiss'


def create(api_token, name, tournament_type=DOUBLE_ELIM, is_unlisted=True):
    """
    Creates a new tournament in Challonge owned by the user with the given API key.

    name can only contain letters, numbers, and underscores.
    Returns a new Tournament object corresponding to the created tournament.
    """
    payload = {
        'tournament': {
            'name': f'{name}',
            # We add unique-ish gibberish to the end to make sure that the url is available.
            # The TO can always change the URL later.
            'url': f'{name}_{str(uuid.uuid1()).replace("-", "_")}',
            'tournament_type': tournament_type,
            'private': is_unlisted,
        }
    }
    resp = util.make_request(
        CHALLONGE_API, '/tournaments.json', params={'api_key': api_token}, data=payload)

    if 'tournament' not in resp:
        raise ValueError(
            "Bracket creation unsuccesful. Challonge returned the following error(s): \n * "
            + '\n * '.join(resp['errors']))

    return Bracket(api_token, resp['tournament']['id'], resp['tournament']['full_challonge_url'])


# Represents a bracket in Challonge.
class Bracket:
    def __init__(self, token, tourney_id, link):
        self.link = link

        self._challonge_token = token
        self._tourney_id = tourney_id
        self._players = []

    @property
    def tourney_id(self):
        return self._tourney_id

    @property
    def players(self):
        # Only return the names.
        # The caller needn't know that challonge IDs even exist.
        return self._players

    def _fetch_players_by_name(self):
        raw = util.make_request(
            CHALLONGE_API, f'/tournaments/{self._tourney_id}/participants.json', {'api_key': self._challonge_token})

        # Raw format is a list of dicts, all with one property "participant".
        # Convert into dict of players by name.
        return {p["participant"]["name"]: p["participant"]["id"] for p in raw}

    # Adds the given players to the tournament bracket.
    # Returns a list of Player objects.
    # NOTE: discord names must be unique! (include the discriminator)
    def create_players(self, names_by_discord_id):
        payload = {
            'participants': [{"name": n} for n in names_by_discord_id.values()],
        }
        util.make_request(
            CHALLONGE_API, f'/tournaments/{self._tourney_id}/participants/bulk_add.json',
            params={'api_key': self._challonge_token},
            data=payload,
            raise_exception_on_http_error=True)

        challonge_ids_by_discord_name = self._fetch_players_by_name()
        self._players = []
        for discord_id, name in names_by_discord_id.items():
            challonge_id = challonge_ids_by_discord_name[name]
            self._players.append(Player(discord_id, challonge_id))

    def fetch_open_matches(self, mid=None):
        if mid is None:
            mid = self._tourney_id

        matches = util.make_request(
            CHALLONGE_API, f'/tournaments/{mid}/matches.json',
            params={'api_key': self._challonge_token, 'state': "open"}
        )

        # Strip out the useless envelope-ish object
        # (an abject with 1 property, "match", and that's it.)
        return [m["match"] for m in matches]


def _sanity_check():
    # Create a new tournament, and add 2 dummy players to it.
    auth_token = sys.argv[1]

    b = create(auth_token, "test_tourney_pls_ignore")
    b.create_players({53190: "Alice", 3519: "Bob"})

    print(b.players)


if __name__ == '__main__':
    _sanity_check()
