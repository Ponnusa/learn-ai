"""Reminder Service (spec section 3.2.G, 8).

A trusted local scheduler, not the language model, triggers reminders --
the LLM must never be relied on to remember a future event or its
timing. Per decision 0002, alarms are not a separate service -- they're
a ReminderRecord with is_alarm=True (an alarm-style alert) rather than a
one-shot spoken notice.

schema.py: ReminderRecord, ReminderSource, Recurrence.
repository.py: ReminderRepository -- create/get/list/update/delete,
plus due_reminders()/mark_fired() for a scheduler loop. Recurring
reminders correctly handle DST transitions by re-interpreting the same
wall-clock time in the reminder's own timezone (see repository.py's
module docstring).

Not yet built: the actual scheduler loop that polls due_reminders() and
triggers playback (waits for real audio I/O -- Milestone 2 hardware),
and natural-language date/time parsing with ambiguity confirmation
(spec section 8) -- a conversation-level concern, not this repository's
job.
"""
