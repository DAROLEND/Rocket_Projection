class Rocket:

    def __init__(self, mass: float, drag_coefficient: float, cross_section_area: float, x: float = 0, y: float = 0, vx: float = 0, vy: float = 0):

        self.mass = mass
        self.drag_coefficient = drag_coefficient
        self.cross_section_area = cross_section_area
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy