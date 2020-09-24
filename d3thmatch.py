#!/usr/bin/env python3
import urllib.request
import json
import os
import time

from datetime import datetime, timezone, timedelta

CHALLONGE_API = 'https://api.challonge.com/v1'
KEY_ENV_VAR = 'API_KEY'
TOURNEY_ENV_VAR = 'TOURNAMENT_ID'

TIMEOUT_IN_MINS = 10
PDT = timezone(timedelta(hours=-7))
CHALLONGE_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'
CHECK_INTERVAL_IN_SECS = 60


class LateMatch:
    def __init__(self, p1ID, p2ID, late_by_mins):
        self.p1ID = p1ID
        self.p2ID = p2ID
        self.late_mins = late_by_mins


def main():
    key = os.environ[KEY_ENV_VAR]
    tourney_id = os.environ[TOURNEY_ENV_VAR]

    players = get_players_by_id(key, tourney_id)

    while True:
        late_players = find_late_matches(get_matches(key, tourney_id))

        for m in late_players:
            p1 = players[m.p1ID]
            p2 = players[m.p2ID]
            print(
                f"Match between {p1['display_name']} and {p2['display_name']} is running {m.late_mins} minutes late.")

        time.sleep(CHECK_INTERVAL_IN_SECS)


def find_late_matches(matches):
    # Sort matches by ID.
    match_by_id = {}
    for m in matches:
        match_by_id[m['id']] = m

    # Filter for open matches.
    open_matches = [m for m in matches if m['state'] == "open"]

    # Find late players.
    late = []
    for m in open_matches:
        last_updated = datetime.strptime(
            m['updated_at'], CHALLONGE_DATE_FORMAT)
        elapsed_mins = (datetime.now(PDT)-last_updated).seconds / 60

        if elapsed_mins > TIMEOUT_IN_MINS:
            late.append(
                LateMatch(m['player1_id'], m['player2_id'], round(elapsed_mins)))

    return late


def get_players_by_id(key, tourney_id):
    raw = make_request(
        CHALLONGE_API, f'/tournaments/{tourney_id}/participants.json', {'api_key': key})

    # Raw format is a list of dicts, all with one property "participant".
    # Convert into dict of players by ID.
    players = {}
    for p in raw:
        player = p["participant"]
        players[player["id"]] = player

    return players


def get_matches(key, tourney_id):
    raw = make_request(
        CHALLONGE_API, f'/tournaments/{tourney_id}/matches.json', {'api_key': key})

    # Raw format is a little weird - a list of dicts, where each dict has one property "match".
    # Convert into list of matches.
    matches = []
    for m in raw:
        matches.append(m["match"])

    return matches


def make_request(base_url, additional_url, params={}):
    """Fetches resource at URL, converts JSON response to object."""

    url = base_url + additional_url
    first_item = True
    for param, value in params.items():
        if first_item:
            url += f'?{param}={value}'
            continue

        url += f'&{param}={value}'

    response = urllib.request.urlopen(url)

    # Convert raw response to usable JSON object
    response_as_string = response.read().decode('utf-8')
    return json.loads(response_as_string)


if __name__ == '__main__':
    main()
