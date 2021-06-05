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
    p2: Player

    call_message_id: Optional[int]
    call_time: Optional[datetime]
    warn_time: Optional[datetime]
    dq_time: Optional[datetime]

    challonge_id: str
    key_id: uuid.UUID


def new_match(p1: Player, p2: Player, external_id: str):
    return Match(
        p1=p1,
        p2=p2,
        challonge_id=external_id,
        call_message_id=None,
        call_time=None,
        warn_time=None,
        dq_time=None,
        key_id=uuid.uuid4(),
    )
