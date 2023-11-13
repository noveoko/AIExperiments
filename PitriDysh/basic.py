import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation

def normalize(value, min_value, max_value):
    """ Normalize a value to be within 0 and 1. """
    return (value - min_value) / (max_value - min_value)

def generate_movement_coordinates(data, num_steps=20):
    """ Generate a list of coordinates for the life form's movement. """
    normalized_data = normalize(data, np.min(data), np.max(data))
    movement_scale = np.std(data) * 0.1

    x, y = np.random.rand(), np.random.rand()  # random starting position
    coordinates = [(x, y)]

    for step in range(1, num_steps):
        dx = (normalized_data[step % len(data)] - 0.5) * movement_scale
        dy = (normalized_data[(step + 1) % len(data)] - 0.5) * movement_scale
        x = max(0, min(1, x + dx))
        y = max(0, min(1, y + dy))
        coordinates.append((x, y))

    return coordinates

def update(frame, data_sets, scatters):
    """ Update function for the animation. """
    for data, scat, pos in zip(data_sets, scatters, frame):
        size = np.mean(data) * 100  # size based on average of data
        color_intensity = np.std(data)  # color intensity based on data variability
        normalized_color_intensity = normalize(color_intensity, 0, np.std(data) + 1)

        scat.set_offsets([pos])
        scat.set_sizes([size])
        scat.set_color((normalized_color_intensity, 0.5, 0.5, 0.5))

    return scatters

def extract_numeric_data(df):
    """
    Extracts columns from a DataFrame that are either integer or float,
    and returns the data in a list of lists format.
    """
    numeric_data = df.select_dtypes(include=['int64', 'float64'])
    data_sets = numeric_data.values.tolist()
    return data_sets

data_sets = extract_numeric_data(df)
# Generate movement coordinates for each data set
movement_coordinates_sets = [generate_movement_coordinates(data) for data in data_sets]

# Set up the figure for animation
fig, ax = plt.subplots()
ax.set_aspect('equal', 'box')
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis('off')

# Create a scatter plot for each life form
scatters = [ax.scatter([], [], s=0) for _ in data_sets]

# Function to generate frames for all life forms
def generate_frames():
    for i in range(len(movement_coordinates_sets[0])):
        yield [coords[i] for coords in movement_coordinates_sets]

# Create the animation
anim = FuncAnimation(fig, update, frames=generate_frames(), fargs=(data_sets, scatters), blit=True, interval=200)

# Save the animation
anim.save('multiple_life_forms_animation.mp4', writer='ffmpeg', fps=5)

plt.show()
