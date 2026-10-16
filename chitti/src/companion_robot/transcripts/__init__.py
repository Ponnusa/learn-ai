"""Full conversation transcripts, for parent transparency (decision
0038).

This knowingly narrows decision 0007/docs/privacy_data_map.md's
blanket "conversation context is never persisted" statement -- see
decision 0038 for why (an explicit parent-transparency request) and
what's still open (no DPIA has been performed; no scheduled retention
enforcement). It does NOT reopen decision 0007 itself:
MemoryCategory.CONVERSATION_CONTEXT stays correctly walled off from
MemoryRepository. This is a deliberately separate, separately-
governed feature, modeled on MemoryRecord's consent/retention shape
rather than bypassing it.

schema.py: TranscriptRecord.
repository.py: TranscriptRepository -- create/list_for_child/delete/
purge_expired, same shape as memory/repository.py.
"""
