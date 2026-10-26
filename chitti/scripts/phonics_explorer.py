#!/usr/bin/env python
"""Standalone phonics-sound explorer -- type a word, see it split into
its real graphemes on screen, and hear each one's real recorded sound
in order, with the grapheme currently playing highlighted. Two passes
per word: slow and segmented first (each grapheme named: "c... a...
t..."), then a quicker blended pass with hyphens between the letters
("c-a-t") so the word visibly comes together, the way phonics
instruction actually teaches segment-then-blend.

Not part of the companion_robot app or voice loop at all -- this is a
throwaway tool for manually checking the repo's own phonics assets
(reading/decodability.py's grapheme segmentation, reading/phonics_audio.py's
real recorded clips) sound and look right, standing on its own two
feet with a minimal pygame window and pygame.mixer for audio. No mic,
no STT, no LLM, no chitti.db.

Run from the chitti/ directory (needs companion_robot importable):
    uv run python scripts/phonics_explorer.py

Type a word at the prompt and press Enter. Ctrl-C or "quit" to exit.
"""
import io
import time

import pygame

from companion_robot.reading.decodability import decompose
from companion_robot.reading.phonics_audio import DEFERRED_GRAPHEMES, get_clip_bytes
from companion_robot.reading.word_timing import pcm_to_wav_bytes

_WIDTH, _HEIGHT = 900, 300
_BG = (20, 20, 30)
_IDLE_COLOR = (230, 230, 230)
_HIGHLIGHT_COLOR = (255, 80, 80)
_SEPARATOR_COLOR = (110, 110, 120)
_NOTE_COLOR = (150, 150, 160)
_FONT_SIZE = 72
_NOTE_FONT_SIZE = 22
_GAP = 24
_SLOW_PAUSE_SECONDS = 0.4  # breathing room between graphemes, segmented pass
_BLEND_PAUSE_SECONDS = 0.08  # quick, so the word visibly blends together
_DEFERRED_NOTE_SECONDS = 1.0


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
    screen, font, note_font, graphemes: list[str], highlight_index: int | None, note: str,
    separator: str = "",
) -> None:
    screen.fill(_BG)
    sep_width = font.size(separator)[0] if separator else 0
    widths = [font.size(g)[0] for g in graphemes]
    total_width = sum(widths) + (sep_width + _GAP) * (len(graphemes) - 1)
    x = (_WIDTH - total_width) // 2
    y = _HEIGHT // 2 - _FONT_SIZE // 2
    for i, grapheme in enumerate(graphemes):
        color = _HIGHLIGHT_COLOR if i == highlight_index else _IDLE_COLOR
        rendered = font.render(grapheme, True, color)
        screen.blit(rendered, (x, y))
        x += widths[i]
        if i < len(graphemes) - 1:
            if separator:
                sep_rendered = font.render(separator, True, _SEPARATOR_COLOR)
                screen.blit(sep_rendered, (x + _GAP // 2, y))
            x += sep_width + _GAP
    if note:
        note_rendered = note_font.render(note, True, _NOTE_COLOR)
        note_rect = note_rendered.get_rect(center=(_WIDTH // 2, _HEIGHT - 40))
        screen.blit(note_rendered, note_rect)
    pygame.display.flip()


def _play_pass(
    screen, font, note_font, graphemes: list[str], grapheme_hits, pause_seconds: float,
    separator: str,
) -> bool:
    """One full pass over every grapheme: highlight it, play its real
    clip (or show why there isn't one), pause, move on. `pause_seconds`
    and `separator` are what tell the slow segmented pass and the
    quick blended pass apart -- same mechanics otherwise."""
    _draw(screen, font, note_font, graphemes, None, "", separator)
    if not _wait(pause_seconds):
        return False

    for i, grapheme_hit in enumerate(grapheme_hits):
        grapheme = grapheme_hit.grapheme
        clip = get_clip_bytes(grapheme)
        if clip is None:
            reason = DEFERRED_GRAPHEMES.get(grapheme, "no clip for this one yet")
            _draw(
                screen, font, note_font, graphemes, i,
                f'no real clip for "{grapheme}" -- {reason}', separator,
            )
            if not _wait(_DEFERRED_NOTE_SECONDS):
                return False
            continue

        _draw(screen, font, note_font, graphemes, i, "", separator)
        sound = pygame.mixer.Sound(io.BytesIO(pcm_to_wav_bytes(clip)))
        sound.play()
        if not _wait(sound.get_length()):
            return False
        if not _wait(pause_seconds):
            return False

    _draw(screen, font, note_font, graphemes, None, "", separator)
    return True


def explore_word(screen, font, note_font, word: str) -> bool:
    """Returns False if the window was closed mid-word."""
    decomposition = decompose(word)
    if not decomposition.graphemes:
        _draw(screen, font, note_font, [word], None, "couldn't segment this word into graphemes")
        return _wait(1.5)

    graphemes = [g.grapheme for g in decomposition.graphemes]

    # Pass 1: slow and segmented -- "c... a... t...", no separator, a
    # real breath between each sound.
    if not _play_pass(screen, font, note_font, graphemes, decomposition.graphemes, _SLOW_PAUSE_SECONDS, ""):
        return False
    if not _wait(0.6):
        return False

    # Pass 2: quick and blended -- "c-a-t", hyphens between the
    # letters, barely any pause -- the word visibly coming together.
    if not _play_pass(screen, font, note_font, graphemes, decomposition.graphemes, _BLEND_PAUSE_SECONDS, "-"):
        return False

    return _wait(0.6)


def main() -> None:
    pygame.init()
    pygame.mixer.init(frequency=24000)
    screen = pygame.display.set_mode((_WIDTH, _HEIGHT))
    pygame.display.set_caption("Chitti phonics explorer")
    font = pygame.font.Font(None, _FONT_SIZE)
    note_font = pygame.font.Font(None, _NOTE_FONT_SIZE)

    print("Chitti phonics explorer -- type a word and press Enter.")
    print("(Ctrl-C or 'quit' to exit.)")
    try:
        while True:
            if not _pump_events():
                break
            word = input("\nword> ").strip()
            if not word or word.lower() in ("quit", "exit"):
                break
            if not explore_word(screen, font, note_font, word):
                break
    except (KeyboardInterrupt, EOFError):
        print("\nBye!")
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
