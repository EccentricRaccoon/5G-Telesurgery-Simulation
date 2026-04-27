import pygame
import sys
import os
import math
import random
import threading
import time as _time
from network import Matlab5GNetwork
from robot import RobotArm, Tissue
from master_console import MasterConsole
from live_graphs import LiveGraphWindow

SCREEN_WIDTH = 900
SCREEN_HEIGHT = 650
FPS = 60
ACCURACY_FAIL_THRESHOLD = 90.0
ACCURACY_GRACE_SAMPLES = 30
FAIL_OVERLAY_DURATION = 1.5

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 50, 50)
BLUE = (50, 80, 220)
GREEN = (50, 200, 50)
GRAY = (200, 200, 200)
DARK_GRAY = (60, 60, 60)
CYAN = (0, 200, 220)
ORANGE = (255, 160, 40)
LIGHT_RED = (255, 100, 100)
LIGHT_GREEN = (100, 255, 100)
DARK_BG = (30, 30, 40)
SKIN_COLOR = (255, 218, 185)
SKIN_DARK = (230, 190, 155)
ORGAN_RED = (180, 40, 40)
ORGAN_PINK = (220, 120, 120)
VEIN_BLUE = (70, 70, 180)
INCISION_YELLOW = (255, 230, 0)
TRAIL_5G = (0, 180, 220, 120)
TRAIL_4G = (255, 140, 0, 120)
DANGER_RED = (255, 30, 30)
GHOST_COLOR = (100, 100, 255, 80)

SPINNER_CHARS = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

# ── Surgical incision path (a complex path the surgeon must trace) ──
def _smooth_path(waypoints, points_per_seg=30):
    """Generate a smooth Catmull-Rom-like path through waypoints."""
    if len(waypoints) < 2:
        return list(waypoints)
    path = []
    for i in range(len(waypoints) - 1):
        p0 = waypoints[max(i - 1, 0)]
        p1 = waypoints[i]
        p2 = waypoints[min(i + 1, len(waypoints) - 1)]
        p3 = waypoints[min(i + 2, len(waypoints) - 1)]
        for j in range(points_per_seg):
            t = j / points_per_seg
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * ((2*p1[0]) + (-p0[0]+p2[0])*t +
                        (2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2 +
                        (-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3)
            y = 0.5 * ((2*p1[1]) + (-p0[1]+p2[1])*t +
                        (2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2 +
                        (-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3)
            path.append((x, y))
    path.append(waypoints[-1])
    return path


def generate_incision_path():
    """Generate a non-overlapping serpentine incision path with sharp turns.
    
    The path never crosses itself but has tight switchbacks and sharp
    direction changes that expose 4G latency/jitter as overshoot.
    """
    waypoints = [
        # ── Row 1: Left to right, gentle entry then sharp dip ──
        (160, 280),
        (250, 270),
        (340, 250),
        (420, 290),
        (500, 250),
        (600, 260),
        (700, 270),
        
        # ── Switchback right to left (lower row) ──
        (720, 320),
        (660, 340),
        (580, 330),
        (500, 360),
        (420, 330),
        (340, 350),
        (260, 340),
        (190, 360),
        
        # ── Switchback left to right (even lower) ──
        (170, 410),
        (250, 400),
        (340, 430),
        (420, 395),
        (500, 425),
        (580, 400),
        (660, 420),
        (730, 410),
        
        # ── Final precision exit — straight line (jitter visible) ──
        (750, 440),
    ]
    
    return _smooth_path(waypoints, points_per_seg=20)


def draw_loading_screen(screen, font_large, font_small, message, progress="", elapsed=0):
    """Draw an animated loading screen while MATLAB is initializing."""
    screen.fill(DARK_BG)
    
    title = font_large.render("5G Telesurgery Simulation", True, CYAN)
    screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, SCREEN_HEIGHT//3 - 40))
    
    spinner = SPINNER_CHARS[int(elapsed * 5) % len(SPINNER_CHARS)]
    msg = font_small.render(f"{spinner}  {message}", True, WHITE)
    screen.blit(msg, (SCREEN_WIDTH//2 - msg.get_width()//2, SCREEN_HEIGHT//2))
    
    if progress:
        prog = font_small.render(progress, True, GRAY)
        screen.blit(prog, (SCREEN_WIDTH//2 - prog.get_width()//2, SCREEN_HEIGHT//2 + 30))
    
    elapsed_text = font_small.render(f"Elapsed: {int(elapsed)}s", True, GRAY)
    screen.blit(elapsed_text, (SCREEN_WIDTH//2 - elapsed_text.get_width()//2, SCREEN_HEIGHT//2 + 60))
    
    pygame.display.flip()


def draw_surgical_scene(screen, incision_path, robot_trail, robot_pos, master_pos, 
                         force, accuracy, metrics, lag_distance, tissues):
    """Draw the full surgical scene with tissue, organs, incision path, and overlays."""
    
    # ── Background: operating table ──
    screen.fill((40, 60, 60))
    
    tissue_rect = pygame.Rect(130, 210, 650, 280)
    pygame.draw.rect(screen, SKIN_COLOR, tissue_rect, border_radius=18)
    pygame.draw.rect(screen, SKIN_DARK, tissue_rect, 3, border_radius=18)
    
    pygame.draw.ellipse(screen, ORGAN_PINK, (180, 370, 100, 60))
    pygame.draw.ellipse(screen, ORGAN_RED, (350, 380, 80, 50))
    pygame.draw.ellipse(screen, ORGAN_PINK, (550, 350, 100, 55))
    pygame.draw.ellipse(screen, ORGAN_RED, (680, 330, 70, 45))
    
    vein_points = [(150, 260), (250, 290), (350, 270), (450, 300), 
                   (550, 280), (650, 260), (740, 290)]
    pygame.draw.lines(screen, VEIN_BLUE, False, vein_points, 2)
    vein_points2 = [(170, 420), (280, 400), (400, 430), (520, 410), (640, 425)]
    pygame.draw.lines(screen, VEIN_BLUE, False, vein_points2, 2)
    vein_points3 = [(200, 320), (300, 340), (400, 310), (500, 330)]
    pygame.draw.lines(screen, VEIN_BLUE, False, vein_points3, 1)

    # ── Draw Highly Dense Tissue (Force Feedback Zones) ──
    font_tiny = pygame.font.SysFont('consolas', 12, bold=True)
    for t in tissues:
        pygame.draw.rect(screen, (200, 110, 110), t.rect, border_radius=8)
        pygame.draw.rect(screen, (150, 50, 50), t.rect, 3, border_radius=8)
        lbl = font_tiny.render("DENSE TISSUE", True, (255, 180, 180))
        screen.blit(lbl, (t.rect[0] + 5, t.rect[1] + 5))

    
    # ── Draw the incision guide path (bright glowing track) ──
    path_points = [(int(p[0]), int(p[1])) for p in incision_path]
    if len(path_points) > 1:
        pygame.draw.lines(screen, (0, 200, 100), False, path_points, 12)
        pygame.draw.lines(screen, (150, 255, 200), False, path_points, 4)
    
    # ── Draw robot trail (shows actual path taken — demonstrates accuracy) ──
    tech = metrics.get('technology', '5G NR')
    trail_color = (0, 180, 220) if '5G' in tech else (255, 140, 0)
    
    if len(robot_trail) > 2:
        trail_pts = [(int(p[0]), int(p[1])) for p in robot_trail]
        if len(trail_pts) > 1:
            pygame.draw.lines(screen, trail_color, False, trail_pts, 3)
    
    # ── Draw the "lag line" connecting master cursor to robot (visualizes latency) ──
    mx, my = int(master_pos[0]), int(master_pos[1])
    rx, ry = int(robot_pos[0]), int(robot_pos[1])
    
    if lag_distance > 5:
        lag_ratio = min(1.0, lag_distance / 100.0)
        lag_r = int(50 + 205 * lag_ratio)
        lag_g = int(200 - 180 * lag_ratio)
        lag_color = (lag_r, lag_g, 50)
        pygame.draw.line(screen, lag_color, (mx, my), (rx, ry), 2)
    
    # ── Ghost cursor (where the surgeon's hand actually is — shows master position) ──
    ghost_surface = pygame.Surface((40, 40), pygame.SRCALPHA)
    pygame.draw.circle(ghost_surface, (100, 100, 255, 80), (20, 20), 18)
    pygame.draw.circle(ghost_surface, (150, 150, 255, 140), (20, 20), 18, 2)
    screen.blit(ghost_surface, (mx - 20, my - 20))
    
    if lag_distance > 15:
        label_surf = pygame.font.SysFont('consolas', 10).render("SURGEON", True, (180, 180, 255))
        screen.blit(label_surf, (mx - 20, my - 28))
    
    # ── Robot arm (where the robot actually is) ──
    pygame.draw.line(screen, GRAY, (SCREEN_WIDTH//2, 180), (rx, ry), 4)
    pygame.draw.circle(screen, GRAY, (SCREEN_WIDTH//2, 180), 8)
    
    tip_color = GREEN if force < 0.3 else (ORANGE if force < 0.7 else DANGER_RED)
    pygame.draw.circle(screen, tip_color, (rx, ry), 8)
    pygame.draw.circle(screen, WHITE, (rx, ry), 8, 2)
    
    if force > 0.1:
        glow_surface = pygame.Surface((60, 60), pygame.SRCALPHA)
        glow_alpha = int(min(180, force * 250))
        pygame.draw.circle(glow_surface, (255, 80, 80, glow_alpha), (30, 30), 25)
        screen.blit(glow_surface, (rx - 30, ry - 30))


def draw_hud(screen, font, font_small, font_title, metrics, force, accuracy, 
             lag_distance, show_comparison, network, packet_drop_flash):
    """Draw the enhanced HUD with metrics, accuracy score, and latency bar."""
    
    tech_color = CYAN if '5G' in metrics['technology'] else ORANGE
    
    # ── Left panel: Network metrics ──
    panel_lines = [
        (f"[ {metrics['technology']} ]", tech_color),
        (f"SNR: {metrics['snr_db']} dB", WHITE),
        (f"Users: {metrics.get('num_users', 1)}", CYAN),
        (f"Profile: {metrics.get('fading_profile', 'Pedestrian')}", ORANGE),
        (f"BLER: {metrics['bler']:.2e}",
         LIGHT_GREEN if metrics['bler'] < 1e-3 else LIGHT_RED),
        (f"Throughput: {metrics['throughput_mbps']:.0f} Mbps", WHITE),
        (f"Latency: {metrics['latency_ms']:.1f} ms",
         LIGHT_GREEN if metrics['latency_ms'] < 10 else LIGHT_RED),
        (f"Jitter: {metrics['jitter_ms']:.2f} ms", WHITE),
        (f"Dropped: {metrics['packets_dropped']}/{metrics['packets_sent']}", 
         LIGHT_RED if metrics['packets_dropped'] > 0 else LIGHT_GREEN),
    ]
    
    panel_h = len(panel_lines) * 20 + 14
    panel_s = pygame.Surface((230, panel_h), pygame.SRCALPHA)
    panel_s.fill((0, 0, 0, 170))
    screen.blit(panel_s, (5, 5))
    
    for i, (text, color) in enumerate(panel_lines):
        img = font.render(text, True, color)
        screen.blit(img, (12, 10 + i * 20))
    
    if metrics.get('live_mode'):
        src = "LIVE"
        src_c = CYAN
    elif metrics['using_matlab']:
        src = "MATLAB"
        src_c = LIGHT_GREEN
    else:
        src = "CSV"
        src_c = ORANGE
    screen.blit(font_small.render(f"[{src}]", True, src_c), (12, 10 + len(panel_lines) * 20))
    
    # ── Right panel: Surgical performance ──
    perf_x = SCREEN_WIDTH - 240
    perf_s = pygame.Surface((235, 110), pygame.SRCALPHA)
    perf_s.fill((0, 0, 0, 170))
    screen.blit(perf_s, (perf_x, 5))
    
    screen.blit(font_title.render("Surgical Performance", True, WHITE), (perf_x + 10, 10))
    
    acc_color = LIGHT_GREEN if accuracy > 80 else (ORANGE if accuracy > 50 else LIGHT_RED)
    screen.blit(font.render(f"Accuracy: {accuracy:.0f}%", True, acc_color), (perf_x + 10, 35))
    bar_bg = pygame.Rect(perf_x + 10, 55, 215, 12)
    bar_fg = pygame.Rect(perf_x + 10, 55, int(215 * accuracy / 100), 12)
    pygame.draw.rect(screen, DARK_GRAY, bar_bg, border_radius=4)
    pygame.draw.rect(screen, acc_color, bar_fg, border_radius=4)
    
    lag_color = LIGHT_GREEN if lag_distance < 10 else (ORANGE if lag_distance < 40 else LIGHT_RED)
    screen.blit(font.render(f"Lag Gap: {lag_distance:.0f} px", True, lag_color), (perf_x + 10, 72))
    screen.blit(font.render(f"Force: {force:.2f}", True, WHITE), (perf_x + 10, 92))
    
    # ── Latency bar (horizontal bar at top center showing current latency) ──
    lat_bar_x = 250
    lat_bar_w = 400
    lat_bar_y = SCREEN_HEIGHT - 65
    
    lat_bg = pygame.Surface((lat_bar_w + 10, 30), pygame.SRCALPHA)
    lat_bg.fill((0, 0, 0, 140))
    screen.blit(lat_bg, (lat_bar_x - 5, lat_bar_y - 5))
    
    max_lat = 30.0
    lat_ms = metrics['latency_ms']
    lat_ratio = min(1.0, lat_ms / max_lat)
    
    pygame.draw.rect(screen, (60, 60, 60), (lat_bar_x, lat_bar_y, lat_bar_w, 8), border_radius=3)
    
    bar_color = LIGHT_GREEN if lat_ms < 5 else (ORANGE if lat_ms < 15 else LIGHT_RED)
    pygame.draw.rect(screen, bar_color, 
                    (lat_bar_x, lat_bar_y, int(lat_bar_w * lat_ratio), 8), border_radius=3)
    
    threshold_x = lat_bar_x + int(lat_bar_w * (10.0 / max_lat))
    pygame.draw.line(screen, WHITE, (threshold_x, lat_bar_y - 3), (threshold_x, lat_bar_y + 11), 2)
    screen.blit(font_small.render("10ms limit", True, WHITE), (threshold_x - 20, lat_bar_y + 12))
    
    screen.blit(font_small.render(f"Latency: {lat_ms:.1f} ms", True, bar_color), 
               (lat_bar_x, lat_bar_y + 12))
    screen.blit(font_small.render(f"0ms", True, GRAY), (lat_bar_x - 2, lat_bar_y - 14))
    screen.blit(font_small.render(f"30ms", True, GRAY), (lat_bar_x + lat_bar_w - 25, lat_bar_y - 14))
    
    # ── Packet drop flash (red border flash when a packet is dropped) ──
    if packet_drop_flash > 0:
        flash_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        flash_alpha = int(min(120, packet_drop_flash * 255))
        pygame.draw.rect(flash_surface, (255, 0, 0, flash_alpha), 
                        (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), 6)
        screen.blit(flash_surface, (0, 0))
    
    # ── Comparison panel (toggled with C) ──
    if show_comparison:
        m5g, m4g = network.get_comparison_metrics()
        cx = SCREEN_WIDTH - 310
        cy = 125
        
        cs = pygame.Surface((305, 130), pygame.SRCALPHA)
        cs.fill((0, 0, 0, 190))
        screen.blit(cs, (cx, cy))
        
        screen.blit(font_title.render("5G vs 4G LIVE", True, WHITE), (cx + 10, cy + 5))
        
        rows = [
            ("", "5G NR", "4G LTE"),
            ("BLER", f"{m5g['bler']:.2e}", f"{m4g['bler']:.2e}"),
            ("Tput", f"{m5g['throughput']:.0f} Mbps", f"{m4g['throughput']:.0f} Mbps"),
            ("Latency", f"{m5g['latency']:.1f} ms", f"{m4g['latency']:.1f} ms"),
            ("Jitter", f"{m5g['jitter']:.2f} ms", f"{m4g['jitter']:.2f} ms"),
        ]
        for i, (label, v5, v4) in enumerate(rows):
            ly = cy + 28 + i * 19
            screen.blit(font_small.render(label, True, GRAY), (cx + 10, ly))
            screen.blit(font_small.render(v5, True, CYAN), (cx + 85, ly))
            screen.blit(font_small.render(v4, True, ORANGE), (cx + 200, ly))
    
    # ── Controls bar (bottom) ──
    ctrl_s = pygame.Surface((SCREEN_WIDTH, 22), pygame.SRCALPHA)
    ctrl_s.fill((0, 0, 0, 140))
    screen.blit(ctrl_s, (0, SCREEN_HEIGHT - 22))
    controls = "1/2:5G  3/4:4G  U/J:Users±5  F:Fading  R:Reset  C:Comp  G:Graph"
    screen.blit(font_small.render(controls, True, GRAY), (10, SCREEN_HEIGHT - 19))


def main():
    pygame.init()
    pygame.joystick.init()
    
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("5G Telesurgery Simulation — MATLAB 5G/LTE Toolbox")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont('consolas', 14)
    font_title = pygame.font.SysFont('consolas', 14, bold=True)
    font_large = pygame.font.SysFont('consolas', 28, bold=True)
    font_small = pygame.font.SysFont('consolas', 11)

    network_holder = [None]
    loading_error = [None]
    loading_status = ["Starting MATLAB engine..."]

    def _load_network():
        try:
            loading_status[0] = "Starting MATLAB engine..."
            network_holder[0] = Matlab5GNetwork(use_matlab=True)
            loading_status[0] = "Done!"
        except Exception as e:
            loading_error[0] = str(e)
            loading_status[0] = f"Error: {e}"

    load_thread = threading.Thread(target=_load_network, daemon=True)
    load_thread.start()
    start_time = _time.time()

    while load_thread.is_alive():
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        elapsed = _time.time() - start_time
        draw_loading_screen(screen, font_large, font_small,
                           loading_status[0],
                           "Initializing MATLAB engine & live simulation thread...",
                           elapsed)
        clock.tick(15)

    network = network_holder[0]
    if network is None:
        print(f"Failed to initialize: {loading_error[0]}")
        network = Matlab5GNetwork(use_matlab=False)



    # ── Live Graph Window ──
    graph_window = LiveGraphWindow()

    # ── Game state ──
    incision_path = generate_incision_path()
    START_POS = (int(incision_path[0][0]), int(incision_path[0][1]))
    master = MasterConsole(start_pos=START_POS)
    robot = RobotArm(start_pos=START_POS)
    tissues = [
        Tissue(rect=(540, 395, 100, 70), stiffness=0.05),
        Tissue(rect=(280, 425, 90, 55), stiffness=0.05),
        Tissue(rect=(620, 250, 80, 60), stiffness=0.05),
    ]
    robot_trail = []
    max_trail_length = 600
    
    show_comparison = False
    force = 0.0
    accuracy = 100.0
    accuracy_samples = 0
    accuracy_sum = 0.0
    lag_distance = 0.0
    packet_drop_flash = 0.0
    prev_dropped = 0
    fail_count = 0
    fail_overlay_timer = 0.0
    stutter_frames = 0
    
    # ── Path completion tracking ──
    path_visited = [False] * len(incision_path)
    VISIT_RADIUS = 20.0
    path_completed = False
    success_overlay_timer = 0.0
    SUCCESS_OVERLAY_DURATION = 3.0
    import numpy as np
    path_np = np.array(incision_path)
    
    running = True
    frame_count = 0
    print(">>> Game loop started <<<")
    while running:
        frame_count += 1
        if frame_count % 300 == 0:
            print(f"Frame {frame_count} | FPS={clock.get_fps():.0f} | Tech={network.active_tech} | Lat={network.current_latency:.1f}ms | BLER={network.current_bler:.5f}")
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    network.set_technology('5g')
                    network.set_snr(25)
                elif event.key == pygame.K_2:
                    network.set_technology('5g')
                    network.set_snr(15)
                elif event.key == pygame.K_3:
                    network.set_technology('4g')
                    network.set_snr(25)
                elif event.key == pygame.K_4:
                    network.set_technology('4g')
                    network.set_snr(15)
                elif event.key == pygame.K_u:
                    network.set_num_users(network.num_users + 5)
                elif event.key == pygame.K_j:
                    network.set_num_users(network.num_users - 5)
                elif event.key == pygame.K_f:
                    network.cycle_fading_profile()
                elif event.key == pygame.K_r:
                    robot_trail.clear()
                    accuracy_samples = 0
                    accuracy_sum = 0.0
                    accuracy = 100.0
                    network.packets_sent = 0
                    network.packets_dropped = 0
                    path_visited = [False] * len(incision_path)
                    path_completed = False
                    robot.position = list(START_POS)
                    master.target_position = list(START_POS)
                elif event.key == pygame.K_c:
                    show_comparison = not show_comparison
                elif event.key == pygame.K_g:
                    graph_window.toggle()
                    print(f"Graph window {'opened' if graph_window.is_running else 'closed'}")

        keys_pressed = pygame.key.get_pressed()
        dt = clock.get_time() / 1000.0
        
        # ── Failure overlay countdown (blocks gameplay while showing) ──
        if fail_overlay_timer > 0:
            fail_overlay_timer -= dt
            
            screen.fill((20, 10, 10))
            fail_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            
            pulse = abs(math.sin(fail_overlay_timer * 4)) * 0.4 + 0.4
            vignette_alpha = int(pulse * 180)
            pygame.draw.rect(fail_surf, (180, 20, 20, vignette_alpha),
                           (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), 20)
            screen.blit(fail_surf, (0, 0))
            
            fail_text = font_large.render("⚠  SURGERY FAILED  ⚠", True, (255, 60, 60))
            screen.blit(fail_text, (SCREEN_WIDTH//2 - fail_text.get_width()//2,
                                    SCREEN_HEIGHT//2 - 60))
            
            reason_text = font.render(f"Accuracy dropped below {ACCURACY_FAIL_THRESHOLD:.0f}%", True, (255, 180, 180))
            screen.blit(reason_text, (SCREEN_WIDTH//2 - reason_text.get_width()//2,
                                      SCREEN_HEIGHT//2 - 10))
            
            restart_text = font.render("Restarting procedure...", True, (200, 200, 200))
            screen.blit(restart_text, (SCREEN_WIDTH//2 - restart_text.get_width()//2,
                                       SCREEN_HEIGHT//2 + 25))
            
            count_text = font_small.render(f"Failed attempts: {fail_count}", True, (255, 140, 100))
            screen.blit(count_text, (SCREEN_WIDTH//2 - count_text.get_width()//2,
                                     SCREEN_HEIGHT//2 + 60))
            
            bar_w = 300
            bar_x = SCREEN_WIDTH//2 - bar_w//2
            bar_y = SCREEN_HEIGHT//2 + 90
            progress = 1.0 - (fail_overlay_timer / FAIL_OVERLAY_DURATION)
            pygame.draw.rect(screen, (60, 60, 60), (bar_x, bar_y, bar_w, 8), border_radius=4)
            pygame.draw.rect(screen, (255, 100, 100), (bar_x, bar_y, int(bar_w * progress), 8), border_radius=4)
            
            pygame.display.flip()
            clock.tick(FPS)
            
            if fail_overlay_timer <= 0:
                fail_overlay_timer = 0
                robot_trail.clear()
                accuracy_samples = 0
                accuracy_sum = 0.0
                accuracy = 100.0
                network.packets_sent = 0
                network.packets_dropped = 0
                prev_dropped = 0
                robot.position = list(START_POS)
                master.target_position = list(START_POS)
                network.master_to_slave_queue.clear()
                network.slave_to_master_queue.clear()
                path_visited = [False] * len(incision_path)
                path_completed = False
                print(f">>> Surgery restarted (attempt #{fail_count + 1}) <<<")
            continue
        
        network.poll_live_step()
        
        master.update_input(keys_pressed)
        network.send_to_slave(list(master.target_position))
        
        forces_received = network.receive_from_slave()
        if forces_received:
            master.apply_force_feedback(forces_received[-1])

        target_positions = network.receive_from_master()
        latest_target = target_positions[-1] if target_positions else None
        
        # ── Network Micro-Stutter Mechanic ──
        metrics = network.get_current_metrics()
        jitter_val = metrics.get('jitter_ms', 0)
        
        if stutter_frames == 0 and jitter_val > 0.5:
            if random.random() < (jitter_val * 0.05):
                stutter_frames = random.randint(3, 10)
                
        if stutter_frames > 0:
            stutter_frames -= 1
        else:
            robot.update_position(latest_target)
            
        force = robot.interact_with_tissue(tissues)
        network.send_to_master(force)
        
        # ── Track robot trail ──
        robot_trail.append(tuple(robot.position))
        if len(robot_trail) > max_trail_length:
            robot_trail.pop(0)
        
        # ── Calculate lag distance (pixels between master and robot) ──
        dx = master.target_position[0] - robot.position[0]
        dy = master.target_position[1] - robot.position[1]
        lag_distance = math.sqrt(dx*dx + dy*dy)
        
        # ── Calculate accuracy (vectorized numpy — fixes freeze) ──
        if len(incision_path) > 0:
            robot_pt = np.array([robot.position[0], robot.position[1]])
            dists = np.sqrt(np.sum((path_np - robot_pt) ** 2, axis=1))
            min_idx = int(np.argmin(dists))
            min_dist = float(dists[min_idx])
            
            if not path_completed:
                visited_mask = dists < VISIT_RADIUS
                for idx in np.where(visited_mask)[0]:
                    path_visited[idx] = True
                
                visit_pct = sum(path_visited) / len(path_visited)
                if visit_pct >= 1.0 and accuracy >= ACCURACY_FAIL_THRESHOLD:
                    path_completed = True
                    success_overlay_timer = SUCCESS_OVERLAY_DURATION
                    print(f">>> SURGERY COMPLETED SUCCESSFULLY! Accuracy: {accuracy:.1f}% <<<")
            
            if 150 < robot.position[0] < 760:
                SAFE_RADIUS = 5.0
                if min_dist <= SAFE_RADIUS:
                    point_accuracy = max(0, 100 - (min_dist * 2))
                else:
                    excess_dist = min_dist - SAFE_RADIUS
                    penalty_multiplier = 1.0 + (force * 3.0)
                    point_accuracy = max(0, 100 - (SAFE_RADIUS * 2) - (excess_dist * 2 * penalty_multiplier))
                
                accuracy_samples += 1
                accuracy_sum += point_accuracy
                accuracy = accuracy_sum / accuracy_samples
        
        # ── Auto-restart check (skip if already completed) ──
        if (not path_completed and
                accuracy_samples > ACCURACY_GRACE_SAMPLES and
                accuracy < ACCURACY_FAIL_THRESHOLD and
                fail_overlay_timer <= 0):
            fail_count += 1
            fail_overlay_timer = FAIL_OVERLAY_DURATION
            print(f"!!! Surgery accuracy {accuracy:.1f}% < {ACCURACY_FAIL_THRESHOLD}% — FAILED (#{fail_count}) !!!")
        
        # ── Packet drop flash ──
        if metrics['packets_dropped'] > prev_dropped:
            packet_drop_flash = 1.0
        prev_dropped = metrics['packets_dropped']
        packet_drop_flash = max(0, packet_drop_flash - 0.03)
        
        # ── Push data to live graph window (every ~0.5s = 30 frames) ──
        if frame_count % 30 == 0 and graph_window.is_running:
            m5g, m4g = network.get_comparison_metrics()
            graph_window.push_data(m5g, m4g)
        
        draw_surgical_scene(screen, incision_path, robot_trail, 
                           robot.position, master.target_position,
                           force, accuracy, metrics, lag_distance, tissues)
        
        draw_hud(screen, font, font_small, font_title, metrics, force, accuracy,
                lag_distance, show_comparison, network, packet_drop_flash)
        
        # ── Fail count badge (top-center) ──
        if fail_count > 0:
            fail_badge = font.render(f"Failed: {fail_count}", True, (255, 100, 100))
            badge_bg = pygame.Surface((fail_badge.get_width() + 16, 22), pygame.SRCALPHA)
            badge_bg.fill((100, 0, 0, 160))
            screen.blit(badge_bg, (SCREEN_WIDTH//2 - badge_bg.get_width()//2, 5))
            screen.blit(fail_badge, (SCREEN_WIDTH//2 - fail_badge.get_width()//2, 8))
            
        # ── Signal Stalled Warning (Stuttering) ──
        if stutter_frames > 0:
            stalled_text = font.render("⚠ SIGNAL STALLED", True, (255, 100, 0))
            screen.blit(stalled_text, (robot.position[0] + 20, robot.position[1] - 20))

        # ── Path progress bar (bottom-left) ──
        visit_pct = sum(path_visited) / len(path_visited) * 100 if path_visited else 0
        prog_x, prog_y = 10, SCREEN_HEIGHT - 48
        prog_bg = pygame.Surface((200, 22), pygame.SRCALPHA)
        prog_bg.fill((0, 0, 0, 160))
        screen.blit(prog_bg, (prog_x, prog_y))
        prog_color = LIGHT_GREEN if visit_pct > 80 else (ORANGE if visit_pct > 40 else WHITE)
        screen.blit(font_small.render(f"Path: {visit_pct:.0f}%", True, prog_color), (prog_x + 4, prog_y + 2))
        pygame.draw.rect(screen, (60, 60, 60), (prog_x + 70, prog_y + 5, 120, 10), border_radius=4)
        pygame.draw.rect(screen, prog_color, (prog_x + 70, prog_y + 5, int(120 * visit_pct / 100), 10), border_radius=4)
        
        # ── Success overlay ──
        if success_overlay_timer > 0:
            success_overlay_timer -= dt
            s_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            s_alpha = min(180, int(success_overlay_timer / SUCCESS_OVERLAY_DURATION * 220))
            s_surf.fill((0, 40, 0, s_alpha))
            screen.blit(s_surf, (0, 0))
            
            s_text = font_large.render("SURGERY SUCCESSFUL!", True, (100, 255, 100))
            screen.blit(s_text, (SCREEN_WIDTH//2 - s_text.get_width()//2, SCREEN_HEIGHT//2 - 50))
            
            a_text = font.render(f"Final Accuracy: {accuracy:.1f}%", True, (200, 255, 200))
            screen.blit(a_text, (SCREEN_WIDTH//2 - a_text.get_width()//2, SCREEN_HEIGHT//2))
            
            t_text = font.render(f"Technology: {metrics.get('technology', '5G NR')}", True, (200, 255, 200))
            screen.blit(t_text, (SCREEN_WIDTH//2 - t_text.get_width()//2, SCREEN_HEIGHT//2 + 25))
            
            r_text = font_small.render("Press R to restart", True, (180, 220, 180))
            screen.blit(r_text, (SCREEN_WIDTH//2 - r_text.get_width()//2, SCREEN_HEIGHT//2 + 60))

        pygame.display.flip()
        clock.tick(FPS)

    graph_window.stop()
    network.cleanup()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
