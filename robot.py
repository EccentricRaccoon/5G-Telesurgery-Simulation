import math

class Tissue:
    def __init__(self, rect, stiffness=0.5):
        """
        Tissue representation.
        rect is a tuple (x, y, width, height).
        stiffness determines how much force is returned per unit of penetration.
        """
        self.rect = rect
        self.stiffness = stiffness

    def calculate_force(self, point, radius=10):
        """
        Calculates force if the point (with given radius) intersects the tissue.
        Returns a scalar value representing the magnitude of the force.
        """
        x, y = point
        tx, ty, tw, th = self.rect
        
        
        closest_x = max(tx, min(x, tx + tw))
        closest_y = max(ty, min(y, ty + th))
        
        dx = x - closest_x
        dy = y - closest_y
        
        distance = math.sqrt(dx**2 + dy**2)
        
        if tx <= x <= tx + tw and ty <= y <= ty + th:
            depth_x = min(x - tx, (tx + tw) - x)
            depth_y = min(y - ty, (ty + th) - y)
            depth = min(depth_x, depth_y) + radius
            force = depth * self.stiffness
            return min(1.0, force)
            
        elif distance < radius:
            depth = radius - distance
            force = depth * self.stiffness
            return min(1.0, force)
            
        return 0.0

class RobotArm:
    def __init__(self, start_pos=(400, 300)):
        self.position = list(start_pos)
        self.radius = 15
        self.speed_limit = 5.0

    def update_position(self, target_pos):
        """Moves towards the target position."""
        if not target_pos:
            return
            
        target_x, target_y = target_pos
        
        dx = target_x - self.position[0]
        dy = target_y - self.position[1]
        
        dist = math.sqrt(dx**2 + dy**2)
        
        if dist > 0:
            move_dist = min(dist, self.speed_limit)
            self.position[0] += (dx / dist) * move_dist
            self.position[1] += (dy / dist) * move_dist

    def interact_with_tissue(self, tissues):
        """Calculates force generated from tissue interaction across multiple zones."""
        total_force = 0.0
        for tissue in tissues:
            total_force += tissue.calculate_force(self.position, self.radius)
        return min(1.0, total_force)
