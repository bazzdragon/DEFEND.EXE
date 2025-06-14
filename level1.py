import pygame
import sys
import time
import math
import json
import os
import subprocess
import random

SETTINGS_FILE = "settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {"invert_colors": False}

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

def invert_color(color):
    if len(color) == 3:
        return tuple(255 - c for c in color)
    elif len(color) == 4:
        return tuple(255 - c for c in color[:3]) + (color[3],)
    else:
        return color

def unlock_level(level):
    settings = load_settings()
    if "unlocked_levels" not in settings or settings["unlocked_levels"] < level:
        settings["unlocked_levels"] = level
        save_settings(settings)

pygame.init()

info = pygame.display.Info()
SCREEN_WIDTH, SCREEN_HEIGHT = info.current_w, info.current_h
VIRTUAL_WIDTH, VIRTUAL_HEIGHT = SCREEN_WIDTH, SCREEN_HEIGHT
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
virtual_surface = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT))

font = pygame.font.SysFont("Arial", 32)
small_font = pygame.font.SysFont("Arial", 20)
big_font = pygame.font.SysFont("Arial", 80)

towers = []
enemies = []
bullets = []
lives = 3
score = 0

PATH = [(0, 400), (400, 400), (400, 700), (1000, 700), (1000, 100), 
        (1600, 100), (1600, 250), (1350, 250), (1350, 650), 
        (1600, 650), (1600, 900), (800, 900), (800, 1100)]

settings = load_settings()
invert = settings.get("invert_colors", False)

MENU_WIDTH = 120
MENU_BG = (50, 50, 80)
TOWER_TYPES = [
    {
        "name": "Blue",
        "color": (0, 0, 200),
        "range": 140,
        "cooldown": 60,
        "fire_rate": 60,
        "acquire_delay": int(1.5 * 60),
    },
    {
        "name": "Red",
        "color": (200, 0, 0),
        "range": 70,
        "cooldown": 30,
        "fire_rate": 30,
        "acquire_delay": int(1.0 * 60),
    },
    {
        "name": "Green",
        "color": (0, 180, 0),
        "range": 180,
        "cooldown": 90,
        "fire_rate": 90,
        "acquire_delay": int(2.0 * 60),
    },
    {
        "name": "Yellow",
        "color": (200, 200, 0),
        "range": 100,
        "cooldown": 45,
        "fire_rate": 45,
        "acquire_delay": int(1.2 * 60),
    },
]

class Tower:
    def __init__(self, x, y, ttype=0):
        self.x, self.y = x, y
        self.type = ttype
        self.range = TOWER_TYPES[ttype]["range"]
        self.cooldown = TOWER_TYPES[ttype]["cooldown"]
        self.fire_rate = TOWER_TYPES[ttype]["fire_rate"]
        self.acquire_delay = TOWER_TYPES[ttype]["acquire_delay"]
        self.target = None

    def draw(self, surf):
        color = TOWER_TYPES[self.type]["color"]
        color = color if not invert else invert_color(color)
        pygame.draw.rect(surf, color, (self.x - 20, self.y - 20, 40, 40))
        pygame.draw.circle(
            surf,
            (100, 100, 255) if not invert else invert_color((100, 100, 255)),
            (self.x, self.y),
            self.range,
            1,
        )

    def shoot(self, enemies, bullets):
        if self.target not in enemies or (
            self.target and math.hypot(self.target.pos[0] - self.x, self.target.pos[1] - self.y) > self.range
        ):
            self.target = None
            self.acquire_delay = 0

        if self.cooldown > 0:
            self.cooldown -= 1
            return

        if self.target is None:
            for enemy in enemies:
                dx = enemy.pos[0] - self.x
                dy = enemy.pos[1] - self.y
                dist = math.hypot(dx, dy)
                if dist <= self.range:
                    self.target = enemy
                    self.acquire_delay = int(1.5 * 60)
                    break

        if self.target:
            if self.acquire_delay > 0:
                self.acquire_delay -= 1
                return
            if not any(bullet.target == self.target and bullet.x == self.x and bullet.y == self.y for bullet in bullets):
                bullets.append(Bullet(self.x, self.y, self.target))
                self.cooldown = self.fire_rate

class Enemy:
    def __init__(self, path):
        self.path = path
        self.pos = list(path[0])
        self.path_index = 0
        self.speed = 1  # Slower base enemy
        self.hp = 1

    def update(self):
        if self.path_index < len(self.path) - 1:
            target = self.path[self.path_index + 1]
            dx, dy = target[0] - self.pos[0], target[1] - self.pos[1]
            dist = (dx**2 + dy**2) ** 0.5
            if dist < self.speed:
                self.pos = list(target)
                self.path_index += 1
            else:
                self.pos[0] += self.speed * dx / dist
                self.pos[1] += self.speed * dy / dist

    def draw(self, surf):
        color = (255, 0, 0) if not invert else invert_color((255, 0, 0))
        pygame.draw.circle(surf, color, (int(self.pos[0]), int(self.pos[1])), 20)

class FastEnemy(Enemy):
    def __init__(self, path):
        super().__init__(path)
        self.speed = 2  # Faster

    def draw(self, surf):
        color = (0, 200, 255) if not invert else invert_color((0, 200, 255))
        pygame.draw.circle(surf, color, (int(self.pos[0]), int(self.pos[1])), 18)

class DurableEnemy(Enemy):
    def __init__(self, path):
        super().__init__(path)
        self.hp = 3
        self.speed = 1

    def draw(self, surf):
        color = (128, 0, 128) if not invert else invert_color((128, 0, 128))
        pygame.draw.circle(surf, color, (int(self.pos[0]), int(self.pos[1])), 24)
        hp_label = small_font.render(str(self.hp), True, (255,255,255) if not invert else (0,0,0))
        surf.blit(hp_label, (int(self.pos[0])-10, int(self.pos[1])-10))

class Bullet:
    def __init__(self, x, y, target):
        self.x = x
        self.y = y
        self.target = target
        self.speed = 8
        self.radius = 8

    def update(self):
        if not self.target:
            return
        dx = self.target.pos[0] - self.x
        dy = self.target.pos[1] - self.y
        dist = math.hypot(dx, dy)
        if dist < self.speed or dist == 0:
            self.x, self.y = self.target.pos[0], self.target.pos[1]
        else:
            self.x += self.speed * dx / dist
            self.y += self.speed * dy / dist

    def draw(self, surf):
        color = (255, 255, 0) if not invert else invert_color((255, 255, 0))
        pygame.draw.circle(surf, color, (int(self.x), int(self.y)), self.radius)

enemy_spawn_timer = 0
enemy_spawn_interval = 120
selected_tower_type = None

# Pause button in bottom right, bigger
pause_button_size = 100
pause_button_rect = pygame.Rect(
    VIRTUAL_WIDTH - pause_button_size - 10,
    VIRTUAL_HEIGHT - pause_button_size - 10,
    pause_button_size,
    pause_button_size
)
paused = False

placing_tower = False
placement_preview = None
dragging = False

# --- Wave system ---
current_wave = 1
max_wave = 3
enemies_to_spawn = []
spawn_cooldown = 0
wave_in_progress = False
game_won = False
game_lost = False

def setup_wave(wave):
    if wave == 1:
        wave_list = [Enemy(PATH) for _ in range(15)]
    elif wave == 2:
        wave_list = [Enemy(PATH) for _ in range(15)] + [FastEnemy(PATH) for _ in range(5)]
    elif wave == 3:
        wave_list = [Enemy(PATH) for _ in range(15)] + [FastEnemy(PATH) for _ in range(10)] + [DurableEnemy(PATH) for _ in range(5)]
    else:
        wave_list = []
    random.shuffle(wave_list)
    return wave_list

def draw_pause_menu(surface):
    overlay = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    surface.blit(overlay, (0, 0))

    resume_rect = pygame.Rect(VIRTUAL_WIDTH//2 - 120, VIRTUAL_HEIGHT//2 - 120, 240, 60)
    settings_rect = pygame.Rect(VIRTUAL_WIDTH//2 - 120, VIRTUAL_HEIGHT//2 - 40, 240, 60)
    restart_rect = pygame.Rect(VIRTUAL_WIDTH//2 - 120, VIRTUAL_HEIGHT//2 + 40, 240, 60)
    mainmenu_rect = pygame.Rect(VIRTUAL_WIDTH//2 - 120, VIRTUAL_HEIGHT//2 + 120, 240, 60)

    resume_color = (100, 200, 100) if not invert else invert_color((100, 200, 100))
    settings_color = (100, 100, 255) if not invert else invert_color((100, 100, 255))
    restart_color = (200, 200, 0) if not invert else invert_color((200, 200, 0))
    mainmenu_color = (200, 0, 0) if not invert else invert_color((200, 0, 0))

    pygame.draw.rect(surface, resume_color, resume_rect)
    pygame.draw.rect(surface, settings_color, settings_rect)
    pygame.draw.rect(surface, restart_color, restart_rect)
    pygame.draw.rect(surface, mainmenu_color, mainmenu_rect)

    text_color = (255, 255, 255) if not invert else (0, 0, 0)

    resume_label = font.render("Resume", True, text_color)
    settings_label = font.render("Settings", True, text_color)
    restart_label = font.render("Restart", True, text_color)
    mainmenu_label = font.render("Main Menu", True, text_color)

    surface.blit(resume_label, resume_label.get_rect(center=resume_rect.center))
    surface.blit(settings_label, settings_label.get_rect(center=settings_rect.center))
    surface.blit(restart_label, restart_label.get_rect(center=restart_rect.center))
    surface.blit(mainmenu_label, mainmenu_label.get_rect(center=mainmenu_rect.center))

    return resume_rect, settings_rect, restart_rect, mainmenu_rect

def is_valid_tower_position(x, y, ttype):
    for tower in towers:
        if math.hypot(tower.x - x, tower.y - y) < 40:
            return False
    for i in range(len(PATH) - 1):
        x1, y1 = PATH[i]
        x2, y2 = PATH[i + 1]
        px, py = x, y
        dx, dy = x2 - x1, y2 - y1
        if dx == dy == 0:
            dist = math.hypot(px - x1, py - y1)
        else:
            t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            dist = math.hypot(px - proj_x, py - proj_y)
        if dist < 40:
            return False
    return True

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (
            event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
        ):
            running = False

        elif event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = pygame.mouse.get_pos()
            vx = int(mx * VIRTUAL_WIDTH / SCREEN_WIDTH)
            vy = int(my * VIRTUAL_HEIGHT / SCREEN_HEIGHT)

            if not paused and pause_button_rect.collidepoint(vx, vy):
                paused = True

            elif paused:
                resume_rect = pygame.Rect(VIRTUAL_WIDTH//2 - 120, VIRTUAL_HEIGHT//2 - 120, 240, 60)
                settings_rect = pygame.Rect(VIRTUAL_WIDTH//2 - 120, VIRTUAL_HEIGHT//2 - 40, 240, 60)
                restart_rect = pygame.Rect(VIRTUAL_WIDTH//2 - 120, VIRTUAL_HEIGHT//2 + 40, 240, 60)
                mainmenu_rect = pygame.Rect(VIRTUAL_WIDTH//2 - 120, VIRTUAL_HEIGHT//2 + 120, 240, 60)
                if resume_rect.collidepoint(vx, vy):
                    paused = False
                elif settings_rect.collidepoint(vx, vy):
                    subprocess.call([sys.executable, "settings.py"])
                    settings = load_settings()
                    invert = settings.get("invert_colors", False)
                elif restart_rect.collidepoint(vx, vy):
                    subprocess.Popen([sys.executable, "level1.py"])
                    running = False
                elif mainmenu_rect.collidepoint(vx, vy):
                    subprocess.Popen([sys.executable, "Start-Menu.py"])
                    running = False

            if not paused and not game_won and not game_lost:
                menu_left = VIRTUAL_WIDTH - MENU_WIDTH
                menu_y = 60
                if not placing_tower:
                    if vx >= menu_left:
                        for i, ttype in enumerate(TOWER_TYPES):
                            rect = pygame.Rect(menu_left + 10, menu_y + i * 70, 100, 60)
                            if rect.collidepoint(vx, vy):
                                selected_tower_type = i
                    elif selected_tower_type is not None:
                        placing_tower = True
                        placement_preview = [vx, vy, selected_tower_type]
                        dragging = True
                        selected_tower_type = None
                else:
                    accept_rect = pygame.Rect(placement_preview[0] + 50, placement_preview[1] - 30, 80, 40)
                    cancel_rect = pygame.Rect(placement_preview[0] - 130, placement_preview[1] - 30, 80, 40)
                    if accept_rect.collidepoint(vx, vy):
                        if is_valid_tower_position(placement_preview[0], placement_preview[1], placement_preview[2]):
                            towers.append(Tower(placement_preview[0], placement_preview[1], placement_preview[2]))
                            placing_tower = False
                            placement_preview = None
                            dragging = False
                    elif cancel_rect.collidepoint(vx, vy):
                        placing_tower = False
                        placement_preview = None
                        dragging = False
                    else:
                        tower_rect = pygame.Rect(placement_preview[0] - 20, placement_preview[1] - 20, 40, 40)
                        if tower_rect.collidepoint(vx, vy):
                            dragging = True

        elif event.type == pygame.MOUSEBUTTONUP:
            dragging = False

        elif event.type == pygame.MOUSEMOTION:
            if placing_tower and dragging:
                mx, my = pygame.mouse.get_pos()
                vx = int(mx * VIRTUAL_WIDTH / SCREEN_WIDTH)
                vy = int(my * VIRTUAL_HEIGHT / SCREEN_HEIGHT)
                placement_preview[0] = vx
                placement_preview[1] = vy

    # --- Wave logic ---
    if not wave_in_progress and not enemies and not enemies_to_spawn and not game_won and not game_lost:
        if current_wave <= max_wave:
            enemies_to_spawn = setup_wave(current_wave)
            wave_in_progress = True
            spawn_cooldown = 0
        else:
            game_won = True

    if wave_in_progress and enemies_to_spawn and not game_won and not game_lost:
        spawn_cooldown -= 1
        if spawn_cooldown <= 0:
            enemy = enemies_to_spawn.pop(0)
            enemies.append(enemy)
            spawn_cooldown = 30

    if wave_in_progress and not enemies_to_spawn and not enemies and not game_won and not game_lost:
        current_wave += 1
        wave_in_progress = False

    if not paused and not game_won and not game_lost:
        for tower in towers:
            tower.shoot(enemies, bullets)

        for bullet in bullets[:]:
            bullet.update()
            if bullet.target and math.hypot(bullet.x - bullet.target.pos[0], bullet.y - bullet.target.pos[1]) < bullet.radius + 20:
                if bullet.target in enemies:
                    bullet.target.hp -= 1
                    if bullet.target.hp <= 0:
                        enemies.remove(bullet.target)
                        score += 1
                bullets.remove(bullet)

        for enemy in enemies[:]:
            enemy.update()
            if enemy.path_index == len(enemy.path) - 1:
                enemies.remove(enemy)
                lives -= 1
                if lives <= 0:
                    game_lost = True

    bg_color = (30, 30, 30) if not invert else (225, 225, 225)
    virtual_surface.fill(bg_color)

    path_color = (0, 255, 0) if not invert else invert_color((0, 255, 0))
    pygame.draw.lines(virtual_surface, path_color, False, PATH, 8)

    for tower in towers:
        tower.draw(virtual_surface)
    for enemy in enemies:
        enemy.draw(virtual_surface)
    for bullet in bullets:
        bullet.draw(virtual_surface)

    fg = (255, 255, 255) if not invert else (0, 0, 0)
    text = font.render(f"Lives: {lives}  Score: {score}", True, fg)
    virtual_surface.blit(text, (10, 10))
    wave_label = font.render(f"Wave: {min(current_wave, max_wave)}", True, fg)
    virtual_surface.blit(wave_label, (10, 50))
    small = small_font.render("ESC to quit, click to place towers", True, fg)
    virtual_surface.blit(small, (10, 90))

    menu_left = VIRTUAL_WIDTH - MENU_WIDTH
    pygame.draw.rect(virtual_surface, MENU_BG, (menu_left, 0, MENU_WIDTH, VIRTUAL_HEIGHT))
    menu_y = 60
    for i, ttype in enumerate(TOWER_TYPES):
        rect = pygame.Rect(menu_left + 10, menu_y + i * 70, 100, 60)
        color = ttype["color"] if not invert else invert_color(ttype["color"])
        pygame.draw.rect(virtual_surface, color, rect)
        if selected_tower_type == i:
            pygame.draw.rect(virtual_surface, (255, 255, 255), rect, 3)
        label = small_font.render(ttype["name"], True, fg)
        virtual_surface.blit(label, (menu_left + 20, menu_y + i * 70 + 15))

    # Draw pause button (bottom right, bigger, thick bars)
    pygame.draw.rect(
        virtual_surface,
        (180, 180, 180) if not invert else invert_color((180, 180, 180)),
        pause_button_rect,
        border_radius=20
    )
    bar_width = 18
    bar_height = 60
    bar_gap = 24
    bar_color = (60, 60, 60) if not invert else invert_color((60, 60, 60))
    x1 = pause_button_rect.x + pause_button_rect.width // 2 - bar_gap // 2 - bar_width
    x2 = pause_button_rect.x + pause_button_rect.width // 2 + bar_gap // 2
    y = pause_button_rect.y + (pause_button_rect.height - bar_height) // 2
    pygame.draw.rect(virtual_surface, bar_color, (x1, y, bar_width, bar_height), border_radius=8)
    pygame.draw.rect(virtual_surface, bar_color, (x2, y, bar_width, bar_height), border_radius=8)

    # Draw placement preview if needed
    if placing_tower and placement_preview:
        px, py, ttype = placement_preview
        valid = is_valid_tower_position(px, py, ttype)
        if valid:
            preview_color = TOWER_TYPES[ttype]["color"] if not invert else invert_color(TOWER_TYPES[ttype]["color"])
            radius_color = (100, 100, 255) if not invert else invert_color((100, 100, 255))
        else:
            preview_color = (200, 50, 50) if not invert else invert_color((200, 50, 50))
            radius_color = (200, 50, 50) if not invert else invert_color((200, 50, 50))
        pygame.draw.rect(virtual_surface, preview_color, (px - 20, py - 20, 40, 40), 2)
        pygame.draw.circle(
            virtual_surface,
            radius_color,
            (px, py),
            TOWER_TYPES[ttype]["range"],
            1,
        )
        accept_rect = pygame.Rect(px + 50, py - 30, 80, 40)
        cancel_rect = pygame.Rect(px - 130, py - 30, 80, 40)
        pygame.draw.rect(virtual_surface, (0, 200, 0), accept_rect)
        pygame.draw.rect(virtual_surface, (200, 0, 0), cancel_rect)
        accept_label = small_font.render("Accept", True, (255, 255, 255))
        cancel_label = small_font.render("Cancel", True, (255, 255, 255))
        virtual_surface.blit(accept_label, (px + 60, py - 22))
        virtual_surface.blit(cancel_label, (px - 120, py - 22))

    if paused:
        draw_pause_menu(virtual_surface)

    # WIN/LOSE SCENES
    if game_won:
        win_text = big_font.render("You Win!", True, (0, 255, 0))
        text_rect = win_text.get_rect(midtop=(VIRTUAL_WIDTH//2, 60))
        # Draw black background rectangle (with some padding)
        bg_rect = pygame.Rect(text_rect.left - 20, text_rect.top - 10, text_rect.width + 40, text_rect.height + 20)
        pygame.draw.rect(virtual_surface, (0, 0, 0), bg_rect)
        virtual_surface.blit(win_text, text_rect)
        unlock_level(2)
        scaled = pygame.transform.scale(virtual_surface, (SCREEN_WIDTH, SCREEN_HEIGHT))
        screen.blit(scaled, (0, 0))
        pygame.display.flip()
        pygame.time.wait(2000)
        subprocess.Popen([sys.executable, "level_select.py"])
        break

    if game_lost:
        lose_text = big_font.render("You Lose!", True, (255, 0, 0))
        text_rect = lose_text.get_rect(midtop=(VIRTUAL_WIDTH//2, 60))
        bg_rect = pygame.Rect(text_rect.left - 20, text_rect.top - 10, text_rect.width + 40, text_rect.height + 20)
        pygame.draw.rect(virtual_surface, (0, 0, 0), bg_rect)
        virtual_surface.blit(lose_text, text_rect)
        restart_rect = pygame.Rect(VIRTUAL_WIDTH//2 - 120, VIRTUAL_HEIGHT//2 + 10, 240, 60)
        levelselect_rect = pygame.Rect(VIRTUAL_WIDTH//2 - 120, VIRTUAL_HEIGHT//2 + 90, 240, 60)
        mainmenu_rect = pygame.Rect(VIRTUAL_WIDTH//2 - 120, VIRTUAL_HEIGHT//2 + 170, 240, 60)
        pygame.draw.rect(virtual_surface, (100, 200, 100), restart_rect)
        pygame.draw.rect(virtual_surface, (100, 100, 255), levelselect_rect)
        pygame.draw.rect(virtual_surface, (200, 0, 0), mainmenu_rect)
        restart_label = font.render("Restart", True, (255,255,255))
        levelselect_label = font.render("Level Select", True, (255,255,255))
        mainmenu_label = font.render("Main Menu", True, (255,255,255))
        virtual_surface.blit(restart_label, restart_label.get_rect(center=restart_rect.center))
        virtual_surface.blit(levelselect_label, levelselect_label.get_rect(center=levelselect_rect.center))
        virtual_surface.blit(mainmenu_label, mainmenu_label.get_rect(center=mainmenu_rect.center))
        scaled = pygame.transform.scale(virtual_surface, (SCREEN_WIDTH, SCREEN_HEIGHT))
        screen.blit(scaled, (0, 0))
        pygame.display.flip()
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    waiting = False
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = pygame.mouse.get_pos()
                    vx = int(mx * VIRTUAL_WIDTH / SCREEN_WIDTH)
                    vy = int(my * VIRTUAL_HEIGHT / SCREEN_HEIGHT)
                    if restart_rect.collidepoint(vx, vy):
                        subprocess.Popen([sys.executable, "level1.py"])
                        waiting = False
                        running = False
                    elif levelselect_rect.collidepoint(vx, vy):
                        subprocess.Popen([sys.executable, "level_select.py"])
                        waiting = False
                        running = False
                    elif mainmenu_rect.collidepoint(vx, vy):
                        subprocess.Popen([sys.executable, "Start-Menu.py"])
                        waiting = False
                        running = False
        break

    scaled = pygame.transform.scale(virtual_surface, (SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.blit(scaled, (0, 0))
    pygame.display.flip()

pygame.quit()
sys.exit()
