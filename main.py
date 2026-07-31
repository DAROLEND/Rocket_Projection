import math
from physics.rocket import Rocket
from physics.enviroment import SimulationEnviroment

v0 = 30
angle_deg = 30

angle_rad = math.radians(angle_deg)
vx = v0 * math.cos(angle_rad)
vy = v0 * math.sin(angle_rad)

my_rocket = Rocket(mass = 0.42, drag_coefficient = 0.47, cross_section_area = 0.039, vx=vx, vy=vy)
my_env = SimulationEnviroment()

point = my_env.simulate(my_rocket)


trajectory = my_env.simulate(my_rocket)

for step in trajectory:
    step_id, t_val, x_val, y_val, vx_val, vy_val = step
    print(f"Id: {step_id} | Час: {t_val:.4f}c. | Координати: (x: {x_val:.4f}, y: {y_val:.4f}) | Швидкість: vx={vx_val:.4f}, vy={vy_val:.4f}")

