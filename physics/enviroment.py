from physics.rocket import Rocket
import math

class SimulationEnviroment:

    def __init__(self, gravity: float = 9.81, air_density: float = 1.225, dt: float = 0.01):

        self.gravity = gravity
        self.air_density = air_density
        self.dt = dt


    def simulate(self, rocket: Rocket) -> list[tuple]:

        step_id = 1
        
        trajectory_points: list[tuple[int, float, float, float, float]] = []

        g = self.gravity
        t = 0
        x = rocket.x
        y = rocket.y
        vx = rocket.vx
        vy = rocket.vy
        air_density = self.air_density
        mass = rocket.mass
        drag_coefficient = rocket.drag_coefficient
        cross_section_area = rocket.cross_section_area
        dt = self.dt


        trajectory_points.append((step_id, t, x, y, vx, vy))

        while True:

            step_id += 1

            v = math.sqrt(vx**2 + vy**2)

            # Сила опору повітря
            if v > 0:
                F_drag = 0.5 * air_density * v**2 * drag_coefficient * cross_section_area

                # Проектування вектора сили опору на Осі Оу та Ох
                drag_x = -F_drag * (vx / v)
                drag_y = -F_drag * (vy / v)

                # Прискорення по горизоньталі та вертикаллі з урахуванням опору
                ax_drag = drag_x / mass
                ay_drag = drag_y / mass
            else:
                ax_drag = 0
                ay_drag = 0

            # Зміна швидкості по горизонталі та вертикалі залежно від діючих сил
            vx = vx + ax_drag * dt
            vy = vy + (ay_drag - g) * dt

            x = x + vx * dt
            y = y + vy * dt
            
            t = t + dt

            trajectory_points.append((step_id, round(t,4), round(x,4), round(y,4), round(vx,4), round(vy, 4)))

            if y < 0 or step_id >= 1000:
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