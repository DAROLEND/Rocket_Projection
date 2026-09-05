SAMPLE_SIMULATION = {
    "mass": 0.8,
    "drag_coefficient": 0.4,
    "cross_section_area": 0.03,
    "v0": 60.0,
    "angle_deg": 45.0,
}


async def test_create_simulation(client):
    res = await client.post("/simulate", json=SAMPLE_SIMULATION)
    assert res.status_code == 200

    data = res.json()
    assert data["id"] > 0
    assert data["apogee"] > 0
    assert data["flight_time"] > 0
    assert len(data["trajectory"]) > 1


async def test_create_simulation_rejects_invalid_input():
    from app.schemas import SimulationCreate
    import pytest as _pytest
    from pydantic import ValidationError

    with _pytest.raises(ValidationError):
        SimulationCreate(**{**SAMPLE_SIMULATION, "mass": -1})

    with _pytest.raises(ValidationError):
        SimulationCreate(**{**SAMPLE_SIMULATION, "angle_deg": 120})


async def test_list_and_get_simulation(client):
    created = (await client.post("/simulate", json=SAMPLE_SIMULATION)).json()

    listed = (await client.get("/simulations")).json()
    assert any(s["id"] == created["id"] for s in listed)

    detail = await client.get(f"/simulations/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["mass"] == SAMPLE_SIMULATION["mass"]


async def test_get_missing_simulation_returns_404(client):
    res = await client.get("/simulations/999999")
    assert res.status_code == 404


async def test_delete_simulation(client):
    created = (await client.post("/simulate", json=SAMPLE_SIMULATION)).json()

    delete_res = await client.delete(f"/simulations/{created['id']}")
    assert delete_res.status_code == 204

    get_res = await client.get(f"/simulations/{created['id']}")
    assert get_res.status_code == 404


async def test_delete_missing_simulation_returns_404(client):
    res = await client.delete("/simulations/999999")
    assert res.status_code == 404


async def test_create_simulation_with_engine_and_rk4(client):
    payload = {
        **SAMPLE_SIMULATION,
        "thrust": 60.0,
        "burn_time": 1.5,
        "propellant_mass": 0.1,
        "integration_method": "rk4",
    }
    res = await client.post("/simulate", json=payload)
    assert res.status_code == 200

    data = res.json()
    assert data["thrust"] == 60.0
    assert data["integration_method"] == "rk4"


async def test_create_simulation_rejects_incomplete_engine_fields():
    from pydantic import ValidationError
    import pytest as _pytest
    from app.schemas import SimulationCreate

    with _pytest.raises(ValidationError):
        SimulationCreate(**{**SAMPLE_SIMULATION, "thrust": 60.0})  # missing burn_time/propellant_mass


async def test_create_simulation_rejects_propellant_heavier_than_rocket():
    from pydantic import ValidationError
    import pytest as _pytest
    from app.schemas import SimulationCreate

    with _pytest.raises(ValidationError):
        SimulationCreate(**{
            **SAMPLE_SIMULATION, "mass": 1.0,
            "thrust": 60.0, "burn_time": 1.0, "propellant_mass": 1.0,
        })


async def test_optimal_angle_endpoint(client):
    res = await client.post("/simulate/optimal-angle", json={
        "mass": 0.5, "drag_coefficient": 0.6, "cross_section_area": 0.05, "v0": 40.0,
    })
    assert res.status_code == 200

    data = res.json()
    assert 0 < data["angle_deg"] < 45
    assert data["landing_x"] > 0


async def test_dispersion_endpoint(client):
    res = await client.post("/simulate/dispersion", json={
        **SAMPLE_SIMULATION, "trials": 20, "angle_std_deg": 1.0, "v0_std_pct": 2.0,
    })
    assert res.status_code == 200

    data = res.json()
    assert len(data["points"]) == 20
    assert data["landing_x_std"] >= 0
    assert "trajectory" in data["nominal"]


async def test_update_simulation_recomputes_in_place(client):
    created = (await client.post("/simulate", json=SAMPLE_SIMULATION)).json()

    updated_payload = {**SAMPLE_SIMULATION, "angle_deg": 60.0, "v0": 80.0}
    res = await client.put(f"/simulations/{created['id']}", json=updated_payload)
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == created["id"]  # same id, not a new one
    assert data["angle_deg"] == 60.0
    assert data["v0"] == 80.0
    assert data["landing_x"] != created["landing_x"]

    listed = (await client.get("/simulations")).json()
    assert sum(1 for s in listed if s["id"] == created["id"]) == 1  # no duplicate row


async def test_update_missing_simulation_returns_404(client):
    res = await client.put(f"/simulations/999999", json=SAMPLE_SIMULATION)
    assert res.status_code == 404


async def test_dispersion_endpoint_caps_trials():
    res_json = {
        **SAMPLE_SIMULATION, "trials": 5000, "angle_std_deg": 1.0, "v0_std_pct": 2.0,
    }
    from app.schemas import DispersionRequest
    import pytest as _pytest
    from pydantic import ValidationError

    with _pytest.raises(ValidationError):
        DispersionRequest(**res_json)
