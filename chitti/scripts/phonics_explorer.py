#!/usr/bin/env python
"""Standalone phonics-sound explorer -- type a word, see it split into
its real graphemes on screen (with its phoneme symbol underneath each
one, e.g. "/s/" under "s"), and hear each one's real recorded sound in
order, with the grapheme currently playing highlighted. Two passes
per word: slow and segmented first (each grapheme named: "c... a...
t..."), then a quicker blended pass with hyphens between the letters
("c-a-t") so the word visibly comes together, the way phonics
instruction actually teaches segment-then-blend.

Not part of the companion_robot app or voice loop at all -- this is a
throwaway tool for manually checking phonics audio sounds and looks
right, standing on its own two feet with a minimal pygame window and
pygame.mixer for audio. No mic, no STT, no LLM, no chitti.db.

Decision pending (NOT yet wired into companion_robot/reading/phonics_audio.py
-- this script is exactly where to try it first, per instruction):
tries a second, separate, user-licensed phonics audio pack
(_PACK_DIR below) alongside Chitti's existing recorded clips
(reading/phonics_audio.py's own get_clip_bytes()), to see whether it
fills a few of that module's own DEFERRED_GRAPHEMES gaps ("x", "qu",
"aw", "u_e") before committing anything into the real package. For
each grapheme: tries the new pack first (by its own exact filename --
no guessed cross-grapheme reuse, e.g. never silently plays "aw" for
"au"), falls back to Chitti's existing clip if the pack doesn't have
it, and says which source it actually used (or that there's no clip
at all) right on screen, so a gap is visible, not silently skipped.

Run from the chitti/ directory (needs companion_robot importable):
    uv run python scripts/phonics_explorer.py

Type a word at the prompt and press Enter. Ctrl-C or "quit" to exit.
"""
import io
import time
from pathlib import Path

import pygame

from companion_robot.reading.decodability import decompose
from companion_robot.reading.phonics_audio import DEFERRED_GRAPHEMES, get_clip_bytes
from companion_robot.reading.word_timing import pcm_to_wav_bytes

# User-confirmed-licensed second pack, tried here (never inside the
# real companion_robot package) before any decision to adopt it.
_PACK_DIR = Path(r"C:\Users\sarav\Downloads\44-sounds-audio-pack\phonemes")

_WIDTH, _HEIGHT = 900, 340
_BG = (20, 20, 30)
_IDLE_COLOR = (230, 230, 230)
_HIGHLIGHT_COLOR = (255, 80, 80)
_SEPARATOR_COLOR = (110, 110, 120)
_IPA_COLOR = (120, 180, 230)
_NOTE_COLOR = (150, 150, 160)
_FONT_SIZE = 72
_IPA_FONT_SIZE = 28
_NOTE_FONT_SIZE = 20
_GAP = 24
_SLOW_PAUSE_SECONDS = 0.4  # breathing room between graphemes, segmented pass
_BLEND_PAUSE_SECONDS = 0.08  # quick, so the word visibly blends together
_DEFERRED_NOTE_SECONDS = 1.0

# Approximate IPA for every grapheme decompose() can produce (see
# reading/decodability.py's own CONSONANTS/DIGRAPHS/R_CONTROLLED/
# VOWEL_TEAMS/GLUED_SOUNDS sets, plus the dynamic a_e/e_e/i_e/o_e/u_e
# silent-e spans) -- for display only, a teaching approximation, not
# a linguistics reference. A couple of these (y, th, oo, ow) are
# genuinely ambiguous in English spelling itself -- shown as the
# single most common reading; "" for anything not listed, so a gap
# here never crashes the display.
_IPA: dict[str, str] = {
    "a": "æ", "e": "ɛ", "i": "ɪ", "o": "ɒ", "u": "ʌ",
    "b": "b", "c": "k", "d": "d", "f": "f", "g": "g", "h": "h",
    "j": "dʒ", "k": "k", "l": "l", "m": "m", "n": "n", "p": "p",
    "q": "k", "r": "r", "s": "s", "t": "t", "v": "v", "w": "w",
    "x": "ks", "y": "j", "z": "z",
    "sh": "ʃ", "ch": "tʃ", "th": "θ", "wh": "w", "ck": "k",
    "ng": "ŋ", "ph": "f", "qu": "kw",
    "ar": "ɑr", "er": "ər", "ir": "ər", "or": "ɔr", "ur": "ər",
    "igh": "aɪ", "ai": "eɪ", "ay": "eɪ", "ee": "iː", "ea": "iː",
    "oa": "oʊ", "oe": "oʊ", "ie": "aɪ", "oo": "uː", "ou": "aʊ",
    "ow": "aʊ", "oi": "ɔɪ", "oy": "ɔɪ", "au": "ɔː", "aw": "ɔː",
    "a_e": "eɪ", "e_e": "iː", "i_e": "aɪ", "o_e": "oʊ", "u_e": "juː",
    "all": "ɔl", "ang": "æŋ", "ing": "ɪŋ", "ong": "ɒŋ", "ung": "ʌŋ",
    "ank": "æŋk", "ink": "ɪŋk", "onk": "ɒŋk", "unk": "ʌŋk",
}


def _ipa_label(grapheme: str) -> str:
    symbol = _IPA.get(grapheme, "")
    return f"/{symbol}/" if symbol else ""


def _pack_clip_path(grapheme: str) -> Path | None:
    """The new pack's own filename for `grapheme`, if it has one --
    only an exact name match (accounting for the pack's own "-"
    where Chitti's silent-e graphemes use "_", e.g. "u_e" -> "u-e.mp3")
    -- never a guessed same-sound-different-spelling substitute
    (e.g. this does NOT hand back "aw.mp3" for "au just because they
    sound alike -- that's a real phonics judgment call to make
    explicitly later, not something to decide silently in a test
    script)."""
    candidate = _PACK_DIR / f"{grapheme.replace('_', '-')}.mp3"
    return candidate if candidate.exists() else None


def _load_sound(grapheme: str) -> tuple["pygame.mixer.Sound | None", str]:
    """Returns (sound, source_label) -- tries the new pack first, then
    Chitti's existing recorded clip, then gives up. `source_label` is
    shown on screen so it's always visible which source (if any)
    actually produced this sound, while testing."""
    pack_path = _pack_clip_path(grapheme)
    if pack_path is not None:
        return pygame.mixer.Sound(str(pack_path)), "new pack"
    clip = get_clip_bytes(grapheme)
    if clip is not None:
        return pygame.mixer.Sound(io.BytesIO(pcm_to_wav_bytes(clip))), "chitti"
    return None, "none"


def _pump_events() -> bool:
    """Keeps the window responsive during waits. Returns False if the
    window was closed (Ctrl-C from the console still works regardless,
    via the KeyboardInterrupt that propagates out of time.sleep())."""
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
    return True


def _wait(seconds: float) -> bool:
    """time.sleep(), but pumping window events every tick so the
    window doesn't look frozen/unresponsive while a clip plays."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not _pump_events():
            return False
        pygame.time.wait(16)
    return True


def _draw(
    screen, font, ipa_font, note_font, graphemes: list[str], highlight_index: int | None,
    note: str, separator: str = "",
) -> None:
    screen.fill(_BG)
    sep_width = font.size(separator)[0] if separator else 0
    widths = [font.size(g)[0] for g in graphemes]
    total_width = sum(widths) + (sep_width + _GAP) * (len(graphemes) - 1)
    x = (_WIDTH - total_width) // 2
    y = _HEIGHT // 2 - _FONT_SIZE // 2
    ipa_y = y + _FONT_SIZE + 6
    for i, grapheme in enumerate(graphemes):
        color = _HIGHLIGHT_COLOR if i == highlight_index else _IDLE_COLOR
        rendered = font.render(grapheme, True, color)
        screen.blit(rendered, (x, y))
        label = _ipa_label(grapheme)
        if label:
            ipa_rendered = ipa_font.render(label, True, _IPA_COLOR if i == highlight_index else _NOTE_COLOR)
            ipa_rect = ipa_rendered.get_rect(centerx=x + widths[i] // 2, y=ipa_y)
            screen.blit(ipa_rendered, ipa_rect)
        x += widths[i]
        if i < len(graphemes) - 1:
            if separator:
                sep_rendered = font.render(separator, True, _SEPARATOR_COLOR)
                screen.blit(sep_rendered, (x + _GAP // 2, y))
            x += sep_width + _GAP
    if note:
        note_rendered = note_font.render(note, True, _NOTE_COLOR)
        note_rect = note_rendered.get_rect(center=(_WIDTH // 2, _HEIGHT - 30))
        screen.blit(note_rendered, note_rect)
    pygame.display.flip()


def _play_pass(
    screen, font, ipa_font, note_font, graphemes: list[str], grapheme_hits, pause_seconds: float,
    separator: str,
) -> bool:
    """One full pass over every grapheme: highlight it, play its
    sound (new pack if it has this grapheme, else Chitti's existing
    clip, else a visible note that neither has one), pause, move on.
    `pause_seconds` and `separator` are what tell the slow segmented
    pass and the quick blended pass apart -- same mechanics otherwise."""
    _draw(screen, font, ipa_font, note_font, graphemes, None, "", separator)
    if not _wait(pause_seconds):
        return False

    for i, grapheme_hit in enumerate(grapheme_hits):
        grapheme = grapheme_hit.grapheme
        sound, source = _load_sound(grapheme)
        if sound is None:
            reason = DEFERRED_GRAPHEMES.get(grapheme, "no clip for this one yet")
            _draw(
                screen, font, ipa_font, note_font, graphemes, i,
                f'no real clip for "{grapheme}" -- {reason}', separator,
            )
            if not _wait(_DEFERRED_NOTE_SECONDS):
                return False
            continue

        _draw(screen, font, ipa_font, note_font, graphemes, i, f"({source})", separator)
        sound.play()
        if not _wait(sound.get_length()):
            return False
        if not _wait(pause_seconds):
            return False

    _draw(screen, font, ipa_font, note_font, graphemes, None, "", separator)
    return True


def explore_word(screen, font, ipa_font, note_font, word: str) -> bool:
    """Returns False if the window was closed mid-word."""
    decomposition = decompose(word)
    if not decomposition.graphemes:
        _draw(
            screen, font, ipa_font, note_font, [word], None,
            "couldn't segment this word into graphemes",
        )
        return _wait(1.5)

    graphemes = [g.grapheme for g in decomposition.graphemes]

    # Pass 1: slow and segmented -- "c... a... t...", no separator, a
    # real breath between each sound.
    if not _play_pass(
        screen, font, ipa_font, note_font, graphemes, decomposition.graphemes,
        _SLOW_PAUSE_SECONDS, "",
    ):
        return False
    if not _wait(0.6):
        return False

    # Pass 2: quick and blended -- "c-a-t", hyphens between the
    # letters, barely any pause -- the word visibly coming together.
    if not _play_pass(
        screen, font, ipa_font, note_font, graphemes, decomposition.graphemes,
        _BLEND_PAUSE_SECONDS, "-",
    ):
        return False

    return _wait(0.6)


def main() -> None:
    pygame.init()
    pygame.mixer.init(frequency=24000)
    screen = pygame.display.set_mode((_WIDTH, _HEIGHT))
    pygame.display.set_caption("Chitti phonics explorer")
    font = pygame.font.Font(None, _FONT_SIZE)
    # Decision pending: pygame's own bundled default font (used for
    # `font`/`note_font` above) is missing glyphs for most IPA symbols
    # (confirmed: has "æ"/"ŋ"/"θ"/"ð", missing "ʃ"/"ʌ"/"ɒ"/"ɪ"/"ɛ"/"ʒ"/
    # "ː"/"ə"/"ɔ" -- they'd render as blank boxes). Segoe UI (bundled
    # with Windows) covers every one used in _IPA below -- confirmed
    # directly, not assumed.
    ipa_font_path = pygame.font.match_font("segoeui")
    ipa_font = pygame.font.Font(ipa_font_path, _IPA_FONT_SIZE)
    note_font = pygame.font.Font(None, _NOTE_FONT_SIZE)

    print("Chitti phonics explorer -- type a word and press Enter.")
    print(f"New pack: {_PACK_DIR} ({'found' if _PACK_DIR.is_dir() else 'NOT FOUND'})")
    print("(Ctrl-C or 'quit' to exit.)")
    try:
        while True:
            if not _pump_events():
                break
            word = input("\nword> ").strip()
            if not word or word.lower() in ("quit", "exit"):
                break
            if not explore_word(screen, font, ipa_font, note_font, word):
                break
    except (KeyboardInterrupt, EOFError):
        print("\nBye!")
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
