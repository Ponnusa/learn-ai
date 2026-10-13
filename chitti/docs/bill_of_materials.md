# Bill of materials — not yet populated

Status: empty skeleton. No hardware has been purchased or finalized; the
project owner confirmed no Raspberry Pi 5 is in hand yet (Milestone 0
decision log, `docs/decisions/0001-milestone-0-scope.md`). Populate this
once real hardware is selected (Milestone 1 onward), and keep it current
through Milestone 7's production-intent BOM (spec section 12).

## Planned structure (fill in as hardware is chosen)

| Component | Part / model | Supplier | Qty | Notes |
|---|---|---|---|---|
| Compute | Raspberry Pi 5 (8GB recommended for dev) | — | 1 | Spec section 3.1 |
| Microphone | — | — | — | Pi-compatible or USB mic array |
| Speaker + amplifier | — | — | — | — |
| Physical mic mute switch | — | — | — | Must be hardware, not software-only (spec core principle, section 3.1) |
| Status/listening LED | — | — | — | — |
| Power supply | — | — | — | Appropriately rated for the full BOM's draw |
| Battery/charging subsystem (optional) | — | — | — | Only if a battery is introduced; needs its own documentation (spec section 3.1) |
| Low-power microcontroller for motor/safety (optional) | — | — | — | Only if motors are introduced later — out of MVP scope today (spec section 2.2) |

## Supplier documentation inventory

Track datasheets, certifications, and compliance-relevant documentation
per component here once sourcing begins (spec Milestone 6 deliverable:
"supplier documentation inventory").
