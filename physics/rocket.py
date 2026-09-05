import math


class Rocket:

    def __init__(
        self,
        mass: float,
        drag_coefficient: float,
        cross_section_area: float,
        x: float = 0,
        y: float = 0,
        vx: float = 0,
        vy: float = 0,
        thrust: float = 0.0,
        burn_time: float = 0.0,
        propellant_mass: float = 0.0,
        parachute_cd: float | None = None,
        parachute_area: float | None = None,
    ):

        self.mass = mass  # wet mass (with propellant), used as the reference mass throughout flight
        self.drag_coefficient = drag_coefficient
        self.cross_section_area = cross_section_area
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy

        self.thrust = thrust
        self.burn_time = burn_time
        self.propellant_mass = propellant_mass

        self.parachute_cd = parachute_cd
        self.parachute_area = parachute_area

        # Thrust is applied along the initial launch direction — this is a simple
        # sounding-rocket model (no active guidance/pitch program), not a steered vehicle.
        v0 = math.sqrt(vx ** 2 + vy ** 2)
        if v0 > 0:
            self._thrust_dir = (vx / v0, vy / v0)
        else:
            self._thrust_dir = (0.0, 1.0)

    def mass_at(self, t: float) -> float:
        if self.propellant_mass <= 0 or self.burn_time <= 0:
            return self.mass
        if t >= self.burn_time:
            return self.mass - self.propellant_mass
        return self.mass - self.propellant_mass * (t / self.burn_time)

    def thrust_accel(self, t: float) -> tuple[float, float]:
        if self.thrust <= 0 or self.burn_time <= 0 or t >= self.burn_time:
            return 0.0, 0.0
        a = self.thrust / self.mass_at(t)
        dir_x, dir_y = self._thrust_dir
        return a * dir_x, a * dir_y

    def drag_profile(self, vy: float) -> tuple[float, float]:
        """Cd/area to use for drag at the current instant — swaps to the parachute's
        (much higher) values once the rocket starts falling, if one is fitted."""
        if self.parachute_cd is not None and self.parachute_area is not None and vy < 0:
            return self.parachute_cd, self.parachute_area
        return self.drag_coefficient, self.cross_section_area
