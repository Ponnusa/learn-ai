"""
Export the currently-open .blend to a single-animation .glb.

Usage: blender.exe --background <scene>.blend --python export_glb.py -- <out.glb>
"""
import bpy
import sys

out_path = sys.argv[-1]

bpy.ops.export_scene.gltf(
    filepath=out_path,
    export_format='GLB',
    export_animations=True,
    # Bake ALL objects into one combined clip, not one clip per object.
    # Blender's default (ACTIONS) exports a separate glTF animation per
    # object; viewers that autoplay only the first clip (e.g. <model-viewer>)
    # then animate just one object and leave everything else frozen at its
    # frame-1 pose. ACTIVE_ACTIONS merges every currently-assigned action
    # into a single glTF animation instead.
    export_animation_mode='ACTIVE_ACTIONS',
    export_frame_range=True,
    export_frame_step=1,
    export_force_sampling=True,
)
print(f"Exported to {out_path}")
