"""Reminder Service (spec section 3.2.G, 8) -- Milestone 3.

A trusted local scheduler, not the language model, triggers reminders --
the LLM must never be relied on to remember a future event or its
timing. Per decision 0002, alarms are not a separate service -- they're
a reminder with an alarm-style alert (louder/sustained audio, voice
snooze/dismiss) rather than a one-shot spoken notice. Nothing
implemented yet.
"""
