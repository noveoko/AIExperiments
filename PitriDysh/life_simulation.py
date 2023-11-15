import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation

class Bacteria:
    def __init__(self, x, y, length, width, color, speed, angle):
        self.x = x
        self.y = y
        self.length = length
        self.width = width
        self.color = color
        self.speed = speed
        self.angle = angle

    def move(self, dt):
        self.x += np.cos(self.angle) * self.speed * dt
        self.y += np.sin(self.angle) * self.speed * dt

class Population:
    def __init__(self, number_of_bacteria, width, height):
        self.bacteria = []
        self.width = width
        self.height = height
        for _ in range(number_of_bacteria):
            x, y = np.random.uniform(0, width), np.random.uniform(0, height)
            length, width = np.random.uniform(1.5, 3), np.random.uniform(0.5, 1.5)
            color = np.random.choice(['brown', 'green', 'blue'])
            speed = np.random.uniform(0.1, 0.5)
            angle = np.random.uniform(0, 2 * np.pi)
            self.bacteria.append(Bacteria(x, y, length, width, color, speed, angle))

    def update(self, frame):
        plt.clf()
        for bact in self.bacteria:
            bact.move(1)
            self.draw_bacteria(bact)
        plt.axis([0, self.width, 0, self.height])
        plt.axis('off')

    @staticmethod
    def draw_bacteria(bacteria):
        x = np.linspace(-bacteria.length/2, bacteria.length/2, 100)
        y1 = np.sqrt((bacteria.width/2)**2 * (1 - (x/(bacteria.length/2))**2))
        y2 = -y1
        plt.fill(np.concatenate([x, x[::-1]]), np.concatenate([y1 + bacteria.y, y2[::-1] + bacteria.y]), bacteria.color)

def animate_population(population, frames, interval, filename):
    fig = plt.figure(figsize=(10, 6))
    anim = FuncAnimation(fig, population.update, frames=frames, interval=interval)
    anim.save(filename, writer='ffmpeg')

# Example usage
population = Population(5, 10, 6)
animate_population(population, frames=200, interval=50, filename='bacteria_simulation.mp4')
