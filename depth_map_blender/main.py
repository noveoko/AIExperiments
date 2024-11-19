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
        name="Image",
        description="Choose a base image",
        default="",
        maxlen=1024,
        subtype='FILE_PATH'
    )
    
    depth_map_path: StringProperty(
        name="Depth Map",
        description="Choose a depth map image",
        default="",
        maxlen=1024,
        subtype='FILE_PATH'
    )
    
    target_object: PointerProperty(
        name="Target Object",
        type=bpy.types.Object,
        description="Select object to apply modifiers to"
    )
    
    subdivision_level: IntProperty(
        name="Subdivision Level",
        description="Number of subdivisions",
        default=32,
        min=1,
        max=256
    )
    
    depth_strength: FloatProperty(
        name="Depth Strength",
        description="Strength of displacement effect",
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
    bl_description = "Convert depth map to 3D mesh"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        props = context.scene.m2form_props
        return props.depth_map_path != "" or props.image_path != ""
    
    def execute(self, context):
        try:
            props = context.scene.m2form_props
            
            # Check for input files
            if not os.path.exists(bpy.path.abspath(props.depth_map_path)):
                self.report({'ERROR'}, "Depth map file not found")
                return {'CANCELLED'}
            
            if props.image_path and not os.path.exists(bpy.path.abspath(props.image_path)):
                self.report({'ERROR'}, "Image file not found")
                return {'CANCELLED'}
            
            # Use existing object or create new one
            if props.target_object:
                obj = props.target_object
            else:
                bpy.ops.mesh.primitive_plane_add(size=2)
                obj = context.active_object
            
            # Clear existing modifiers
            obj.modifiers.clear()
            
            # Add subdivision modifier
            subdiv = obj.modifiers.new(name="Subdivision", type='SUBSURF')
            subdiv.levels = props.subdivision_level
            subdiv.render_levels = props.subdivision_level
            
            # Add displacement modifier
            displace = obj.modifiers.new(name="Displacement", type='DISPLACE')
            
            # Load and apply depth map texture
            if props.depth_map_path:
                depth_tex = bpy.data.textures.new(name="Depth", type='IMAGE')
                depth_img = bpy.data.images.load(bpy.path.abspath(props.depth_map_path))
                depth_tex.image = depth_img
                displace.texture = depth_tex
                displace.strength = props.depth_strength
            
            # Create or get material
            mat_name = "m2Form_Material"
            mat = bpy.data.materials.get(mat_name)
            if mat:
                mat.user_clear()
                bpy.data.materials.remove(mat)
            mat = bpy.data.materials.new(name=mat_name)
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
                img = bpy.data.images.load(bpy.path.abspath(props.image_path))
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
            obj.select_set(True)
            context.view_layer.objects.active = obj
            bpy.ops.object.shade_smooth()
            obj.data.use_auto_smooth = True
            obj.data.auto_smooth_angle = props.smoothing_factor * 3.14159
            
            self.report({'INFO'}, "Depth map applied successfully")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
            return {'CANCELLED'}

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

class M2FORM_PT_main_panel(Panel):
    bl_label = "m2Form"
    bl_idname = "M2FORM_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'm2Form'
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.m2form_props
        
        # Title
        layout.label(text="m2Form")
        
        # Main Inputs
        box = layout.box()
        box.label(text="Main Inputs")
        
        # Depth Map
        row = box.row()
        row.prop(props, "depth_map_path")
        op = row.operator("m2form.choose_image", text="", icon='FILE_FOLDER')
        op.is_depth_map = True
        
        # Base Image
        row = box.row()
        row.prop(props, "image_path")
        op = row.operator("m2form.choose_image", text="", icon='FILE_FOLDER')
        op.is_depth_map = False
        
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
    M2FORM_OT_choose_image,
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
