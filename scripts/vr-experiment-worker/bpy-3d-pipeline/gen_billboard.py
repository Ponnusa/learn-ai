"""
Generate a bpy script for a static image billboard (no LLM call needed -
deterministic). Used for image/nano-banana segments, which don't need 3D
content, just a correctly-sized, correctly-lit textured plane on screen for
the segment's real duration.

Usage: python gen_billboard.py <boilerplate.py> <segment.json> <image.png> <out.blend> <out.py>

segment.json is the segment metadata as returned by the vr-experiment
endpoint (needs actual_duration_seconds or target_duration_seconds).
"""
import json
import sys

try:
    from PIL import Image
except ImportError:
    Image = None

BOILERPLATE_PATH = sys.argv[1]
SEG_JSON_PATH = sys.argv[2]
IMAGE_PATH = sys.argv[3]
OUT_BLEND_PATH = sys.argv[4]
OUT_PY_PATH = sys.argv[5]

seg = json.load(open(SEG_JSON_PATH, encoding="utf-8"))
duration = seg.get("actual_duration_seconds") or seg.get("target_duration_seconds") or 8.0

if Image is not None:
    img_w, img_h = Image.open(IMAGE_PATH).size
else:
    print("WARNING: Pillow not installed - assuming 16:9 (1280x720). "
          "pip install pillow for correct aspect ratio.")
    img_w, img_h = 1280, 720

boilerplate = open(BOILERPLATE_PATH, encoding="utf-8").read()
boilerplate = boilerplate.replace("<OUTPUT_BLEND_PATH>", OUT_BLEND_PATH.replace("\\", "/"))

image_path_fwd = IMAGE_PATH.replace("\\", "/")

scene_code = f'''
def make_image_material(name, image_path):
    """Textured material for billboard image segments - uses an Emission
    shader, not the Principled BSDF's Base Color, so the image displays at
    its own natural brightness (like a screen showing it) instead of being
    physically lit by the scene's Sun lamp (which made a deliberately dim
    period photo look almost black)."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    tex_node = nodes.new("ShaderNodeTexImage")
    tex_node.image = bpy.data.images.load(image_path)
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Strength"].default_value = 1.0
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(tex_node.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat

# --- Billboard plane (image aspect ratio {img_w}x{img_h}) ---
# Size is baked into the MESH (not object.scale) - fade_in/fade_out hardcode
# scale targets of (0.001,0.001,0.001) and (1,1,1), so a custom object.scale
# here would get silently overwritten the moment either is called, shrinking
# the billboard down to a near-invisible speck right as it finishes fading in.
import mathutils
ASPECT = {img_w} / {img_h}
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 0, 0))
plane = bpy.context.active_object
plane.name = "Billboard"
plane.data.transform(mathutils.Matrix.Diagonal((ASPECT * 3.0, 3.0, 1.0, 1.0)))
plane.rotation_euler = (math.radians(90), 0, 0)  # stand upright facing -Y camera
# Default plane UVs (axis-aligned 0-1 square, generated at creation) are left
# as-is - an explicit smart_project() re-unwrap rotated the texture 90 deg
# in testing, since it optimizes layout rather than preserving orientation.

img_mat = make_image_material("BillboardMat", "{image_path_fwd}")
plane.data.materials.append(img_mat)

# --- Sun light + camera ---
bpy.ops.object.light_add(type='SUN', location=(2, -4, 4))
bpy.context.active_object.data.energy = 3

bpy.ops.object.camera_add(location=(0, -9, 0))
cam = bpy.context.active_object
cam.rotation_euler = (math.radians(90), 0, 0)
scene.camera = cam

# --- Static hold for the segment's real on-screen duration. No scale
# animation - a growing/shrinking bounding box confuses model-viewer's
# auto-framing (it recomputes "ideal" camera distance as the model's bounds
# change), which is what made the billboard look zoomed-out/mis-framed even
# with explicit camera-orbit/field-of-view set. A constant-size static plane
# keeps the bounding box (and therefore the framing) stable throughout. ---
t = {duration}

scene.frame_end = sec_to_frame(t) + 5
scene.frame_current = 1
bpy.ops.wm.save_as_mainfile(filepath="{OUT_BLEND_PATH.replace(chr(92), '/')}")
'''

full_script = boilerplate + scene_code
with open(OUT_PY_PATH, "w", encoding="utf-8") as f:
    f.write(full_script)
print(f"Wrote {OUT_PY_PATH} (duration={duration:.1f}s, aspect={img_w}x{img_h})")
