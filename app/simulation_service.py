import math
from physics.rocket import Rocket
from physics.enviroment import SimulationEnviroment


def run_simulation(mass: float, drag_coefficient: float, cross_section_area: float,
                    v0: float, angle_deg: float) -> dict:
    angle_rad = math.radians(angle_deg)
    vx = v0 * math.cos(angle_rad)
    vy = v0 * math.sin(angle_rad)

    rocket = Rocket(
        mass=mass,
        drag_coefficient=drag_coefficient,
        cross_section_area=cross_section_area,
        vx=vx,
        vy=vy,
    )
    env = SimulationEnviroment()
    trajectory = env.simulate(rocket)

    apogee = max(point[3] for point in trajectory)  # y_val — індекс 3
    flight_time = trajectory[-1][1]                  # t_val останньої точки
    max_velocity = max(math.sqrt(p[4] ** 2 + p[5] ** 2) for p in trajectory)
    landing_x = trajectory[-1][2]                     # x_val останньої точки

    return {
        "apogee": apogee,
        "flight_time": flight_time,
        "max_velocity": max_velocity,
        "landing_x": landing_x,
        "trajectory": trajectory,
    }