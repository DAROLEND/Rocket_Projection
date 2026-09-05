import math

from physics.rocket import Rocket


class SimulationEnvironment:

    def __init__(self, gravity: float = 9.81, air_density: float = 1.225, dt: float = 0.01, max_time: float = 120.0):

        self.gravity = gravity
        self.air_density = air_density
        self.dt = dt
        self.max_time = max_time  # safety cutoff in seconds, independent of dt

    def _acceleration(self, rocket: Rocket, t: float, vx: float, vy: float) -> tuple[float, float]:
        """Total acceleration from gravity + air drag + engine thrust (if still burning)."""
        v = math.sqrt(vx ** 2 + vy ** 2)
        mass = rocket.mass_at(t)
        drag_coefficient, cross_section_area = rocket.drag_profile(vy)

        if v > 0:
            F_drag = 0.5 * self.air_density * v ** 2 * drag_coefficient * cross_section_area
            ax_drag = -F_drag * (vx / v) / mass
            ay_drag = -F_drag * (vy / v) / mass
        else:
            ax_drag = 0.0
            ay_drag = 0.0

        thrust_ax, thrust_ay = rocket.thrust_accel(t)

        ax = ax_drag + thrust_ax
        ay = ay_drag + thrust_ay - self.gravity
        return ax, ay

    def _euler_step(self, rocket: Rocket, t: float, state: tuple, dt: float) -> tuple:
        """Semi-implicit (symplectic) Euler: velocity is updated from forces evaluated
        at the start of the step, then position is updated using the *new* velocity."""
        x, y, vx, vy = state
        ax, ay = self._acceleration(rocket, t, vx, vy)

        new_vx = vx + ax * dt
        new_vy = vy + ay * dt
        new_x = x + new_vx * dt
        new_y = y + new_vy * dt
        return (new_x, new_y, new_vx, new_vy)

    def _derivative(self, rocket: Rocket, t: float, state: tuple) -> tuple:
        x, y, vx, vy = state
        ax, ay = self._acceleration(rocket, t, vx, vy)
        return (vx, vy, ax, ay)

    def _rk4_step(self, rocket: Rocket, t: float, state: tuple, dt: float) -> tuple:
        """Classic 4th-order Runge-Kutta — higher accuracy per step than Euler, at the
        cost of 4 force evaluations instead of 1."""
        k1 = self._derivative(rocket, t, state)
        s2 = tuple(s + dt / 2 * k for s, k in zip(state, k1))
        k2 = self._derivative(rocket, t + dt / 2, s2)
        s3 = tuple(s + dt / 2 * k for s, k in zip(state, k2))
        k3 = self._derivative(rocket, t + dt / 2, s3)
        s4 = tuple(s + dt * k for s, k in zip(state, k3))
        k4 = self._derivative(rocket, t + dt, s4)

        return tuple(
            s + dt / 6 * (a + 2 * b + 2 * c + d)
            for s, a, b, c, d in zip(state, k1, k2, k3, k4)
        )

    def simulate(self, rocket: Rocket, method: str = "euler") -> list[tuple]:

        step = self._rk4_step if method == "rk4" else self._euler_step

        step_id = 1
        trajectory_points: list[tuple[int, float, float, float, float, float]] = []

        t = 0.0
        state = (rocket.x, rocket.y, rocket.vx, rocket.vy)
        trajectory_points.append((step_id, t, *state))

        while True:
            step_id += 1

            state = step(rocket, t, state, self.dt)
            t = t + self.dt

            x, y, vx, vy = state
            trajectory_points.append((step_id, round(t, 4), round(x, 4), round(y, 4), round(vx, 4), round(vy, 4)))

            if y < 0 or t >= self.max_time:
                break

        def interpolate_landing(points_list) -> tuple:

            point_a, point_b = points_list[-2:]

            '''
            point_a: точка ДО приземлення (y > 0)
            point_b: точка ПІСЛЯ приземлення (y < 0)
            '''

            step_id_a, t_a, x_a, y_a, vx_a, vy_a = point_a
            step_id_b, t_b, x_b, y_b, vx_b, vy_b = point_b

            k = y_a / (y_a - y_b)

            inter_t = t_a + k * (t_b - t_a)
            inter_x = x_a + k * (x_b - x_a)
            inter_vx = vx_a + k * (vx_b - vx_a)
            inter_vy = vy_a + k * (vy_b - vy_a)

            new_point = (step_id_b, inter_t, inter_x, 0, inter_vx, inter_vy)
            points_list[-1] = new_point

            return points_list

        # Перевірка на те, чи y дійсно менше 0 в останньому елементі списку
        if trajectory_points[-1][3] < 0:
            return interpolate_landing(trajectory_points)
        return trajectory_points
