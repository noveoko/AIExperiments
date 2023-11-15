import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation

class Bacteria:
    def __init__(self, x, y, radius, color, speed, angle, width_bound, height_bound):
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.speed = speed
        self.angle = angle
        self.width_bound = width_bound
        self.height_bound = height_bound

    def move(self, dt):
        self.x += np.cos(self.angle) * self.speed * dt
        self.y += np.sin(self.angle) * self.speed * dt

        # Boundary collision
        if not self.radius <= self.x <= self.width_bound - self.radius:
            self.angle = np.pi - self.angle
        if not self.radius <= self.y <= self.height_bound - self.radius:
            self.angle = -self.angle

class Population:
    def __init__(self, number_of_bacteria, width, height):
        self.bacteria = []
        self.width = width
        self.height = height
        for _ in range(number_of_bacteria):
            x, y = np.random.uniform(20, width-20), np.random.uniform(20, height-20)
            radius = np.random.uniform(5, 10)
            color = np.random.choice(['brown', 'green', 'blue'])
            speed = np.random.uniform(0.1, 0.5)
            angle = np.random.uniform(0, 2 * np.pi)
            self.bacteria.append(Bacteria(x, y, radius, color, speed, angle, self.width, self.height))

    def update(self, frame):
        plt.clf()
        plt.axis([0, self.width, 0, self.height])
        plt.axis('off')
        
        for bact in self.bacteria:
            bact.move(1)
        
        self.check_collisions()
        
        for bact in self.bacteria:
            self.draw_bacteria(bact)

    def check_collisions(self):
        for i, bact1 in enumerate(self.bacteria):
            for bact2 in self.bacteria[i+1:]:
                dx = bact1.x - bact2.x
                dy = bact1.y - bact2.y
                distance = np.sqrt(dx**2 + dy**2)

                if distance < bact1.radius + bact2.radius:
                    bact1.angle, bact2.angle = bact2.angle, bact1.angle
                    bact1.move(1)
                    bact2.move(1)

    @staticmethod
    def draw_bacteria(bacteria):
        circle = plt.Circle((bacteria.x, bacteria.y), bacteria.radius, color=bacteria.color)
        plt.gca().add_patch(circle)

def animate_population(population, frames, interval, filename):
    fig = plt.figure(figsize=(10, 6))
    anim = FuncAnimation(fig, population.update, frames=frames, interval=interval)
    anim.save(filename, writer='ffmpeg')

# Example usage
population = Population(5, 100, 60)
animate_population(population, frames=200, interval=50, filename='bacteria_simulation.mp4')
