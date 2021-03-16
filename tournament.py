import pathlib
import pickle
import os
import uuid

from dataclasses import dataclass

STATE_BACKUP_DIR = 'tournament_backups/'


@dataclass
class Player:
    discord_id: int
    challonge_id: str
    key_id: uuid.UUID

def new_player(discord_id: int, challonge_id: str) -> Player:
    return Player(discord_id, challonge_id, uuid.uuid4())

class State:
    """
    Manages state of a tournament being run.
    This class backs info up in a nonvolatile way.
    """

    def __init__(self, tournament_id: str):
        self._tournament_id = tournament_id
        self._called_matches = set()
        self._players = []
        # NOTE: Anytime you add a relevant piece of tournament state, you must
        # add it to _load_from and _save as well.

        # Make sure our backup folder exists.
        if not os.path.exists(STATE_BACKUP_DIR):
            print(
                f"WARNING: backup directory '{STATE_BACKUP_DIR}' does not exist. Creating.")
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
        self._called_matches = state['called_match_ids']
        self._players = state['players']

    def _save(self):
        # If we crash before writing to the file we might lose state, but
        # the likelihood of that is fairly small (I hope), and the penalty
        # for that happening now is that (only the open matches) might get
        # pinged twice. So...whatever.
        with open(self._save_file_name, 'wb') as save_file:
            pickle.dump({
                'called_match_ids': self._called_matches,
                'players': self._players,
            }, save_file)
            save_file.flush()

    @property
    def tournament_id(self):
        return self._tournament_id

    @property
    def players(self):
        return self._players

    def add_players(self, players):
        # We can only ever add players, because we just store the player data here.
        # Which players are actually playing (like if one gets removed or something)
        # is determined in bracket.py.
        self._players += players
        self._save()

    def mark_called(self, match_id):
        self._called_matches.add(match_id)
        self._save()

    def was_called(self, match_id):
        return match_id in self._called_matches
