"""LullabyRecord schema (decision 0041). See this package's
__init__.py for why there is no stored filename -- the audio file's
path on disk is always derived from id, never from parent input.
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class LullabyRecord:
    id: str
    title: str
    created_at: datetime
