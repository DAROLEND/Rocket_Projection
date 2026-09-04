import json
from anthropic import Anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select
from app.models import Simulation

from app.config import settings
from app.simulation_service import run_simulation
from app.models import Simulation
from app.rag_service import index_simulation, search_similar_with_ids

_client = Anthropic(api_key=settings.anthropic_api_key)

_tools = [
    {
        "name": "run_new_simulation",
        "description": "Launch a new rocket trajectory simulation and save it to the database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mass": {"type": "number", "description": "rocket mass in kg"},
                "v0": {"type": "number", "description": "initial launch velocity in m/s"},
                "angle_deg": {"type": "number", "description": "launch angle in degrees, 0-90"},
                "drag_coefficient": {"type": "number", "description": "default 0.47"},
                "cross_section_area": {"type": "number", "description": "default 0.03"},
            },
            "required": ["mass", "v0", "angle_deg"],
        },
    },
    {
        "name": "search_past_simulations",
        "description": "Search existing simulation data to answer questions about past simulations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "the user's question"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_all_simulations",
        "description": "Get a complete list of ALL simulations in the database, without any filtering or ranking. Use this when the user asks to see all simulations, how many exist, or wants a full overview.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "show_existing_simulation",
        "description": "Use this when the user wants to VIEW, SHOW, PLAY, or WATCH an EXISTING simulation by its ID — without creating a new one. This does NOT run a new simulation, it just confirms the ID to display.",
        "input_schema": {
            "type": "object",
            "properties": {
                "simulation_id": {"type": "integer", "description": "the ID of the existing simulation to show"},
            },
            "required": ["simulation_id"],
        },
    },
]

_SYSTEM_PROMPT = (
    "You are a rocket trajectory assistant with four tools: "
    "run_new_simulation, search_past_simulations, list_all_simulations, show_existing_simulation. "
    "\n\n"
    "CRITICAL RULE: if the user refers to an EXISTING simulation by number/ID and wants to "
    "view, show, play, watch, or 'run/launch' it (e.g. 'запусти симуляцію №1', 'show sim 3', "
    "'play the first one') — this means DISPLAY the existing one, NOT create a new one. "
    "In this case: call list_all_simulations only if you don't already know the ID exists, "
    "then call show_existing_simulation with that exact ID. NEVER call run_new_simulation "
    "for a request that references an existing simulation by number — that would create an "
    "unwanted duplicate. "
    "\n\n"
    "Only call run_new_simulation when the user gives brand NEW physical parameters "
    "(mass, velocity, angle) that are not just a reference to an existing simulation's ID. "
    "\n\n"
    "Always respond in the same language the user wrote in. Be concise and cite real numbers."
)


async def _execute_tool(name: str, tool_input: dict, db: AsyncSession) -> tuple[str, int | None]:
    if name == "show_existing_simulation":
        sim_id = tool_input["simulation_id"]
        sim = await db.get(Simulation, sim_id)
        if sim is None:
            return f"Simulation #{sim_id} not found.", None
        return f"Showing simulation #{sim_id}: apogee={sim.apogee:.2f}m, flight_time={sim.flight_time:.2f}s", sim_id

    if name == "list_all_simulations":
        result = await db.execute(select(Simulation).order_by(Simulation.id))
        sims = result.scalars().all()
        if not sims:
            return "No simulations in the database yet.", None
        lines = [
            f"#{s.id}: mass={s.mass}kg, v0={s.v0}m/s, angle={s.angle_deg}°, "
            f"drag_coefficient={s.drag_coefficient}, cross_section_area={s.cross_section_area}, "
            f"apogee={s.apogee:.2f}m, flight_time={s.flight_time:.2f}s, landing_x={s.landing_x:.2f}m"
            for s in sims
        ]
        return "\n".join(lines), None

    if name == "run_new_simulation":
        mass = tool_input["mass"]
        v0 = tool_input["v0"]
        angle_deg = tool_input["angle_deg"]
        drag_coefficient = tool_input.get("drag_coefficient", 0.47)
        cross_section_area = tool_input.get("cross_section_area", 0.03)

        result = run_simulation(
            mass=mass,
            drag_coefficient=drag_coefficient,
            cross_section_area=cross_section_area,
            v0=v0,
            angle_deg=angle_deg,
        )

        simulation = Simulation(
            mass=mass,
            drag_coefficient=drag_coefficient,
            cross_section_area=cross_section_area,
            v0=v0,
            angle_deg=angle_deg,
            apogee=result["apogee"],
            flight_time=result["flight_time"],
            max_velocity=result["max_velocity"],
            landing_x=result["landing_x"],
            trajectory=result["trajectory"],
        )
        db.add(simulation)
        await db.commit()
        await db.refresh(simulation)
        index_simulation(simulation)

        text = (
            f"Simulation #{simulation.id} created: apogee={result['apogee']:.2f}m, "
            f"flight_time={result['flight_time']:.2f}s, landing_x={result['landing_x']:.2f}m"
        )
        return text, simulation.id

    if name == "search_past_simulations":
        results = search_similar_with_ids(tool_input["query"], top_k=5)
        if not results:
            return "No simulations found in the database yet.", None
        return "\n".join(f"- {doc}" for _, doc in results), None

    return f"Unknown tool: {name}", None


async def run_agent(message: str, db: AsyncSession) -> dict:
    messages = [{"role": "user", "content": message}]
    last_simulation_id = None

    for step in range(8):
        response = _client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            system=_SYSTEM_PROMPT,
            tools=_tools,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            text_blocks = [b.text for b in response.content if b.type == "text"]
            reply = "\n".join(text_blocks) if text_blocks else "Готово."
            return {"reply": reply, "simulation_id": last_simulation_id}

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_text, sim_id = await _execute_tool(block.name, block.input, db)
                if sim_id is not None:
                    last_simulation_id = sim_id
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })

        messages.append({"role": "user", "content": tool_results})

    return {"reply": "Забагато кроків, спробуй перефразувати запит.", "simulation_id": last_simulation_id}