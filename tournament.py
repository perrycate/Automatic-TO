import os
import pickle
import uuid

from dataclasses import dataclass
from typing import List

STATE_BACKUP_DIR = 'tournament_backups/'


@dataclass
class Player:
    discord_id: int
    challonge_id: str
    key_id: uuid.UUID


def new_player(discord_id: int, challonge_id: str) -> Player:
    return Player(discord_id, challonge_id, uuid.uuid4())


_ADMIN = 'admin_id'
_MATCHES = 'called_match_ids'
_PLAYERS = 'players'


class State:
    """
    Manages state of a tournament being run.
    This class backs info up in a nonvolatile way.
    """

    def __init__(self, tournament_id: str):
        self._tournament_id = tournament_id
        self._called_matches = set()
        self._players = []
        self._admin_id = None
        # NOTE: Anytime you add a relevant piece of tournament state, you must
        # add it to _load_from and _save as well.
        # WARNING: Do not add state in the constructor. Make separate set_<thingy> methods.

        # Make sure our backup folder exists.
        if not os.path.exists(STATE_BACKUP_DIR):
            print(
                f"WARNING: backup directory '{STATE_BACKUP_DIR}' does not exist. Creating."
            )
            os.makedirs(STATE_BACKUP_DIR)

        # Will blow up if 2 bots are managing the same tournament.
        # Things would blow up if you had that happening anyway.
        self._save_file_name = f'{STATE_BACKUP_DIR}/{self.tournament_id}'

        # Read state if possible.
        if os.path.exists(self._save_file_name):
            with open(self._save_file_name, 'rb') as save_file:
                self._load_from(save_file)

    def _load_from(self, file):
        state = pickle.load(file)
        self._called_matches = state[_MATCHES]
        self._players = state[_PLAYERS]
        self._admin_id = state[_ADMIN]

    def _save(self):
        # If we crash before writing to the file we might lose state, but
        # the likelihood of that is fairly small (I hope), and the penalty
        # for that happening now is that (only the open matches) might get
        # pinged twice. So...whatever.
        with open(self._save_file_name, 'wb') as save_file:
            pickle.dump(
                {
                    _MATCHES: self._called_matches,
                    _PLAYERS: self._players,
                    _ADMIN: self._admin_id,
                }, save_file)
            save_file.flush()

    @property
    def tournament_id(self):
        return self._tournament_id

    @property
    def players(self):
        return self._players

    @property
    def admin_id(self):
        return self._admin_id

    def add_players(self, players: List[Player]):
        # We can only ever add players, because we just store the player data here.
        # Which players are actually playing (like if one gets removed or something)
        # is determined in bracket.py.
        self._players += players
        self._save()

    def set_admin(self, admin_id: int):
        self._admin_id = admin_id
        self._save()

    def mark_called(self, match_id):
        self._called_matches.add(match_id)
        self._save()

    def was_called(self, match_id):
        return match_id in self._called_matches
