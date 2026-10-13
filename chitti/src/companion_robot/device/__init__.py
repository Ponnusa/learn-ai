"""Device Controller (spec section 3.2.A) -- Milestone 1.

Owns hardware abstraction (audio, LEDs, buttons, future motors), startup/
shutdown, watchdog/health monitoring, local emergency-stop, and hardware
mute-state enforcement. Must never be reachable from companion_robot.
conversation -- the Conversation Service has no path to motor control,
GPIO, or emergency-stop (spec core principle 6; docs/architecture.md's
"Safety boundary" section). Nothing implemented yet.
"""
