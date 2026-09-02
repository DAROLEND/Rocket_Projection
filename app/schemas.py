from pydantic import BaseModel, Field

class SimulationCreate(BaseModel):
    mass: float = Field(gt=0, description="Маса ракети, кг")
    drag_coefficient: float = Field(gt=0)
    cross_section_area: float = Field(gt=0)
    v0: float = Field(gt=0, description="Початкова швидкість, м/с")
    angle_deg: float = Field(ge=0, le=90, description="Кут запуску, градуси")

class SimulationResult(BaseModel):
    id: int
    mass: float
    drag_coefficient: float
    cross_section_area: float
    v0: float
    angle_deg: float
    apogee: float
    flight_time: float
    max_velocity: float
    landing_x: float

    class Config:
        from_attributes = True  # дозволяє створювати схему прямо з SQLAlchemy об'єкта

class SimulationDetail(SimulationResult):
    trajectory: list

class AskRequest(BaseModel):
    question: str = Field(min_length=3, description="Питання про твої симуляції")

class AskResponse(BaseModel):
    answer: str = Field(description="Пряма відповідь на питання користувача")
    confidence: str = Field(description="high, medium, або low — впевненість у відповіді")
    relevant_simulation_ids: list[int] = Field(description="ID симуляцій, використаних для відповіді")