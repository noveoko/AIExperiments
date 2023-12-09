def wrap_waveform_in_circle(wave_function, num_points=1000, num_cycles=5, fill_color='blue', fill_alpha=0.5, radius_scale=1.0):
    """
    Wraps a waveform around a circle with adjustable radius, fill color, and transparency.

    :param wave_function: A function that defines the waveform.
    :param num_points: Number of points to plot on the circle.
    :param num_cycles: Number of cycles of the wave to wrap around the circle.
    :param fill_color: Color of the fill.
    :param fill_alpha: Alpha (transparency) of the fill.
    :param radius_scale: Scale factor for the radius of the circle.
    :return: None
    """
    # Generate points along the circle
    theta = np.linspace(0, 2 * np.pi * num_cycles, num_points)
    r = (1 + wave_function(theta)) * radius_scale

    # Convert polar coordinates to Cartesian coordinates for plotting
    x = r * np.cos(theta)
    y = r * np.sin(theta)

    # Plot the waveform with fill
    plt.figure(figsize=(6, 6))
    plt.fill(x, y, color=fill_color, alpha=fill_alpha)
    plt.axis('equal')
    plt.title('Waveform Wrapped Around a Circle')
    plt.show()

# Example of using the updated function with radius scaling
wrap_waveform_in_circle(waveform_from_list_smoothed, fill_color='green', fill_alpha=0.5, radius_scale=1.5)
