import unittest
import pymunk 
from function_form2 import main, initialize_physics, load_svg_shapes, list_to_waveform

class TestSimulation(unittest.TestCase):
    def setUp(self):
        # Initialize with test data
        self.shapes = ['test_shape1.svg', 'test_shape2.svg']
        self.space = pymunk.Space()

    def test_load_svg_shapes(self):
        loaded_shapes = load_svg_shapes(self.shapes, self.space)
        self.assertTrue(len(loaded_shapes) > 0, "Shapes should be loaded")

    def test_initialize_physics(self):
        # Assuming we have a test shape loaded
        loaded_shapes = load_svg_shapes(self.shapes, self.space)
        initialize_physics(loaded_shapes, self.space)
        # Test for a specific physical property, like mass
        for shape in loaded_shapes:
            self.assertTrue(shape.body.mass > 0, "Mass should be set")

    def test_update_physics(self):
        # This test might be more complex as it requires checking the state change
        pass

    def test_video_output(self):
        main(self.shapes)
        # Check if the video file is created
        import os
        self.assertTrue(os.path.isfile('simulation.mp4'), "Video file should be created")

if __name__ == '__main__':
    unittest.main()

