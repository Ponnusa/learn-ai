import os
import sys
import json
import requests

BOILERPLATE_PATH = sys.argv[1]
MANIM_SOURCE_PATH = sys.argv[2]
OUTPUT_BLEND_PATH = sys.argv[3]
OUT_PY_PATH = sys.argv[4]

boilerplate = open(BOILERPLATE_PATH, encoding="utf-8").read()
boilerplate = boilerplate.replace("<OUTPUT_BLEND_PATH>", OUTPUT_BLEND_PATH.replace("\\", "/"))
manim_source = open(MANIM_SOURCE_PATH, encoding="utf-8").read()

prompt = f"""Here is a fixed, already-debugged Blender Python (bpy) boilerplate file.
It defines animation helpers (fade_in, fade_out, create_reveal, indicate,
make_text, make_arrow, make_box, make_disc, the _get_fcurves compatibility
shim) and scene setup (engine, FPS, background color, color constants
BLUE/ORANGE/YELLOW/WHITE/GREEN).

Do NOT redefine, rewrite, or modify anything above the
">>> GENERATED CONTENT GOES BELOW THIS LINE <<<" marker. Do NOT change the
render engine string or re-implement any helper - use them exactly as defined.

--- BOILERPLATE (for reference only, do not repeat it in your answer) ---
{boilerplate}
--- END BOILERPLATE ---

Below is a REAL Manim scene from this project's video pipeline. Your job is
to PORT it faithfully to bpy using the boilerplate above - same objects,
same layout, same sequence of self.play() beats, same approximate colors and
timing (use each play's run_time where given; a wait() advances t with no
animation call). This is a faithful translation, not a reimagining - do not
invent new 3D flourishes or change the composition.

--- REAL MANIM SOURCE ---
{manim_source}
--- END MANIM SOURCE ---

Translation rules:
- Coordinate mapping: Manim's (x, y, 0) -> bpy (x, 0, y). Manim's Y axis
  (UP/DOWN) becomes bpy's Z (up); Manim's X (LEFT/RIGHT) stays bpy's X; bpy's
  Y (depth, toward/away from camera) stays 0 unless a small offset helps
  layering (e.g. -0.05 so a background circle doesn't z-fight a foreground
  shape at the same depth).
- Shape mapping: Rectangle/RoundedRectangle -> make_box(name, width, height,
  color) (corner radius is not modeled, that's fine). Circle -> make_disc
  (name, radius, color). DashedVMobject wrapping a Circle -> just make_disc,
  dashing isn't worth modeling. Line -> a thin make_box or a rotated
  make_arrow's shaft alone. Arrow -> make_arrow(start, end, color). Text ->
  make_text(body, location, size, color) (translate font_size roughly:
  Manim font_size 32 ~= make_text size 0.5, scale proportionally).
- Ignore anything voiceover/audio-related (set_speech_service, self.voiceover
  blocks, AzureService, VoiceoverScene) - this port is visuals only. Just
  unwrap the self.play(...) calls that were inside the voiceover `with`
  block and sequence them normally with self.wait()-equivalent gaps.
- VGroup - no direct bpy equivalent needed; just create and animate the
  member objects individually in the same relative positions.
- Manim named colors you'll see and their approximate RGB (0-1 range):
  WHITE=(1,1,1) GRAY=(0.5,0.5,0.5) LIGHT_GRAY=(0.7,0.7,0.7)
  DARK_BROWN=(0.25,0.15,0.1) GOLD=(0.83,0.69,0.22) TEAL=(0.2,0.7,0.65)
  YELLOW=(1,0.85,0) BLUE=(0.1,0.4,0.9) ORANGE=(0.95,0.5,0.1)
  GREEN=(0.2,0.9,0.3) RED=(0.9,0.2,0.2) or use this file's own BLUE/ORANGE/
  YELLOW/WHITE/GREEN constants where a close match exists.
- Add one Sun light and one Camera looking along +Y (matching the
  boilerplate's existing convention: camera at roughly (0, -12, 0),
  rotation_euler=(radians(90),0,0)), framed to fit the whole composition -
  widen the camera distance if the scene is wide (this one spans roughly
  x=-6 to x=4 based on the source's coordinates).
- If any object needs constant/linear motion, use
  set_fcurve_easing(obj, "location", easing='AUTO', interpolation='LINEAR')
  - never pass easing='LINEAR' (kp.easing only accepts AUTO/EASE_IN/
  EASE_OUT/EASE_IN_OUT).
- End with exactly:
    scene.frame_end = sec_to_frame(t) + 5
    scene.frame_current = 1
    bpy.ops.wm.save_as_mainfile(filepath="{OUTPUT_BLEND_PATH.replace(chr(92), '/')}")

Respond with ONLY the Python code (no markdown fences, no prose before or after)."""

resp = requests.post(
    "https://api.anthropic.com/v1/messages",
    headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    },
    json={
        "model": "claude-sonnet-4-6",
        "max_tokens": 8000,
        "messages": [{"role": "user", "content": prompt}],
    },
    timeout=180,
)
resp.raise_for_status()
data = resp.json()

if data.get("stop_reason") == "max_tokens":
    print("WARNING: response truncated (stop_reason=max_tokens) - likely incomplete.")

text = data["content"][0]["text"].strip()
if text.startswith("```"):
    text = text.split("```", 2)[1]
    if text.startswith("python"):
        text = text[len("python"):]
    text = text.strip()
    if text.endswith("```"):
        text = text[:-3].strip()

full_script = boilerplate + "\n" + text + "\n"
with open(OUT_PY_PATH, "w", encoding="utf-8") as f:
    f.write(full_script)

print(f"Usage: input={data['usage']['input_tokens']} output={data['usage']['output_tokens']}")
print(f"Wrote {OUT_PY_PATH} ({len(full_script)} chars)")
