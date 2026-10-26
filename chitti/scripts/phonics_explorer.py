#!/usr/bin/env python
"""Standalone phonics-sound explorer -- type a word, see it split into
its real graphemes on screen, and hear each one's real recorded sound
in order, with the grapheme currently playing highlighted.

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
_NOTE_COLOR = (150, 150, 160)
_FONT_SIZE = 72
_NOTE_FONT_SIZE = 22
_GAP = 24
_STEP_PAUSE_SECONDS = 0.4  # breathing room between graphemes, after the clip finishes


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


def _draw(screen, font, note_font, graphemes: list[str], highlight_index: int | None, note: str) -> None:
    screen.fill(_BG)
    widths = [font.size(g)[0] for g in graphemes]
    total_width = sum(widths) + _GAP * (len(graphemes) - 1)
    x = (_WIDTH - total_width) // 2
    y = _HEIGHT // 2 - _FONT_SIZE // 2
    for i, grapheme in enumerate(graphemes):
        color = _HIGHLIGHT_COLOR if i == highlight_index else _IDLE_COLOR
        rendered = font.render(grapheme, True, color)
        screen.blit(rendered, (x, y))
        x += widths[i] + _GAP
    if note:
        note_rendered = note_font.render(note, True, _NOTE_COLOR)
        note_rect = note_rendered.get_rect(center=(_WIDTH // 2, _HEIGHT - 40))
        screen.blit(note_rendered, note_rect)
    pygame.display.flip()


def explore_word(screen, font, note_font, word: str) -> bool:
    """Returns False if the window was closed mid-word."""
    decomposition = decompose(word)
    if not decomposition.graphemes:
        _draw(screen, font, note_font, [word], None, "couldn't segment this word into graphemes")
        return _wait(1.5)

    graphemes = [g.grapheme for g in decomposition.graphemes]
    _draw(screen, font, note_font, graphemes, None, "")
    if not _wait(0.4):
        return False

    for i, grapheme_hit in enumerate(decomposition.graphemes):
        grapheme = grapheme_hit.grapheme
        clip = get_clip_bytes(grapheme)
        if clip is None:
            reason = DEFERRED_GRAPHEMES.get(grapheme, "no clip for this one yet")
            _draw(screen, font, note_font, graphemes, i, f'no real clip for "{grapheme}" -- {reason}')
            if not _wait(1.0):
                return False
            continue

        _draw(screen, font, note_font, graphemes, i, "")
        sound = pygame.mixer.Sound(io.BytesIO(pcm_to_wav_bytes(clip)))
        sound.play()
        if not _wait(sound.get_length()):
            return False
        if not _wait(_STEP_PAUSE_SECONDS):
            return False

    _draw(screen, font, note_font, graphemes, None, "")
    return _wait(0.5)


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
