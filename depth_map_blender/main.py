bl_info = {
    "name": "zForm - Depth Map to 3D Mesh",
    "author": "Assistant",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > zForm",
    "description": "Convert depth maps and images to 3D meshes",
    "category": "3D View",
}

import bpy
import os
from bpy.props import (
    StringProperty,
    FloatProperty,
    IntProperty,
    EnumProperty,
    BoolProperty
)
from bpy.types import (
    Panel,
    Operator,
    PropertyGroup,
)

class ZFormProperties(PropertyGroup):
    image_path: StringProperty(
        name="Image",
        description="Path to the base image",
        default="",
        maxlen=1024,
        subtype='FILE_PATH'
    )
    
    depth_map_path: StringProperty(
        name="Depth Map",
        description="Path to the depth map image",
        default="",
        maxlen=1024,
        subtype='FILE_PATH'
    )
    
    subdivision_level: IntProperty(
        name="Subdivision Level",
        description="Level of mesh subdivision",
        default=32,
        min=1,
        max=256
    )
    
    depth_strength: FloatProperty(
        name="Depth Strength",
        description="Strength of the depth effect",
        default=1.0,
        min=0.0,
        max=10.0
    )
    
    smoothing_factor: FloatProperty(
        name="Smoothing",
        description="Amount of mesh smoothing",
        default=0.5,
        min=0.0,
        max=1.0
    )
    
    metallic: FloatProperty(
        name="Metallic",
        description="Material metallic value",
        default=0.0,
        min=0.0,
        max=1.0
    )
    
    roughness: FloatProperty(
        name="Roughness",
        description="Material roughness value",
        default=0.5,
        min=0.0,
        max=1.0
    )
    
    ior: FloatProperty(
        name="IOR",
        description="Index of Refraction",
        default=1.45,
        min=1.0,
        max=3.0
    )

class ZFORM_OT_create_mesh(Operator):
    bl_idname = "zform.create_mesh"
    bl_label = "Create 3D Mesh"
    bl_description = "Convert depth map to 3D mesh"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.zform_props
        
        # Create plane
        bpy.ops.mesh.primitive_plane_add(size=2)
        obj = context.active_object
        
        # Add subdivision modifier
        subdiv = obj.modifiers.new(name="Subdivision", type='SUBSURF')
        subdiv.levels = props.subdivision_level
        subdiv.render_levels = props.subdivision_level
        
        # Add displacement modifier
        displace = obj.modifiers.new(name="Displacement", type='DISPLACE')
        
        # Load and apply depth map texture
        if props.depth_map_path:
            depth_tex = bpy.data.textures.new(name="Depth", type='IMAGE')
            depth_img = bpy.data.images.load(props.depth_map_path)
            depth_tex.image = depth_img
            displace.texture = depth_tex
            displace.strength = props.depth_strength
        
        # Create material
        mat = bpy.data.materials.new(name="zForm_Material")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        # Clear default nodes
        nodes.clear()
        
        # Create nodes
        node_principled = nodes.new('ShaderNodeBsdfPrincipled')
        node_output = nodes.new('ShaderNodeOutputMaterial')
        
        # Load and apply base image texture
        if props.image_path:
            node_tex = nodes.new('ShaderNodeTexImage')
            img = bpy.data.images.load(props.image_path)
            node_tex.image = img
            links.new(node_tex.outputs['Color'], node_principled.inputs['Base Color'])
        
        # Connect nodes
        links.new(node_principled.outputs['BSDF'], node_output.inputs['Surface'])
        
        # Set material properties
        node_principled.inputs['Metallic'].default_value = props.metallic
        node_principled.inputs['Roughness'].default_value = props.roughness
        node_principled.inputs['IOR'].default_value = props.ior
        
        # Assign material to object
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
        
        # Apply smooth shading
        bpy.ops.object.shade_smooth()
        obj.data.use_auto_smooth = True
        obj.data.auto_smooth_angle = props.smoothing_factor * 3.14159
        
        return {'FINISHED'}

class ZFORM_PT_main_panel(Panel):
    bl_label = "zForm"
    bl_idname = "ZFORM_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'zForm'
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.zform_props
        
        # File inputs
        layout.label(text="Input Files:")
        layout.prop(props, "image_path")
        layout.prop(props, "depth_map_path")
        
        # Mesh settings
        layout.label(text="Mesh Settings:")
        layout.prop(props, "subdivision_level")
        layout.prop(props, "depth_strength")
        layout.prop(props, "smoothing_factor")
        
        # Material settings
        layout.label(text="Material Settings:")
        layout.prop(props, "metallic")
        layout.prop(props, "roughness")
        layout.prop(props, "ior")
        
        # Create button
        layout.separator()
        layout.operator("zform.create_mesh", text="Create 3D Mesh")

classes = (
    ZFormProperties,
    ZFORM_OT_create_mesh,
    ZFORM_PT_main_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.zform_props = bpy.props.PointerProperty(type=ZFormProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.zform_props

if __name__ == "__main__":
    register()