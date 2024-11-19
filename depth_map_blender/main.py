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

class M2FormProperties(PropertyGroup):
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
        target_object: PointerProperty(
        name="Target Object",
        type=bpy.types.Object,
        description="Object to apply effects to"
    )

class M2FORM_OT_create_mesh(Operator):
    bl_idname = "m2form.create_mesh"
    bl_label = "Create 3D Mesh"
    bl_description = "Convert depth map to 3D mesh"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.m2form_props
        
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
        mat = bpy.data.materials.new(name="m2Form_Material")
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

class M2FORM_PT_main_panel(Panel):
    bl_label = "m2Form"
    bl_idname = "M2FORM_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'm2Form'
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.m2form_props
        
        # Title and Open Image button
        row = layout.row()
        row.label(text="m2Form")
        row.operator("m2form.open_image", text="Open Image")
        
        # Main Inputs
        box = layout.box()
        box.label(text="Main Inputs")
        box.prop(props, "depth_map_path", text="Depth Map")
        box.prop(props, "image_path", text="Image")
        box.prop(props, "target_object", text="Target Object")
        
        # Mesh View
        box = layout.box()
        box.label(text="Mesh View")
        row = box.row(align=True)
        row.operator("m2form.view_front", text="Front")
        row.operator("m2form.view_side", text="Side")
        row.operator("m2form.view_top", text="Top")
        
        box.prop(props, "subdivision_level", text="Subdivision Levels")
        box.prop(props, "smoothing_factor", text="Smooth Factor")
        box.prop(props, "depth_strength", text="Depth Strength")
        
        # Material Properties
        box = layout.box()
        box.label(text="Material Properties")
        box.prop(props, "metallic")
        box.prop(props, "roughness")
        box.prop(props, "ior")
        
        # Apply button
        layout.operator("m2form.create_mesh", text="Apply Depth Map")

classes = (
    M2FormProperties,
    M2FORM_OT_create_mesh,
    M2FORM_OT_view_front,
    M2FORM_OT_view_side,
    M2FORM_OT_view_top,
    M2FORM_PT_main_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.m2form_props = bpy.props.PointerProperty(type=M2FormProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.m2form_props

if __name__ == "__main__":
    register()
