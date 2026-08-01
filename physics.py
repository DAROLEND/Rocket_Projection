import math

density = 1.225


def calculate_trajectory(v0: float, angle_deg: float, dt: float, mass: float, drag_coefficient: float, cross_section_area: float) -> list[tuple[int, float, float, float, float, float]]:

    g = 9.81
    x = 0
    y = 0
    t = 0
    step_id = 1
    

    trajectory_points: list[tuple[int, float, float, float, float]] = []

    angle_rad = math.radians(angle_deg)
    vx = v0 * math.cos(angle_rad)
    vy = v0 * math.sin(angle_rad)

    trajectory_points.append((step_id, t, x, y, vx, vy))

    while True:

        step_id += 1

        v = math.sqrt(vx**2 + vy**2)

        # Сила опору повітря
        if v > 0:
            F_drag = 0.5 * density * v**2 * drag_coefficient * cross_section_area

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
        point_b: точка ПІСЛЯ приземлення (y < 0)п
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

trajectory = calculate_trajectory(v0=30, angle_deg=30, dt=0.01, mass  = 0.42, drag_coefficient = 0.47, cross_section_area = 0.039)

for step in trajectory:
    step_id, t_val, x_val, y_val, vx_val, vy_val = step
    print(f"Id: {step_id} | Час: {t_val:.4f}c. | Координати: (x: {x_val:.4f}, y: {y_val:.4f}) | Швидкість: vx={vx_val:.4f}, vy={vy_val:.4f}")