bl_info = {
    "name": "m2Form - Depth Map to 3D Mesh",
    "author": "Assistant",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > m2Form",
    "description": "Convert depth maps and images to 3D meshes",
    "category": "3D View",
}

import bpy
import os
from bpy.props import (StringProperty, FloatProperty, IntProperty, 
                      EnumProperty, BoolProperty, PointerProperty)
from bpy.types import Panel, Operator, PropertyGroup
from bpy_extras.io_utils import ImportHelper

# Properties
class M2FormProperties(PropertyGroup):
    image_path: StringProperty(
        name="Base Image",
        description="Choose your 2D image",
        default="",
        maxlen=1024,
        subtype='FILE_PATH'
    )
    
    depth_map_path: StringProperty(
        name="Depth Map",
        description="Choose the depth map for your image",
        default="",
        maxlen=1024,
        subtype='FILE_PATH'
    )
    
    subdivision_level: IntProperty(
        name="Subdivision",
        description="Level of mesh detail (higher values = more detail)",
        default=8,  # Changed to match video's preferred default
        min=1,
        max=32
    )
    
    depth_strength: FloatProperty(
        name="Depth",
        description="Strength of the depth effect (1.0 = normal, 2.0 = enhanced)",
        default=1.0,  # Video shows 1.0 works best for most cases
        min=0.0,
        max=2.0,
        precision=2
    )
    
    smoothing_factor: FloatProperty(
        name="Smooth",
        description="Amount of mesh smoothing",
        default=0.8,  # Changed based on video demonstration
        min=0.0,
        max=1.0,
        precision=2
    )

class M2FORM_OT_choose_image(Operator, ImportHelper):
    bl_idname = "m2form.choose_image"
    bl_label = "Choose Image"
    
    filter_glob: StringProperty(
        default='*.jpg;*.jpeg;*.png;*.tif;*.tiff',
        options={'HIDDEN'}
    )
    
    is_depth_map: BoolProperty(
        name="Is Depth Map",
        description="Whether this is a depth map or base image",
        default=False
    )
    
    def execute(self, context):
        props = context.scene.m2form_props
        if self.is_depth_map:
            props.depth_map_path = self.filepath
        else:
            props.image_path = self.filepath
        return {'FINISHED'}

class M2FORM_OT_create_mesh(Operator):
    bl_idname = "m2form.create_mesh"
    bl_label = "Apply Depth Map"
    bl_description = "Convert your image and depth map to 3D mesh"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        props = context.scene.m2form_props
        return props.depth_map_path != "" and props.image_path != ""
    
    def execute(self, context):
        try:
            props = context.scene.m2form_props
            
            # Check for input files
            if not os.path.exists(bpy.path.abspath(props.depth_map_path)):
                self.report({'ERROR'}, "Please select a depth map")
                return {'CANCELLED'}
            
            if not os.path.exists(bpy.path.abspath(props.image_path)):
                self.report({'ERROR'}, "Please select a base image")
                return {'CANCELLED'}
            
            # Create new plane
            bpy.ops.mesh.primitive_plane_add(size=2)
            obj = context.active_object
            
            # Add subdivision modifier
            subdiv = obj.modifiers.new(name="Subdivision", type='SUBSURF')
            subdiv.levels = props.subdivision_level
            subdiv.render_levels = props.subdivision_level
            subdiv.quality = 3  # Higher quality subdivisions
            
            # Add displacement modifier
            displace = obj.modifiers.new(name="Displacement", type='DISPLACE')
            
            # Load and apply depth map texture
            depth_tex = bpy.data.textures.new(name="Depth", type='IMAGE')
            depth_img = bpy.data.images.load(bpy.path.abspath(props.depth_map_path))
            depth_tex.image = depth_img
            displace.texture = depth_tex
            displace.strength = props.depth_strength
            displace.mid_level = 0.5  # Center the displacement
            
            # Create material
            mat = bpy.data.materials.new(name="m2Form_Material")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            
            # Clear default nodes
            nodes.clear()
            
            # Create nodes
            node_tex = nodes.new('ShaderNodeTexImage')
            node_principled = nodes.new('ShaderNodeBsdfPrincipled')
            node_output = nodes.new('ShaderNodeOutputMaterial')
            
            # Load and apply base image texture
            img = bpy.data.images.load(bpy.path.abspath(props.image_path))
            node_tex.image = img
            
            # Connect nodes
            links.new(node_tex.outputs['Color'], node_principled.inputs['Base Color'])
            links.new(node_principled.outputs['BSDF'], node_output.inputs['Surface'])
            
            # Position nodes nicely
            node_tex.location = (-300, 300)
            node_principled.location = (0, 300)
            node_output.location = (300, 300)
            
            # Assign material
            obj.data.materials.clear()
            obj.data.materials.append(mat)
            
            # Apply smooth shading
            bpy.ops.object.shade_smooth()
            obj.data.use_auto_smooth = True
            obj.data.auto_smooth_angle = props.smoothing_factor * 3.14159
            
            # Set up optimal view
            bpy.ops.view3d.view_axis(type='FRONT')
            bpy.ops.view3d.view_selected(use_all_regions=False)
            
            self.report({'INFO'}, "3D mesh created successfully")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
            return {'CANCELLED'}

class M2FORM_PT_main_panel(Panel):
    bl_label = "m2Form"
    bl_idname = "M2FORM_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'm2Form'
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.m2form_props
        
        # Base Image Selection
        box = layout.box()
        row = box.row()
        row.prop(props, "image_path", text="Base Image")
        row.operator("m2form.choose_image", text="", icon='FILE_FOLDER').is_depth_map = False
        
        # Depth Map Selection
        row = box.row()
        row.prop(props, "depth_map_path", text="Depth Map")
        row.operator("m2form.choose_image", text="", icon='FILE_FOLDER').is_depth_map = True
        
        # Settings
        box = layout.box()
        box.prop(props, "subdivision_level")
        box.prop(props, "smoothing_factor")
        box.prop(props, "depth_strength")
        
        # Apply button
        layout.operator("m2form.create_mesh", text="Apply Depth Map", icon='MESH_DATA')

classes = (
    M2FormProperties,
    M2FORM_OT_choose_image,
    M2FORM_OT_create_mesh,
    M2FORM_PT_main_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.m2form_props = PointerProperty(type=M2FormProperties)

def unregister():
    del bpy.types.Scene.m2form_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
