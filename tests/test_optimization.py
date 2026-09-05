import pytest

from app.simulation_service import find_optimal_angle, run_dispersion, run_simulation


def test_optimal_angle_beats_45_degrees_under_drag():
    """With quadratic drag, 45° is no longer optimal — the found angle should
    give at least as much range as 45° (and, for a draggy/slow case, strictly more)."""
    result = find_optimal_angle(mass=0.5, v0=40.0, drag_coefficient=0.6, cross_section_area=0.05)
    range_at_45 = run_simulation(
        mass=0.5, drag_coefficient=0.6, cross_section_area=0.05, v0=40.0, angle_deg=45.0
    )["landing_x"]

    assert result["angle_deg"] < 45.0
    assert result["landing_x"] >= range_at_45


def test_optimal_angle_without_drag_is_near_45():
    """Sanity check against the textbook case: with no drag, range is maximized at 45°."""
    result = find_optimal_angle(mass=1.0, v0=40.0, drag_coefficient=1e-9, cross_section_area=1e-9)
    assert result["angle_deg"] == pytest.approx(45.0, abs=1.0)


def test_dispersion_mean_tracks_nominal_and_std_grows_with_noise():
    nominal_landing_x = run_simulation(
        mass=0.5, drag_coefficient=0.4, cross_section_area=0.03, v0=40.0, angle_deg=45.0
    )["landing_x"]

    low_noise = run_dispersion(
        mass=0.5, drag_coefficient=0.4, cross_section_area=0.03, v0=40.0, angle_deg=45.0,
        trials=100, angle_std_deg=0.5, v0_std_pct=1.0,
    )
    high_noise = run_dispersion(
        mass=0.5, drag_coefficient=0.4, cross_section_area=0.03, v0=40.0, angle_deg=45.0,
        trials=100, angle_std_deg=5.0, v0_std_pct=10.0,
    )

    assert low_noise["landing_x_mean"] == pytest.approx(nominal_landing_x, rel=0.15)
    assert len(low_noise["points"]) == 100
    assert high_noise["landing_x_std"] > low_noise["landing_x_std"]


def test_dispersion_zero_noise_collapses_to_nominal():
    result = run_dispersion(
        mass=0.5, drag_coefficient=0.4, cross_section_area=0.03, v0=40.0, angle_deg=45.0,
        trials=20, angle_std_deg=0.0, v0_std_pct=0.0,
    )
    assert result["landing_x_std"] == pytest.approx(0.0, abs=1e-9)
