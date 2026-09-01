# VR / 3D Experiment — Notes

Everything learned building and debugging the VR-viability experiment: the
routing-plan classifier, the Manim-to-bpy pipeline (both "faithful port" and
"fresh 3D content" modes), every bug hit and how it was fixed, and the
resulting recommendation for using this on real videos.

Status: **prototype, not production**. See "Production-readiness gap" at the
end before trying to wire this into the real render pipeline.

---

## 1. What this is

Two related but separate experiments, both scoped as read-only/isolated —
neither touches the production DB, render pipeline, or asset manifest:

1. **Routing-plan classifier** (`run.ps1` + `backend/routers/vr_experiment.py`,
   both committed) — for an existing video, classify each Manim segment as
   `2d` (flat, stays a video panel) or `3d` (genuinely spatial, worth a VR
   scene) via one Anthropic API call per segment. Non-Manim segments
   (`image`, `video`) are never classified — always `billboard`.
2. **bpy 3D-generation pipeline** (`bpy-3d-pipeline/`, this folder) — given
   either a topic description or a real Manim scene's source, generate a
   Blender Python script that builds an actual 3D scene, export it to
   `.glb`, and view it locally. Two generation modes:
   - `generate_segment.py` — **fresh content**. Give it an open topic
     description; the model invents genuinely 3D content, biased toward
     spatial structure (vectors in space, real 3D motion) over flat diagrams.
   - `port_manim_to_bpy.py` — **faithful port**. Give it a real Manim
     scene's source code; the model translates it 1:1 into bpy using the
     same helper functions, same layout, same colors/timing. Explicitly
     told not to invent anything.

Both generation modes emit a bpy script built on a shared, hand-debugged
**boilerplate** (`bpy_boilerplate_gltf_safe.py` or `bpy_boilerplate_manim_port.py`,
the latter = the former + two more shape helpers for Manim's `Rectangle`/
`Circle`). The LLM is only ever asked to write the scene-specific content
*below* a marker line — never to redefine the helpers themselves. This was
the single most effective thing for reliability: every bug we hit was in
the boilerplate (code we wrote), never in what the LLM generated per scene.

---

## 2. Why classify at all instead of just always going 3D

Tested both ways on video 172 (Rutherford's Gold Foil Experiment):

- **Faithful ports** of the 5 real Manim segments render fine and export
  fine, but are still visually *flat* — the source content is a
  deliberately top-down 2D schematic, and porting it to bpy just makes a
  flat diagram float in 3D space. Technically VR-*compatible*, not
  VR-*worthwhile*.
- **Fresh content** for the same 5 topics produced genuinely spatial
  results — e.g. a real diagonal deflection arrow for the scattering
  result, particles traveling through actual 3D space.

This matches what the classifier already found on this same video: **all 5
Manim segments came back `2d`**. That's not a classifier failure — it's an
accurate read that this particular content is inherently flat. See §6 for
what that implies for existing vs. new videos.

---

## 3. Architecture pieces (what's committed vs. local-only)

**Committed to the repo (production code):**
- `backend/routers/vr_experiment.py` — `GET /api/admin/vr-experiment/video/{id}`,
  superadmin-gated, one read-only SELECT against `videos`/`video_segments`.
  Re-signs `source_asset_url`/`clip_url` fresh on every read (see bug list,
  §4.15) since the stored values are presigned URLs baked in at render time.
- `scripts/vr-experiment-worker/run.ps1` — the classifier script. Logs in
  (or reuses a cached token), fetches a video's segments, classifies each
  Manim segment via a **direct Anthropic API call** (not the `claude` CLI —
  deliberately, so classification is billed to a separate
  `ANTHROPIC_API_KEY` pay-as-you-go account instead of eating into a Claude
  Code subscription's usage), writes `routing_plan.json` + per-segment
  code/logs to a local temp folder.

**Local-only prototype code (this folder, `bpy-3d-pipeline/`):**
- `bpy_boilerplate_gltf_safe.py` — the core helper library (materials,
  fade/reveal/indicate animation helpers, text, arrows).
- `bpy_boilerplate_manim_port.py` — same, plus `make_box`/`make_disc` for
  mapping Manim's `Rectangle`/`Circle`.
- `generate_segment.py` — fresh-content generation (topic → bpy script).
- `port_manim_to_bpy.py` — faithful-port generation (real Manim source →
  bpy script).
- `gen_billboard.py` — deterministic (no LLM) billboard-plane generator for
  image/video segments.
- `export_glb.py` — exports the currently-open `.blend` to a single-
  animation `.glb`.
- `render_frames.py` — renders specific frame numbers to PNG for visual
  verification (see debugging technique in §5).
- `viewer_template.html` — a `<model-viewer>`-based local page for viewing
  the resulting `.glb`s, served via `python -m http.server <port>`.

None of the bpy-3d-pipeline code has been run against the production
render queue or written back to the DB — it only ever reads a video's
segments (via the endpoint above) and writes local files.

---

## 4. Bugs found and fixed (chronological, with root cause)

### 4.1 — Wrong Blender render engine identifier
`'BLENDER_EEVEE_NEXT'` isn't a valid enum on the installed Blender version.
**Fix:** use `'BLENDER_EEVEE'`.

### 4.2 — PowerShell not finding `blender.exe`
Windows won't run executables from the current folder by default.
**Fix:** `.\blender.exe`, or add Blender's install folder to PATH.

### 4.3 — Material alpha keyframes silently dropped by glTF export
glTF's core spec doesn't support animating material opacity, only object
transforms (location/rotation/scale). Blender's exporter drops alpha
keyframes with no error or warning. Since our `fade_in`/`fade_out` used to
animate alpha, the LAST alpha value written before export (often `0`, if an
object faded out later in the timeline) became that object's permanent,
static, invisible state after export.
**Fix:** rewrote `fade_in`/`fade_out`/`create_reveal` to animate **scale**
(0.001 → 1, or the reverse) instead of alpha — scale is a transform and
survives export. `make_material` was also changed to always create fully
opaque materials (alpha param kept in the signature for compatibility, but
ignored), so nothing can get stuck invisible from a stale bake.

### 4.4 — Text objects not surviving export
`bpy.ops.object.text_add()` creates a `FONT`/curve-type object, which the
glTF exporter can skip or mishandle.
**Fix:** convert every text object to a mesh immediately after creation:
`bpy.ops.object.convert(target='MESH')` (already baked into `make_text`).

### 4.5 — `Action` object has no attribute `fcurves`
Blender 4.4+ restructured animation storage into "layered actions"
(layers → strips → channelbags → fcurves), breaking direct `action.fcurves`
access.
**Fix:** `_get_fcurves()` compatibility shim — tries the old path first,
falls back to walking `action.layers[].strips[].channelbag(slot).fcurves`.
Used everywhere the code needs to touch existing keyframe curves (mainly
`set_fcurve_easing`).

### 4.6 — `kp.easing = 'LINEAR'` raises TypeError
`Keyframe.easing` only accepts `AUTO`/`EASE_IN`/`EASE_OUT`/`EASE_IN_OUT`.
`'LINEAR'` is a valid value for `interpolation`, not `easing` — passing it
as easing crashes. This recurred a few times in LLM-generated code before
being added as an explicit rule in both generation prompts.
**Fix:** for genuinely linear/constant motion, use
`set_fcurve_easing(obj, "location", easing='AUTO', interpolation='LINEAR')`.
Both `generate_segment.py` and `port_manim_to_bpy.py` now explicitly warn
against `easing='LINEAR'` in their prompts.

### 4.7 — Blender 5.2 requires `media_type='VIDEO'` before `file_format='FFMPEG'`
Blender 5.2 added `image_settings.media_type` (`IMAGE`/`MULTI_LAYER_IMAGE`/
`VIDEO`); `file_format` only accepts `FFMPEG` when `media_type='VIDEO'` is
set first — otherwise it's not in the enum's valid list and errors.
**Fix:** always set `media_type = 'VIDEO'` before `file_format = 'FFMPEG'`
when configuring video render output.

### 4.8 — Billboard plane shrinks to a speck right after fading in
A billboard's size was set via `plane.scale = (aspect*3, 3, 1)` *after*
creation. `fade_in()`/`fade_out()` hardcode scale targets of
`(0.001, 0.001, 0.001)` and `(1, 1, 1)` — calling either overwrites any
custom scale, so the billboard's real size got silently replaced with a
1-unit default the moment it finished fading in.
**Fix:** bake the size into the **mesh** instead of `object.scale`, via
`plane.data.transform(Matrix.Diagonal((sx, sy, sz, 1)))` right after
creation. The object's own `.scale` then stays untouched by fade helpers,
which is exactly what they expect.

### 4.9 — Only one object animates in the web viewer; everything else frozen
Blender's default glTF export mode (`ACTIONS`) creates one glTF animation
**per object**. `<model-viewer>`'s `autoplay` only plays the first clip by
default — so only one object (whichever action came first) actually
animated; everything else sat at its frame-1 pose.
**Fix:** export with `export_animation_mode='ACTIVE_ACTIONS'` — merges every
currently-assigned action into a single combined glTF animation. Verify with
`pygltflib`: `len(gltf.animations) == 1` and the channel count covers every
node that should move.

### 4.10 — `auto-rotate` makes flat content flicker/vanish
Orbiting the camera around a paper-thin plane (a billboard image, or a
"top-down 2D view" Manim-ported schematic) makes it go edge-on and nearly
disappear for part of every rotation — looked like "goes fast, unclear,
zoomed out."
**Fix:** don't set `auto-rotate` on `<model-viewer>` for scenes containing
flat/2D content. Reserve it for genuinely 3D scenes.

### 4.11 — Billboard images: wrong orientation + severely underexposed
Two compounding bugs, only found by actually rendering a still frame and
looking at it (see §5):
- `bpy.ops.uv.smart_project()` re-unwrapped the plane's UVs with an
  unpredictable rotation (it optimizes layout, not orientation) — images
  came out sideways.
- The image was wired into the Principled BSDF's Base Color, meaning it
  was *physically lit* by the scene's Sun lamp. Combined with Blender's
  default AgX color management (which lifts near-black values into a
  washed-out gray), a deliberately dim period photo rendered almost black.
**Fix:** (a) don't call `smart_project()` — the plane's default UVs
(generated at creation) are already correctly oriented; (b) use an
**Emission** shader instead of Base Color, so the image displays at its
own natural brightness regardless of scene lighting — like a screen
showing it, not a photo being lit by a lamp.

### 4.12 — Text illegible against the background
Same root cause as 4.11(b): white text on a Principled-BSDF surface, lit
by the Sun lamp, against an AgX-washed-out near-black background — very
low contrast either direction.
**Fix:** `make_text()` now builds an Emission-shader material instead of
calling the regular (physically-lit) `make_material()`. Because `indicate()`
can flash a text label's color, `keyframe_color()` was also made to check
for either a Principled BSDF *or* an Emission node and keyframe whichever
one exists.

### 4.13 — Arrowheads floating detached from their shafts
The single most involved bug — three separate root causes that all had to
be fixed together, found by rendering multiple frames across an arrow's
animation and a fully-settled late frame (see §5):

1. **Missing `matrix_parent_inverse` on first attempt.** Plain
   `child.parent = X` in the Python API does *not* compute
   `matrix_parent_inverse` — Blender then re-reads the child's existing
   world-space `.location` as a *local offset from the parent's origin*,
   silently stacking on top of it. On short/centered arrows (the original
   reference scene's test cases) the error was invisible by coincidence;
   on longer or off-center arrows it's a large, obvious drift.
2. **Rotation applied to the parent *after* children were already
   parented.** Setting `matrix_parent_inverse = parent.matrix_world.inverted()`
   correctly freezes a child's position *at the moment of parenting* — but
   if the parent's rotation is set *afterward*, that later change swings
   any off-center child (like the arrowhead, which sits away from the
   parent's own origin) around to the wrong place.
3. **The rotation formula itself was wrong for tilted/diagonal arrows.**
   The original formula, `angle = atan2(direction.y, direction.x)`, only
   accounts for the X/Y components of the direction vector — it silently
   ignores Z entirely. Since arrows in this pipeline's convention live in
   the X-Z plane (Y ≈ 0, used as depth), any arrow with a Z tilt (i.e. most
   of them — anything not perfectly horizontal) got rotated to a
   completely wrong orientation, while the head's *position* (computed
   directly from the real 3D direction vector) stayed correct — guaranteeing
   a visible mismatch between where the shaft pointed and where the head sat.

   **The actual fix ended up being conceptually different from patching
   1 or 2**, once it became clear *why* they didn't fully work: children
   should **inherit** the parent's rotation (that's the entire mechanism
   for pointing a default Z-aligned cylinder/cone along an arbitrary
   direction) — `matrix_parent_inverse` specifically **cancels** the
   parent's rotation as seen from the child, which is the wrong tool for
   that goal, no matter what order you set it in.

   **Final, correct approach** (in `make_arrow()` now):
   - Rotate the parent using `direction.to_track_quat('Z', 'Y')` — Blender's
     own, well-tested direction-to-quaternion math, not a hand-rolled
     formula. Handles any 3D direction correctly, not just X-Y-plane ones.
   - Position children as **local Z-axis offsets** (`(0,0,0)` for the
     shaft, `(0,0,length*0.42)` for the head) — not world coordinates —
     with **no** `matrix_parent_inverse` override at all (leave Blender's
     real default, which is identity, exactly as-is).
4. **A fourth, orthogonal gotcha surfaced while debugging this one:**
   reading `object.matrix_world` immediately after changing
   `.rotation_quaternion` or `.parent` returns a **stale** value in
   headless/background Blender — the dependency graph isn't recomputed
   until something forces it (`bpy.context.view_layer.update()`, or the
   renderer's own full evaluation before drawing a frame). This produced
   very confusing intermediate results while iterating on the fix above
   (a `matrix_parent_inverse` computed from a stale, pre-rotation
   `matrix_world` got permanently baked in wrong, since it's a stored
   value, not dynamically recalculated). Not an issue in the final fix
   (which reads `matrix_world` nowhere), but worth remembering for any
   future debugging that inspects transforms mid-script.

### 4.14 — Newton's Law 1 built on the wrong (non-glTF-safe) boilerplate
An early generation of Law 1 used the *original* alpha-based boilerplate
(the one built for direct Blender rendering only, before the glTF-safe
variant existed) — unlike Law 2 and Law 3, which correctly used the
scale-based glTF-safe version from the start. Native Blender rendering
looked fine (alpha animation works natively), but the exported `.glb` was
missing/wrong objects, since alpha animation doesn't survive export (see
§4.3) — this boilerplate mismatch is exactly the failure mode §4.3 was
written to prevent, just not caught for this one file at generation time.
**Fix:** extract the scene-specific content (everything after the
`>>> GENERATED CONTENT GOES BELOW THIS LINE <<<` marker) from the broken
file and re-splice it onto the current, correct `bpy_boilerplate_gltf_safe.py`
— no LLM regeneration needed, since the scene code only calls the shared
helper functions, whose signatures are identical between boilerplate
variants.
**Lesson:** when adding a new scene, double-check *which* boilerplate file
was actually used, especially if copy-pasting a previous generation
command — the two boilerplates produce visually-identical native Blender
renders, so this class of bug is invisible until you actually check the
exported `.glb`.

### 4.15 — Stored R2 URLs go stale, breaking image downloads
`video_segments.source_asset_url`/`clip_url` in the DB are presigned URLs
baked in **at render time** (1-hour expiry) — for any video older than an
hour, they're dead. Cost real time: initial image downloads 403'd.
**Fix (committed, production code):** `vr_experiment.py`'s endpoint now
re-signs both URLs fresh from the stored R2 key on every read, instead of
trusting the DB value.

### 4.16 — Cached auth token corrupted by a UTF-8 BOM
`run.ps1` caches its JWT to `.token` after login (valid 30 days, so
`-Email`/`-Password` aren't needed every run). PowerShell's
`Out-File -Encoding utf8` writes UTF-8 **with a BOM** by default. Reading
that file raw in a different tool (Python, `curl`) and using it as a
Bearer token includes the 3 BOM bytes, silently corrupting it —
`{"detail":"Invalid or expired token"}`, even though the token itself was
fine and well within its 30-day validity.
**Fix:** read the cached token with `encoding='utf-8-sig'` (or equivalent
BOM-stripping) wherever it's consumed outside PowerShell itself.

---

## 5. Debugging techniques that actually worked

- **Render a still frame from the scene's own camera and look at it** —
  by far the highest-value technique in this whole exercise. Several bugs
  (billboard orientation/exposure, arrow detachment) were only found this
  way; reasoning about the transform math abstractly repeatedly produced
  wrong conclusions (see §4.13's multi-attempt history). `render_frames.py`
  in this folder does this: pass specific frame numbers, get PNGs back.
- **Render multiple frames spanning an animation**, not just one — a
  "detached" bug can look fine at one frame and wrong at another; checking
  frame 1, a mid-animation frame, and a frame well past all keyframes
  (fully "settled") separates animation-timing artifacts from genuine
  static positioning bugs.
- **Verify glTF exports with `pygltflib`** rather than trusting the export
  log — `pygltflib.GLTF2().load(path)` lets you check
  `len(gltf.animations)`, channel counts, node `scale`/position, and
  accessor min/max directly. Caught the single-vs-multiple-animation bug
  (§4.9) and confirmed the billboard mesh-size fix (§4.8) before ever
  opening a viewer.
- **Isolate the exact failing operation in a minimal script** once a bug
  is suspected in a specific API call (e.g. `to_track_quat`,
  `matrix_parent_inverse`) — small standalone repro scripts were much
  faster to iterate on than rebuilding a full scene each time.

---

## 6. Recommendation: existing videos vs. new videos

**For existing videos** (retrofitting a video that already has recorded/
timed narration): don't regenerate content freely. Use the routing-plan
classifier's verdict — most segments will come back `2d` (confirmed on the
one real video tested); for those, present a flat panel/screen in VR
rather than forcing 3D geometry that gains nothing. For segments the
classifier calls `3d`, use a **faithful port**, not fresh generation —
fresh content breaks the video's existing narration sync, and re-timing an
already-recorded voiceover is real, ongoing cost, not a one-time fix.

**For new videos** (no existing narration to preserve): generate 3D-native,
directly, for segments that are inherently spatial — skip the Manim
intermediate step entirely for those. The classification decision should
move earlier, into storyboard planning (deciding "spatial" vs "flat" per
segment *before* generation, the same judgment the routing-plan classifier
already makes, just applied prospectively). Spatial segments route to a
bpy codegen path; flat segments keep using Manim as today.

---

## 7. Production-readiness gap

What's in this folder is a prototype that got a handful of scenes working
correctly through interactive, by-hand debugging (render a frame, look at
it, fix, repeat). Before this could plug into the real storyboard/render
pipeline, it needs the same rigor the existing Manim path already has:

- A QA/retry loop — something like the vision critic used for generated
  images, but for bpy scenes (even just "does the exported glb have exactly
  one animation and does the bounding box look reasonable" as an automated
  gate would catch several of the bugs above).
- Broader shape/primitive coverage than the five helper functions built so
  far (`make_text`, `make_arrow`, `make_box`, `make_disc`, plus the
  billboard plane) — real Manim scenes use many more Mobject types.
- A fallback to flat/Manim when 3D generation fails or produces something
  visibly wrong, rather than shipping whatever came out.
- Cost/latency budgeting — each scene here cost one Sonnet 4.6 call
  (~$0.01-0.05 depending on scene complexity) plus render time; fine for
  hand-testing a handful of segments, not yet sized for full-catalog batch
  processing.
