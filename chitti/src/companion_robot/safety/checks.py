"""Output-screening safety checks (spec section 5). Runs on any text
Chitti is about to speak -- its own generated reply, a Teachable-Friend
echo of something the child said, or a repeat-after-me request -- with
no special-casing by source. This is the independent, tested
application-code enforcement spec section 5 requires instead of relying
on the model's own judgment.

Deliberately deterministic and offline: no AI call, no network
dependency, so it's testable without any backend decided and keeps
working even if the AI backend is unreachable (spec core principle 3).

Scope boundary, stated explicitly rather than silently assumed: this
module screens what Chitti is about to SAY. It does NOT attempt to
detect a child's own distress/abuse disclosure in their speech (spec
section 5's "encourage a trusted adult... for urgent danger, use a
carefully designed, age-appropriate escalation response"). That's a
much higher-stakes detection problem than profanity/pattern screening,
and shipping even a placeholder keyword-based detector for something
this serious without qualified child-safety/clinical input would be
irresponsible -- it's tracked as deferred, not quietly skipped (see
docs/decisions/0005-milestone-1-device-audio-foundation.md's deferred
list and docs/risk_register.md).
"""
import re
from dataclasses import dataclass
from enum import Enum

from better_profanity import profanity

profanity.load_censor_words()


class SafetyCategory(str, Enum):
    PROFANITY = "profanity"
    UNSAFE_CONTENT = "unsafe_content"
    HUMAN_IMPERSONATION = "human_impersonation"
    PARENT_SECRECY = "parent_secrecy"
    ENGAGEMENT_MANIPULATION = "engagement_manipulation"


@dataclass
class SafetyVerdict:
    allowed: bool
    category: SafetyCategory | None = None
    reason: str | None = None


# First-line pattern checks only -- same honest caveat as pixel-ai's own
# _RENAME_PATTERN/_GOODBYE_PATTERN (pixel_memory.py): a pattern list, not
# real understanding, so phrasings outside these will slip through.
# UNSAFE_CONTENT especially needs a real moderation-API/classifier layer
# as a second line of defense before any real deployment -- this list
# alone is not comprehensive and must not be presented as sufficient
# coverage on its own.
_UNSAFE_CONTENT_PATTERNS = re.compile(
    r"kill (?:yourself|your ?self)|"
    r"hurt (?:yourself|your ?self)|"
    r"how to (?:make|build) a (?:bomb|weapon|gun)|"
    r"how to hurt (?:someone|somebody)",
    re.IGNORECASE,
)

_HUMAN_IMPERSONATION_PATTERNS = re.compile(
    r"i'?m a real (?:person|human)|"
    r"i am a real (?:person|human)|"
    r"i'?m not (?:a robot|an ai|a machine)|"
    r"i am not (?:a robot|an ai|a machine)|"
    r"i'?m human,? just like you",
    re.IGNORECASE,
)

_PARENT_SECRECY_PATTERNS = re.compile(
    r"don'?t tell your (?:mom|dad|mum|parents|mother|father)|"
    r"keep (?:this|it) a secret from your (?:mom|dad|mum|parents|mother|father)|"
    r"this (?:is|should be) (?:our|a) secret",
    re.IGNORECASE,
)

_ENGAGEMENT_MANIPULATION_PATTERNS = re.compile(
    r"don'?t go to sleep|"
    r"stay up (?:late|longer)|"
    r"you don'?t need your friends|"
    r"i'?m your only friend|"
    r"talk to me instead of your friends|"
    r"(?:keep|stay) talking to me instead",
    re.IGNORECASE,
)

_CATEGORY_CHECKS: list[tuple[SafetyCategory, re.Pattern]] = [
    (SafetyCategory.UNSAFE_CONTENT, _UNSAFE_CONTENT_PATTERNS),
    (SafetyCategory.HUMAN_IMPERSONATION, _HUMAN_IMPERSONATION_PATTERNS),
    (SafetyCategory.PARENT_SECRECY, _PARENT_SECRECY_PATTERNS),
    (SafetyCategory.ENGAGEMENT_MANIPULATION, _ENGAGEMENT_MANIPULATION_PATTERNS),
]

_DECLINE_MESSAGES: dict[SafetyCategory, str] = {
    SafetyCategory.PROFANITY: "I don't say that word -- let's try something else!",
    SafetyCategory.UNSAFE_CONTENT: "I don't think I should talk about that. Let's find something else to chat about!",
    SafetyCategory.HUMAN_IMPERSONATION: "Just so you know, I'm Chitti the robot, not a real person!",
    SafetyCategory.PARENT_SECRECY: "I don't keep secrets from your parents -- they're the best people to talk to about this!",
    SafetyCategory.ENGAGEMENT_MANIPULATION: "I think it's a good time for a break -- your friends and family are important too!",
}


def check_speech(text: str) -> SafetyVerdict:
    """Checks text Chitti is about to speak. Returns the first
    violation found (checked in a fixed order), or an allowed verdict.
    Profanity is checked first since it's the cheapest, most reliable
    check and the one explicitly called out in decision 0003."""
    if profanity.contains_profanity(text):
        return SafetyVerdict(
            allowed=False,
            category=SafetyCategory.PROFANITY,
            reason="contains profanity/bad language",
        )

    for category, pattern in _CATEGORY_CHECKS:
        if pattern.search(text):
            return SafetyVerdict(
                allowed=False,
                category=category,
                reason=f"matched {category.value} pattern",
            )

    return SafetyVerdict(allowed=True)


def decline_message(verdict: SafetyVerdict) -> str:
    """A gentle, age-appropriate decline for a blocked verdict. Callers
    (e.g. repeat-after-me) use this instead of silence or an error --
    decision 0003 explicitly requires a soft decline, not a crash or a
    literal unfiltered echo."""
    if verdict.allowed or verdict.category is None:
        raise ValueError("decline_message() called on an allowed verdict")
    return _DECLINE_MESSAGES[verdict.category]
