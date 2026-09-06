import pygame-ce
import random
import math
from settings import *


class Room:
    def __init__(self, x, y, w, h, room_type="normal"):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.room_type = room_type
        self.connected = False
        self.has_items = False
        self.cleared = False

    def center(self):
        return (self.x + self.w // 2, self.y + self.h // 2)

    def overlaps(self, other, margin=2):
        return (self.x - margin < other.x + other.w and
                self.x + self.w + margin > other.x and
                self.y - margin < other.y + other.h and
                self.y + self.h + margin > other.y)


class Level:
    def __init__(self, chapter_data, chapter_num):
        self.data = chapter_data
        self.chapter_num = chapter_num
        self.width = chapter_data["width"]
        self.height = chapter_data["height"]
        self.tiles = []
        self.rooms = []
        self.corridors = []
        self.safe_room_start = None
        self.safe_room_end = None
        self.spawn_point = (0, 0)
        self.safe_zone_tiles = set()
        self.generate()

    def generate(self):
        self.tiles = [[1 for _ in range(self.height)] for _ in range(self.width)]

        rooms = []
        attempts = 0
        target_rooms = random.randint(8, 12)

        while len(rooms) < target_rooms and attempts < 200:
            attempts += 1
            rw = random.randint(8, 16)
            rh = random.randint(8, 14)
            rx = random.randint(2, self.width - rw - 2)
            ry = random.randint(2, self.height - rh - 2)
            new_room = Room(rx, ry, rw, rh)

            overlaps = False
            for room in rooms:
                if new_room.overlaps(room, 3):
                    overlaps = True
                    break
            if not overlaps:
                rooms.append(new_room)

        if len(rooms) < 3:
            rooms = [
                Room(5, 5, 12, 10),
                Room(30, 5, 12, 10),
                Room(55, 25, 12, 10),
            ]

        rooms[0].room_type = "safe_start"
        rooms[-1].room_type = "safe_end"
        self.safe_room_start = rooms[0]
        self.safe_room_end = rooms[-1]

        for room in rooms:
            for x in range(room.x, room.x + room.w):
                for y in range(room.y, room.y + room.h):
                    if 0 <= x < self.width and 0 <= y < self.height:
                        self.tiles[x][y] = 2 if room.room_type.startswith("safe") else 0

        for i in range(len(rooms) - 1):
            self._connect_rooms(rooms[i], rooms[i + 1])

        for room in rooms:
            self.rooms.append(room)

        sc = rooms[0].center()
        self.spawn_point = (sc[0] * TILE_SIZE + TILE_SIZE // 2, sc[1] * TILE_SIZE + TILE_SIZE // 2)

    def _connect_rooms(self, room_a, room_b):
        ax, ay = room_a.center()
        bx, by = room_b.center()

        x, y = ax, ay
        while x != bx:
            if 0 <= x < self.width and 0 <= y < self.height:
                self.tiles[x][y] = 0
                if y + 1 < self.height:
                    self.tiles[x][y + 1] = 0
            x += 1 if bx > x else -1

        while y != by:
            if 0 <= x < self.width and 0 <= y < self.height:
                self.tiles[x][y] = 0
                if x + 1 < self.width:
                    self.tiles[x + 1][y] = 0
            y += 1 if by > y else -1

    def is_walkable(self, world_x, world_y):
        tx = int(world_x // TILE_SIZE)
        ty = int(world_y // TILE_SIZE)
        if 0 <= tx < self.width and 0 <= ty < self.height:
            return self.tiles[tx][ty] != 1
        return False

    def is_in_safe_zone(self, world_x, world_y):
        tx = int(world_x // TILE_SIZE)
        ty = int(world_y // TILE_SIZE)
        if 0 <= tx < self.width and 0 <= ty < self.height:
            return self.tiles[tx][ty] == 2
        return False

    def get_random_walkable_position(self, exclude_safe=False):
        attempts = 0
        while attempts < 500:
            x = random.randint(1, self.width - 2) * TILE_SIZE + random.randint(8, TILE_SIZE - 8)
            y = random.randint(1, self.height - 2) * TILE_SIZE + random.randint(8, TILE_SIZE - 8)
            if self.is_walkable(x, y):
                if exclude_safe and self.is_in_safe_zone(x, y):
                    attempts += 1
                    continue
                return (x, y)
            attempts += 1
        return (self.spawn_point[0] + 50, self.spawn_point[1])

    def get_random_enemy_spawn(self, player_pos, min_dist=300):
        for _ in range(50):
            pos = self.get_random_walkable_position(exclude_safe=True)
            dx = pos[0] - player_pos[0]
            dy = pos[1] - player_pos[1]
            if math.sqrt(dx * dx + dy * dy) >= min_dist:
                return pos
        return self.get_random_walkable_position(exclude_safe=True)

    def draw(self, surface, camera_x, camera_y):
        start_tx = max(0, int(camera_x // TILE_SIZE) - 1)
        end_tx = min(self.width, int((camera_x + SCREEN_WIDTH) // TILE_SIZE) + 2)
        start_ty = max(0, int(camera_y // TILE_SIZE) - 1)
        end_ty = min(self.height, int((camera_y + SCREEN_HEIGHT) // TILE_SIZE) + 2)

        for tx in range(start_tx, end_tx):
            for ty in range(start_ty, end_ty):
                sx = tx * TILE_SIZE - camera_x
                sy = ty * TILE_SIZE - camera_y
                tile = self.tiles[tx][ty]

                if tile == 1:
                    pygame.draw.rect(surface, COLORS["wall"], (int(sx), int(sy), TILE_SIZE, TILE_SIZE))
                    pygame.draw.rect(surface, COLORS["wall_top"], (int(sx), int(sy), TILE_SIZE, TILE_SIZE // 3))
                elif tile == 0:
                    c = COLORS["floor_dark"] if (tx + ty) % 2 == 0 else COLORS["floor_light"]
                    pygame.draw.rect(surface, c, (int(sx), int(sy), TILE_SIZE, TILE_SIZE))
                elif tile == 2:
                    pygame.draw.rect(surface, COLORS["safe_green"], (int(sx), int(sy), TILE_SIZE, TILE_SIZE))
                    pygame.draw.rect(surface, COLORS["dark_green"], (int(sx), int(sy), TILE_SIZE, TILE_SIZE), 1)
                elif tile == 3:
                    pygame.draw.rect(surface, COLORS["door"], (int(sx), int(sy), TILE_SIZE, TILE_SIZE))

        for room in self.rooms:
            if room.room_type == "safe_start" or room.room_type == "safe_end":
                cx, cy = room.center()
                sx = cx * TILE_SIZE - camera_x
                sy = cy * TILE_SIZE - camera_y - 20
                label = "SAFE ROOM" if room.room_type == "safe_end" else "SAFE ROOM"
                font = pygame.font.SysFont(None, 20)
                surf = font.render(label, True, COLORS["safe_green"])
                surface.blit(surf, (int(sx) - surf.get_width() // 2, int(sy)))
