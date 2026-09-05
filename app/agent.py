import json
from collections import OrderedDict
from typing import AsyncIterator

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select
from app.models import Simulation

from app.config import settings
from app.database import async_session
from app.simulation_service import run_simulation, find_optimal_angle
from app.models import Simulation
from app.rag_service import index_simulation, search_similar_with_ids

_async_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

_MODEL = "claude-sonnet-4-5"

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
    {
        "name": "compare_simulations",
        "description": (
            "Activate the side-by-side comparison view for 2-6 EXISTING simulations by ID. "
            "Use this whenever the user asks to compare, overlay, or show multiple simulations "
            "together (e.g. 'порівняй симуляції 2, 3 та 4', 'compare sims 1 and 5')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "simulation_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "2 to 6 IDs of existing simulations to compare",
                },
            },
            "required": ["simulation_ids"],
        },
    },
    {
        "name": "find_optimal_angle",
        "description": (
            "Numerically find the launch angle that maximizes range (landing distance) for "
            "a given mass/speed/drag, then run and save that simulation. Use this whenever the "
            "user asks for the 'best', 'optimal', or 'maximum distance' angle instead of giving "
            "one themselves (e.g. 'який кут дасть найбільшу дальність для маси 1кг і швидкості 40м/с')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mass": {"type": "number", "description": "rocket mass in kg"},
                "v0": {"type": "number", "description": "initial launch velocity in m/s"},
                "drag_coefficient": {"type": "number", "description": "default 0.47"},
                "cross_section_area": {"type": "number", "description": "default 0.03"},
            },
            "required": ["mass", "v0"],
        },
    },
]

_SYSTEM_PROMPT = (
    "You are a rocket trajectory assistant with six tools: "
    "run_new_simulation, search_past_simulations, list_all_simulations, show_existing_simulation, "
    "compare_simulations, find_optimal_angle. "
    "\n\n"
    "CRITICAL RULE: if the user asks for the angle that gives the BEST/MAXIMUM/OPTIMAL range "
    "(e.g. 'найкращий кут для дальності', 'what angle gives max distance'), call "
    "find_optimal_angle instead of run_new_simulation — don't guess an angle yourself. "
    "\n\n"
    "CRITICAL RULE: if the user refers to an EXISTING simulation by number/ID and wants to "
    "view, show, play, watch, or 'run/launch' it (e.g. 'запусти симуляцію №1', 'show sim 3', "
    "'play the first one') — this means DISPLAY the existing one, NOT create a new one. "
    "In this case: call list_all_simulations only if you don't already know the ID exists, "
    "then call show_existing_simulation with that exact ID. NEVER call run_new_simulation "
    "for a request that references an existing simulation by number — that would create an "
    "unwanted duplicate. "
    "\n\n"
    "CRITICAL RULE: if the user asks to COMPARE, overlay, or show multiple (2+) existing "
    "simulations together (e.g. 'порівняй 2, 3 та 4', 'compare sims 1 and 5'), call "
    "compare_simulations with those IDs. Do NOT call show_existing_simulation repeatedly for "
    "this — only compare_simulations actually activates the comparison view. "
    "\n\n"
    "Only call run_new_simulation when the user gives brand NEW physical parameters "
    "(mass, velocity, angle) that are not just a reference to an existing simulation's ID. "
    "\n\n"
    "Always respond in the same language the user wrote in. Be concise and cite real numbers."
)


# In-memory per-session conversation history so the agent remembers earlier
# turns (e.g. "а тепер додай ще #5"). No persistence beyond process lifetime —
# fine for a demo, and bounded below so long-running sessions can't grow forever.
_MAX_HISTORY_TURNS = 8
_MAX_SESSIONS = 200
_conversations: "OrderedDict[str, list[dict]]" = OrderedDict()


def _get_history(session_id: str | None) -> list[dict]:
    if not session_id:
        return []
    return list(_conversations.get(session_id, []))


def _save_history(session_id: str | None, messages: list[dict]) -> None:
    if not session_id:
        return

    # Cut only at real turn boundaries (a plain-text user message), never in the
    # middle of a tool_use/tool_result pair — otherwise the next API call would
    # ship an orphaned tool_result with no matching tool_use and get rejected.
    turn_starts = [i for i, m in enumerate(messages) if m["role"] == "user" and isinstance(m["content"], str)]
    if len(turn_starts) > _MAX_HISTORY_TURNS:
        messages = messages[turn_starts[-_MAX_HISTORY_TURNS]:]

    _conversations[session_id] = messages
    _conversations.move_to_end(session_id)
    while len(_conversations) > _MAX_SESSIONS:
        _conversations.popitem(last=False)


async def _create_and_save_simulation(
    db: AsyncSession, mass: float, v0: float, angle_deg: float,
    drag_coefficient: float = 0.47, cross_section_area: float = 0.03,
) -> Simulation:
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
    return simulation


async def _execute_tool(name: str, tool_input: dict, db: AsyncSession) -> tuple[str, int | None, list[int] | None]:
    if name == "show_existing_simulation":
        sim_id = tool_input["simulation_id"]
        sim = await db.get(Simulation, sim_id)
        if sim is None:
            return f"Simulation #{sim_id} not found.", None, None
        return f"Showing simulation #{sim_id}: apogee={sim.apogee:.2f}m, flight_time={sim.flight_time:.2f}s", sim_id, None

    if name == "compare_simulations":
        ids = list(dict.fromkeys(tool_input["simulation_ids"]))[:6]
        if len(ids) < 2:
            return "Need at least 2 simulation IDs to compare.", None, None

        found_ids = []
        lines = []
        for sim_id in ids:
            sim = await db.get(Simulation, sim_id)
            if sim is None:
                lines.append(f"#{sim_id}: not found, skipped")
                continue
            found_ids.append(sim_id)
            lines.append(
                f"#{sim.id}: apogee={sim.apogee:.2f}m, flight_time={sim.flight_time:.2f}s, landing_x={sim.landing_x:.2f}m"
            )

        if len(found_ids) < 2:
            return "Not enough valid simulations to compare.\n" + "\n".join(lines), None, None

        return "Comparing:\n" + "\n".join(lines), None, found_ids

    if name == "list_all_simulations":
        result = await db.execute(select(Simulation).order_by(Simulation.id))
        sims = result.scalars().all()
        if not sims:
            return "No simulations in the database yet.", None, None
        lines = [
            f"#{s.id}: mass={s.mass}kg, v0={s.v0}m/s, angle={s.angle_deg}°, "
            f"drag_coefficient={s.drag_coefficient}, cross_section_area={s.cross_section_area}, "
            f"apogee={s.apogee:.2f}m, flight_time={s.flight_time:.2f}s, landing_x={s.landing_x:.2f}m"
            for s in sims
        ]
        return "\n".join(lines), None, None

    if name == "run_new_simulation":
        simulation = await _create_and_save_simulation(
            db,
            mass=tool_input["mass"],
            v0=tool_input["v0"],
            angle_deg=tool_input["angle_deg"],
            drag_coefficient=tool_input.get("drag_coefficient", 0.47),
            cross_section_area=tool_input.get("cross_section_area", 0.03),
        )
        text = (
            f"Simulation #{simulation.id} created: apogee={simulation.apogee:.2f}m, "
            f"flight_time={simulation.flight_time:.2f}s, landing_x={simulation.landing_x:.2f}m"
        )
        return text, simulation.id, None

    if name == "find_optimal_angle":
        mass = tool_input["mass"]
        v0 = tool_input["v0"]
        drag_coefficient = tool_input.get("drag_coefficient", 0.47)
        cross_section_area = tool_input.get("cross_section_area", 0.03)

        optimal = find_optimal_angle(
            mass=mass, v0=v0, drag_coefficient=drag_coefficient, cross_section_area=cross_section_area,
        )
        simulation = await _create_and_save_simulation(
            db, mass=mass, v0=v0, angle_deg=optimal["angle_deg"],
            drag_coefficient=drag_coefficient, cross_section_area=cross_section_area,
        )
        text = (
            f"Optimal launch angle is {optimal['angle_deg']:.1f}° — simulation #{simulation.id} "
            f"created: apogee={simulation.apogee:.2f}m, flight_time={simulation.flight_time:.2f}s, "
            f"landing_x={simulation.landing_x:.2f}m (max range)"
        )
        return text, simulation.id, None

    if name == "search_past_simulations":
        results = search_similar_with_ids(tool_input["query"], top_k=5)
        if not results:
            return "No simulations found in the database yet.", None, None
        return "\n".join(f"- {doc}" for _, doc in results), None, None

    return f"Unknown tool: {name}", None, None


async def run_agent(message: str, db: AsyncSession, session_id: str | None = None) -> dict:
    messages = _get_history(session_id)
    messages.append({"role": "user", "content": message})
    last_simulation_id = None
    last_compare_ids = None

    for step in range(8):
        response = await _async_client.messages.create(
            model=_MODEL,
            max_tokens=1000,
            system=_SYSTEM_PROMPT,
            tools=_tools,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            _save_history(session_id, messages)
            text_blocks = [b.text for b in response.content if b.type == "text"]
            reply = "\n".join(text_blocks) if text_blocks else "Готово."
            return {
                "reply": reply,
                "simulation_id": last_simulation_id,
                "compare_simulation_ids": last_compare_ids,
            }

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_text, sim_id, compare_ids = await _execute_tool(block.name, block.input, db)
                if sim_id is not None:
                    last_simulation_id = sim_id
                if compare_ids is not None:
                    last_compare_ids = compare_ids
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })

        messages.append({"role": "user", "content": tool_results})

    _save_history(session_id, messages)
    return {
        "reply": "Забагато кроків, спробуй перефразувати запит.",
        "simulation_id": last_simulation_id,
        "compare_simulation_ids": last_compare_ids,
    }


def _sse(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


async def run_agent_stream(message: str, session_id: str | None = None) -> AsyncIterator[str]:
    """Same tool-use loop as run_agent, but streams text as it's generated and
    emits a line per tool call so the frontend can show a live trace of what
    the agent is doing, not just the final answer."""
    messages = _get_history(session_id)
    messages.append({"role": "user", "content": message})
    last_simulation_id = None
    last_compare_ids = None

    async with async_session() as db:
        for step in range(8):
            async with _async_client.messages.stream(
                model=_MODEL,
                max_tokens=1000,
                system=_SYSTEM_PROMPT,
                tools=_tools,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield _sse({"type": "text_delta", "text": text})
                response = await stream.get_final_message()

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                _save_history(session_id, messages)
                yield _sse({
                    "type": "done",
                    "simulation_id": last_simulation_id,
                    "compare_simulation_ids": last_compare_ids,
                })
                return

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    yield _sse({"type": "tool_call", "name": block.name, "input": block.input})
                    result_text, sim_id, compare_ids = await _execute_tool(block.name, block.input, db)
                    if sim_id is not None:
                        last_simulation_id = sim_id
                    if compare_ids is not None:
                        last_compare_ids = compare_ids
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    })

            messages.append({"role": "user", "content": tool_results})

        fallback = "Забагато кроків, спробуй перефразувати запит."
        messages.append({"role": "assistant", "content": [{"type": "text", "text": fallback}]})
        _save_history(session_id, messages)
        yield _sse({"type": "text_delta", "text": fallback})
        yield _sse({
            "type": "done",
            "simulation_id": last_simulation_id,
            "compare_simulation_ids": last_compare_ids,
        })