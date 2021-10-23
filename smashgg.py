#!/usr/bin/env python3
"""
Thin wrapper for smash.gg's API.

Roughly matches the challonge API wrapper, for the methods we actually want to use at least.
"""
import os
from dataclasses import dataclass

import util

# TODO figure out actual page limits. For now, 500 will do.
_EVENT_SETS_QUERY_STR = '''
query EventSets($eventId: ID!) {
  event(id: $eventId) {
    id
    name
    sets(
      sortType: STANDARD
      perPage: 500
    ) {
      pageInfo {
        total
      }
      nodes {
        id
        startedAt
        completedAt
        slots {
          id
          entrant {
            id
            name
          }
        }
      }
    }
  }
}'''


@dataclass
class Match:
    id: str
    p1_id: str
    p2_id: str


class Client:
    def __init__(self, api_key: str):
        self._api_key = api_key

    def list_matches(self, event_id: str):
        '''Returns a list of in-progress matches.'''
        result_data = util.make_request(
            'https://api.smash.gg/gql/alpha',
            '',
            method='POST',
            data={
                'query': _EVENT_SETS_QUERY_STR,
                'variables': {
                    "eventId": event_id
                }
            },
            headers={'Authorization': f'Bearer {self._api_key}'})

        open_matches = []
        for match_data in result_data['data']['event']['sets']['nodes']:
            # Only add open matches.
            if (not match_data['startedAt']) or match_data['completedAt']:
                continue

            new_match = Match(
                id=match_data['id'],
                p1_id=match_data['slots'][0]['entrant']['id'],
                p2_id=match_data['slots'][1]['entrant']['id'],
            )
            open_matches.append(new_match)

        return open_matches


# Sanity check.
if __name__ == '__main__':
    c = Client(os.getenv('SMASH_GG_TOKEN'))
    print(c.list_matches('635806'))
