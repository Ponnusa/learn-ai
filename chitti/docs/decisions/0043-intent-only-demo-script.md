# 0043 — Intent-only demo script

Date: 2026-10-17
Status: Accepted

## Context

After decision 0042 shipped, testing it meant first clicking through
`voice_loop_demo.py`'s typed "Choose mode (1/2/3/4)" menu before ever
reaching a turn that could exercise intent detection -- awkward for a
feature whose whole point is not needing that menu once a
conversation is underway. Product owner asked for a **separate**
script with no typed menu at all, purely for testing mode-switching.

## What shipped

`voice_loop_demo.py`'s `main()` is split into two reusable pieces so
nothing is duplicated:
- `setup_demo() -> DemoContext`: everything that was inline setup code
  in `main()` (backends, repositories, the screen face, profile
  selection, the welcome-back greeting) -- unchanged behavior, just
  extracted.
- `run_mode_dispatch_loop(next_mode, ctx)`: the mode-dispatch loop
  decision 0042 added to `main()` -- also unchanged, just extracted so
  a second entry point can reuse it.

`main()` itself is now just: `setup_demo()`, print the menu, read the
typed choice, call `run_mode_dispatch_loop()`.

New `intent_demo.py`: calls the same `setup_demo()` and
`run_mode_dispatch_loop()`, skipping the typed menu entirely and
starting in Just Chat (`"3"`) -- decision 0042's detection takes over
from the very first thing said. Prints a short reminder of example
phrases to try.

## Consequences

No behavior change to `main()`/`voice_loop_demo.py`'s existing flow --
confirmed by the full existing test suite passing unchanged (277
passing, 1 skipped). No new tests added specifically for this decision:
`setup_demo()`/`run_mode_dispatch_loop()` are the exact same code
`main()` already ran, covered by whatever coverage already existed
indirectly; `intent_demo.py` itself is a thin, two-line orchestration
script with nothing new to unit-test.

## Not yet done

Nothing deferred -- this is a scoped convenience script, not a product
feature.
