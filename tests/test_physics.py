import math

import pytest

from physics.rocket import Rocket
from physics.environment import SimulationEnvironment


def test_no_drag_apogee_matches_kinematics():
    """With drag disabled, apogee should match the closed-form v0y^2 / (2g)."""
    v0, angle_deg = 50.0, 60.0
    vx = v0 * math.cos(math.radians(angle_deg))
    vy = v0 * math.sin(math.radians(angle_deg))

    rocket = Rocket(mass=1.0, drag_coefficient=0.0, cross_section_area=0.03, vx=vx, vy=vy)
    trajectory = SimulationEnvironment(dt=0.001).simulate(rocket)

    apogee = max(point[3] for point in trajectory)
    expected_apogee = vy ** 2 / (2 * 9.81)

    assert apogee == pytest.approx(expected_apogee, rel=0.01)


def test_finer_dt_does_not_truncate_flight():
    """Regression test: the simulation used to hard-cap at 1000 steps regardless
    of dt, so a smaller dt silently cut the trajectory short before landing."""
    rocket = Rocket(mass=1.0, drag_coefficient=0.0, cross_section_area=0.03, vx=10.0, vy=40.0)
    trajectory = SimulationEnvironment(dt=0.001).simulate(rocket)

    assert trajectory[-1][3] == pytest.approx(0.0, abs=1e-3)


def test_drag_reduces_range_and_apogee():
    """Adding air resistance should never let the rocket fly farther or higher."""
    rocket_kwargs = dict(mass=0.5, cross_section_area=0.03, vx=30.0, vy=30.0)

    no_drag = SimulationEnvironment().simulate(Rocket(drag_coefficient=0.0, **rocket_kwargs))
    with_drag = SimulationEnvironment().simulate(Rocket(drag_coefficient=0.8, **rocket_kwargs))

    apogee_no_drag = max(p[3] for p in no_drag)
    apogee_with_drag = max(p[3] for p in with_drag)
    landing_x_no_drag = no_drag[-1][2]
    landing_x_with_drag = with_drag[-1][2]

    assert apogee_with_drag < apogee_no_drag
    assert landing_x_with_drag < landing_x_no_drag


def test_trajectory_lands_at_ground_level():
    """The interpolated final point should sit at y=0, not just below it."""
    rocket = Rocket(mass=1.0, drag_coefficient=0.4, cross_section_area=0.03, vx=20.0, vy=15.0)
    trajectory = SimulationEnvironment().simulate(rocket)

    assert trajectory[-1][3] == pytest.approx(0.0, abs=1e-6)
    assert trajectory[-1][1] > 0  # flight time is positive


def test_heavier_rocket_experiences_less_relative_drag():
    """Heavier rockets should retain range better under the same drag, since drag
    deceleration scales with 1/mass."""
    common = dict(drag_coefficient=0.6, cross_section_area=0.03, vx=25.0, vy=25.0)

    light = SimulationEnvironment().simulate(Rocket(mass=0.2, **common))
    heavy = SimulationEnvironment().simulate(Rocket(mass=5.0, **common))

    assert heavy[-1][2] > light[-1][2]


def test_thrust_raises_apogee_and_burns_propellant_mass():
    """A burning engine should add extra altitude on top of the coast-only case,
    and mass should shed exactly propellant_mass by the end of the burn."""
    common = dict(mass=1.0, drag_coefficient=0.4, cross_section_area=0.03, vx=20.0, vy=35.0)

    coasting = Rocket(**common)
    powered = Rocket(thrust=80.0, burn_time=1.5, propellant_mass=0.2, **common)

    no_thrust_traj = SimulationEnvironment().simulate(coasting)
    with_thrust_traj = SimulationEnvironment().simulate(powered)

    assert max(p[3] for p in with_thrust_traj) > max(p[3] for p in no_thrust_traj)
    assert powered.mass_at(1.5) == pytest.approx(1.0 - 0.2)
    assert powered.mass_at(0.75) == pytest.approx(1.0 - 0.1)


def test_thrust_off_after_burnout():
    """Once burn_time elapses there should be no more thrust acceleration."""
    rocket = Rocket(mass=1.0, drag_coefficient=0.4, cross_section_area=0.03, vx=10.0, vy=10.0,
                     thrust=100.0, burn_time=2.0, propellant_mass=0.1)

    assert rocket.thrust_accel(1.0) != (0.0, 0.0)
    assert rocket.thrust_accel(2.5) == (0.0, 0.0)


def test_parachute_slows_descent():
    """A parachute should only kick in once the rocket starts falling (vy < 0),
    and should noticeably extend flight time by slowing the descent."""
    common = dict(mass=0.5, drag_coefficient=0.4, cross_section_area=0.03, vx=15.0, vy=25.0)

    no_parachute = SimulationEnvironment().simulate(Rocket(**common))
    with_parachute = SimulationEnvironment().simulate(
        Rocket(parachute_cd=1.5, parachute_area=0.3, **common)
    )

    assert with_parachute[-1][1] > no_parachute[-1][1]

    rocket = Rocket(parachute_cd=1.5, parachute_area=0.3, **common)
    assert rocket.drag_profile(vy=5.0) == (rocket.drag_coefficient, rocket.cross_section_area)
    assert rocket.drag_profile(vy=-5.0) == (1.5, 0.3)


def test_rk4_close_to_euler_for_smooth_trajectory():
    """RK4 and semi-implicit Euler should broadly agree on a simple ballistic arc —
    if they diverge wildly, something is wrong with one of the integrators."""
    kwargs = dict(mass=1.0, drag_coefficient=0.4, cross_section_area=0.03, vx=20.0, vy=30.0)

    euler_traj = SimulationEnvironment().simulate(Rocket(**kwargs), method="euler")
    rk4_traj = SimulationEnvironment().simulate(Rocket(**kwargs), method="rk4")

    euler_apogee = max(p[3] for p in euler_traj)
    rk4_apogee = max(p[3] for p in rk4_traj)

    assert rk4_apogee == pytest.approx(euler_apogee, rel=0.02)
