from sqlalchemy import Float, Integer, JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.database import Base

class Simulation(Base):
    __tablename__ = "simulations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # вхідні параметри
    mass: Mapped[float] = mapped_column(Float)
    drag_coefficient: Mapped[float] = mapped_column(Float)
    cross_section_area: Mapped[float] = mapped_column(Float)
    v0: Mapped[float] = mapped_column(Float)
    angle_deg: Mapped[float] = mapped_column(Float)

    # опційні параметри двигуна — якщо не задані, чиста балістична траєкторія (як раніше)
    thrust: Mapped[float | None] = mapped_column(Float, nullable=True)
    burn_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    propellant_mass: Mapped[float | None] = mapped_column(Float, nullable=True)

    # опційний парашут — спрацьовує в момент початку падіння (vy < 0)
    parachute_cd: Mapped[float | None] = mapped_column(Float, nullable=True)
    parachute_area: Mapped[float | None] = mapped_column(Float, nullable=True)

    integration_method: Mapped[str] = mapped_column(String, nullable=False, server_default="euler")

    # результати
    apogee: Mapped[float] = mapped_column(Float)
    flight_time: Mapped[float] = mapped_column(Float)
    max_velocity: Mapped[float] = mapped_column(Float)
    landing_x: Mapped[float] = mapped_column(Float)

    trajectory: Mapped[list] = mapped_column(JSON)  # повний список точок

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())