import pygame
import sys
import random
import math
from settings import *
from entities import *
from world import *
from ui import *


class Game:
    def __init__(self):
        pygame.init()
        pygame.mouse.set_visible(False)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Left 4 Dead 2D")
        self.clock = pygame.time.Clock()
        self.running = True

        self.state = "menu"
        self.menu = MenuSystem()
        self.hud = HUD()
        self.camera = Camera()

        self.players = []
        self.enemies = []
        self.bullets = []
        self.items = []
        self.particles = []
        self.explosions = []

        self.current_player_idx = 0
        self.level = None
        self.chapter_num = 0
        self.chapter_data = None

        self.wave_active = False
        self.current_wave = 0
        self.total_waves = 0
        self.wave_timer = 0
        self.wave_delay = 180
        self.between_waves = True
        self.wave_delay_timer = 0
        self.horde_spawned = 0
        self.horde_target = 0
        self.finale_active = False
        self.finale_wave = 0
        self.safe_room_reached = False
        self.game_over = False
        self.game_over_timer = 0
        self.victory = False
        self.score = 0
        self.chapter_timer = 0
        self.wave_info = {"active": False, "current": 0, "total": 0, "remaining": 0}
        self.total_score = 0

        self.selected_char = 0
        self.char_ids = list(CHARACTER_DATA.keys())

        self.ai_players = []

        self.horde_sound_timer = 0
        self.pill_effect_timer = 0

        self.joystick = None
        self.has_controller = False
        self._init_controller()
        self.controller_aim_x = 0
        self.controller_aim_y = 0
        self.controller_move_x = 0
        self.controller_move_y = 0
        self.rt_pressed = False
        self.left_bumper_prev = False
        self.right_bumper_prev = False

    def _init_controller(self):
        try:
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.has_controller = True
                print(f"Controle conectado: {self.joystick.get_name()}")
            else:
                self.has_controller = False
        except Exception as e:
            self.has_controller = False
            print(f"Erro ao inicializar controle: {e}")

    def new_game(self, char_id, chapter=0):
        self.chapter_num = chapter
        self.chapter_data = CAMPAIGN["chapters"][chapter]
        self.total_waves = self.chapter_data["safe_room_waves"] + self.chapter_data["horde_waves"]
        self.level = Level(self.chapter_data, chapter)

        self.players.clear()
        self.enemies.clear()
        self.bullets.clear()
        self.items.clear()
        self.particles.clear()
        self.explosions.clear()
        self.ai_players.clear()

        spawn_x, spawn_y = self.level.spawn_point
        player = Player(char_id, spawn_x, spawn_y, 0)
        player.give_starting_weapon()
        self.players.append(player)

        ai_chars = [c for c in self.char_ids if c != char_id]
        random.shuffle(ai_chars)
        for i in range(3):
            ai_player = Player(ai_chars[i], spawn_x + (i + 1) * 40, spawn_y, i + 1)
            ai_player.give_starting_weapon()
            self.players.append(ai_player)
            self.ai_players.append(AIPlayer(ai_player))

        self.current_player_idx = 0
        self.wave_active = False
        self.current_wave = 0
        self.between_waves = True
        self.wave_delay_timer = 120
        self.finale_active = False
        self.finale_wave = 0
        self.safe_room_reached = False
        self.game_over = False
        self.game_over_timer = 0
        self.victory = False
        self.score = 0
        self.chapter_timer = 0

        self._spawn_initial_items()

        self.state = "chapter_intro"
        self.chapter_intro_timer = 200

    def _spawn_initial_items(self):
        for _ in range(5):
            pos = self.level.get_random_walkable_position(exclude_safe=True)
            item_type = random.choice(["medkit", "pills", "ammo", "ammo"])
            self.items.append(Item(item_type, pos[0], pos[1]))
        weapon_types = ["weapon_shotgun", "weapon_smg", "weapon_rifle", "weapon_sniper", "weapon_grenade"]
        for _ in range(3):
            pos = self.level.get_random_walkable_position(exclude_safe=True)
            self.items.append(Item(random.choice(weapon_types), pos[0], pos[1]))

    def spawn_particles(self, x, y, color, count=5):
        for _ in range(count):
            angle = random.uniform(0, 360)
            speed = random.uniform(1, 4)
            vx = math.cos(math.radians(angle)) * speed
            vy = math.sin(math.radians(angle)) * speed
            self.particles.append(Particle(x, y, vx, vy, color,
                                          random.randint(2, 4), random.randint(15, 30)))

    def spawn_explosion(self, x, y, radius, color=(255, 150, 30)):
        self.explosions.append(Explosion(x, y, radius, color))
        self.camera.shake(8, 15)
        for _ in range(20):
            angle = random.uniform(0, 360)
            speed = random.uniform(2, 8)
            vx = math.cos(math.radians(angle)) * speed
            vy = math.sin(math.radians(angle)) * speed
            c = random.choice([COLORS["orange"], COLORS["yellow"], COLORS["red"]])
            self.particles.append(Particle(x, y, vx, vy, c,
                                          random.randint(3, 6), random.randint(20, 40), 0.05))

    def spawn_horde(self, size=None):
        if size is None:
            size = self.chapter_data["horde_size_base"] + self.current_wave * self.chapter_data["horde_growth"]
        self.horde_target = size
        self.horde_spawned = 0
        self.wave_active = True
        self.between_waves = False
        self.wave_info = {
            "active": True,
            "current": self.current_wave,
            "total": self.total_waves,
            "remaining": size,
        }
        self.hud.add_message("A HORDA VEM!", COLORS["red"], 90)

    def spawn_special_enemy(self, enemy_type=None):
        player = self.players[self.current_player_idx]
        pos = self.level.get_random_enemy_spawn((player.x, player.y), 350)
        if enemy_type is None:
            rate = self.chapter_data["special_spawn_rate"]
            if random.random() < rate:
                enemy_type = random.choice(["boomer", "smoker", "hunter"])
                if self.chapter_data.get("has_tank") and random.random() < 0.1:
                    enemy_type = "tank"
                if self.chapter_data.get("has_witch") and random.random() < 0.08:
                    enemy_type = "witch"
            else:
                enemy_type = "common"
        self.enemies.append(Enemy(enemy_type, pos[0], pos[1], self.current_wave))

    def update_waves(self, now):
        if self.game_over or self.victory:
            return

        self.chapter_timer += 1

        if self.between_waves:
            self.wave_delay_timer -= 1
            if self.wave_delay_timer <= 0:
                self.current_wave += 1
                if self.current_wave > self.total_waves:
                    self.safe_room_reached = True
                    self._advance_to_next_chapter()
                    return
                if self.current_wave <= self.chapter_data["safe_room_waves"]:
                    self.hud.add_message(
                        f"Onda {self.current_wave}/{self.total_waves} de zumbis",
                        COLORS["yellow"],
                    )
                    for _ in range(5 + self.current_wave * 3):
                        self.spawn_special_enemy("common")
                    self.between_waves = False
                    self.wave_timer = 300
                else:
                    self.spawn_horde()
            return

        if self.wave_active:
            if self.horde_spawned < self.horde_target:
                spawn_rate = max(2, 8 - self.current_wave)
                if self.chapter_timer % spawn_rate == 0:
                    self.spawn_special_enemy()
                    self.horde_spawned += 1

            if self.chapter_timer % 300 == 0:
                pos = self.level.get_random_walkable_position(exclude_safe=True)
                item_type = random.choice(["ammo", "ammo", "pills", "adrenaline"])
                self.items.append(Item(item_type, pos[0], pos[1]))

            alive_enemies = sum(1 for e in self.enemies if e.alive)
            self.wave_info["remaining"] = alive_enemies + (self.horde_target - self.horde_spawned)

            if self.horde_spawned >= self.horde_target and alive_enemies == 0:
                self.wave_active = False
                self.between_waves = True
                self.wave_delay_timer = self.wave_delay
                self.hud.add_message(
                    f"Onda {self.current_wave} concluida!", COLORS["green"], 60
                )
                if self.current_wave > self.chapter_data["safe_room_waves"]:
                    self.safe_room_reached = True
                    self._advance_to_next_chapter()
                    return
                self._drop_wave_rewards()
        else:
            self.wave_timer -= 1
            if self.wave_timer <= 0 and not self.between_waves:
                self.between_waves = True
                self.wave_delay_timer = self.wave_delay

    def _drop_wave_rewards(self):
        for _ in range(4):
            pos = self.level.get_random_walkable_position()
            item_type = random.choice(["medkit", "pills", "ammo", "ammo", "ammo", "adrenaline"])
            self.items.append(Item(item_type, pos[0], pos[1]))
        if random.random() < 0.4:
            pos = self.level.get_random_walkable_position()
            weapon_types = ["weapon_shotgun", "weapon_smg", "weapon_rifle", "weapon_sniper", "weapon_grenade"]
            self.items.append(Item(random.choice(weapon_types), pos[0], pos[1]))

    def _advance_to_next_chapter(self):
        if self.chapter_num < len(CAMPAIGN["chapters"]) - 1:
            self.total_score += self.score
            self.chapter_num += 1
            self.chapter_data = CAMPAIGN["chapters"][self.chapter_num]
            self.total_waves = (
                self.chapter_data["safe_room_waves"] + self.chapter_data["horde_waves"]
            )
            self.level = Level(self.chapter_data, self.chapter_num)
            spawn_x, spawn_y = self.level.spawn_point
            for i, p in enumerate(self.players):
                p.x = spawn_x + i * 40
                p.y = spawn_y
                if p.hp < p.max_hp:
                    p.heal(20)
                for wpn in p.weapons:
                    p.ammo[wpn] = WEAPON_DATA[wpn]["magazine"]
            self.enemies.clear()
            self.bullets.clear()
            self.items.clear()
            self.current_wave = 0
            self.between_waves = True
            self.wave_delay_timer = 180
            self.finale_active = False
            self.safe_room_reached = False
            self.wave_info = {"active": False, "current": 0, "total": 0, "remaining": 0}
            self.state = "chapter_intro"
            self.chapter_intro_timer = 200
            self._spawn_initial_items()
            self.hud.add_message(
                f"Capitulo {self.chapter_num + 1}: {self.chapter_data['name']}",
                COLORS["cyan"],
                120,
            )
        else:
            self.victory = True
            self.total_score += self.score
            self.state = "victory"

    def update_entities(self, now, keys, mouse_pos, mouse_buttons, dt):
        cam_x, cam_y = self.camera.get_offset()
        player = self.players[self.current_player_idx]

        for p in self.players:
            if p == player:
                ctrl_move = (self.controller_move_x, self.controller_move_y) if self.has_controller else None
                ctrl_aim = (self.controller_aim_x, self.controller_aim_y) if self.has_controller else None
                p.update(now, keys, mouse_pos, mouse_buttons, cam_x, cam_y, dt, self.level,
                         ctrl_move, ctrl_aim)
            if not p.alive:
                continue
            if p.bleeding and p.hp > 0:
                p.hp -= 0.05
                if self.chapter_timer % 30 == 0:
                    self.spawn_particles(p.x, p.y, COLORS["blood"], 2)

        for ai in self.ai_players:
            ai.update(now, self.enemies, self)

        for e in self.enemies:
            e.update(now, self.players, self.enemies, self)

        self.enemies = [e for e in self.enemies if e.alive]

        for bullet in self.bullets:
            bullet.update()
            if not bullet.alive:
                continue
            if not self.level.is_walkable(bullet.x, bullet.y):
                bullet.alive = False
                self.spawn_particles(bullet.x, bullet.y, COLORS["orange"], 3)
                continue

            if bullet.explosive:
                hit = False
                for e in self.enemies:
                    if e.alive:
                        dx = bullet.x - e.x
                        dy = bullet.y - e.y
                        if math.sqrt(dx * dx + dy * dy) < bullet.size + e.size:
                            hit = True
                            break
                for p in self.players:
                    if p.alive:
                        dx = bullet.x - p.x
                        dy = bullet.y - p.y
                        if math.sqrt(dx * dx + dy * dy) < bullet.size + p.size:
                            hit = True
                            break
                if hit:
                    bullet.alive = False
                    self.spawn_explosion(bullet.x, bullet.y, bullet.explosion_radius)
                    for e in self.enemies:
                        if e.alive:
                            dx = bullet.x - e.x
                            dy = bullet.y - e.y
                            dist = math.sqrt(dx * dx + dy * dy)
                            if dist < bullet.explosion_radius:
                                falloff = 1 - dist / bullet.explosion_radius
                                if e.take_damage(bullet.damage * falloff):
                                    player.kills += 1
                                    player.score += e.points
                                    self.spawn_particles(e.x, e.y, COLORS["blood"], 8)
                    for p in self.players:
                        if p.alive and p.player_id != bullet.owner_id:
                            dx = bullet.x - p.x
                            dy = bullet.y - p.y
                            dist = math.sqrt(dx * dx + dy * dy)
                            if dist < bullet.explosion_radius:
                                falloff = 1 - dist / bullet.explosion_radius
                                p.take_damage(bullet.damage * falloff * 0.3)
                    continue

            for e in self.enemies:
                if e.alive:
                    dx = bullet.x - e.x
                    dy = bullet.y - e.y
                    if math.sqrt(dx * dx + dy * dy) < bullet.size + e.size:
                        bullet.alive = False
                        self.spawn_particles(bullet.x, bullet.y, COLORS["blood"], 4)
                        if e.take_damage(bullet.damage):
                            player.kills += 1
                            player.score += e.points
                            self.score += e.points
                            self.spawn_particles(e.x, e.y, COLORS["blood"], 8)
                            if e.explode_on_death:
                                self.spawn_explosion(e.x, e.y, e.explode_radius)
                                for p in self.players:
                                    if p.alive:
                                        dx2 = p.x - e.x
                                        dy2 = p.y - e.y
                                        dist = math.sqrt(dx2 * dx2 + dy2 * dy2)
                                        if dist < e.explode_radius:
                                            p.take_damage(e.damage)
                                            p.vomit_timer = 3000
                            if e.attracts_horde:
                                self.spawn_horde(15)
                        break

            if bullet.owner_id != 0:
                for p in self.players:
                    if p.alive and p.player_id != bullet.owner_id:
                        dx = bullet.x - p.x
                        dy = bullet.y - p.y
                        if math.sqrt(dx * dx + dy * dy) < bullet.size + p.size:
                            bullet.alive = False
                            p.take_damage(bullet.damage * 0.5)
                            self.spawn_particles(p.x, p.y, COLORS["blood"], 3)
                            break

        self.bullets = [b for b in self.bullets if b.alive]

        for item in self.items:
            if item.alive:
                for p in self.players:
                    if p.alive:
                        dx = p.x - item.x
                        dy = p.y - item.y
                        if math.sqrt(dx * dx + dy * dy) < 30:
                            item.apply(p)
        self.items = [i for i in self.items if i.alive]

        for p in self.players:
            px = max(p.size, min(p.x, self.level.width * TILE_SIZE - p.size))
            py = max(p.size, min(p.y, self.level.height * TILE_SIZE - p.size))
            if self.level.is_walkable(px, py):
                p.x = px
                p.y = py

        self.particles = [p for p in self.particles if p.update()]
        self.explosions = [e for e in self.explosions if e.alive]
        for exp in self.explosions:
            exp.update()

    def handle_input(self, now):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if self.state == "menu":
                self._handle_menu_event(event, now)
            elif self.state == "character_select":
                self._handle_char_select_event(event, now)
            elif self.state == "playing":
                self._handle_game_event(event, now)
            elif self.state == "paused":
                self._handle_pause_event(event, now)
            elif self.state == "game_over":
                self._handle_game_over_event(event, now)
            elif self.state == "victory":
                self._handle_victory_event(event, now)
            elif self.state == "chapter_intro":
                pass

    def _handle_menu_event(self, event, now):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_w or event.key == pygame.K_UP:
                self.menu.selected_option = max(0, self.menu.selected_option - 1)
            elif event.key == pygame.K_s or event.key == pygame.K_DOWN:
                self.menu.selected_option = min(2, self.menu.selected_option + 1)
            elif event.key == pygame.K_RETURN:
                if self.menu.selected_option == 0:
                    self.state = "character_select"
                elif self.menu.selected_option == 1:
                    self.running = False

        if event.type == pygame.JOYBUTTONDOWN:
            if event.button == 12:
                self.menu.selected_option = max(0, self.menu.selected_option - 1)
            elif event.button == 13:
                self.menu.selected_option = min(2, self.menu.selected_option + 1)
            elif event.button == 7:
                if self.menu.selected_option == 0:
                    self.state = "character_select"
                elif self.menu.selected_option == 1:
                    self.running = False

    def _handle_char_select_event(self, event, now):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_a or event.key == pygame.K_LEFT:
                self.menu.selected_char = (self.menu.selected_char - 1) % len(self.char_ids)
            elif event.key == pygame.K_d or event.key == pygame.K_RIGHT:
                self.menu.selected_char = (self.menu.selected_char + 1) % len(self.char_ids)
            elif event.key == pygame.K_RETURN:
                char_id = self.char_ids[self.menu.selected_char]
                self.new_game(char_id)
            elif event.key == pygame.K_ESCAPE:
                self.state = "menu"

        if event.type == pygame.JOYBUTTONDOWN:
            if event.button == 14:
                self.menu.selected_char = (self.menu.selected_char - 1) % len(self.char_ids)
            elif event.button == 15:
                self.menu.selected_char = (self.menu.selected_char + 1) % len(self.char_ids)
            elif event.button == 7:
                char_id = self.char_ids[self.menu.selected_char]
                self.new_game(char_id)
            elif event.button == 8:
                self.state = "menu"

    def _handle_game_event(self, event, now):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = "paused"
                self.menu.selected_option = 0
            elif event.key == pygame.K_q:
                self.players[0].use_ability(now)
            elif event.key == pygame.K_r:
                self._reload_weapon(now)
            elif event.key == pygame.K_f:
                self._use_medkit()
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                idx = event.key - pygame.K_1
                p = self.players[0]
                if idx < len(p.weapons):
                    p.current_weapon_idx = idx
            elif event.key == pygame.K_TAB:
                self.menu.show_minimap = getattr(self.menu, "show_minimap", False)
            elif event.key == pygame.K_e:
                self._interact(now)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self._handle_shooting(now)
            elif event.button == 3:
                self.players[0].switch_weapon(1)
            elif event.button == 4:
                self.players[0].switch_weapon(-1)
            elif event.button == 5:
                self.players[0].switch_weapon(1)

        if event.type == pygame.JOYBUTTONDOWN:
            if event.button == 5:
                self.players[0].use_ability(now)
            elif event.button == 1:
                self._reload_weapon(now)
            elif event.button == 2:
                self._use_medkit()
            elif event.button == 0:
                self._interact(now)
            elif event.button == 8:
                self.players[0].switch_weapon(-1)
            elif event.button == 9:
                self.players[0].switch_weapon(1)
            elif event.button == 6:
                self.state = "paused"
                self.menu.selected_option = 0

    def _handle_shooting(self, now):
        player = self.players[0]
        if player.current_weapon and WEAPON_DATA[player.current_weapon]["auto"]:
            return
        bullets = player.shoot(now)
        self.bullets.extend(bullets)
        if bullets:
            self.camera.shake(2, 3)

    def _handle_controller_shooting(self, now):
        if not self.has_controller or not self.joystick:
            return
        try:
            rt = self.joystick.get_axis(5)
            if rt > 0.5 and not self.rt_pressed:
                self.rt_pressed = True
                self._handle_shooting(now)
            elif rt < 0.3:
                self.rt_pressed = False
        except Exception:
            pass

    def _handle_continuous_shooting(self, now):
        player = self.players[0]
        if not player.current_weapon:
            return
        if WEAPON_DATA[player.current_weapon]["auto"]:
            mouse_buttons = pygame.mouse.get_pressed()
            trigger = False
            if self.has_controller and self.joystick:
                try:
                    rt = self.joystick.get_axis(5)
                    trigger = rt > 0.5
                except:
                    pass
            if mouse_buttons[0] or trigger:
                bullets = player.shoot(now)
                self.bullets.extend(bullets)
                if bullets:
                    self.camera.shake(1, 2)

    def _reload_weapon(self, now):
        player = self.players[0]
        if not player.current_weapon:
            return
        wpn = player.current_weapon
        if player.ammo[wpn] < WEAPON_DATA[wpn]["magazine"]:
            needed = WEAPON_DATA[wpn]["magazine"] - player.ammo[wpn]
            available = min(needed, player.reserve_ammo.get(wpn, 0))
            player.ammo[wpn] += available
            player.reserve_ammo[wpn] -= available
            self.hud.add_message("Recarregando...", COLORS["yellow"], 30)

    def _use_medkit(self):
        player = self.players[0]
        if player.use_medkit():
            self.hud.add_message("Medkit usado! +40 HP", COLORS["green"], 45)
            self.spawn_particles(player.x, player.y, COLORS["green"], 8)
        elif player.medkits == 0:
            self.hud.add_message("Sem medkits!", COLORS["red"], 30)

    def _interact(self, now):
        player = self.players[0]
        for item in self.items:
            if item.alive:
                dx = player.x - item.x
                dy = player.y - item.y
                if math.sqrt(dx * dx + dy * dy) < 50:
                    item.apply(player)
                    self.hud.add_message(f"Pegou: {ITEM_DATA[item.type]['name']}", COLORS["green"], 30)
                    break

        for p in self.players:
            if p != player and not p.alive:
                dx = player.x - p.x
                dy = player.y - p.y
                if math.sqrt(dx * dx + dy * dy) < 50:
                    p.alive = True
                    p.hp = 30
                    self.hud.add_message(f"{p.name} resgatado!", COLORS["cyan"], 60)
                    break

    def _handle_pause_event(self, event, now):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = "playing"
            elif event.key == pygame.K_w or event.key == pygame.K_UP:
                self.menu.selected_option = max(0, self.menu.selected_option - 1)
            elif event.key == pygame.K_s or event.key == pygame.K_DOWN:
                self.menu.selected_option = min(2, self.menu.selected_option + 1)
            elif event.key == pygame.K_RETURN:
                if self.menu.selected_option == 0:
                    self.state = "playing"
                elif self.menu.selected_option == 1:
                    self.new_game(self.char_ids[self.menu.selected_char])
                    self.state = "playing"
                elif self.menu.selected_option == 2:
                    self.state = "menu"

    def _handle_game_over_event(self, event, now):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.game_over_timer = 0
                self.new_game(self.char_ids[self.menu.selected_char])
            elif event.key == pygame.K_ESCAPE:
                self.game_over_timer = 0
                self.state = "menu"

    def _handle_victory_event(self, event, now):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.new_game(self.char_ids[self.menu.selected_char])
            elif event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self.state = "menu"

    def check_game_over(self):
        alive = [p for p in self.players if p.alive]
        if not alive:
            self.game_over = True
            self.game_over_timer = 4 * FPS
            self.state = "game_over"

    def _update_controller_input(self):
        if not self.has_controller or not self.joystick:
            return
        try:
            self.controller_move_x = self.joystick.get_axis(0)
            self.controller_move_y = self.joystick.get_axis(1)
            self.controller_aim_x = self.joystick.get_axis(2)
            self.controller_aim_y = self.joystick.get_axis(3)
            lb = self.joystick.get_button(4)
            rb = self.joystick.get_button(5)
            if rb and not self.right_bumper_prev:
                self.players[0].switch_weapon(1)
            if lb and not self.left_bumper_prev:
                self.players[0].switch_weapon(-1)
            self.left_bumper_prev = lb
            self.right_bumper_prev = rb
        except Exception:
            pass

    def draw(self, now):
        self.screen.fill(COLORS["black"])

        if self.state == "menu":
            self.menu.draw_main_menu(self.screen, now, self.joystick.get_name() if self.has_controller and self.joystick else "Nenhum")
        elif self.state == "character_select":
            self.menu.draw_character_select(self.screen)
        elif self.state == "chapter_intro":
            self.level.draw(self.screen, *self.camera.get_offset())
            for p in self.players:
                p.draw(self.screen, *self.camera.get_offset())
                p.draw_health_bar(self.screen, *self.camera.get_offset())
            self.menu.draw_chapter_intro(self.screen, self.chapter_data, self.chapter_intro_timer)
        elif self.state == "playing" or self.state == "paused":
            cam_x, cam_y = self.camera.get_offset()
            self.level.draw(self.screen, cam_x, cam_y)

            for item in self.items:
                item.draw(self.screen, cam_x, cam_y)

            for e in self.enemies:
                e.draw(self.screen, cam_x, cam_y)

            for p in self.players:
                p.draw(self.screen, cam_x, cam_y)
                p.draw_health_bar(self.screen, cam_x, cam_y)

            for bullet in self.bullets:
                bullet.draw(self.screen, cam_x, cam_y)

            for exp in self.explosions:
                exp.draw(self.screen, cam_x, cam_y)

            for particle in self.particles:
                particle.draw(self.screen, cam_x, cam_y)

            player = self.players[self.current_player_idx]
            self.hud.draw(self.screen, self.players, self.current_player_idx,
                         self.wave_info, self.chapter_data["name"] if self.chapter_data else "", now,
                         self.has_controller)

            self.menu.draw_minimap(self.screen, self.level, self.players, self.enemies,
                                  SCREEN_WIDTH - 160, 10, 150)

            if self.state == "paused":
                self.menu.draw_pause_menu(self.screen)

        elif self.state == "game_over":
            self.menu.draw_game_over(self.screen, self.score,
                                    self.chapter_data["name"] if self.chapter_data else "",
                                    self.game_over_timer // FPS)
        elif self.state == "victory":
            self.menu.draw_victory(self.screen, self.total_score)

        pygame.display.flip()

    def run(self):
        pygame.mixer.init()
        while self.running:
            now = pygame.time.get_ticks()
            dt = self.clock.tick(FPS)

            self.handle_input(now)

            if self.state == "chapter_intro":
                self.chapter_intro_timer -= 1
                if self.chapter_intro_timer <= 0:
                    self.state = "playing"

            if self.state == "game_over":
                self.game_over_timer -= 1
                if self.game_over_timer <= 0:
                    self.state = "menu"

            if self.state == "playing":
                keys = pygame.key.get_pressed()
                mouse_pos = pygame.mouse.get_pos()
                mouse_buttons = pygame.mouse.get_pressed()

                self._update_controller_input()
                self._handle_continuous_shooting(now)
                self._handle_controller_shooting(now)
                self.update_entities(now, keys, mouse_pos, mouse_buttons, dt)
                self.update_waves(now)

                cam_x, cam_y = self.camera.get_offset()
                player = self.players[self.current_player_idx]
                self.camera.update(player.x, player.y)

                self.hud.update()

                self.check_game_over()

            self.draw(now)

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = Game()
    game.run()
