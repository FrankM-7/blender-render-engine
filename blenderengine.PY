import bpy
import array
import gpu
from gpu_extras.presets import draw_texture_2d
from mathutils import Vector
import numpy as np

def corput(n, base):
    # generate a Van der Corput sequence between -0.5 and 0.5
    q, denom = 0, 1
    while n:
        denom *= base
        n, remainder = divmod(n, base)
        q += remainder / denom
    return q - 0.5

def ray_cast(scene, origin, direction):
    return scene.ray_cast(scene.view_layers[0].depsgraph, origin, direction)

def RT_trace_ray(scene, ray_orig, ray_dir):
    # First, we cast a ray into the scene using Blender's built-in function
    has_hit, hit_loc, hit_norm, _, hit_obj, _ = ray_cast(scene, ray_orig, ray_dir)

    # set initial color (black) for the pixel
    color = np.zeros(3)

    # if the ray hits nothing in the scene
    # return black
    if not has_hit:
        return color
    return np.array([1, 0.0, 0.0])


class CustomRenderEngine(bpy.types.RenderEngine):
    # These three members are used by blender to set up the
    # RenderEngine; define its internal name, visible name and capabilities.
    bl_idname = "CUSTOM"
    bl_label = "Custom"
    bl_use_preview = True

    # Init is called whenever a new render engine instance is created. Multiple
    # instances may exist at the same time, for example for a viewport and final
    # render.
    def __init__(self):
        self.scene_data = None
        self.draw_data = None

    # When the render engine instance is destroy, this is called. Clean up any
    # render engine data here, for example stopping running render threads.
    def __del__(self):
        pass

    # This is the method called by Blender for both final renders (F12) and
    # small preview for materials, world and lights.
    def render(self, depsgraph):
        scene = depsgraph.scene
        scale = scene.render.resolution_percentage / 100.0
        self.size_x = int(scene.render.resolution_x * scale)
        self.size_y = int(scene.render.resolution_y * scale)

        sample_count = 1
        width = int(scene.render.resolution_x * scale)
        height = int(scene.render.resolution_y * scale)

        focal_length = scene.camera.data.lens / scene.camera.data.sensor_width
        aspect_ratio = height / width
        dx = 1 / width
        dy = aspect_ratio / height
        corput_x = [corput(i, 2) * dx for i in range(sample_count)]
        corput_y = [corput(i, 3) * dy for i in range(sample_count)]
        cam_location = scene.camera.location
        cam_orientation = scene.camera.rotation_euler

        color = [0, 0, 0, 1.0]

        pixel_count = self.size_x * self.size_y
        rect = [color] * pixel_count

        max_x = -20
        min_x = 20

        for s in range(sample_count):
            for y in range(self.size_y):
                screen_y = ((y - (height / 2)) / height) * aspect_ratio
                
                for x in range(self.size_x):
                    screen_x = (x - (width / 2)) / width

                    ray_dir = Vector((screen_x + corput_x[s], screen_y + corput_y[s], -focal_length))
                    ray_dir.rotate(cam_orientation)
                    ray_dir = ray_dir.normalized()

                    color = RT_trace_ray(scene, cam_location, ray_dir)

                    # create a ray
                    r, g, b = color[0], color[1], color[2]
                    rect[y*self.size_x + x] = [r, g, b, 1.0]   
                    
        # Here we write the pixel values to the RenderResult
        result = self.begin_result(0, 0, self.size_x, self.size_y)
        layer = result.layers[0].passes["Combined"]
        layer.rect = rect
        self.end_result(result)


class CustomDrawData:
    def __init__(self, dimensions):
        # Generate dummy float image buffer
        self.dimensions = dimensions
        width, height = dimensions

        pixels = width * height * array.array('f', [0.1, 0.2, 0.1, 1.0])
        pixels = gpu.types.Buffer('FLOAT', width * height * 4, pixels)

        # Generate texture
        self.texture = gpu.types.GPUTexture((width, height), format='RGBA16F', data=pixels)

        # Note: This is just a didactic example.
        # In this case it would be more convenient to fill the texture with:
        # self.texture.clear('FLOAT', value=[0.1, 0.2, 0.1, 1.0])

    def __del__(self):
        del self.texture

    def draw(self):
        draw_texture_2d(self.texture, (0, 0), self.texture.width, self.texture.height)


# RenderEngines also need to tell UI Panels that they are compatible with.
# We recommend to enable all panels marked as BLENDER_RENDER, and then
# exclude any panels that are replaced by custom panels registered by the
# render engine, or that are not supported.
def get_panels():
    exclude_panels = {
        'VIEWLAYER_PT_filter',
        'VIEWLAYER_PT_layer_passes',
    }

    panels = []
    for panel in bpy.types.Panel.__subclasses__():
        if hasattr(panel, 'COMPAT_ENGINES') and 'BLENDER_RENDER' in panel.COMPAT_ENGINES:
            if panel.__name__ not in exclude_panels:
                panels.append(panel)

    return panels


def register():
    # Register the RenderEngine
    bpy.utils.register_class(CustomRenderEngine)

    for panel in get_panels():
        panel.COMPAT_ENGINES.add('CUSTOM')


def unregister():
    bpy.utils.unregister_class(CustomRenderEngine)

    for panel in get_panels():
        if 'CUSTOM' in panel.COMPAT_ENGINES:
            panel.COMPAT_ENGINES.remove('CUSTOM')


if __name__ == "__main__":
    register()