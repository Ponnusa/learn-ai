"""TranscriptRecord schema (decision 0038) -- the full text of one
session, for parent transparency. Governed like a MemoryRecord
(consent, retention, expiry) without being one -- see this package's
__init__.py for why conversation content lives here and not in
memory/.
"""
from dataclasses import dataclass
from datetime import datetime

from companion_robot.engagement.schema import EngagementMode
from companion_robot.memory.schema import ConsentStatus


@dataclass
class TranscriptRecord:
    id: str
    child_profile_id: str
    mode: EngagementMode
    content: str
    created_at: datetime
    consent_or_authorization_status: ConsentStatus
    retention_policy: str
    expires_at: datetime | None = None
