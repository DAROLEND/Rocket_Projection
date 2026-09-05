from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

class SimulationCreate(BaseModel):
    mass: float = Field(gt=0, description="Маса ракети, кг", examples=[0.8])
    drag_coefficient: float = Field(gt=0, examples=[0.4])
    cross_section_area: float = Field(gt=0, description="Площа перерізу, м²", examples=[0.03])
    v0: float = Field(gt=0, description="Початкова швидкість, м/с", examples=[60])
    angle_deg: float = Field(ge=0, le=90, description="Кут запуску, градуси", examples=[45])

    thrust: float | None = Field(default=None, gt=0, description="Тяга двигуна, Н (опційно)")
    burn_time: float | None = Field(default=None, gt=0, description="Час горіння двигуна, с (опційно)")
    propellant_mass: float | None = Field(default=None, gt=0, description="Маса палива, кг (опційно)")

    parachute_cd: float | None = Field(default=None, gt=0, description="Коеф. опору парашута (опційно)")
    parachute_area: float | None = Field(default=None, gt=0, description="Площа парашута, м² (опційно)")

    integration_method: Literal["euler", "rk4"] = Field(default="euler", description="Метод чисельного інтегрування")

    @model_validator(mode="after")
    def _validate_engine_and_parachute(self):
        engine_fields = (self.thrust, self.burn_time, self.propellant_mass)
        if any(f is not None for f in engine_fields) and not all(f is not None for f in engine_fields):
            raise ValueError("thrust, burn_time і propellant_mass потрібно задавати разом")
        if self.propellant_mass is not None and self.propellant_mass >= self.mass:
            raise ValueError("propellant_mass має бути меншою за mass (інакше суха маса <= 0)")

        parachute_fields = (self.parachute_cd, self.parachute_area)
        if any(f is not None for f in parachute_fields) and not all(f is not None for f in parachute_fields):
            raise ValueError("parachute_cd і parachute_area потрібно задавати разом")

        return self

class SimulationResult(BaseModel):
    id: int
    mass: float
    drag_coefficient: float
    cross_section_area: float
    v0: float
    angle_deg: float

    thrust: float | None = None
    burn_time: float | None = None
    propellant_mass: float | None = None
    parachute_cd: float | None = None
    parachute_area: float | None = None
    integration_method: str = "euler"

    apogee: float = Field(description="Максимальна висота, м")
    flight_time: float = Field(description="Час польоту, с")
    max_velocity: float = Field(description="Максимальна швидкість, м/с")
    landing_x: float = Field(description="Дальність приземлення, м")

    model_config = ConfigDict(from_attributes=True)  # дозволяє створювати схему прямо з SQLAlchemy об'єкта

class SimulationDetail(SimulationResult):
    trajectory: list = Field(description="Точки траєкторії: (step, t, x, y, vx, vy)")

class AskRequest(BaseModel):
    question: str = Field(min_length=3, description="Питання про твої симуляції", examples=["Яка симуляція мала найбільшу дальність?"])

class AskResponse(BaseModel):
    answer: str = Field(description="Пряма відповідь на питання користувача")
    confidence: str = Field(description="high, medium, або low — впевненість у відповіді")
    relevant_simulation_ids: list[int] = Field(description="ID симуляцій, використаних для відповіді")

class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, description="Повідомлення до AI-агента", examples=["Порівняй симуляції 2, 3 та 4"])
    session_id: str | None = Field(default=None, description="ID діалогу для збереження контексту між повідомленнями")

class AgentChatResponse(BaseModel):
    reply: str
    simulation_id: int | None = Field(default=None, description="ID симуляції, яку варто показати (якщо є)")
    compare_simulation_ids: list[int] | None = Field(default=None, description="ID симуляцій для режиму порівняння (якщо агент його активував)")

class OptimalAngleRequest(BaseModel):
    mass: float = Field(gt=0, examples=[0.8])
    drag_coefficient: float = Field(gt=0, examples=[0.4])
    cross_section_area: float = Field(gt=0, examples=[0.03])
    v0: float = Field(gt=0, examples=[60])

class OptimalAngleResponse(BaseModel):
    angle_deg: float = Field(description="Знайдений оптимальний кут запуску, градуси")
    apogee: float
    flight_time: float
    max_velocity: float
    landing_x: float = Field(description="Максимальна дальність при цьому куті, м")

class DispersionRequest(BaseModel):
    mass: float = Field(gt=0, examples=[0.8])
    drag_coefficient: float = Field(gt=0, examples=[0.4])
    cross_section_area: float = Field(gt=0, examples=[0.03])
    v0: float = Field(gt=0, examples=[60])
    angle_deg: float = Field(ge=0, le=90, examples=[45])

    thrust: float | None = Field(default=None, gt=0)
    burn_time: float | None = Field(default=None, gt=0)
    propellant_mass: float | None = Field(default=None, gt=0)
    parachute_cd: float | None = Field(default=None, gt=0)
    parachute_area: float | None = Field(default=None, gt=0)

    trials: int = Field(default=200, ge=10, le=500, description="Кількість Monte Carlo прогонів")
    angle_std_deg: float = Field(default=1.0, ge=0, description="Стд. відхилення шуму кута, градуси")
    v0_std_pct: float = Field(default=2.0, ge=0, description="Стд. відхилення шуму швидкості, % від v0")

class DispersionPoint(BaseModel):
    landing_x: float
    apogee: float
    flight_time: float

class DispersionResponse(BaseModel):
    nominal: dict = Field(description="Результат номінального (без шуму) запуску")
    points: list[DispersionPoint]
    landing_x_mean: float
    landing_x_std: float
