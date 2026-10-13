"""Versioned memory record schema (spec section 6). No storage or
business logic -- this module defines the shape only. A SQLite-backed
repository implementing create/review/update/delete arrives in
Milestone 3, per docs/decisions/0001-milestone-0-scope.md.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MemoryCategory(str, Enum):
    """The five categories spec section 6 defines. Conversation context
    is listed here for completeness but must never actually be
    persisted as a durable MemoryRecord -- it's session-only by
    definition (see docs/privacy_data_map.md)."""

    CONVERSATION_CONTEXT = "conversation_context"
    PERSONAL_PREFERENCE = "personal_preference"
    REMINDER = "reminder"
    LEARNING_STATE = "learning_state"
    DAILY_SUMMARY = "daily_summary"


class MemorySource(str, Enum):
    """Who/what created this record. Spec section 6 requires memory
    creation to be explicitly approved -- SYSTEM_INFERRED exists for
    completeness but any repository implementation must gate it behind
    the same explicit-approval requirement as the others, not treat it
    as a quieter default path."""

    CHILD = "child"
    PARENT = "parent"
    SYSTEM_INFERRED = "system_inferred"


class ConsentStatus(str, Enum):
    """Whether the required consent/authorization for this specific
    record is in place. Deliberately not a bool -- PENDING exists so a
    record can exist (e.g. awaiting parent confirmation) without being
    treated as authorized yet."""

    GRANTED = "granted"
    PENDING = "pending"
    REVOKED = "revoked"


@dataclass
class MemoryRecord:
    """One versioned, schema'd memory record (spec section 6).

    schema_version lets a future migration distinguish old-shaped rows
    from new ones -- start at 1 and bump on any field change once a
    real repository exists.
    """

    id: str
    category: MemoryCategory
    content: str
    created_at: datetime
    updated_at: datetime
    source: MemorySource
    consent_or_authorization_status: ConsentStatus
    retention_policy: str
    schema_version: int = 1
    expires_at: datetime | None = None
