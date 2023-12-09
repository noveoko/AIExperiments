import pygame
!pip install pymunk svgpathtools
import pymunk
from svgpathtools import svg2paths
import numpy as np
import cv2

def wrap_waveform_in_circle_export_svg(wave_function, num_points=1000, num_cycles=5, fill_color='blue', fill_alpha=0.5, 
                                       line_color='black', line_alpha=1.0, diameter_to_wave_max_ratio=1.0, 
                                       smoothness=0, export_svg=False, svg_filename="waveform_circle.svg"):
    """
    Wraps a waveform around a circle with adjustable parameters and option to export a clean SVG of the shape.

    :param wave_function: A function that defines the waveform.
    :param num_points: Number of points to plot on the circle.
    :param num_cycles: Number of cycles of the wave to wrap around the circle.
    :param fill_color: Color of the fill.
    :param fill_alpha: Alpha (transparency) of the fill.
    :param line_color: Color of the line.
    :param line_alpha: Alpha (transparency) of the line.
    :param diameter_to_wave_max_ratio: Ratio of the circle's diameter to the maximum amplitude of the wave.
    :param smoothness: A value between 0 and 1 indicating the degree of smoothing.
    :param export_svg: If True, exports the plot as an SVG file.
    :param svg_filename: The filename for the SVG file.
    :return: None
    """
    # Adjust the wave_function with smoothing
    adjusted_wave_function = list_to_waveform(wave_function(np.linspace(0, 2 * np.pi, num_points)), smoothness)

    # Generate points along the circle
    theta = np.linspace(0, 2 * np.pi * num_cycles, num_points)
    wave_values = adjusted_wave_function(theta)
    max_wave_amplitude = np.max(np.abs(wave_values))
    
    # Adjust the radius based on the maximum wave amplitude
    r = 1 + (wave_values / max_wave_amplitude) * diameter_to_wave_max_ratio

    # Convert polar coordinates to Cartesian coordinates for plotting
    x = r * np.cos(theta)
    y = r * np.sin(theta)

    # Create the plot
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.fill(x, y, color=fill_color, alpha=fill_alpha, edgecolor=line_color, linewidth=1.5)
    ax.set_axis_off()  # Turn off the axis
    ax.set_aspect('equal', 'box')  # Keep the aspect ratio of the plot

    # Export as SVG if required
    if export_svg:
        fig.savefig(svg_filename, format='svg', bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close(fig)  # Close the plot to prevent it from displaying in this case
        #print(f"SVG file saved as {svg_filename}")
    else:
        plt.show()

# Example usage with SVG export
example_list = [1, 2, 3, 4, 5]
waveform_from_list = list_to_waveform(example_list)
wrap_waveform_in_circle_export_svg(waveform_from_list, fill_color='red', fill_alpha=0.5, 
                                   line_color='black', line_alpha=0.8, diameter_to_wave_max_ratio=1.5, 
                                   smoothness=0.5, export_svg=True, svg_filename="clean_waveform.svg")

def list_to_waveform(lst, smoothness=0):
    """
    Converts a list of integers to a waveform function, with optional smoothing.
    
    :param lst: A list of integers.
    :param smoothness: A value between 0 and 1 indicating the degree of smoothing.
    :return: A function representing the waveform.
    """
    smoothed_lst = smooth_waveform(lst, smoothness)
    
    max_theta = 2 * np.pi  # Full circle
    lst_len = len(smoothed_lst)

    def waveform(theta):
        indices = (theta % max_theta) / max_theta * lst_len
        indices = indices.astype(int)  # Convert to integer indices
        return np.array([smoothed_lst[i] * 0.1 for i in indices])  # Scale the values and create the waveform

    return waveform

import random

one_hundred_waveforms = [list_to_waveform([random.randint(1,100) for x in range(100)]) for x in range(100)]

shapes = []

for i in range(100):
  path = f'{i}_Wv.svg'
  wrap_waveform_in_circle_export_svg(one_hundred_waveforms[i], svg_filename=path,export_svg=True)
  shapes.append(path)

def load_svg_shapes(svg_filenames, space):
    shapes = []
    for filename in svg_filenames:
        paths, attributes = svg2paths(filename)

        for path, attr in zip(paths, attributes):
            # Check if 'id' key exists in the attr dictionary
            if 'id' in attr:
                if 'circle' in attr['id']:
                    shape = create_circle(path, space)
                elif 'polygon' in attr['id']:
                    shape = create_polygon(path, space)
                shapes.append(shape)
            else:
                print(f"No 'id' attribute found for a path in {filename}")
    return shapes

def initialize_physics(shapes, space):
    for shape in shapes:
        shape_body, shape_obj = shape
        shape_body.mass = 1
        if isinstance(shape_obj, pymunk.Circle):
            shape_body.moment = pymunk.moment_for_circle(shape_body.mass, 0, shape_obj.radius)
        # Add more conditions for different shape types
        space.add(shape_body, shape_obj)

def update_physics(space, dt):
    space.step(dt)

def render(screen, shapes):
    screen.fill((255, 255, 255))
    for shape in shapes:
        shape_obj, shape_body = shape
        if isinstance(shape_obj, pymunk.Circle):
            pygame_position = pymunk.pygame_util.to_pygame(shape_body.position, screen)
            pygame.draw.circle(screen, (0, 0, 0), pygame_position, int(shape_obj.radius), 0)
        # Add more rendering conditions for other shapes
    pygame.display.flip()

def main(shapes):
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    space = pymunk.Space()

    svg_filenames = shapes
    shapes = load_svg_shapes(svg_filenames, space)
    initialize_physics(shapes, space)

    # Video capture settings
    video_size = (800, 600)
    video_fps = 60
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec used to compress the frames
    video = cv2.VideoWriter('simulation.mp4', fourcc, video_fps, video_size)

    running = True
    clock = pygame.time.Clock()
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        update_physics(space, 1/60)
        render(screen, shapes)

        # Capture the frame
        frame = pygame.surfarray.array3d(screen)
        frame = frame.transpose([1, 0, 2])
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        video.write(frame)

        clock.tick(video_fps)

    video.release()
    pygame.quit()

if __name__ == "__main__":
    main(shapes)
