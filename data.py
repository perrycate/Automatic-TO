# data.py contains dataclasses and functions to instantiate them.
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Player:
    discord_id: int
    challonge_id: str
    key_id: uuid.UUID


def new_player(discord_id: int, challonge_id: str) -> Player:
    return Player(discord_id, challonge_id, uuid.uuid4())


@dataclass
class Match:
    p1: Player
    p1_checked_in: bool

    p2: Player
    p2_checked_in: bool

    challonge_id: str
    call_time: Optional[datetime]
    key_id: uuid.UUID


def new_match(p1: Player, p2: Player, external_id: str):
    return Match(
        p1=p1,
        p1_checked_in=False,
        p2=p2,
        p2_checked_in=False,
        challonge_id=external_id,
        call_time=None,
        key_id=uuid.uuid4(),
    )

