import pygame

class MasterConsole:
    def __init__(self, start_pos=(400, 300)):
        self.target_position = list(start_pos)
        self.cursor_speed = 5.0
        self.joystick = None
        
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            print(f"Controller connected: {self.joystick.get_name()}")
        else:
            print("No controller found. You can use arrow keys instead.")

    def update_input(self, keys_pressed):
        """
        Reads input from controller or keyboard and updates the target position.
        """
        dx, dy = 0, 0
        
        if self.joystick:
            axis_x = self.joystick.get_axis(0)
            axis_y = self.joystick.get_axis(1)
            
            if abs(axis_x) > 0.1: dx = axis_x * self.cursor_speed
            if abs(axis_y) > 0.1: dy = axis_y * self.cursor_speed
            
        else:
            if keys_pressed[pygame.K_LEFT]: dx = -self.cursor_speed
            if keys_pressed[pygame.K_RIGHT]: dx = self.cursor_speed
            if keys_pressed[pygame.K_UP]: dy = -self.cursor_speed
            if keys_pressed[pygame.K_Down] if hasattr(pygame, 'K_Down') else keys_pressed[pygame.K_DOWN]: dy = self.cursor_speed

        self.target_position[0] += dx
        self.target_position[1] += dy
        self.target_position[0] = max(0, min(900, self.target_position[0]))
        self.target_position[1] = max(0, min(650, self.target_position[1]))

    def apply_force_feedback(self, force):
        """
        Applies rumble to the controller based on force magnitude (0.0 to 1.0).
        """
        if self.joystick:
            try:
                self.joystick.rumble(force, force, 100)
            except Exception as e:
                pass
