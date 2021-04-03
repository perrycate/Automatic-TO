#!/usr/bin/env python3
"""This is a thin wrapper for challonge's API."""

import uuid
import enum

from dataclasses import dataclass
from typing import Tuple, List, Dict

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
                                 data=payload)

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
        print(payload)
        print(tourney_id)
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

    def list_matches(self, tourney_id: str) -> List[Match]:

        matches = util.make_request(CHALLONGE_API,
                                    f'/tournaments/{tourney_id}/matches.json',
                                    params={
                                        'api_key': self._api_key,
                                        'state': "open"
                                    })

        # Strip out the useless envelope-ish object
        # (an abject with 1 property, "match", and that's it.)
        return [_to_match(m) for m in matches]


def _to_match(envelope):
    match_obj = envelope["match"]
    return Match(
        match_obj['id'],
        match_obj['player1_id'],
        match_obj['player2_id'],
    )

