import os
import sys
import json
import requests

BOILERPLATE_PATH = sys.argv[1]
OUTPUT_BLEND_PATH = sys.argv[2]
TOPIC = sys.argv[3]
OUT_PY_PATH = sys.argv[4]

boilerplate = open(BOILERPLATE_PATH, encoding="utf-8").read()
boilerplate = boilerplate.replace("<OUTPUT_BLEND_PATH>", OUTPUT_BLEND_PATH.replace("\\", "/"))

prompt = f"""Here is a fixed, already-debugged Blender Python (bpy) boilerplate file.
It defines animation helper functions (fade_in, fade_out, create_reveal, indicate,
make_text, make_arrow, make_material, keyframe_*, the _get_fcurves compatibility
shim for Blender 4.4+'s layered-actions system) and scene setup (engine, FPS,
background color, color constants BLUE/ORANGE/YELLOW/WHITE/GREEN).

Do NOT redefine, rewrite, or modify anything above the
">>> GENERATED CONTENT GOES BELOW THIS LINE <<<" marker. Do NOT change the
render engine string or re-implement any helper - use them exactly as defined.

--- BOILERPLATE (for reference only, do not repeat it in your answer) ---
{boilerplate}
--- END BOILERPLATE ---

Write ONLY the code that goes below that marker, for this topic:

TOPIC: {TOPIC}

Requirements:
- This is one segment of an educational physics video. Genuinely spatial/3D
  content is strongly preferred over flat 2D diagrams wherever physically
  real - e.g. force/velocity/acceleration vectors as 3D arrows in space,
  objects moving along real 3D paths, not everything flattened onto one
  plane facing the camera.
- Use make_arrow() for any vectors, make_text() for labels, fade_in/fade_out/
  create_reveal/indicate for animation beats - mirror how a Manim scene's
  self.play(...) calls would be sequenced (add a comment above each beat
  showing the Manim-equivalent call, like the boilerplate's own style).
- Add a Sun light and a Camera, and set scene.camera - frame the whole scene.
- Keep it to roughly 15-25 seconds of animation (t accumulates across beats).
- If any object needs constant/linear motion (no easing), call
  set_fcurve_easing(obj, "location", easing='AUTO', interpolation='LINEAR').
  Never pass easing='LINEAR' - kp.easing only accepts AUTO/EASE_IN/EASE_OUT/
  EASE_IN_OUT ('LINEAR' is a valid interpolation value, not an easing value,
  and passing it as easing raises a TypeError).
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
    timeout=120,
)
resp.raise_for_status()
data = resp.json()

if data.get("stop_reason") == "max_tokens":
    print("WARNING: response was truncated (stop_reason=max_tokens) - the script is likely incomplete (missing save_as_mainfile). Raise max_tokens and regenerate.")

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
