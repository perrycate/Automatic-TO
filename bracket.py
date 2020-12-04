#!/usr/bin/env python3
import util
import sys
import pprint
import uuid

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

    return Bracket(api_token, resp['tournament']['id'])


# Represents a bracket in Challonge.
class Bracket:
    def __init__(self, token, tourney_id):
        self._challonge_token = token
        self._tourney_id = tourney_id
        self._players = self._fetch_players_by_id()

    def _fetch_players_by_id(self):
        raw = util.make_request(
            CHALLONGE_API, f'/tournaments/{self._tourney_id}/participants.json', {'api_key': self._challonge_token})

        # Raw format is a list of dicts, all with one property "participant".
        # Convert into dict of players by ID.
        return {p["participant"]["id"]: p["participant"]["name"] for p in raw}

    @property
    def players(self):
        return self._players

    def add_players(self, names):
        payload = {
            'participants': [{"name": n} for n in names],
        }
        util.make_request(
            CHALLONGE_API, f'/tournaments/{self._tourney_id}/participants/bulk_add.json',
            params={'api_key': self._challonge_token},
            data=payload,
            raise_exception_on_http_error=True)

        self._players = self._fetch_players_by_id()


def _sanity_check():
    # Create a new tournament, and add 2 dummy players to it.
    auth_token = sys.argv[1]

    b = create(auth_token, "test_tourney_pls_ignore")
    b.add_players(['alice', 'bob'])


if __name__ == '__main__':
    _sanity_check()
