import pickle

from os import path


STATE_BACKUP_DIR = '/tmp/'


class TourneyState:
    """
    Manages state of a tournament being run.
    This class backs info up in a nonvolatile way.
    """

    # TODO next:
    # Load this from file if present
    # see note in main.py

    def __init__(self, tournament_id: str):
        self._tournament_id = tournament_id
        self._called_matches = set()

        # Will blow up if 2 bots are managing the same tournament.
        # Things would blow up if you had that happening anyway.
        save_file_name = f'{STATE_BACKUP_DIR}{self.tournament_id}'

        # Read state if possible.
        if path.exists(save_file_name):
            save_file = open(save_file_name, 'r')
            self = pickle.load(save_file)
            return

        self._save_file = open(save_file_name, 'w')

    def tournament_id(self):
        return self._tournament_id

    def mark_called(self, match_id):
        self._called_matches.add(match_id)
        self._save()

    def was_called(self, match_id):
        return match_id in self._called_matches

    def _save(self):
        # TODO
        #pickle.dump(self, self._save_file)
        self._save_file.flush()
