from contextlib import asynccontextmanager
import anyio
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import engine, Base, get_db, ensure_schema_migrated
from app.models import Simulation
from app.schemas import (
    SimulationCreate,
    SimulationResult,
    SimulationDetail,
    AskRequest,
    AskResponse,
    AgentChatRequest,
    AgentChatResponse,
    OptimalAngleRequest,
    OptimalAngleResponse,
    DispersionRequest,
    DispersionResponse,
)
from app.simulation_service import run_simulation, find_optimal_angle, run_dispersion
from app.rag_service import index_simulation, answer_question, _collection
from app.agent import run_agent, run_agent_stream


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await ensure_schema_migrated(conn)
    yield


app = FastAPI(
    title="Rocket Trajectory API",
    description=(
        "Фізична симуляція траєкторії ракети з опором повітря, плюс RAG (semantic "
        "search + structured output) та AI-агент з tool-use над тими ж даними."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static", html=True), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
      <head><meta charset="UTF-8"><title>Rocket Trajectory API</title></head>
      <body style="font-family: sans-serif; text-align: center; margin-top: 100px;">
        <h1>Rocket Trajectory API</h1>
        <p><a href="/docs">Swagger docs</a></p>
        <p><a href="/static/index.html" style="font-size: 18px; padding: 10px 20px; background: #2563eb; color: white; text-decoration: none; border-radius: 8px;">Відкрити візуалізацію</a></p>
      </body>
    </html>
    """


@app.post("/simulate", response_model=SimulationDetail, tags=["simulations"], summary="Запустити нову симуляцію")
async def create_simulation(payload: SimulationCreate, db: AsyncSession = Depends(get_db)):
    result = run_simulation(**payload.model_dump())

    simulation = Simulation(
        mass=payload.mass,
        drag_coefficient=payload.drag_coefficient,
        cross_section_area=payload.cross_section_area,
        v0=payload.v0,
        angle_deg=payload.angle_deg,
        thrust=payload.thrust,
        burn_time=payload.burn_time,
        propellant_mass=payload.propellant_mass,
        parachute_cd=payload.parachute_cd,
        parachute_area=payload.parachute_area,
        integration_method=payload.integration_method,
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


@app.post(
    "/simulate/optimal-angle",
    response_model=OptimalAngleResponse,
    tags=["simulations"],
    summary="Знайти кут запуску з максимальною дальністю",
    description=(
        "Без опору повітря оптимальний кут завжди 45°. З квадратичним опором дальність "
        "як функція кута лишається одновершинною, але пік зсувається нижче 45° - шукаємо "
        "його чисельно golden-section search'ем, а не з формули."
    ),
)
async def optimal_angle(payload: OptimalAngleRequest):
    result = await anyio.to_thread.run_sync(
        lambda: find_optimal_angle(
            mass=payload.mass, v0=payload.v0,
            drag_coefficient=payload.drag_coefficient, cross_section_area=payload.cross_section_area,
        )
    )
    return result


@app.post(
    "/simulate/dispersion",
    response_model=DispersionResponse,
    tags=["simulations"],
    summary="Monte Carlo розкид приземлення",
    description=(
        "Прогонить один і той самий запуск N разів з випадковим шумом на кут і швидкість, "
        "і повертає розкид точок приземлення (не зберігається в БД - суто аналіз)."
    ),
)
async def dispersion(payload: DispersionRequest):
    result = await anyio.to_thread.run_sync(
        lambda: run_dispersion(**payload.model_dump())
    )
    return result


@app.get("/simulations", response_model=list[SimulationResult], tags=["simulations"], summary="Список усіх симуляцій")
async def list_simulations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Simulation).order_by(Simulation.id.desc()))
    return result.scalars().all()


@app.get("/simulations/{simulation_id}", response_model=SimulationDetail, tags=["simulations"], summary="Деталі симуляції з повною траєкторією")
async def get_simulation(simulation_id: int, db: AsyncSession = Depends(get_db)):
    simulation = await db.get(Simulation, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return simulation


@app.put(
    "/simulations/{simulation_id}",
    response_model=SimulationDetail,
    tags=["simulations"],
    summary="Редагувати симуляцію (перерахунок з новими параметрами, той самий id)",
)
async def update_simulation(simulation_id: int, payload: SimulationCreate, db: AsyncSession = Depends(get_db)):
    simulation = await db.get(Simulation, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    result = run_simulation(**payload.model_dump())

    simulation.mass = payload.mass
    simulation.drag_coefficient = payload.drag_coefficient
    simulation.cross_section_area = payload.cross_section_area
    simulation.v0 = payload.v0
    simulation.angle_deg = payload.angle_deg
    simulation.thrust = payload.thrust
    simulation.burn_time = payload.burn_time
    simulation.propellant_mass = payload.propellant_mass
    simulation.parachute_cd = payload.parachute_cd
    simulation.parachute_area = payload.parachute_area
    simulation.integration_method = payload.integration_method
    simulation.apogee = result["apogee"]
    simulation.flight_time = result["flight_time"]
    simulation.max_velocity = result["max_velocity"]
    simulation.landing_x = result["landing_x"]
    simulation.trajectory = result["trajectory"]

    await db.commit()
    await db.refresh(simulation)

    index_simulation(simulation)

    return simulation


@app.post(
    "/ask",
    response_model=AskResponse,
    tags=["rag"],
    summary="Питання по симуляціях (RAG, structured output)",
    description=(
        "Чистий RAG-пайплайн: embedding питання -> semantic search по ChromaDB -> "
        "grounded-відповідь від Claude у вигляді structured output (Instructor). "
        "Без tool-use - одноразовий запит-відповідь."
    ),
)
async def ask_question(payload: AskRequest):
    result = answer_question(payload.question)
    return result


@app.post(
    "/agent/chat",
    response_model=AgentChatResponse,
    tags=["agent"],
    summary="AI-агент з tool use (без стрімінгу)",
    description="Той самий агент, що й /agent/chat/stream, але повертає готову відповідь одним блоком - зручно для curl/скриптів.",
)
async def agent_chat(payload: AgentChatRequest, db: AsyncSession = Depends(get_db)):
    result = await run_agent(payload.message, db, payload.session_id)
    return AgentChatResponse(**result)


@app.post(
    "/agent/chat/stream",
    tags=["agent"],
    summary="AI-агент з tool use (NDJSON-стрім)",
    description=(
        "Стрімить відповідь агента по токенах плюс окремі події на кожен виклик "
        "інструменту, щоб фронтенд міг показати живий трейс роботи агента. "
        "Формат: newline-delimited JSON, по одному events на рядок - "
        "{type: text_delta|tool_call|done}."
    ),
)
async def agent_chat_stream(payload: AgentChatRequest):
    return StreamingResponse(
        run_agent_stream(payload.message, payload.session_id),
        media_type="application/x-ndjson",
    )


@app.delete("/simulations/{simulation_id}", status_code=204, tags=["simulations"], summary="Видалити симуляцію (SQL + ChromaDB)")
async def delete_simulation(simulation_id: int, db: AsyncSession = Depends(get_db)):
    simulation = await db.get(Simulation, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    await db.delete(simulation)
    await db.commit()

    try:
        _collection.delete(ids=[str(simulation_id)])
    except Exception:
        pass  # якщо запису нема в ChromaDB - ігноруємо, не критично

    return None