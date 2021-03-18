#!/usr/bin/env python3
import pprint
import sys
import uuid

import tournament
import util

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
    resp = util.make_request(CHALLONGE_API,
                             '/tournaments.json',
                             params={'api_key': api_token},
                             data=payload)

    if 'tournament' not in resp:
        raise ValueError(
            "Bracket creation unsuccesful. Challonge returned the following error(s): \n * "
            + '\n * '.join(resp['errors']))

    return _Bracket(api_token, tournament.State(
        resp['tournament']['id'])), resp['tournament']['full_challonge_url']


def resume(api_token: str, tournament_id: str):
    return _Bracket(api_token, tournament.State(tournament_id))


# Represents a bracket in Challonge.
class _Bracket:
    def __init__(self, token: str, state: tournament.State):
        self._challonge_token = token
        self._local_state = state

    @property
    def tourney_id(self):
        return self._local_state.tournament_id

    @property
    def players(self):
        # Note that we do not contact challonge to see if any players have been
        # added or removed. This is ok because:
        # * If players were added, we have no idea how to relate it to their
        #       discord ids yet anyway.
        # * If players were removed, they won't have any matches, so it doesn't
        #       really matter if we have a little extra data.
        return self._local_state.players

    # Adds the given players to the tournament bracket.
    # Returns a list of Player objects.
    # NOTE: discord names must be unique! (include the discriminator)
    def create_players(self, names_by_discord_id):
        payload = {
            'participants': [{
                "name": n
            } for n in names_by_discord_id.values()],
        }
        resp = util.make_request(
            CHALLONGE_API,
            f'/tournaments/{self.tourney_id}/participants/bulk_add.json',
            params={'api_key': self._challonge_token},
            data=payload,
            raise_exception_on_http_error=True)

        # Response format is a list of dicts, all with one property "participant".
        # Convert into dict of players by name.
        challonge_ids_by_discord_name = {
            p["participant"]["name"]: p["participant"]["id"]
            for p in resp
        }

        players = []
        for discord_id, name in names_by_discord_id.items():
            challonge_id = challonge_ids_by_discord_name[name]
            players.append(tournament.new_player(discord_id, challonge_id))

        self._local_state.add_players(players)

    def fetch_open_matches(self, mid=None):
        if mid is None:
            mid = self.tourney_id

        matches = util.make_request(CHALLONGE_API,
                                    f'/tournaments/{mid}/matches.json',
                                    params={
                                        'api_key': self._challonge_token,
                                        'state': "open"
                                    })

        # Strip out the useless envelope-ish object
        # (an abject with 1 property, "match", and that's it.)
        return [m["match"] for m in matches]

    # These operations work on our "local state", that is, there is no
    # equivalent information to update/read from challonge. We still make it
    # a part of _Bracket because clients shouldn't have to care what state
    # exists where.

    def mark_called(self, mid):
        return self._local_state.mark_called(mid)

    def was_called(self, mid):
        return self._local_state.was_called(mid)


def _sanity_check():
    # Create a new tournament, and add 2 dummy players to it.
    auth_token = sys.argv[1]

    b, _ = create(auth_token, "test_tourney_pls_ignore")
    print(f"bracket id: {b.tourney_id}")
    b.create_players({53190: "Alice", 3519: "Bob"})

    # Make sure we resume and stuff.
    resumed = resume(auth_token, b.tourney_id)
    print(resumed.players)


if __name__ == '__main__':
    _sanity_check()
