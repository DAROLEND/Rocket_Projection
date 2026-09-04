from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import engine, Base, get_db
from app.models import Simulation
from app.schemas import (
    SimulationCreate,
    SimulationResult,
    SimulationDetail,
    AskRequest,
    AskResponse,
    AgentChatRequest,
    AgentChatResponse,
)
from app.simulation_service import run_simulation
from app.rag_service import index_simulation, answer_question

from app.agent import run_agent

from app.rag_service import index_simulation, answer_question, _collection


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Rocket Trajectory API", lifespan=lifespan)

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


@app.post("/simulate", response_model=SimulationDetail)
async def create_simulation(payload: SimulationCreate, db: AsyncSession = Depends(get_db)):
    result = run_simulation(**payload.model_dump())

    simulation = Simulation(
        mass=payload.mass,
        drag_coefficient=payload.drag_coefficient,
        cross_section_area=payload.cross_section_area,
        v0=payload.v0,
        angle_deg=payload.angle_deg,
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


@app.get("/simulations", response_model=list[SimulationResult])
async def list_simulations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Simulation).order_by(Simulation.id.desc()))
    return result.scalars().all()


@app.get("/simulations/{simulation_id}", response_model=SimulationDetail)
async def get_simulation(simulation_id: int, db: AsyncSession = Depends(get_db)):
    simulation = await db.get(Simulation, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return simulation


@app.post("/ask", response_model=AskResponse)
async def ask_question(payload: AskRequest):
    result = answer_question(payload.question)
    return result

@app.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(payload: AgentChatRequest, db: AsyncSession = Depends(get_db)):
    result = await run_agent(payload.message, db)
    return AgentChatResponse(**result)

@app.delete("/simulations/{simulation_id}", status_code=204)
async def delete_simulation(simulation_id: int, db: AsyncSession = Depends(get_db)):
    simulation = await db.get(Simulation, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    await db.delete(simulation)
    await db.commit()

    try:
        _collection.delete(ids=[str(simulation_id)])
    except Exception:
        pass  # якщо запису нема в ChromaDB — ігноруємо, не критично

    return None