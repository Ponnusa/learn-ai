"""Wires everything together: reads narration lines (typed at a
terminal, or from a --script file for a repeatable demo), sends each
one to the LLM on a background thread (so the animation never freezes
waiting on the API round trip), and renders the result live.

Deliberately typed narration, not voice -- per the brainstorm this
project exists to test, the riskiest piece is "does the LLM reliably
map narration to the fixed sprite vocabulary," which has nothing to
do with speech-to-text. Wiring in a mic is a separate, later step
once this loop itself feels good (see README.md).
"""
import argparse
import logging
import os
import queue
import sys
import threading

from .engine import SceneEngine
from .llm import SceneGenerationError, narration_to_scene
from .renderer import SceneRenderer

logger = logging.getLogger(__name__)

_FPS = 30


def _read_narration_lines(script_path: str | None, narration_queue: "queue.Queue[str]", stop_event: threading.Event) -> None:
    """Runs on its own thread so blocking on input() (or reading a
    script file line by line, paced the same way) never stalls the
    render loop. Reads from `script_path` if given, otherwise stdin."""
    try:
        source = open(script_path, encoding="utf-8") if script_path else sys.stdin
        with source if script_path else _no_close(source):
            for line in source:
                if stop_event.is_set():
                    break
                line = line.strip()
                if line and not line.startswith("#"):
                    narration_queue.put(line)
                    if script_path:
                        input("  (press Enter to send the next line) ")
    except EOFError:
        pass


class _no_close:
    """Lets `with` be used uniformly over stdin (which must NOT be
    closed) and a real file (which should be) above."""

    def __init__(self, stream) -> None:
        self._stream = stream

    def __enter__(self):
        return self._stream

    def __exit__(self, *_exc) -> None:
        pass


def _request_scene(client, model, narration, prior_scene, result_queue) -> None:
    try:
        scene, warnings = narration_to_scene(client, narration, prior_scene, model=model)
        result_queue.put(("ok", scene, warnings))
    except SceneGenerationError as exc:
        result_queue.put(("error", str(exc), []))
    except Exception as exc:  # noqa: BLE001 -- any API/network failure degrades the same way
        logger.exception("scene generation failed")
        result_queue.put(("error", str(exc), []))


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fullscreen", action="store_true", help="Use for the real HDMI display.")
    parser.add_argument(
        "--script", metavar="FILE",
        help="Read narration lines from FILE instead of the keyboard (see fixtures/sample_narrations.txt).",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Missing ANTHROPIC_API_KEY -- copy .env.example to .env and fill it in.")
        sys.exit(1)
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    model = os.environ.get("STORY_STAGE_MODEL", "claude-sonnet-5-5")

    renderer = SceneRenderer(fullscreen=args.fullscreen)
    engine = SceneEngine()

    narration_queue: "queue.Queue[str]" = queue.Queue()
    result_queue: "queue.Queue[tuple[str, object, list[str]]]" = queue.Queue()
    stop_event = threading.Event()
    reader_thread = threading.Thread(
        target=_read_narration_lines, args=(args.script, narration_queue, stop_event), daemon=True,
    )
    reader_thread.start()

    if not args.script:
        print("Type a line of story narration and press Enter.")
    print("Close the window, press Escape, or Ctrl-C here to quit.")

    thinking = False
    status_text = ""
    running = True
    try:
        while running:
            running = renderer.pump_events()

            if not thinking and not narration_queue.empty():
                narration = narration_queue.get()
                thinking = True
                status_text = "Thinking..."
                threading.Thread(
                    target=_request_scene,
                    args=(client, model, narration, engine.scene, result_queue),
                    daemon=True,
                ).start()

            if not result_queue.empty():
                kind, payload, warnings = result_queue.get()
                thinking = False
                status_text = ""
                if kind == "ok":
                    engine.apply_scene(payload)
                    for warning in warnings:
                        logger.warning("scene validation: %s", warning)
                else:
                    status_text = f"(couldn't update the scene: {payload})"
                    logger.warning("scene generation failed: %s", payload)

            engine.tick()
            renderer.draw(engine, status_text=status_text)
            renderer.tick(fps=_FPS)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        renderer.shutdown()


if __name__ == "__main__":
    main()
