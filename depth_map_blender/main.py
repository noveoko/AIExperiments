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
from bpy.props import (StringProperty, FloatProperty, IntProperty, 
                      EnumProperty, BoolProperty, PointerProperty)
from bpy.types import Panel, Operator, PropertyGroup

# Properties
class M2FormProperties(PropertyGroup):
      image_path: StringProperty(
        name="Image",
        subtype='FILE_PATH',
        # Add filter
        filter_glob='*.jpg;*.jpeg;*.png;*.tif;*.tiff'
    )
    depth_map_path: StringProperty(
        name="Depth Map",
        subtype='FILE_PATH'
    )
    target_object: PointerProperty(
        name="Target Object",
        type=bpy.types.Object
    )
    subdivision_level: IntProperty(
        name="Subdivision Level",
        default=32,
        min=1,
        max=256
    )
    depth_strength: FloatProperty(
        name="Depth Strength",
        default=1.0,
        min=0.0,
        max=10.0
    )
    smoothing_factor: FloatProperty(
        name="Smoothing",
        default=0.5,
        min=0.0,
        max=1.0
    )
    metallic: FloatProperty(
        name="Metallic",
        default=0.0,
        min=0.0,
        max=1.0
    )
    roughness: FloatProperty(
        name="Roughness",
        default=0.5,
        min=0.0,
        max=1.0
    )
    ior: FloatProperty(
        name="IOR",
        default=1.45,
        min=1.0,
        max=3.0
    )

# Operators
class M2FORM_OT_open_image(Operator):
    bl_idname = "m2form.open_image"
    bl_label = "Open Image"
    
    filepath: StringProperty(subtype='FILE_PATH')
    
    def execute(self, context):
        # Currently opens preferences, should open file browser instead
        bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
        return {'FINISHED'}

class M2FORM_OT_create_mesh(Operator):
    bl_idname = "m2form.create_mesh"
    bl_label = "Create 3D Mesh"
    bl_description = "Convert depth map to 3D mesh"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.m2form_props
        obj = props.target_object or context.active_object
        
        if not obj:
            self.report({'ERROR'}, "No target object selected")
            return {'CANCELLED'}
            
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

class M2FORM_OT_view_front(Operator):
    bl_idname = "m2form.view_front"
    bl_label = "Front"
    
    def execute(self, context):
        bpy.ops.view3d.view_axis(type='FRONT')
        return {'FINISHED'}

class M2FORM_OT_view_side(Operator):
    bl_idname = "m2form.view_side"
    bl_label = "Side"
    
    def execute(self, context):
        bpy.ops.view3d.view_axis(type='RIGHT')
        return {'FINISHED'}

class M2FORM_OT_view_top(Operator):
    bl_idname = "m2form.view_top"
    bl_label = "Top"
    
    def execute(self, context):
        bpy.ops.view3d.view_axis(type='TOP')
        return {'FINISHED'}

# Panel
class M2FORM_PT_main_panel(Panel):
    bl_label = "m2Form"
    bl_idname = "M2FORM_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'm2Form'
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.m2form_props
        
        # Title and Open Image
        row = layout.row()
        row.label(text="m2Form")
        row.operator("m2form.open_image", text="Open Image")
        
        # Main Inputs
        box = layout.box()
        box.label(text="Main Inputs")
        box.prop(props, "depth_map_path")
        box.prop(props, "image_path")
        box.prop(props, "target_object")
        
        # Mesh View
        box = layout.box()
        box.label(text="Mesh View")
        row = box.row(align=True)
        row.operator("m2form.view_front")
        row.operator("m2form.view_side")
        row.operator("m2form.view_top")
        
        box.prop(props, "subdivision_level")
        box.prop(props, "smoothing_factor")
        box.prop(props, "depth_strength")
        
        # Material Properties
        box = layout.box()
        box.label(text="Material Properties")
        box.prop(props, "metallic")
        box.prop(props, "roughness")
        box.prop(props, "ior")
        
        # Apply button
        layout.operator("m2form.create_mesh")

classes = (
    M2FormProperties,
    M2FORM_OT_open_image,
    M2FORM_OT_create_mesh,
    M2FORM_OT_view_front,
    M2FORM_OT_view_side,
    M2FORM_OT_view_top,
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

