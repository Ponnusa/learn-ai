# Story Stage

A standalone prototype to test the riskiest piece of "a kid narrates a
story live, and a screen renders an animated 2D scene": **does an LLM
reliably turn messy, kid-style narration into strict JSON that stays
inside a fixed sprite vocabulary?**

No microphone, no Raspberry Pi, no real sprite art yet -- on purpose.
Narration is typed (or read from a script file for a repeatable demo)
so this loop can be proven out on a laptop first; only once it feels
good does it make sense to move onto real hardware with a mic and
better visuals.

## How it fits together

```
your narration (typed)
    -> llm.py           Claude, constrained to a fixed enum vocabulary (asset_library.py)
    -> schema.py         validates the reply; any out-of-vocabulary value is
                          CLAMPED to a safe default (never trusted raw, never crashes)
    -> engine.py          holds the current scene, animates its one-shot events
                          (move/speak/jump) over real time
    -> renderer.py        pygame window, redrawn every frame from the engine's state
```

Each module only depends on the one below it in that list --
`schema.py`/`llm.py`/`engine.py` have no pygame dependency at all, so
they (and their tests) run with no display needed. Only
`renderer.py`/`cli.py` touch pygame.

## Setup

```
cd story_stage
cp .env.example .env     # fill in ANTHROPIC_API_KEY
uv sync --extra dev
uv run pytest            # 24 tests, no API calls, no display needed
```

## Running it

```
uv run story-stage
```

Type a line of narration and press Enter. The LLM call runs on a
background thread, so the window keeps rendering (showing "Thinking...")
instead of freezing while it waits. Each new line is sent WITH the
current scene as context, so the model updates it (moves/adds
characters) rather than starting over -- see `llm.py`'s own prompt.

Close the window, press Escape, or Ctrl-C in the terminal to quit.

### A repeatable demo, no typing live

```
uv run story-stage --script fixtures/sample_narrations.txt
```

Reads narration lines from the file instead of the keyboard, pausing
after each one so you can advance it on cue (handy for actually
presenting this to someone, including the kid it's for).

### On the real HDMI display later

```
./scripts/run_demo.sh
```

Runs full-screen. Nothing here is Pi-specific -- this was deliberately
tested on a regular laptop screen first (see the brainstorm that
started this project). Once it feels good, it should move to the Pi 5
mentioned in that brainstorm unchanged; a Pi 1 B+ (the actual Chitti
hardware) is not a target here at all -- that device doesn't even have
a reliable SDL video driver (see `chitti/`'s own screen_face.py for
what that failure looks like), and 1-core ARMv6 is almost certainly
too slow for pygame animation regardless of this prototype's results.

## What to watch for while testing

Straight from the brainstorm this project exists to validate:

- **Does it stay inside the vocabulary even when the kid says
  something wild** ("a dragon that's also a robot")? Check the
  terminal for `scene validation:` warnings -- every clamp is logged,
  so you can see exactly what got substituted without the demo ever
  crashing over it.
- **Does a follow-up line correctly update the existing scene** rather
  than replacing it wholesale? (The princess should land next to the
  dragon that was already there, not alone in an empty new scene.)
- **Latency** -- is the "Thinking..." wait short enough for a kid's
  attention span? The status text and background-thread design exist
  specifically so this is easy to feel out and tune (e.g. a shorter
  `max_tokens`, a faster model) once you've watched it run for real.

## Not built here (by design)

- No microphone/STT -- typed narration only, see above for why.
- No real sprite art -- every character is a colored circle + label
  (`asset_library.py`'s own docstring explains the swap path once art
  exists).
- No persistence -- the scene lives only in memory for the process's
  lifetime; nothing is saved between runs.
- No connection to Chitti's own codebase (`chitti/`) -- genuinely
  standalone, so it can be thrown away or merged in later without
  having touched anything there.
