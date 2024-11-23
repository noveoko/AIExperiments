import bpy
import numpy as np
import cv2
from yolov8.detect import DetectPredictor

class YOLOv8MotionTracker(bpy.types.Operator):
    """Use YOLOv8 for advanced motion tracking in Blender"""
    bl_idname = "object.yolov8_motion_tracker"
    bl_label = "YOLOv8 Motion Tracker"
    bl_options = {'REGISTER', 'UNDO'}

    def __init__(self):
        self.predictor = DetectPredictor(model='yolov8n.pt')

    def invoke(self, context, event):
        # Get current 3D view and active camera
        scene = context.scene
        camera = scene.camera

        if not camera:
            self.report({'ERROR'}, "No active camera found in the scene.")
            return {'CANCELLED'}

        # Capture frame from camera
        frame = self.capture_frame(camera)

        if frame is None:
            self.report({'ERROR'}, "Failed to capture frame from the camera.")
            return {'CANCELLED'}

        # Run YOLOv8 object detection
        results = self.predictor(frame)

        # Process YOLOv8 results and update Blender motion tracking
        self.update_motion_tracking(results, camera)

        return {'FINISHED'}

    def capture_frame(self, camera):
        # Render the scene from the camera's perspective to an offscreen buffer
        scene = bpy.context.scene
        render = bpy.context.scene.render
        render.filepath = "//temp_render.png"
        bpy.ops.render.render(write_still=True)

        # Load the rendered image as a numpy array
        image_path = bpy.path.abspath(render.filepath)
        frame = cv2.imread(image_path)
        if frame is not None:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame

    def update_motion_tracking(self, results, camera):
        # Process YOLOv8 detection results and update Blender motion tracking data
        for detection in results.boxes:
            # Get bounding box coordinates
            x1, y1, x2, y2 = map(int, detection.xyxy[0])

            # Convert 2D bounding box to 3D position in camera space
            position_3d = self.project_to_3d(x1, y1, x2, y2, camera)

            if position_3d:
                # Add or update motion tracking marker in Blender
                self.add_motion_tracking_marker(position_3d)

    def project_to_3d(self, x1, y1, x2, y2, camera):
        # Estimate 3D position based on bounding box center and camera parameters
        scene = bpy.context.scene
        render = scene.render
        bbox_center_x = (x1 + x2) / 2
        bbox_center_y = (y1 + y2) / 2

        # Normalize coordinates to -1 to 1 range (screen space)
        normalized_x = (bbox_center_x / render.resolution_x) * 2 - 1
        normalized_y = (bbox_center_y / render.resolution_y) * 2 - 1

        # Use Blender's camera matrix for unprojection
        depth = 1.0  # Assumes objects are at a fixed depth for simplicity
        coord_3d = camera.matrix_world @ camera.calc_matrix_camera(
            scene.render.resolution_x / scene.render.resolution_y
        ).inverted() @ np.array([normalized_x, normalized_y, -depth, 1.0])

        # Convert to world space and return
        return coord_3d[:3]

    def add_motion_tracking_marker(self, position_3d):
        # Add or update a motion tracking marker in the Blender scene
        scene = bpy.context.scene
        tracker = scene.tracking

        # Create a new tracking object if none exists
        if not tracker.objects:
            tracking_object = tracker.objects.new("YOLOv8_Tracking")
        else:
            tracking_object = tracker.objects[0]

        # Add a new marker to the tracking object
        marker = tracking_object.tracks.new(position_3d)
        marker.name = "Object_Tracking_Marker"

        # Set the marker's keyframe
        marker.markers.insert(frame=bpy.context.scene.frame_current, co=position_3d)

def register():
    bpy.utils.register_class(YOLOv8MotionTracker)

def unregister():
    bpy.utils.unregister_class(YOLOv8MotionTracker)
