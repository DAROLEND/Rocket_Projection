import math
import random

from physics.rocket import Rocket
from physics.environment import SimulationEnvironment


def run_simulation(
    mass: float, drag_coefficient: float, cross_section_area: float,
    v0: float, angle_deg: float,
    thrust: float = 0.0, burn_time: float = 0.0, propellant_mass: float = 0.0,
    parachute_cd: float | None = None, parachute_area: float | None = None,
    integration_method: str = "euler",
) -> dict:
    angle_rad = math.radians(angle_deg)
    vx = v0 * math.cos(angle_rad)
    vy = v0 * math.sin(angle_rad)

    rocket = Rocket(
        mass=mass,
        drag_coefficient=drag_coefficient,
        cross_section_area=cross_section_area,
        vx=vx,
        vy=vy,
        thrust=thrust or 0.0,
        burn_time=burn_time or 0.0,
        propellant_mass=propellant_mass or 0.0,
        parachute_cd=parachute_cd,
        parachute_area=parachute_area,
    )
    env = SimulationEnvironment()
    trajectory = env.simulate(rocket, method=integration_method)

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


def find_optimal_angle(
    mass: float, v0: float, drag_coefficient: float = 0.47, cross_section_area: float = 0.03,
    angle_min: float = 1.0, angle_max: float = 89.0, tol: float = 0.1,
) -> dict:
    """Golden-section search for the launch angle that maximizes range.

    Without drag the optimum is always 45°; with quadratic air resistance the
    range-vs-angle curve is still unimodal but peaks below 45° (and lower still
    for draggier/slower rockets), so a closed-form answer doesn't exist and we
    search for it numerically instead.
    """

    def range_at(angle_deg: float) -> float:
        return run_simulation(
            mass=mass, drag_coefficient=drag_coefficient, cross_section_area=cross_section_area,
            v0=v0, angle_deg=angle_deg,
        )["landing_x"]

    invphi = (math.sqrt(5) - 1) / 2   # 1/phi
    invphi2 = (3 - math.sqrt(5)) / 2  # 1/phi^2

    a, b = angle_min, angle_max
    h = b - a
    if h <= tol:
        best_angle = (a + b) / 2
        return {"angle_deg": best_angle, **run_simulation(
            mass=mass, drag_coefficient=drag_coefficient, cross_section_area=cross_section_area,
            v0=v0, angle_deg=best_angle,
        )}

    n = math.ceil(math.log(tol / h) / math.log(invphi))
    c = a + invphi2 * h
    d = a + invphi * h
    yc = range_at(c)
    yd = range_at(d)

    for _ in range(max(n - 1, 0)):
        if yc > yd:
            b, d, yd = d, c, yc
            h = invphi * h
            c = a + invphi2 * h
            yc = range_at(c)
        else:
            a, c, yc = c, d, yd
            h = invphi * h
            d = a + invphi * h
            yd = range_at(d)

    best_angle = c if yc > yd else d
    result = run_simulation(
        mass=mass, drag_coefficient=drag_coefficient, cross_section_area=cross_section_area,
        v0=v0, angle_deg=best_angle,
    )
    return {"angle_deg": round(best_angle, 2), **result}


def run_dispersion(
    mass: float, drag_coefficient: float, cross_section_area: float, v0: float, angle_deg: float,
    trials: int = 200, angle_std_deg: float = 1.0, v0_std_pct: float = 2.0,
    thrust: float = 0.0, burn_time: float = 0.0, propellant_mass: float = 0.0,
    parachute_cd: float | None = None, parachute_area: float | None = None,
) -> dict:
    """Monte Carlo landing dispersion: re-run the same shot `trials` times with
    small random noise on angle and launch speed, and report where it actually lands."""

    nominal = run_simulation(
        mass=mass, drag_coefficient=drag_coefficient, cross_section_area=cross_section_area,
        v0=v0, angle_deg=angle_deg, thrust=thrust, burn_time=burn_time, propellant_mass=propellant_mass,
        parachute_cd=parachute_cd, parachute_area=parachute_area,
    )

    landing_points = []
    for _ in range(trials):
        noisy_angle = angle_deg + random.gauss(0, angle_std_deg)
        noisy_angle = min(max(noisy_angle, 0.1), 89.9)
        noisy_v0 = v0 * (1 + random.gauss(0, v0_std_pct / 100))
        noisy_v0 = max(noisy_v0, 0.1)

        trial = run_simulation(
            mass=mass, drag_coefficient=drag_coefficient, cross_section_area=cross_section_area,
            v0=noisy_v0, angle_deg=noisy_angle, thrust=thrust, burn_time=burn_time,
            propellant_mass=propellant_mass, parachute_cd=parachute_cd, parachute_area=parachute_area,
        )
        landing_points.append({
            "landing_x": trial["landing_x"],
            "apogee": trial["apogee"],
            "flight_time": trial["flight_time"],
        })

    landing_xs = [p["landing_x"] for p in landing_points]
    mean_x = sum(landing_xs) / len(landing_xs)
    variance = sum((x - mean_x) ** 2 for x in landing_xs) / len(landing_xs)

    return {
        "nominal": nominal,
        "points": landing_points,
        "landing_x_mean": mean_x,
        "landing_x_std": math.sqrt(variance),
    }
