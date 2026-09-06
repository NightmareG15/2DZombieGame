import pygame-ce
import math
import random
import time
from settings import *


class Bullet:
    def __init__(self, x, y, angle, weapon_data, owner_id=0, is_crit=False):
        self.x = x
        self.y = y
        self.angle = angle
        self.speed = weapon_data["bullet_speed"]
        self.damage = weapon_data["damage"] * (3 if is_crit else 1)
        self.color = (255, 50, 50) if is_crit else weapon_data["bullet_color"]
        self.size = weapon_data["size"]
        self.vx = math.cos(math.radians(angle)) * self.speed
        self.vy = math.sin(math.radians(angle)) * self.speed
        self.alive = True
        self.owner_id = owner_id
        self.is_crit = is_crit
        self.explosive = weapon_data.get("explosive", False)
        self.explosion_radius = weapon_data.get("explosion_radius", 0)
        self.lifetime = 120
        self.trail = []

    def update(self):
        self.trail.append((self.x, self.y))
        if len(self.trail) > 5:
            self.trail.pop(0)
        self.x += self.vx
        self.y += self.vy
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.alive = False

    def draw(self, surface, camera_x, camera_y):
        sx = self.x - camera_x
        sy = self.y - camera_y
        if -20 < sx < SCREEN_WIDTH + 20 and -20 < sy < SCREEN_HEIGHT + 20:
            for i, (tx, ty) in enumerate(self.trail):
                alpha = (i + 1) / len(self.trail) if self.trail else 1
                ts = max(1, int(self.size * alpha * 0.5))
                tc = tuple(int(c * alpha * 0.6) for c in self.color)
                pygame.draw.circle(surface, tc, (int(tx - camera_x), int(ty - camera_y)), ts)
            pygame.draw.circle(surface, self.color, (int(sx), int(sy)), self.size)
            if self.is_crit:
                pygame.draw.circle(surface, COLORS["yellow"], (int(sx), int(sy)), self.size + 2, 1)


class Explosion:
    def __init__(self, x, y, radius, color=(255, 150, 30)):
        self.x = x
        self.y = y
        self.radius = radius
        self.max_radius = radius
        self.color = color
        self.alive = True
        self.timer = 20
        self.damage_applied = False

    def update(self):
        self.timer -= 1
        self.radius = self.max_radius * (1 - self.timer / 20)
        if self.timer <= 0:
            self.alive = False

    def draw(self, surface, camera_x, camera_y):
        sx = self.x - camera_x
        sy = self.y - camera_y
        if -self.max_radius < sx < SCREEN_WIDTH + self.max_radius:
            if -self.max_radius < sy < SCREEN_HEIGHT + self.max_radius:
                r = int(self.radius)
                alpha = self.timer / 20
                c = tuple(int(ch * alpha) for ch in self.color)
                if r > 0:
                    pygame.draw.circle(surface, c, (int(sx), int(sy)), r)
                    c2 = (min(255, c[0] + 60), min(255, c[1] + 30), c[2])
                    inner = max(1, r // 2)
                    pygame.draw.circle(surface, c2, (int(sx), int(sy)), inner)


class Particle:
    def __init__(self, x, y, vx, vy, color, size=3, lifetime=30, gravity=0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.size = size
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.gravity = gravity

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        self.vx *= 0.98
        self.vy *= 0.98
        self.lifetime -= 1
        return self.lifetime > 0

    def draw(self, surface, camera_x, camera_y):
        sx = self.x - camera_x
        sy = self.y - camera_y
        if -5 < sx < SCREEN_WIDTH + 5 and -5 < sy < SCREEN_HEIGHT + 5:
            alpha = self.lifetime / self.max_lifetime
            s = max(1, int(self.size * alpha))
            c = tuple(int(ch * alpha) for ch in self.color)
            pygame.draw.circle(surface, c, (int(sx), int(sy)), s)


class Player:
    def __init__(self, char_id, x, y, player_id=0):
        data = CHARACTER_DATA[char_id]
        self.char_id = char_id
        self.player_id = player_id
        self.x = x
        self.y = y
        self.hp = data["hp"]
        self.max_hp = data["hp"]
        self.speed = data["speed"]
        self.color = data["color"]
        self.name = data["name"]
        self.size = 14
        self.angle = 0
        self.alive = True
        self.incapacitated = False
        self.bleeding = False
        self.bleed_timer = 0

        self.weapons = []
        self.current_weapon_idx = 0
        self.ammo = {}
        self.reserve_ammo = {}

        self.ability_name = data["ability"]
        self.ability_cooldown = data["ability_cooldown"]
        self.ability_last_used = 0
        self.ability_active = False
        self.ability_timer = 0

        self.speed_boost = 1.0
        self.speed_boost_end = 0

        self.shoot_cooldown = 0
        self.kills = 0
        self.score = 0
        self.damage_taken = 0

        self.invulnerable_timer = 0
        self.hit_flash = 0

        self.vomit_timer = 0
        self.tongue_attached = False
        self.tongue_source = None

        self.medkits = 0
        self.max_medkits = 3

    def give_starting_weapon(self):
        self.add_weapon("pistol")
        self.reserve_ammo["pistol"] = 120

    def add_weapon(self, weapon_id):
        if len(self.weapons) < 3:
            if weapon_id not in self.weapons:
                self.weapons.append(weapon_id)
                self.ammo[weapon_id] = WEAPON_DATA[weapon_id]["magazine"]
                self.reserve_ammo[weapon_id] = WEAPON_DATA[weapon_id].get("max_ammo", 60)
                if len(self.weapons) == 1:
                    self.current_weapon_idx = 0
                return True
        return False

    def switch_weapon(self, direction):
        if len(self.weapons) > 1:
            self.current_weapon_idx = (self.current_weapon_idx + direction) % len(self.weapons)

    @property
    def current_weapon(self):
        if self.weapons:
            return self.weapons[self.current_weapon_idx]
        return None

    def take_damage(self, amount):
        if self.invulnerable_timer > 0 or not self.alive:
            return
        self.hp -= amount
        self.damage_taken += amount
        self.hit_flash = 8
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        elif self.hp <= 25:
            self.bleeding = True

    def heal(self, amount):
        if not self.alive and not self.incapacitated:
            return
        self.hp = min(self.max_hp, self.hp + amount)
        if self.hp > 25:
            self.bleeding = False

    def use_ability(self, now):
        if now - self.ability_last_used < self.ability_cooldown:
            return False
        self.ability_last_used = now

        if self.char_id == "chef":
            self.ability_active = True
            self.ability_timer = 500
            return True
        elif self.char_id == "carlos":
            self.heal(30)
            return True
        elif self.char_id == "raquel":
            self.speed_boost = 2.0
            self.speed_boost_end = now + 4000
            return True
        elif self.char_id == "nicolas":
            self.ability_active = True
            self.ability_timer = 5000
            return True
        return False

    def get_ability_cooldown_percent(self, now):
        elapsed = now - self.ability_last_used
        return min(1.0, elapsed / self.ability_cooldown) if self.ability_cooldown > 0 else 1.0

    def use_medkit(self):
        if self.medkits > 0 and self.alive:
            self.medkits -= 1
            self.heal(40)
            return True
        return False

    def add_medkit(self):
        if self.medkits < self.max_medkits:
            self.medkits += 1
            return True
        return False

    def _auto_reload(self):
        if not self.current_weapon:
            return
        wpn = self.current_weapon
        if self.ammo.get(wpn, 0) < WEAPON_DATA[wpn]["magazine"]:
            needed = WEAPON_DATA[wpn]["magazine"] - self.ammo.get(wpn, 0)
            available = min(needed, self.reserve_ammo.get(wpn, 0))
            if available > 0:
                self.ammo[wpn] += available
                self.reserve_ammo[wpn] -= available

    def update(self, now, keys, mouse_pos, mouse_buttons, camera_x, camera_y, dt, level=None,
               controller_move=None, controller_aim=None):
        if not self.alive:
            return

        if self.invulnerable_timer > 0:
            self.invulnerable_timer -= dt
        if self.hit_flash > 0:
            self.hit_flash -= 1
        if self.vomit_timer > 0:
            self.vomit_timer -= dt

        if now > self.speed_boost_end:
            self.speed_boost = 1.0

        if self.tongue_attached:
            return

        dx, dy = 0, 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1

        if controller_move:
            cmx, cmy = controller_move
            deadzone = 0.15
            if abs(cmx) > deadzone:
                dx = cmx
            if abs(cmy) > deadzone:
                dy = cmy

        if dx != 0 or dy != 0:
            length = math.sqrt(dx * dx + dy * dy)
            if length > 1:
                dx /= length
                dy /= length
            spd = self.speed * self.speed_boost
            new_x = self.x + dx * spd
            new_y = self.y + dy * spd
            if level:
                can_x = level.is_walkable(new_x, self.y)
                can_y = level.is_walkable(self.x, new_y)
                can_xy = level.is_walkable(new_x, new_y)
                if can_xy:
                    self.x = new_x
                    self.y = new_y
                elif can_x:
                    self.x = new_x
                elif can_y:
                    self.y = new_y
            else:
                self.x = new_x
                self.y = new_y

        world_x = mouse_pos[0] + camera_x
        world_y = mouse_pos[1] + camera_y
        self.angle = math.degrees(math.atan2(world_y - self.y, world_x - self.x))

        if controller_aim:
            cax, cay = controller_aim
            deadzone = 0.2
            if abs(cax) > deadzone or abs(cay) > deadzone:
                self.angle = math.degrees(math.atan2(cay, cax))

    def shoot(self, now):
        if not self.alive or not self.current_weapon:
            return []
        wep = WEAPON_DATA[self.current_weapon]
        if now - self.shoot_cooldown < wep["fire_rate"]:
            return []
        if self.ammo.get(self.current_weapon, 0) <= 0:
            self._auto_reload()
            return []

        self.shoot_cooldown = now
        self.ammo[self.current_weapon] -= 1

        bullets = []
        pellets = wep.get("pellets", 1)
        is_crit = False
        if self.char_id == "nicolas" and self.ability_active:
            is_crit = random.random() < 0.3

        if self.char_id == "chef" and self.ability_active:
            for p in range(pellets):
                spread = random.uniform(-wep["spread"], wep["spread"])
                for offset in [-8, 8]:
                    ox = offset * math.cos(math.radians(self.angle + 90))
                    oy = offset * math.sin(math.radians(self.angle + 90))
                    b = Bullet(self.x + ox, self.y + oy, self.angle + spread, wep, self.player_id, is_crit)
                    bullets.append(b)
        else:
            for p in range(pellets):
                spread = random.uniform(-wep["spread"], wep["spread"])
                b = Bullet(self.x, self.y, self.angle + spread, wep, self.player_id, is_crit)
                bullets.append(b)

        return bullets

    def draw(self, surface, camera_x, camera_y):
        if not self.alive:
            return
        sx = self.x - camera_x
        sy = self.y - camera_y
        if -30 > sx or sx > SCREEN_WIDTH + 30 or -30 > sy or sy > SCREEN_HEIGHT + 30:
            return

        color = self.color
        if self.hit_flash > 0:
            color = COLORS["white"]
        elif self.vomit_timer > 0:
            color = (150, 200, 50)
        elif self.bleeding:
            pulse = abs(math.sin(time.time() * 5)) * 0.3
            color = tuple(max(0, int(c * (1 - pulse))) for c in self.color)

        pygame.draw.circle(surface, color, (int(sx), int(sy)), self.size)
        pygame.draw.circle(surface, (min(255, color[0] + 40), min(255, color[1] + 40), min(255, color[2] + 40)),
                          (int(sx) - 3, int(sy) - 3), 4)

        gun_len = 18
        gun_x = sx + math.cos(math.radians(self.angle)) * gun_len
        gun_y = sy + math.sin(math.radians(self.angle)) * gun_len
        pygame.draw.line(surface, COLORS["gray"], (int(sx), int(sy)), (int(gun_x), int(gun_y)), 3)

        if self.tongue_attached:
            if self.tongue_source:
                tsx = self.tongue_source.x - camera_x
                tsy = self.tongue_source.y - camera_y
                pygame.draw.line(surface, COLORS["pink"], (int(tsx), int(tsy)), (int(sx), int(sy)), 3)

        if self.speed_boost > 1.0:
            pygame.draw.circle(surface, COLORS["cyan"], (int(sx), int(sy)), self.size + 4, 1)

        if self.ability_active and self.char_id == "chef":
            pygame.draw.circle(surface, COLORS["yellow"], (int(sx), int(sy)), self.size + 6, 2)

        if self.player_id != 0:
            name_font = pygame.font.SysFont(None, 16)
            name_surf = name_font.render(self.name, True, COLORS["white"])
            surface.blit(name_surf, (int(sx) - name_surf.get_width() // 2, int(sy) - self.size - 16))

    def draw_health_bar(self, surface, camera_x, camera_y):
        if not self.alive:
            return
        sx = self.x - camera_x
        sy = self.y - camera_y
        bar_w = 30
        bar_h = 4
        bx = int(sx) - bar_w // 2
        by = int(sy) + self.size + 6
        pygame.draw.rect(surface, COLORS["dark_gray"], (bx, by, bar_w, bar_h))
        fill = max(0, self.hp / self.max_hp)
        hc = COLORS["red"] if fill < 0.3 else COLORS["yellow"] if fill < 0.6 else COLORS["green"]
        pygame.draw.rect(surface, hc, (bx, by, int(bar_w * fill), bar_h))


class Enemy:
    def __init__(self, enemy_type, x, y, wave_num=1):
        data = ENEMY_DATA[enemy_type]
        self.type = enemy_type
        self.x = x
        self.y = y
        self.hp = data["hp"] + (wave_num - 1) * 3
        self.max_hp = self.hp
        self.damage = data["damage"]
        self.speed = data["speed"]
        self.color = data["color"]
        self.size = data["size"]
        self.attack_range = data["attack_range"]
        self.attack_cooldown = data["attack_cooldown"]
        self.last_attack = 0
        self.alive = True
        self.points = data["points"]
        self.state = "chase"
        self.target = None
        self.angle = 0
        self.hit_flash = 0

        self.explode_on_death = data.get("explode_on_death", False)
        self.explode_radius = data.get("explode_radius", 0)
        self.attracts_horde = data.get("attracts_horde", False)
        self.vomit_chance = data.get("vomit_chance", 0)

        self.tongue_range = data.get("tongue_range", 0)
        self.tongue_damage = data.get("tongue_damage", 0)
        self.pull_speed = data.get("pull_speed", 0)
        self.tongue_active = False
        self.tongue_target = None
        self.tongue_length = 0

        self.pounce_speed = data.get("pounce_speed", 0)
        self.pounce_damage = data.get("pounce_damage", 0)
        self.pounce_stun = data.get("pounce_stun", 0)
        self.pouncing = False
        self.pounce_target = None
        self.pounce_pos = None

        self.charge_speed = data.get("charge_speed", 0)
        self.charge_damage = data.get("charge_damage", 0)
        self.charging = False
        self.charge_dir = (0, 0)

        self.wander_speed = data.get("wander_speed", 0)
        self.frightened_range = data.get("frightened_range", 0)
        self.cry_range = data.get("cry_range", 0)
        self.is_crying = True
        self.wander_angle = random.uniform(0, 360)
        self.wander_timer = 0

    def _try_move(self, dx, dy, speed, level=None):
        if speed == 0:
            return
        new_x = self.x + dx * speed
        new_y = self.y + dy * speed
        if level:
            can_x = level.is_walkable(new_x, self.y)
            can_y = level.is_walkable(self.x, new_y)
            can_xy = level.is_walkable(new_x, new_y)
            if can_xy:
                self.x = new_x
                self.y = new_y
            elif can_x:
                self.x = new_x
            elif can_y:
                self.y = new_y
        else:
            self.x = new_x
            self.y = new_y

    def _find_path_direction(self, target_x, target_y, level):
        if level is None:
            dx = target_x - self.x
            dy = target_y - self.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 0:
                return dx / dist, dy / dist
            return 0, 0

        sx = int(self.x // TILE_SIZE)
        sy = int(self.y // TILE_SIZE)
        gx = int(target_x // TILE_SIZE)
        gy = int(target_y // TILE_SIZE)

        sx = max(0, min(sx, level.width - 1))
        sy = max(0, min(sy, level.height - 1))
        gx = max(0, min(gx, level.width - 1))
        gy = max(0, min(gy, level.height - 1))

        if sx == gx and sy == gy:
            dx = target_x - self.x
            dy = target_y - self.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 0:
                return dx / dist, dy / dist
            return 0, 0

        from collections import deque
        visited = set()
        parent = {}
        queue = deque()
        queue.append((sx, sy))
        visited.add((sx, sy))

        found = False
        max_steps = 30
        steps = 0

        while queue and steps < max_steps:
            cx, cy = queue.popleft()
            steps += 1

            if cx == gx and cy == gy:
                found = True
                break

            for ndx, ndy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = cx + ndx, cy + ndy
                if 0 <= nx < level.width and 0 <= ny < level.height:
                    if (nx, ny) not in visited and level.tiles[nx][ny] != 1:
                        visited.add((nx, ny))
                        parent[(nx, ny)] = (cx, cy)
                        queue.append((nx, ny))

        if not found:
            dx = target_x - self.x
            dy = target_y - self.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 0:
                return dx / dist, dy / dist
            return 0, 0

        node = (gx, gy)
        while parent.get(node) != (sx, sy):
            node = parent[node]

        next_tx = node[0]
        next_ty = node[1]
        next_x = next_tx * TILE_SIZE + TILE_SIZE // 2
        next_y = next_ty * TILE_SIZE + TILE_SIZE // 2

        dx = next_x - self.x
        dy = next_y - self.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 0:
            return dx / dist, dy / dist
        return 0, 0

    def find_nearest_player(self, players, max_dist=9999):
        nearest = None
        min_dist = max_dist
        for p in players:
            if p.alive and not p.incapacitated:
                dx = p.x - self.x
                dy = p.y - self.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < min_dist:
                    min_dist = dist
                    nearest = p
        return nearest, min_dist

    def update(self, now, players, enemies, game):
        if not self.alive:
            return
        if self.hit_flash > 0:
            self.hit_flash -= 1

        if self.type == "witch":
            self._update_witch(now, players, game)
            return

        if self.type == "tank":
            self._update_tank(now, players, game)
            return

        if self.type == "smoker":
            self._update_smoker(now, players, game)
            return

        if self.type == "hunter":
            self._update_hunter(now, players, game)
            return

        if self.type == "boomer":
            self._update_boomer(now, players, game)
            return

        self._update_common(now, players, game)

    def _update_common(self, now, players, game):
        level = game.level
        target, dist = self.find_nearest_player(players, 400)
        if target:
            pdx, pdy = self._find_path_direction(target.x, target.y, level)
            self._try_move(pdx, pdy, self.speed, level)
            self.angle = math.degrees(math.atan2(target.y - self.y, target.x - self.x))
            if dist <= self.attack_range and now - self.last_attack >= self.attack_cooldown:
                self.last_attack = now
                target.take_damage(self.damage)
                game.spawn_particles(target.x, target.y, COLORS["blood"], 5)
        else:
            self.wander_timer -= 1
            if self.wander_timer <= 0:
                self.wander_angle = random.uniform(0, 360)
                self.wander_timer = random.randint(30, 90)
            self._try_move(math.cos(math.radians(self.wander_angle)),
                          math.sin(math.radians(self.wander_angle)),
                          self.speed * 0.3, level)

    def _update_boomer(self, now, players, game):
        level = game.level
        target, dist = self.find_nearest_player(players, 350)
        if target:
            pdx, pdy = self._find_path_direction(target.x, target.y, level)
            self._try_move(pdx, pdy, self.speed, level)
            self.angle = math.degrees(math.atan2(target.y - self.y, target.x - self.x))
            if dist <= self.attack_range and now - self.last_attack >= self.attack_cooldown:
                self.last_attack = now
                if random.random() < self.vomit_chance:
                    target.vomit_timer = 3000
                    game.spawn_particles(target.x, target.y, (100, 200, 50), 10)
        else:
            self.wander_timer -= 1
            if self.wander_timer <= 0:
                self.wander_angle = random.uniform(0, 360)
                self.wander_timer = random.randint(30, 90)
            self._try_move(math.cos(math.radians(self.wander_angle)),
                          math.sin(math.radians(self.wander_angle)),
                          self.speed * 0.3, level)

    def _update_smoker(self, now, players, game):
        level = game.level
        if self.tongue_active and self.tongue_target:
            target = self.tongue_target
            if target.alive and not target.incapacitated:
                dx = self.x - target.x
                dy = self.y - target.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 0:
                    target.x += (dx / dist) * self.pull_speed
                    target.y += (dy / dist) * self.pull_speed
                target.take_damage(self.tongue_damage * 0.016)
                self.tongue_length = dist
                if dist > self.tongue_range:
                    self.tongue_active = False
                    self.tongue_target = None
            else:
                self.tongue_active = False
                self.tongue_target = None
        else:
            target, dist = self.find_nearest_player(players, self.tongue_range)
            if target and now - self.last_attack >= self.attack_cooldown:
                self.last_attack = now
                self.tongue_active = True
                self.tongue_target = target
                self.tongue_length = dist
            elif target:
                if dist > self.attack_range:
                    pdx, pdy = self._find_path_direction(target.x, target.y, level)
                    self._try_move(pdx, pdy, self.speed, level)
                self.angle = math.degrees(math.atan2(target.y - self.y, target.x - self.x))

    def _update_hunter(self, now, players, game):
        level = game.level
        if self.pouncing and self.pounce_target:
            target = self.pounce_target
            dx = target.x - self.x
            dy = target.y - self.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 20:
                self.pouncing = False
                target.take_damage(self.pounce_damage)
                target.invulnerable_timer = self.pounce_stun
                game.spawn_particles(target.x, target.y, COLORS["red"], 8)
                self.pounce_target = None
            elif dist > 0:
                pdx, pdy = self._find_path_direction(target.x, target.y, level)
                self._try_move(pdx, pdy, self.pounce_speed, level)
                self.angle = math.degrees(math.atan2(dy, dx))
        else:
            target, dist = self.find_nearest_player(players, self.attack_range)
            if target and now - self.last_attack >= self.attack_cooldown:
                self.last_attack = now
                self.pouncing = True
                self.pounce_target = target
            elif target:
                if dist > 50:
                    pdx, pdy = self._find_path_direction(target.x, target.y, level)
                    self._try_move(pdx, pdy, self.speed, level)
                self.angle = math.degrees(math.atan2(target.y - self.y, target.x - self.x))

    def _update_tank(self, now, players, game):
        level = game.level
        if self.charging:
            self._try_move(self.charge_dir[0], self.charge_dir[1], self.charge_speed, level)
            for p in players:
                if p.alive:
                    dx = p.x - self.x
                    dy = p.y - self.y
                    if math.sqrt(dx * dx + dy * dy) < self.size + p.size:
                        p.take_damage(self.charge_damage)
                        game.spawn_particles(p.x, p.y, COLORS["red"], 10)
            self.charging = False
        else:
            target, dist = self.find_nearest_player(players, 500)
            if target:
                pdx, pdy = self._find_path_direction(target.x, target.y, level)
                self._try_move(pdx, pdy, self.speed, level)
                self.angle = math.degrees(math.atan2(target.y - self.y, target.x - self.x))
                if dist <= self.attack_range and now - self.last_attack >= self.attack_cooldown:
                    self.last_attack = now
                    if dist > 0:
                        self.charging = True
                        self.charge_dir = (pdx, pdy)
                        game.spawn_particles(self.x, self.y, COLORS["orange"], 5)

    def _update_witch(self, now, players, game):
        level = game.level
        if self.is_crying:
            target, dist = self.find_nearest_player(players, self.frightened_range)
            if target and dist < self.frightened_range * 0.5:
                self.is_crying = False
                self.speed = 2.5
                self.target = target
                game.spawn_particles(self.x, self.y, COLORS["pink"], 15)
            elif target:
                self.angle = math.degrees(math.atan2(target.y - self.y, target.x - self.x))
        else:
            if self.target and self.target.alive:
                dx = self.target.x - self.x
                dy = self.target.y - self.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 0:
                    self._try_move(dx / dist, dy / dist, self.speed, level)
                self.angle = math.degrees(math.atan2(dy, dx))
                if dist <= self.attack_range and now - self.last_attack >= self.attack_cooldown:
                    self.last_attack = now
                    self.target.take_damage(self.damage)
                    game.spawn_particles(self.target.x, self.target.y, COLORS["blood"], 12)
            else:
                self.is_crying = True
                self.speed = self.wander_speed

    def take_damage(self, amount):
        self.hp -= amount
        self.hit_flash = 6
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    def draw(self, surface, camera_x, camera_y):
        if not self.alive:
            return
        sx = self.x - camera_x
        sy = self.y - camera_y
        if -40 > sx or sx > SCREEN_WIDTH + 40 or -40 > sy or sy > SCREEN_HEIGHT + 40:
            return

        color = self.color
        if self.hit_flash > 0:
            color = COLORS["white"]

        if self.type == "tank":
            pygame.draw.rect(surface, color, (int(sx) - self.size, int(sy) - self.size,
                                             self.size * 2, self.size * 2))
            pygame.draw.rect(surface, COLORS["dark_gray"],
                           (int(sx) - self.size, int(sy) - self.size, self.size * 2, self.size * 2), 2)
            if self.charging:
                pygame.draw.circle(surface, COLORS["orange"], (int(sx), int(sy)), self.size + 10, 2)
        elif self.type == "witch":
            pygame.draw.circle(surface, color, (int(sx), int(sy)), self.size)
            pygame.draw.circle(surface, COLORS["dark_red"], (int(sx), int(sy)), self.size, 2)
            if not self.is_crying:
                for i in range(3):
                    angle = self.angle + (i - 1) * 30
                    lx = sx + math.cos(math.radians(angle)) * 15
                    ly = sy + math.sin(math.radians(angle)) * 15
                    pygame.draw.line(surface, COLORS["dark_red"], (int(sx), int(sy)), (int(lx), int(ly)), 2)
        elif self.type == "boomer":
            pygame.draw.circle(surface, color, (int(sx), int(sy)), self.size)
            pygame.draw.circle(surface, COLORS["dark_green"], (int(sx), int(sy)), self.size, 2)
            for i in range(4):
                angle = i * 90 + time.time() * 50
                bx = sx + math.cos(math.radians(angle)) * (self.size + 5)
                by = sy + math.sin(math.radians(angle)) * (self.size + 5)
                pygame.draw.circle(surface, COLORS["dark_green"], (int(bx), int(by)), 4)
        elif self.type == "smoker":
            pygame.draw.circle(surface, color, (int(sx), int(sy)), self.size)
            if self.tongue_active and self.tongue_target:
                tx = self.tongue_target.x - camera_x
                ty = self.tongue_target.y - camera_y
                points = []
                segments = 10
                for i in range(segments + 1):
                    t = i / segments
                    px = sx + (tx - sx) * t + math.sin(t * 6 + time.time() * 8) * 5
                    py = sy + (ty - sy) * t + math.cos(t * 6 + time.time() * 8) * 5
                    points.append((int(px), int(py)))
                if len(points) > 1:
                    pygame.draw.lines(surface, COLORS["pink"], False, points, 3)
        elif self.type == "hunter":
            pygame.draw.circle(surface, color, (int(sx), int(sy)), self.size)
            if self.pouncing:
                pygame.draw.circle(surface, COLORS["red"], (int(sx), int(sy)), self.size + 5, 2)
                pygame.draw.line(surface, COLORS["red"], (int(sx), int(sy)),
                               (int(self.pounce_target.x - camera_x), int(self.pounce_target.y - camera_y)), 1)
        else:
            pygame.draw.circle(surface, color, (int(sx), int(sy)), self.size)
            pygame.draw.circle(surface, COLORS["dark_gray"], (int(sx), int(sy)), self.size, 1)

        if self.hp < self.max_hp:
            bar_w = self.size * 2
            bar_h = 3
            bx = int(sx) - bar_w // 2
            by = int(sy) - self.size - 8
            pygame.draw.rect(surface, COLORS["dark_gray"], (bx, by, bar_w, bar_h))
            fill = max(0, self.hp / self.max_hp)
            pygame.draw.rect(surface, COLORS["red"], (bx, by, int(bar_w * fill), bar_h))


class Item:
    def __init__(self, item_type, x, y):
        data = ITEM_DATA[item_type]
        self.type = item_type
        self.x = x
        self.y = y
        self.color = data["color"]
        self.size = data["size"]
        self.alive = True
        self.bob_offset = random.uniform(0, 6.28)

    def apply(self, player):
        data = ITEM_DATA[self.type]
        if self.type == "medkit":
            if not player.add_medkit():
                player.heal(data["heal"])
        elif self.type == "pills":
            player.heal(data["heal"])
        elif self.type == "ammo":
            if player.current_weapon:
                wpn = player.current_weapon
                max_ammo = WEAPON_DATA[wpn].get("max_ammo", 60)
                player.reserve_ammo[wpn] = min(max_ammo,
                    player.reserve_ammo.get(wpn, 0) + data["ammo_amount"])
        elif self.type == "adrenaline":
            player.speed_boost = data["speed_boost"]
            player.speed_boost_end = pygame.time.get_ticks() + data["duration"]
        elif self.type.startswith("weapon_"):
            weapon_id = data["weapon_id"]
            if player.add_weapon(weapon_id):
                pass
            else:
                if player.current_weapon:
                    wpn = player.current_weapon
                    max_ammo = WEAPON_DATA[wpn].get("max_ammo", 60)
                    player.reserve_ammo[wpn] = min(max_ammo,
                        player.reserve_ammo.get(wpn, 0) + WEAPON_DATA[wpn]["magazine"])
        self.alive = False

    def draw(self, surface, camera_x, camera_y):
        if not self.alive:
            return
        sx = self.x - camera_x
        sy = self.y - camera_y
        if -20 > sx or sx > SCREEN_WIDTH + 20 or -20 > sy or sy > SCREEN_HEIGHT + 20:
            return
        bob = math.sin(time.time() * 3 + self.bob_offset) * 3
        sy_draw = sy + bob
        pygame.draw.rect(surface, self.color,
                        (int(sx) - self.size, int(sy_draw) - self.size, self.size * 2, self.size * 2))
        pygame.draw.rect(surface, COLORS["white"],
                        (int(sx) - self.size, int(sy_draw) - self.size, self.size * 2, self.size * 2), 1)

        glow = abs(math.sin(time.time() * 2 + self.bob_offset)) * 0.3
        gc = tuple(min(255, int(c + c * glow)) for c in self.color)
        pygame.draw.circle(surface, gc, (int(sx), int(sy_draw)), self.size + 4, 1)


class AIPlayer:
    def __init__(self, player):
        self.player = player
        self.target_pos = None
        self.move_timer = 0
        self.shoot_timer = 0

    def update(self, now, enemies, game):
        p = self.player
        if not p.alive or p.incapacitated:
            return
        level = game.level

        nearest_enemy = None
        min_dist = 400
        for e in enemies:
            if e.alive:
                dx = e.x - p.x
                dy = e.y - p.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < min_dist:
                    min_dist = dist
                    nearest_enemy = e

        if nearest_enemy:
            dx = nearest_enemy.x - p.x
            dy = nearest_enemy.y - p.y
            dist = math.sqrt(dx * dx + dy * dy)
            p.angle = math.degrees(math.atan2(dy, dx))

            if dist > 100:
                move_x = dx / dist * p.speed * 0.7
                move_y = dy / dist * p.speed * 0.7
                if dist > 250:
                    new_x = p.x + move_x
                    new_y = p.y + move_y
                    if level:
                        if level.is_walkable(new_x, p.y):
                            p.x = new_x
                        if level.is_walkable(p.x, new_y):
                            p.y = new_y
                    else:
                        p.x = new_x
                        p.y = new_y
                elif dist < 80:
                    new_x = p.x - move_x * 0.5
                    new_y = p.y - move_y * 0.5
                    if level:
                        if level.is_walkable(new_x, p.y):
                            p.x = new_x
                        if level.is_walkable(p.x, new_y):
                            p.y = new_y
                    else:
                        p.x = new_x
                        p.y = new_y
                else:
                    perp_x = -dy / dist * p.speed * 0.5
                    perp_y = dx / dist * p.speed * 0.5
                    if now % 2000 < 1000:
                        new_x = p.x + perp_x
                        new_y = p.y + perp_y
                    else:
                        new_x = p.x - perp_x
                        new_y = p.y - perp_y
                    if level:
                        if level.is_walkable(new_x, p.y):
                            p.x = new_x
                        if level.is_walkable(p.x, new_y):
                            p.y = new_y
                    else:
                        p.x = new_x
                        p.y = new_y

            if dist < 300 and now - self.shoot_timer > 200:
                self.shoot_timer = now
                bullets = p.shoot(now)
                game.bullets.extend(bullets)
        else:
            self.move_timer -= 1
            if self.move_timer <= 0:
                self.move_timer = random.randint(60, 120)
                self.target_pos = (p.x + random.uniform(-200, 200), p.y + random.uniform(-200, 200))
            if self.target_pos:
                dx = self.target_pos[0] - p.x
                dy = self.target_pos[1] - p.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 10:
                    new_x = p.x + (dx / dist) * p.speed * 0.5
                    new_y = p.y + (dy / dist) * p.speed * 0.5
                    if level:
                        if level.is_walkable(new_x, p.y):
                            p.x = new_x
                        if level.is_walkable(p.x, new_y):
                            p.y = new_y
                    else:
                        p.x = new_x
                        p.y = new_y

        if p.hp < p.max_hp * 0.5:
            if p.medkits > 0:
                p.use_medkit()
            else:
                for item in game.items:
                    if item.alive:
                        dx = item.x - p.x
                        dy = item.y - p.y
                        if math.sqrt(dx * dx + dy * dy) < 50:
                            if item.type in ("medkit", "pills", "weapon_shotgun", "weapon_smg",
                                              "weapon_rifle", "weapon_sniper", "weapon_grenade"):
                                item.apply(p)
                                break
