"""Lullaby/MP3 library (decision 0041): parent-uploaded audio files
Chitti can play back, managed from the Parent Controls web UI.
Modeled on parent_controls/stories.py (same trust model -- risk
register #14 -- the parent is the authorizing adult, no content
moderation needed), but deliberately simpler: no stored filename. The
audio file's path on disk is always derived from the record's own id
(data/lullabies/{id}.mp3), never from parent-supplied input, so there
is nothing to sanitize.

schema.py: LullabyRecord.
repository.py: LullabyRepository -- same create/list_all/get/delete
shape as parent_controls/stories.py:StoryRepository.
"""
