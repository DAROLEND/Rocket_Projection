from sqlalchemy import Float, Integer, JSON, DateTime, func
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

    # результати
    apogee: Mapped[float] = mapped_column(Float)
    flight_time: Mapped[float] = mapped_column(Float)
    max_velocity: Mapped[float] = mapped_column(Float)
    landing_x: Mapped[float] = mapped_column(Float)

    trajectory: Mapped[list] = mapped_column(JSON)  # повний список точок

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())