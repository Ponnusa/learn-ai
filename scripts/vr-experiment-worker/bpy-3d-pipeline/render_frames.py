import bpy
import sys

frames = [int(x) for x in sys.argv[-1].split(",")]
out_dir = sys.argv[-2]
scene = bpy.context.scene
scene.render.resolution_x = 960
scene.render.resolution_y = 540
scene.render.resolution_percentage = 100
scene.render.image_settings.media_type = 'IMAGE'
scene.render.image_settings.file_format = 'PNG'
for f in frames:
    scene.frame_current = f
    scene.render.filepath = f"{out_dir}/frame_{f}.png"
    bpy.ops.render.render(write_still=True)
    print(f"Rendered frame {f}")
