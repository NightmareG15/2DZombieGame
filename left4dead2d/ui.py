import pygame
import math
import time
from settings import *


class Camera:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.target_x = 0
        self.target_y = 0
        self.shake_x = 0
        self.shake_y = 0
        self.shake_intensity = 0
        self.shake_duration = 0

    def update(self, target_x, target_y):
        self.target_x = target_x - SCREEN_WIDTH // 2
        self.target_y = target_y - SCREEN_HEIGHT // 2
        self.x += (self.target_x - self.x) * 0.1
        self.y += (self.target_y - self.y) * 0.1

        if self.shake_duration > 0:
            self.shake_duration -= 1
            self.shake_x = (0.5 - random.random()) * self.shake_intensity
            self.shake_y = (0.5 - random.random()) * self.shake_intensity
            self.shake_intensity *= 0.9
        else:
            self.shake_x = 0
            self.shake_y = 0

    def shake(self, intensity=5, duration=10):
        self.shake_intensity = intensity
        self.shake_duration = duration

    def get_offset(self):
        return (self.x + self.shake_x, self.y + self.shake_y)


import random


class HUD:
    def __init__(self):
        self.font_large = None
        self.font_medium = None
        self.font_small = None
        self.font_tiny = None
        self.message_queue = []
        self.message_timer = 0

    def init_fonts(self):
        self.font_large = pygame.font.SysFont("Arial", 36, bold=True)
        self.font_medium = pygame.font.SysFont("Arial", 24)
        self.font_small = pygame.font.SysFont("Arial", 16)
        self.font_tiny = pygame.font.SysFont("Arial", 12)

    def add_message(self, text, color=COLORS["white"], duration=120):
        self.message_queue.append({"text": text, "color": color, "timer": duration, "alpha": 255})

    def update(self):
        for msg in self.message_queue:
            msg["timer"] -= 1
        self.message_queue = [m for m in self.message_queue if m["timer"] > 0]

    def draw(self, surface, players, current_player_idx, wave_info, chapter_name, now, has_controller=False):
        if not self.font_large:
            self.init_fonts()

        player = players[current_player_idx]

        self._draw_player_stats(surface, player, now)
        self._draw_team_status(surface, players, current_player_idx)
        self._draw_weapon_info(surface, player)
        self._draw_medkit_inventory(surface, player, has_controller)
        self._draw_crosshair(surface)
        self._draw_messages(surface)
        if wave_info:
            self._draw_wave_info(surface, wave_info)

        if not player.alive:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((100, 0, 0, 100))
            surface.blit(overlay, (0, 0))
            txt = self.font_large.render("MORTO", True, COLORS["red"])
            surface.blit(txt, (SCREEN_WIDTH // 2 - txt.get_width() // 2, SCREEN_HEIGHT // 2 - 30))
            hint = self.font_medium.render("Pressione R para reiniciar", True, COLORS["white"])
            surface.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT // 2 + 20))

    def _draw_player_stats(self, surface, player, now):
        panel_w = 250
        panel_h = 100
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 150))
        surface.blit(panel, (10, SCREEN_HEIGHT - panel_h - 10))

        x, y = 15, SCREEN_HEIGHT - panel_h - 5

        name_surf = self.font_medium.render(player.name, True, player.color)
        surface.blit(name_surf, (x, y))

        y += 28
        pygame.draw.rect(surface, COLORS["dark_gray"], (x, y, 200, 16))
        hp_fill = max(0, player.hp / player.max_hp)
        hp_color = COLORS["red"] if hp_fill < 0.3 else COLORS["yellow"] if hp_fill < 0.6 else COLORS["green"]
        pygame.draw.rect(surface, hp_color, (x, y, int(200 * hp_fill), 16))
        hp_text = self.font_small.render(f"HP: {int(player.hp)}/{player.max_hp}", True, COLORS["white"])
        surface.blit(hp_text, (x + 5, y))

        y += 22
        ability_cd = player.get_ability_cooldown_percent(now)
        ab_color = COLORS["cyan"] if ability_cd >= 1.0 else COLORS["gray"]
        pygame.draw.rect(surface, COLORS["dark_gray"], (x, y, 150, 12))
        pygame.draw.rect(surface, ab_color, (x, y, int(150 * ability_cd), 12))
        ab_text = self.font_small.render(f"[Q] {player.ability_name}", True, COLORS["white"])
        surface.blit(ab_text, (x + 5, y - 2))

        y += 18
        score_text = self.font_small.render(f"Score: {player.score} | Kills: {player.kills}", True, COLORS["yellow"])
        surface.blit(score_text, (x, y))

    def _draw_team_status(self, surface, players, current_idx):
        x = SCREEN_WIDTH - 220
        y = 10
        panel = pygame.Surface((210, 30 + len(players) * 28), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 150))
        surface.blit(panel, (x, y))

        title = self.font_small.render("Team", True, COLORS["white"])
        surface.blit(title, (x + 5, y + 5))
        y += 25

        for i, p in enumerate(players):
            color = COLORS["white"] if p.alive else COLORS["dark_gray"]
            marker = ">> " if i == current_idx else "   "
            status = "Dead" if not p.alive else f"HP:{int(p.hp)}"
            txt = self.font_small.render(f"{marker}{p.name}: {status}", True, color)
            surface.blit(txt, (x + 5, y))
            y += 22

    def _draw_weapon_info(self, surface, player):
        if not player.current_weapon:
            return
        wep = WEAPON_DATA[player.current_weapon]
        x = 10
        y = SCREEN_HEIGHT - 140

        panel = pygame.Surface((200, 55), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 150))
        surface.blit(panel, (x, y))

        name = self.font_small.render(wep["name"], True, COLORS["white"])
        surface.blit(name, (x + 5, y + 5))

        ammo = player.ammo.get(player.current_weapon, 0)
        reserve = player.reserve_ammo.get(player.current_weapon, 0)
        ammo_color = COLORS["red"] if ammo == 0 else COLORS["white"]
        ammo_txt = self.font_medium.render(f"{ammo} / {reserve}", True, ammo_color)
        surface.blit(ammo_txt, (x + 5, y + 25))

        for i in range(len(player.weapons)):
            wx = x + 130 + i * 25
            wc = player.color if i == player.current_weapon_idx else COLORS["gray"]
            pygame.draw.rect(surface, wc, (wx, y + 10, 20, 30))
            pygame.draw.rect(surface, COLORS["white"], (wx, y + 10, 20, 30), 1)
            idx_txt = self.font_small.render(str(i + 1), True, COLORS["white"])
            surface.blit(idx_txt, (wx + 6, y + 18))

    def _draw_medkit_inventory(self, surface, player, has_controller=False):
        x = 10
        y = SCREEN_HEIGHT - 185
        panel = pygame.Surface((120, 35), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 150))
        surface.blit(panel, (x, y))

        icon_color = COLORS["red"]
        pygame.draw.rect(surface, icon_color, (x + 5, y + 8, 18, 18))
        pygame.draw.line(surface, COLORS["white"], (x + 10, y + 17), (x + 18, y + 17), 2)
        pygame.draw.line(surface, COLORS["white"], (x + 14, y + 13), (x + 14, y + 21), 2)

        count = player.medkits
        count_color = COLORS["white"] if count > 0 else COLORS["dark_gray"]
        count_txt = self.font_medium.render(f"x{count}", True, count_color)
        surface.blit(count_txt, (x + 30, y + 6))

        key = "Y" if has_controller else "F"
        hint_color = COLORS["yellow"] if count > 0 else COLORS["dark_gray"]
        hint_txt = self.font_tiny.render(f"[{key}]", True, hint_color)
        surface.blit(hint_txt, (x + 80, y + 12))

    def _draw_crosshair(self, surface):
        mx, my = pygame.mouse.get_pos()
        size = 10
        color = COLORS["white"]
        pygame.draw.line(surface, color, (mx - size, my), (mx - 4, my), 2)
        pygame.draw.line(surface, color, (mx + 4, my), (mx + size, my), 2)
        pygame.draw.line(surface, color, (mx, my - size), (mx, my - 4), 2)
        pygame.draw.line(surface, color, (mx, my + 4), (mx, my + size), 2)
        pygame.draw.circle(surface, color, (mx, my), 2)

    def _draw_messages(self, surface):
        y = SCREEN_HEIGHT // 2 - 50
        for msg in self.message_queue:
            alpha = min(255, msg["timer"] * 4)
            txt = self.font_medium.render(msg["text"], True, msg["color"])
            bg = pygame.Surface((txt.get_width() + 10, txt.get_height() + 4), pygame.SRCALPHA)
            bg.fill((0, 0, 0, min(150, alpha)))
            surface.blit(bg, (SCREEN_WIDTH // 2 - txt.get_width() // 2 - 5, y - 2))
            surface.blit(txt, (SCREEN_WIDTH // 2 - txt.get_width() // 2, y))
            y += 30

    def _draw_wave_info(self, surface, wave_info):
        if not wave_info.get("active"):
            return
        txt = self.font_large.render(f"Horde. Wave {wave_info['current']}/{wave_info['total']}", True, COLORS["red"])
        pulse = abs(math.sin(time.time() * 4)) * 0.3 + 0.7
        c = tuple(int(ch * pulse) for ch in COLORS["red"])
        txt = self.font_large.render(f"Horde. Wave {wave_info['current']}/{wave_info['total']}", True, c)
        surface.blit(txt, (SCREEN_WIDTH // 2 - txt.get_width() // 2, 50))

        remaining = wave_info.get("remaining", 0)
        rem_txt = self.font_medium.render(f"Remaining Zombies: {remaining}", True, COLORS["white"])
        surface.blit(rem_txt, (SCREEN_WIDTH // 2 - rem_txt.get_width() // 2, 90))


class MenuSystem:
    def __init__(self):
        self.font_large = None
        self.font_medium = None
        self.font_small = None
        self.font_tiny = None
        self.selected_char = 0
        self.char_ids = list(CHARACTER_DATA.keys())
        self.menu_state = "main"
        self.selected_option = 0
        self.scroll_offset = 0
        self.controller_name = "None"

    def init_fonts(self):
        self.font_large = pygame.font.SysFont("Arial", 48, bold=True)
        self.font_medium = pygame.font.SysFont("Arial", 28)
        self.font_small = pygame.font.SysFont("Arial", 18)
        self.font_tiny = pygame.font.SysFont("Arial", 14)

    def draw_main_menu(self, surface, now, controller_name="None"):
        if not self.font_large:
            self.init_fonts()
        self.controller_name = controller_name

        surface.fill(COLORS["black"])

        for i in range(20):
            y = i * 40
            c = (20 + i * 2, 5 + i, 5 + i)
            pygame.draw.rect(surface, c, (0, y, SCREEN_WIDTH, 40))

        for i in range(15):
            x = (now // 30 + i * 100) % (SCREEN_WIDTH + 200) - 100
            y = 100 + i * 40 + math.sin(now / 1000 + i) * 20
            s = 3
            pygame.draw.circle(surface, (80, 30, 30), (int(x), int(y)), s)

        title1 = self.font_large.render("LEFT 4", True, COLORS["red"])
        title2 = self.font_large.render("DEAD 2D", True, COLORS["red"])
        shadow1 = self.font_large.render("LEFT 4", True, COLORS["dark_gray"])
        shadow2 = self.font_large.render("DEAD 2D", True, COLORS["dark_gray"])
        surface.blit(shadow1, (SCREEN_WIDTH // 2 - title1.get_width() // 2 + 3, 83))
        surface.blit(shadow2, (SCREEN_WIDTH // 2 - title2.get_width() // 2 + 3, 138))
        surface.blit(title1, (SCREEN_WIDTH // 2 - title1.get_width() // 2, 80))
        surface.blit(title2, (SCREEN_WIDTH // 2 - title2.get_width() // 2, 135))

        subtitle = self.font_small.render("An 2D Parody of Left 4 Dead", True, COLORS["light_gray"])
        surface.blit(subtitle, (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, 190))

        ctrl_hint = f"Controller: {controller_name}"
        ctrl_color = COLORS["green"] if controller_name != "None" else COLORS["gray"]
        ctrl_surf = self.font_tiny.render(ctrl_hint, True, ctrl_color)
        surface.blit(ctrl_surf, (SCREEN_WIDTH // 2 - ctrl_surf.get_width() // 2, 210))

        options = ["Play", "Quit"]
        for i, opt in enumerate(options):
            y = 250 + i * 50
            color = COLORS["yellow"] if i == self.selected_option else COLORS["white"]
            if i == self.selected_option:
                pygame.draw.rect(surface, (60, 60, 40), (SCREEN_WIDTH // 2 - 200, y - 5, 400, 35))
                arrow = ">> "
            else:
                arrow = "   "
            txt = self.font_medium.render(f"{arrow}{opt}", True, color)
            surface.blit(txt, (SCREEN_WIDTH // 2 - txt.get_width() // 2, y))

        controls_y = SCREEN_HEIGHT - 140
        pygame.draw.rect(surface, (15, 15, 25), (20, controls_y, SCREEN_WIDTH - 40, 100))
        pygame.draw.rect(surface, COLORS["dark_gray"], (20, controls_y, SCREEN_WIDTH - 40, 100), 1)
        ctrl_title = self.font_small.render("CONTROLS", True, COLORS["yellow"])
        surface.blit(ctrl_title, (40, controls_y + 5))

        keys_left = [
            "WASD: Move | Mouse: Aim | LeftClick: Shoot | R: Reload",
            "Q: Special Ability | F: Medkit | E: Interact",
            "Scroll/RightClick/1,2,3: Swap Weapon | ESC: Pause",
        ]
        keys_right = [
            "Controle: LeftStick=Move | RightStick=Aim | RT/R1=Shoot",
            "Y/Square=Special Ability | B/Circle=Reload | X/Triangle=Medkit "
            "A/Cross=Interact | LB/RB: Swap Weapon | Start: Pause",
        ]
        for i, line in enumerate(keys_left):
            surf = self.font_tiny.render(line, True, COLORS["light_gray"])
            surface.blit(surf, (40, controls_y + 25 + i * 20))
        for i, line in enumerate(keys_right):
            surf = self.font_tiny.render(line, True, COLORS["light_gray"])
            surface.blit(surf, (SCREEN_WIDTH // 2 + 20, controls_y + 25 + i * 20))

        hint = self.font_small.render("W/S to select, ENTER to confirm", True, COLORS["gray"])
        surface.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT - 25))

        ver = self.font_small.render("V0.0.1 - Built with Python", True, COLORS["gray"])
        surface.blit(ver, (SCREEN_WIDTH - 200, SCREEN_HEIGHT - 25))

    def draw_character_select(self, surface):
        if not self.font_large:
            self.init_fonts()
        surface.fill((10, 10, 20))

        title = self.font_large.render("Select Your Survivor", True, COLORS["white"])
        surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 30))

        card_w = 250
        card_h = 350
        total_w = len(self.char_ids) * (card_w + 20) - 20
        start_x = (SCREEN_WIDTH - total_w) // 2

        for i, cid in enumerate(self.char_ids):
            data = CHARACTER_DATA[cid]
            x = start_x + i * (card_w + 20)
            y = 120
            selected = i == self.selected_char

            card_color = (40, 40, 60) if selected else (25, 25, 35)
            border_color = data["color"] if selected else COLORS["dark_gray"]
            pygame.draw.rect(surface, card_color, (x, y, card_w, card_h))
            pygame.draw.rect(surface, border_color, (x, y, card_w, card_h), 3 if selected else 1)

            pygame.draw.circle(surface, data["color"], (x + card_w // 2, y + 50), 30)
            pygame.draw.circle(surface, (min(255, data["color"][0] + 40), min(255, data["color"][1] + 40),
                                         min(255, data["color"][2] + 40)),
                             (x + card_w // 2 - 8, y + 42), 10)

            gun_angle = -30
            gx = x + card_w // 2 + 15
            gy = y + 50
            end_x = gx + math.cos(math.radians(gun_angle)) * 20
            end_y = gy + math.sin(math.radians(gun_angle)) * 20
            pygame.draw.line(surface, COLORS["gray"], (gx, gy), (int(end_x), int(end_y)), 3)

            name_txt = self.font_medium.render(data["name"], True, data["color"])
            surface.blit(name_txt, (x + card_w // 2 - name_txt.get_width() // 2, y + 90))

            desc_txt = self.font_small.render(data["desc"], True, COLORS["light_gray"])
            surface.blit(desc_txt, (x + card_w // 2 - desc_txt.get_width() // 2, y + 115))

            stats_y = y + 145
            hp_bar_w = 180
            pygame.draw.rect(surface, COLORS["dark_gray"], (x + 35, stats_y, hp_bar_w, 12))
            hp_fill = data["hp"] / 150
            pygame.draw.rect(surface, COLORS["green"], (x + 35, stats_y, int(hp_bar_w * hp_fill), 12))
            hp_label = self.font_small.render(f"HP: {data['hp']}", True, COLORS["white"])
            surface.blit(hp_label, (x + 35, stats_y - 15))

            stats_y += 25
            pygame.draw.rect(surface, COLORS["dark_gray"], (x + 35, stats_y, hp_bar_w, 12))
            spd_fill = data["speed"] / 4.0
            pygame.draw.rect(surface, COLORS["cyan"], (x + 35, stats_y, int(hp_bar_w * spd_fill), 12))
            spd_label = self.font_small.render(f"Speed: {data['speed']:.1f}", True, COLORS["white"])
            surface.blit(spd_label, (x + 35, stats_y - 15))

            stats_y += 30
            ab_title = self.font_small.render("Special Ability:", True, COLORS["yellow"])
            surface.blit(ab_title, (x + 35, stats_y))

            stats_y += 18
            ab_name = self.font_small.render(data["ability"], True, COLORS["cyan"])
            surface.blit(ab_name, (x + 35, stats_y))

            stats_y += 18
            ab_desc_words = data["ability_desc"].split()
            line = ""
            for word in ab_desc_words:
                test = line + " " + word if line else word
                if self.font_small.size(test)[0] > card_w - 40:
                    desc_surf = self.font_small.render(line, True, COLORS["light_gray"])
                    surface.blit(desc_surf, (x + 35, stats_y))
                    stats_y += 15
                    line = word
                else:
                    line = test
            if line:
                desc_surf = self.font_small.render(line, True, COLORS["light_gray"])
                surface.blit(desc_surf, (x + 35, stats_y))

            if selected:
                pygame.draw.rect(surface, COLORS["yellow"], (x + 10, y + card_h - 35, card_w - 20, 25))
                sel_txt = self.font_small.render("Selected", True, COLORS["black"])
                surface.blit(sel_txt, (x + card_w // 2 - sel_txt.get_width() // 2, y + card_h - 33))

        hint = self.font_small.render("A/D or Arrows to Select, ENTER to confirm", True, COLORS["gray"])
        surface.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT - 50))

        hint2 = self.font_small.render("ESC to return", True, COLORS["gray"])
        surface.blit(hint2, (SCREEN_WIDTH // 2 - hint2.get_width() // 2, SCREEN_HEIGHT - 25))

    def draw_pause_menu(self, surface):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        title = self.font_large.render("Pause", True, COLORS["white"])
        surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 150))

        options = ["Continue", "Restart", "Return To Menu"]
        for i, opt in enumerate(options):
            y = 250 + i * 50
            color = COLORS["yellow"] if i == self.selected_option else COLORS["white"]
            prefix = ">> " if i == self.selected_option else "   "
            txt = self.font_medium.render(f"{prefix}{opt}", True, color)
            surface.blit(txt, (SCREEN_WIDTH // 2 - txt.get_width() // 2, y))

    def draw_loading(self, surface, chapter_name, progress=0):
        surface.fill((5, 5, 15))
        title = self.font_large.render("Loading...", True, COLORS["white"])
        surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 2 - 50))

        name = self.font_medium.render(chapter_name, True, COLORS["cyan"])
        surface.blit(name, (SCREEN_WIDTH // 2 - name.get_width() // 2, SCREEN_HEIGHT // 2 + 10))

        bar_w = 400
        bar_x = SCREEN_WIDTH // 2 - bar_w // 2
        bar_y = SCREEN_HEIGHT // 2 + 60
        pygame.draw.rect(surface, COLORS["dark_gray"], (bar_x, bar_y, bar_w, 20))
        pygame.draw.rect(surface, COLORS["cyan"], (bar_x, bar_y, int(bar_w * progress), 20))
        pygame.draw.rect(surface, COLORS["white"], (bar_x, bar_y, bar_w, 20), 2)

    def draw_game_over(self, surface, score, chapter, timer_secs):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((80, 0, 0, 200))
        surface.blit(overlay, (0, 0))

        title = self.font_large.render("You are Dead.", True, COLORS["red"])
        surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 150))

        score_txt = self.font_medium.render(f"Final Score: {score}", True, COLORS["yellow"])
        surface.blit(score_txt, (SCREEN_WIDTH // 2 - score_txt.get_width() // 2, 230))

        chapter_txt = self.font_medium.render(f"Chapter: {chapter}", True, COLORS["white"])
        surface.blit(chapter_txt, (SCREEN_WIDTH // 2 - chapter_txt.get_width() // 2, 270))

        countdown = max(1, timer_secs)
        hint = self.font_medium.render(f"Returning to menu in {countdown}s...", True, COLORS["gray"])
        surface.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 340))

    def draw_victory(self, surface, score):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 50, 0, 200))
        surface.blit(overlay, (0, 0))

        title = self.font_large.render("End of campaign.", True, COLORS["green"])
        surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 150))

        subtitle = self.font_medium.render("The survivors have escaped!", True, COLORS["white"])
        surface.blit(subtitle, (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, 210))

        score_txt = self.font_large.render(f"Final Score: {score}", True, COLORS["yellow"])
        surface.blit(score_txt, (SCREEN_WIDTH // 2 - score_txt.get_width() // 2, 270))

        hint = self.font_medium.render("ENTER to Return to menu | R to Replay", True, COLORS["gray"])
        surface.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 350))

    def draw_chapter_intro(self, surface, chapter_data, timer):
        alpha = min(255, timer * 3) if timer > 0 else max(0, 255 - (200 - timer) * 3)
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        surface.blit(overlay, (0, 0))

        if timer > 20:
            chapter_num = self.font_medium.render(f"Chapter 1", True, COLORS["gray"])
            surface.blit(chapter_num, (SCREEN_WIDTH // 2 - chapter_num.get_width() // 2, SCREEN_HEIGHT // 2 - 80))

            name = self.font_large.render(chapter_data["name"], True, COLORS["red"])
            surface.blit(name, (SCREEN_WIDTH // 2 - name.get_width() // 2, SCREEN_HEIGHT // 2 - 40))

            subtitle = self.font_medium.render(chapter_data["subtitle"], True, COLORS["cyan"])
            surface.blit(subtitle, (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, SCREEN_HEIGHT // 2 + 10))

            desc = self.font_small.render(chapter_data["description"], True, COLORS["light_gray"])
            surface.blit(desc, (SCREEN_WIDTH // 2 - desc.get_width() // 2, SCREEN_HEIGHT // 2 + 50))

    def draw_minimap(self, surface, level, players, enemies, x, y, size):
        map_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        map_surf.fill((0, 0, 0, 150))

        scale_x = size / (level.width * TILE_SIZE)
        scale_y = size / (level.height * TILE_SIZE)

        for tx in range(level.width):
            for ty in range(level.height):
                tile = level.tiles[tx][ty]
                if tile == 1:
                    px = int(tx * TILE_SIZE * scale_x)
                    py = int(ty * TILE_SIZE * scale_y)
                    pygame.draw.rect(map_surf, (60, 60, 70), (px, py, max(1, int(TILE_SIZE * scale_x)),
                                                              max(1, int(TILE_SIZE * scale_y))))
                elif tile == 2:
                    px = int(tx * TILE_SIZE * scale_x)
                    py = int(ty * TILE_SIZE * scale_y)
                    pygame.draw.rect(map_surf, (30, 100, 40), (px, py, max(1, int(TILE_SIZE * scale_x)),
                                                               max(1, int(TILE_SIZE * scale_y))))

        for p in players:
            if p.alive:
                px = int(p.x * scale_x)
                py = int(p.y * scale_y)
                pygame.draw.circle(map_surf, p.color, (px, py), 3)

        for e in enemies:
            if e.alive:
                px = int(e.x * scale_x)
                py = int(e.y * scale_y)
                pygame.draw.circle(map_surf, COLORS["red"], (px, py), 2)

        pygame.draw.rect(map_surf, COLORS["white"], (0, 0, size, size), 1)
        surface.blit(map_surf, (x, y))
