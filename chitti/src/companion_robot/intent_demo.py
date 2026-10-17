"""Intent-detection-only demo (decision 0043): no typed "Choose mode"
menu at all -- starts straight in Just Chat and relies entirely on
decision 0042's hybrid intent detection to pick the real mode from
whatever is said first, and to keep switching after that. Exists
purely to test mode-switching/intent detection in isolation, without
the typed menu getting in the way of that test.

Reuses voice_loop_demo.py's setup_demo()/run_mode_dispatch_loop()
rather than duplicating them -- the only difference from main() there
is how the starting mode is chosen: a fixed "3" (Just Chat) here
instead of a typed choice.
"""
import asyncio

from companion_robot.voice_loop_demo import run_mode_dispatch_loop, setup_demo


async def main() -> None:
    ctx = await setup_demo()

    print("Chitti intent-detection demo -- no menu, just start talking.")
    print(
        'Try things like: "tell me a story", "play a song", '
        '"let\'s just chat", or "let me teach you something".'
    )
    await run_mode_dispatch_loop("3", ctx)


if __name__ == "__main__":
    asyncio.run(main())
