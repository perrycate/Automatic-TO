#!/usr/bin/env python3
"""This is a thin wrapper for challonge's API."""
import enum
import sys
import uuid
from dataclasses import dataclass
from typing import Tuple, List, Dict

import data
import util

CHALLONGE_API = 'https://api.challonge.com/v1'


class TourneyType(enum.Enum):
    SINGLE_ELIM = 'single elimination'
    DOUBLE_ELIM = 'double elimination'
    ROUND_ROBIN = 'round robin'
    SWISS = 'swiss'


@dataclass
class Match:
    id: str
    p1_id: str
    p2_id: str


class Client:
    def __init__(self, api_key):
        self._api_key = api_key

    def create_tournament(self, name, tournament_type=TourneyType.DOUBLE_ELIM, is_unlisted=True) -> Tuple[str, str]:
        """
        Creates a tournament with the given name.
        Returns the tournament ID and url.
        """
        payload = {
            'tournament': {
                'name': f'{name}',
                # We add unique-ish gibberish to the end to make sure that the url is available.
                # The TO can always change the URL later.
                'url': f'{name}_{str(uuid.uuid1()).replace("-", "_")}',
                'tournament_type': tournament_type.value,
                'private': is_unlisted,
            }
        }
        resp = util.make_request(CHALLONGE_API,
                                 '/tournaments.json',
                                 params={'api_key': self._api_key},
                                 data=payload,
                                 raise_exception_on_http_error=False)

        if 'tournament' not in resp:
            raise ValueError(
                "Bracket creation unsuccessful. Challonge returned the following error(s): \n * "
                + '\n * '.join(resp['errors']))

        return resp['tournament']['id'], resp['tournament']['full_challonge_url']

    def add_players(self, tourney_id, names: List[str]) -> Dict[str, str]:
        """
        Adds the list of participant names to the tournament with the given tourney_id.
        Returns a map of the given names to their challonge participant IDs.
        """
        payload = {
            'participants': [{"name": n} for n in names],
        }
        resp = util.make_request(
            CHALLONGE_API,
            f'/tournaments/{tourney_id}/participants/bulk_add.json',
            params={'api_key': self._api_key},
            data=payload,
            raise_exception_on_http_error=True)

        # Response format is a list of dicts, all with one property "participant".
        # Convert into dict of players by name.
        return {
            p["participant"]["name"]: p["participant"]["id"]
            for p in resp
        }

    def update_username(self, tourney_id: str, player: data.Player, name: str):
        """
        Updates a player's username in challonge.
        Returns true iff the user was present in the tournament.

        Note that the "username" is not the display name - it is the actual
        username of the account, so they can update their own scores.
        """

        payload = {
            'participant': {
                'challonge_username': name,
            }
        }
        util.make_request(
            CHALLONGE_API,
            f'/tournaments/{tourney_id}/participants/{player.challonge_id}.json',
            params={'api_key': self._api_key},
            data=payload,
            raise_exception_on_http_error=True,
            method='PUT',
        )

    def list_matches(self, tourney_id: str) -> List[Match]:
        matches = util.make_request(CHALLONGE_API,
                                    f'/tournaments/{tourney_id}/matches.json',
                                    params={
                                        'api_key': self._api_key,
                                        'state': "open"
                                    },
                                    raise_exception_on_http_error=True)

        # Strip out the useless envelope-ish object
        # (an abject with 1 property, "match", and that's it.)
        return [_to_match(m) for m in matches]

    def set_score(self, tourney_id: str, match_id: str, p1_score: int, p2_score: int, winner_id: str):
        util.make_request(CHALLONGE_API,
                          f'/tournaments/{tourney_id}/matches/{match_id}.json',
                          params={'api_key': self._api_key},
                          data={
                              'match': {
                                  'scores_csv': f'{p1_score}-{p2_score}',
                                  'winner_id': winner_id,
                              }
                          },
                          method='PUT',
                          raise_exception_on_http_error=True)


def _to_match(envelope):
    match_obj = envelope["match"]
    return Match(
        match_obj['id'],
        match_obj['player1_id'],
        match_obj['player2_id'],
    )


def _sanity_check():
    # Create a new tournament, and add 2 dummy players to it.
    auth_token = sys.argv[1]

    c = Client(api_key=auth_token)
    tid, url = c.create_tournament("test_tourney_please_ignore")
    print(url)
    c.add_players(tid, ["Eve", "Mallory"])
    # Start tourney, then press enter in terminal.
    input()
    match = c.list_matches(tid)[0]

    c.set_score(tid, match.id, 69, 420, match.p2_id)


if __name__ == '__main__':
    _sanity_check()
