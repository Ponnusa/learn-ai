import bpy
import math
from mathutils import Vector

FPS = 24
bpy.context.scene.render.fps = FPS

def sec_to_frame(seconds):
    return int(seconds * FPS)

# --- clean scene ---
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start = 1
scene.render.engine = 'BLENDER_EEVEE'  # realtime alpha blending in viewport

# =========================================================
# HELPERS (glTF-safe: scale-based visibility, not alpha - glTF's core spec
# can't animate material opacity, only object transforms. See make_material/
# fade_in/fade_out/create_reveal below.)
# =========================================================

def make_material(name, color, alpha=1.0):
    # alpha kept in the signature for call compatibility but ignored - always
    # fully opaque, so nothing gets stuck invisible after export.
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color[:3], 1.0)
    bsdf.inputs["Alpha"].default_value = 1.0
    return mat

def keyframe_alpha(mat, frame, alpha):
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Alpha"].default_value = alpha
    bsdf.inputs["Alpha"].keyframe_insert(data_path="default_value", frame=frame)

def keyframe_color(mat, frame, color):
    """Handles both material types this file creates: the Principled BSDF
    used by 3D shapes, and the Emission shader used by text (make_text) -
    indicate() can be called on either (e.g. flashing a text label)."""
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color[:3], 1.0)
        bsdf.inputs["Base Color"].keyframe_insert(data_path="default_value", frame=frame)
        return
    emission = mat.node_tree.nodes.get("Emission")
    if emission:
        emission.inputs["Color"].default_value = (*color[:3], 1.0)
        emission.inputs["Color"].keyframe_insert(data_path="default_value", frame=frame)

def keyframe_loc(obj, frame):
    obj.keyframe_insert(data_path="location", frame=frame)

def keyframe_scale(obj, frame):
    obj.keyframe_insert(data_path="scale", frame=frame)

def _get_fcurves(id_data):
    """Compatibility shim: Blender 4.4+ moved fcurves under layers/strips/channelbags
    (the 'layered actions' system). Fall back to that path if the old
    action.fcurves attribute isn't available."""
    anim = id_data.animation_data
    if not anim or not anim.action:
        return []
    action = anim.action
    if hasattr(action, "fcurves"):
        return action.fcurves
    try:
        slot = anim.action_slot
        fcurves = []
        for layer in action.layers:
            for strip in layer.strips:
                channelbag = strip.channelbag(slot, ensure=True)
                if channelbag:
                    fcurves.extend(channelbag.fcurves)
        return fcurves
    except Exception:
        return []

def set_fcurve_easing(id_data, data_path, easing='EASE_IN_OUT', interpolation='BEZIER'):
    """Apply easing to all keyframes on a given data_path (object or material node-tree).
    NOTE: kp.easing only accepts AUTO/EASE_IN/EASE_OUT/EASE_IN_OUT - never pass
    'LINEAR' as the easing value (that's a valid interpolation value, not an
    easing value). For linear motion use interpolation='LINEAR', easing='AUTO'."""
    for fc in _get_fcurves(id_data):
        if fc.data_path == data_path:
            for kp in fc.keyframe_points:
                kp.interpolation = interpolation
                kp.easing = easing

def fade_in(obj, mat, start_frame, end_frame, shift_vec, target_alpha=1.0, easing='EASE_IN_OUT'):
    """glTF-safe: scale-based reveal (0.001 -> 1) instead of alpha, since
    scale is a transform and actually survives glTF export. mat/target_alpha
    kept in the signature for compatibility but unused here."""
    final_loc = obj.location.copy()
    start_loc = (final_loc[0] - shift_vec[0], final_loc[1] - shift_vec[1], final_loc[2] - shift_vec[2])

    obj.location = start_loc
    keyframe_loc(obj, start_frame)
    obj.scale = (0.001, 0.001, 0.001)
    keyframe_scale(obj, start_frame)

    obj.location = final_loc
    keyframe_loc(obj, end_frame)
    obj.scale = (1, 1, 1)
    keyframe_scale(obj, end_frame)

    set_fcurve_easing(obj, "location", easing)
    set_fcurve_easing(obj, "scale", easing)

def fade_out(obj, mat, start_frame, end_frame, shift_vec, start_alpha=1.0, easing='EASE_IN'):
    """glTF-safe: scale-based hide (1 -> 0.001) instead of alpha."""
    start_loc = obj.location.copy()
    end_loc = (start_loc[0] + shift_vec[0], start_loc[1] + shift_vec[1], start_loc[2] + shift_vec[2])

    obj.location = start_loc
    keyframe_loc(obj, start_frame)
    obj.scale = (1, 1, 1)
    keyframe_scale(obj, start_frame)

    obj.location = end_loc
    keyframe_loc(obj, end_frame)
    obj.scale = (0.001, 0.001, 0.001)
    keyframe_scale(obj, end_frame)

    set_fcurve_easing(obj, "location", easing)
    set_fcurve_easing(obj, "scale", easing)

def make_text(body, location, size=0.4, color=(1, 1, 1), alpha=1.0):
    bpy.ops.object.text_add(location=location)
    txt = bpy.context.active_object
    txt.data.body = body
    txt.data.size = size
    txt.data.extrude = 0.015
    txt.data.align_x = 'CENTER'
    txt.data.align_y = 'CENTER'
    # face the camera (camera looks along +Y; text default lies flat in XY, so
    # rotate 90 deg about X to stand it upright in the XZ plane)
    txt.rotation_euler = (math.radians(90), 0, 0)

    # Emissive material, not the physically-lit make_material() every other
    # shape uses - text needs to read clearly regardless of scene lighting.
    # A Sun-lit white Principled BSDF surface, combined with Blender's
    # default AgX color management lifting the near-black background into a
    # washed-out gray, left text nearly illegible (very low contrast either
    # way you look at it).
    mat = bpy.data.materials.new(name=f"mat_{body}_{id(txt)}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*color[:3], 1.0)
    emission.inputs["Strength"].default_value = 2.0
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    txt.data.materials.append(mat)

    bpy.context.view_layer.objects.active = txt
    bpy.ops.object.convert(target='MESH')
    return txt, mat

def make_arrow(start, end, color=(1, 1, 0), radius=0.05):
    direction = Vector([end[i] - start[i] for i in range(3)])
    length = direction.length
    mid = [(start[i] + end[i]) / 2 for i in range(3)]

    bpy.ops.object.empty_add(location=mid)
    parent = bpy.context.active_object
    parent.name = "ArrowGroup"
    # Point the (default Z-aligned) cylinder/cone children along `direction`
    # using Blender's own direction-to-rotation math, not a hand-rolled
    # atan2(y,x) formula - that only accounts for the X/Y components and
    # silently gives the wrong orientation for any arrow with a Z tilt
    # (which is most of them, since arrows live in the X-Z plane here).
    parent.rotation_mode = 'QUATERNION'
    parent.rotation_quaternion = direction.to_track_quat('Z', 'Y')

    # Children are positioned as LOCAL Z-axis offsets (the axis the rotation
    # above aligns to `direction`) - NOT world coordinates, and with no
    # matrix_parent_inverse override (Blender's real default for a plain
    # `.parent = X` assignment is identity, which is what we want here).
    # matrix_parent_inverse CANCELS the parent's rotation as seen from the
    # child - exactly the wrong tool when the goal is for children to
    # inherit that rotation, which is the actual mechanism that points a
    # default Z-aligned cylinder/cone along an arbitrary direction. Shaft
    # sits at the parent's own origin (offset 0); head sits further out
    # along local Z by the same 0.42-of-length fraction as before.
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=length * 0.85, location=(0, 0, 0))
    shaft = bpy.context.active_object
    shaft.parent = parent

    bpy.ops.mesh.primitive_cone_add(radius1=radius * 2.2, depth=length * 0.18, location=(0, 0, length * 0.42))
    head = bpy.context.active_object
    head.parent = parent

    mat = make_material(f"arrow_mat_{id(parent)}", color, alpha=0.0)  # starts invisible for Create
    shaft.data.materials.append(mat)
    head.data.materials.append(mat)

    return parent, mat

def create_reveal(obj, mat, start_frame, end_frame, target_color, easing='EASE_IN_OUT'):
    """glTF-safe: scale-only (no alpha keyframes - scale already fully hides
    the object at 0.001, so alpha adds nothing exportable).
    KNOWN LIMITATION: collapses local X ("width"), not local Z (the true
    length axis for an ArrowGroup per make_arrow's to_track_quat rotation).
    For arrows this means the shaft doesn't visibly grow along its length -
    it's at full length from frame 1, just briefly pinched in cross-section.
    Never fixed since it wasn't the reported bug; if you need a real
    "drawing itself" reveal for an arrow, collapse local Z instead of local
    X when `obj` is an ArrowGroup."""
    obj.scale = (0.001, 1, 1)  # collapse along local length axis
    keyframe_scale(obj, start_frame)

    obj.scale = (1, 1, 1)
    keyframe_scale(obj, end_frame)

    set_fcurve_easing(obj, "scale", easing)

def indicate(obj, mat, start_frame, end_frame, base_color, flash_color=(0.2, 0.9, 0.3), scale_factor=1.15):
    """Mirrors Manim's Indicate(): scale up + color flash to `flash_color`, then back.
    (Color flash may not survive glTF export - the scale pulse is what's guaranteed to show.)"""
    mid_frame = (start_frame + end_frame) // 2

    obj.scale = (1, 1, 1)
    keyframe_scale(obj, start_frame)
    keyframe_color(mat, start_frame, base_color)

    obj.scale = (scale_factor, scale_factor, scale_factor)
    keyframe_scale(obj, mid_frame)
    keyframe_color(mat, mid_frame, flash_color)

    obj.scale = (1, 1, 1)
    keyframe_scale(obj, end_frame)
    keyframe_color(mat, end_frame, base_color)

    set_fcurve_easing(obj, "scale", 'EASE_IN_OUT')

def make_box(name, width, height, color, depth=0.15):
    """Maps Manim's Rectangle/RoundedRectangle (corner radius not modeled,
    close enough for a quick 3D port). location is set by the caller after
    creation, same as every other make_* helper here."""
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (width / 2, depth / 2, height / 2)
    mat = make_material(f"{name}_mat", color)
    obj.data.materials.append(mat)
    return obj, mat

def make_disc(name, radius, color, depth=0.05):
    """Maps Manim's Circle (filled). A short cylinder standing in the XZ
    plane, matching this file's Manim-Y-becomes-bpy-Z coordinate convention."""
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth)
    obj = bpy.context.active_object
    obj.name = name
    obj.rotation_euler = (math.radians(90), 0, 0)
    mat = make_material(f"{name}_mat", color)
    obj.data.materials.append(mat)
    return obj, mat

# =========================================================
# SCENE BUILD
# =========================================================

BLUE = (0.1, 0.4, 0.9)
ORANGE = (0.95, 0.5, 0.1)
YELLOW = (1.0, 0.85, 0.0)
WHITE = (1.0, 1.0, 1.0)
GREEN = (0.2, 0.9, 0.3)

# background color (ManimColor "#0D1117")
scene.world = bpy.data.worlds.new("Background")
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0x0D / 255, 0x11 / 255, 0x17 / 255, 1.0)

# =========================================================
# >>> GENERATED CONTENT GOES BELOW THIS LINE <<<
# Add: objects for this segment's content, a Sun light + Camera (scene.camera
# must be set), then a TIMELINE section (t = 0.0; ...; each self.play()-style
# beat advances t), ending with:
#   scene.frame_end = sec_to_frame(t) + 5
#   scene.frame_current = 1
#   bpy.ops.wm.save_as_mainfile(filepath="<OUTPUT_BLEND_PATH>")
# =========================================================
