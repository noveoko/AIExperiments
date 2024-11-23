# YOLOv8 Motion Tracker for Blender

This Blender add-on integrates YOLOv8 object detection into Blender for advanced motion tracking. It uses the YOLOv8 model to detect objects in rendered frames, projects 2D bounding boxes into 3D space, and adds motion tracking markers to the Blender scene.

---

## Features

- **YOLOv8 Integration**: Leverages the YOLOv8 object detection model for robust and accurate detections.
- **Motion Tracking**: Automatically generates motion tracking markers in Blender based on detected objects.
- **2D-to-3D Projection**: Converts bounding box detections into 3D positions using Blender's camera settings.
- **Real-Time Updates**: Updates markers dynamically for frame-by-frame animation.

---

## Prerequisites

1. **Blender 3.0+**
   - Ensure you have Blender installed. [Download Blender](https://www.blender.org/)

2. **Python Packages**:
   - `ultralytics` (YOLOv8 library)
   - `opencv-python`
   - `numpy`

   Install these dependencies using pip:
   ```bash
   pip install ultralytics opencv-python numpy
   ```

3. **YOLOv8 Model**:
   - Download the YOLOv8 model file (e.g., `yolov8n.pt`) from the [Ultralytics GitHub repository](https://github.com/ultralytics/ultralytics).

---

## Installation

1. **Save the Script**:
   - Save the `yolov8_motion_tracker.py` script to a directory on your computer.

2. **Enable the Add-on**:
   - Open Blender.
   - Go to **Edit > Preferences > Add-ons**.
   - Click **Install...** and select the `yolov8_motion_tracker.py` file.
   - Enable the "YOLOv8 Motion Tracker" add-on from the list.

---

## Usage

1. **Set Up Your Scene**:
   - Ensure your scene has an active camera. The add-on will render frames from this camera.

2. **Run the Add-on**:
   - In the 3D Viewport, press **F3** (or spacebar in older versions) to bring up the search menu.
   - Search for **"YOLOv8 Motion Tracker"** and select it.

3. **Motion Tracking**:
   - The add-on will:
     1. Render a frame from the active camera.
     2. Detect objects in the frame using YOLOv8.
     3. Project detections into 3D space.
     4. Add motion tracking markers for detected objects.

---

## Customization

- **Model File**:
  - By default, the add-on uses `yolov8n.pt`. To use a different model, update the `self.predictor` line in the script:
    ```python
    self.predictor = DetectPredictor(model='your_model_file.pt')
    ```

- **Depth Estimation**:
  - The add-on uses a fixed depth for projecting 2D detections to 3D space. Modify the `depth` value in the `project_to_3d` method for better results, or integrate a depth estimation algorithm.

---

## Troubleshooting

- **No Active Camera**:
  - Ensure your scene has an active camera. You can set it by selecting a camera and pressing `Ctrl+0` in the viewport.

- **Frame Capture Issues**:
  - Check if the temporary render file (`//temp_render.png`) is being generated correctly. Ensure you have write permissions in your working directory.

- **Dependencies Missing**:
  - Verify all required Python packages are installed by running:
    ```bash
    pip list
    ```

- **Performance**:
  - Use a lightweight YOLOv8 model (e.g., `yolov8n.pt`) for faster processing.

---

## Future Enhancements

- Improved depth estimation for 3D projections.
- Real-time video feed integration.
- Enhanced marker management (e.g., tracking lost objects).
- Support for multi-object tracking.

---

## License

This add-on is provided under the [MIT License](https://opensource.org/licenses/MIT). You are free to use, modify, and distribute it.

---

## Credits

- YOLOv8 Model: [Ultralytics](https://github.com/ultralytics)
- Blender API: [Blender Documentation](https://docs.blender.org/api/current/)
- OpenCV and NumPy libraries for image processing.
