"""Manual face-expression test script (decision 0045): pick a
(DeviceState, mode) combination from a menu and hold it on screen, so
each decision 0044 dot-matrix expression can be checked individually
on real hardware without running the full voice loop demo.
"""
import asyncio

from companion_robot.device.interfaces import DeviceState
from companion_robot.device.screen_face import ScreenFaceDeviceController

# Each entry: (menu label, DeviceState, mode). mode=None uses the
# plain per-state default (_BASE_EXPRESSIONS); the rest pair a state
# with one of the four conversation modes so mode-specific overrides
# (currently only "music") can be checked too.
_CASES: list[tuple[str, DeviceState, str | None]] = [
    ("Listening (default)", DeviceState.LISTENING, None),
    ("Thinking (default)", DeviceState.PROCESSING, None),
    ("Speaking (default)", DeviceState.SPEAKING, None),
    ("Idle (default)", DeviceState.IDLE, None),
    ("Muted", DeviceState.MUTED, None),
    ("Error / retry", DeviceState.ERROR, None),
    ("Listening -- chat mode", DeviceState.LISTENING, "chat"),
    ("Speaking -- chat mode", DeviceState.SPEAKING, "chat"),
    ("Listening -- story mode", DeviceState.LISTENING, "story"),
    ("Speaking -- story mode", DeviceState.SPEAKING, "story"),
    ("Listening -- learning mode", DeviceState.LISTENING, "learning"),
    ("Speaking -- learning mode", DeviceState.SPEAKING, "learning"),
    ("Listening -- music mode", DeviceState.LISTENING, "music"),
    ("Speaking -- music mode (open mouth)", DeviceState.SPEAKING, "music"),
    ("Idle -- music mode", DeviceState.IDLE, "music"),
]


async def main() -> None:
    face = ScreenFaceDeviceController()
    await face.start()
    try:
        while True:
            print("\nFace expression test -- pick one to display (Ctrl-C to quit):")
            for i, (label, _, _) in enumerate(_CASES):
                print(f"{i + 1}) {label}")
            choice = input("Choice: ").strip()
            try:
                _, state, mode = _CASES[int(choice) - 1]
            except (ValueError, IndexError):
                print("Not a valid choice.")
                continue
            face.set_status_led(state)
            face.set_expression_mode(mode)
            print(f"Showing: state={state.value}, mode={mode!r}.")
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nBye!")
    finally:
        await face.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
