"""
Snake Game — Python 图形界面版 (Pygame)
=========================================
"""
import pygame
import random
import sys
import os
import json
import math
import array
from collections import deque

# ═══════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════
WINDOW_WIDTH = 780
WINDOW_HEIGHT = 780
WINDOW_PVP_WIDTH = 800
WINDOW_PVP_HEIGHT = 800
SETTINGS_FILE = "settings.json"
HIGH_SCORE_FILE = "highscore.txt"

GRID_CLASSIC = 20
GRID_PVP = 40
GRID_PVP_MIN = 20
GRID_PVP_MAX = 40

BATTLE_LIVES_MIN = 1
BATTLE_LIVES_MAX = 10
BATTLE_LIVES_DEFAULT = 3
BULLET_COOLDOWN = 5   # 发射冷却帧数


# 速度预设
SPEED_PRESETS = [
    ("蜗牛", 5),
    ("慢速", 8),
    ("中速", 12),
    ("快速", 16),
    ("极速", 22),
]

# 颜色
BLACK       = (0, 0, 0)
WHITE       = (255, 255, 255)
GREEN       = (72, 200, 72)
RED         = (225, 75, 75)
BLUE        = (65, 140, 225)
BLUE_BRIGHT = (115, 185, 245)
GRAY        = (140, 148, 158)
GRAY_DARK   = (85, 92, 100)
DARK_GREEN  = (48, 155, 58)
DARK_GREEN2 = (28, 90, 36)
ORANGE      = (235, 155, 55)
PURPLE      = (155, 85, 210)
DARK_BG     = (18, 18, 28)
GRID_COLOR  = (34, 36, 46)
PANEL_BG    = (22, 22, 36)
BORDER_COLOR = (48, 155, 65)

# 中文字体 — 优先用打包内置字体, 再尝试系统字体
def _get_fonts_dir():
    # PyInstaller 打包后字体在 sys._MEIPASS/fonts 下
    if getattr(sys, 'frozen', False):
        bundled = os.path.join(sys._MEIPASS, "fonts")
        if os.path.isdir(bundled):
            return bundled
    return None

_SYSTEM_FONTS = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/NotoSansSC-VF.ttf",
    "C:/Windows/Fonts/SIMLI.TTF",
    "C:/Windows/Fonts/STSONG.TTF",
]

def _get_chinese_font(size):
    fdir = _get_fonts_dir()
    if fdir:
        for name in os.listdir(fdir):
            path = os.path.join(fdir, name)
            if os.path.isfile(path):
                return pygame.font.Font(path, size)
    for path in _SYSTEM_FONTS:
        if os.path.exists(path):
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


# ═══════════════════════════════════════════════════════════════
# 音效生成 (程序化合成, 不依赖外部文件)
# ═══════════════════════════════════════════════════════════════
SAMPLE_RATE = 22050

def _make_tone(freq, duration_ms, volume=0.5, wave="sine"):
    """生成单频音"""
    n = int(SAMPLE_RATE * duration_ms / 1000)
    buf = array.array('h', [0]) * n
    for i in range(n):
        t = i / SAMPLE_RATE
        # 渐入渐出包络 (避免爆音)
        env = 1.0
        fade_len = min(n // 10, 200)
        if i < fade_len:
            env = i / fade_len
        if i > n - fade_len:
            env = (n - i) / fade_len
        val = 0
        if wave == "sine":
            val = math.sin(2 * math.pi * freq * t)
        elif wave == "square":
            val = 1.0 if math.sin(2 * math.pi * freq * t) > 0 else -1.0
        elif wave == "saw":
            val = 2.0 * (freq * t - math.floor(freq * t + 0.5))
        buf[i] = int(volume * 0.7 * env * 32767 * val)
    return pygame.mixer.Sound(buffer=buf.tobytes())

def _make_sweep(freq_start, freq_end, duration_ms, volume=0.5, wave="sine"):
    """生成扫频音 (频率从 start 渐变到 end)"""
    n = int(SAMPLE_RATE * duration_ms / 1000)
    buf = array.array('h', [0]) * n
    for i in range(n):
        t = i / SAMPLE_RATE
        progress = i / n if n > 1 else 0
        freq = freq_start + (freq_end - freq_start) * progress
        env = 1.0
        fade_len = min(n // 15, 100)
        if i < fade_len:
            env = i / fade_len
        if i > n - fade_len:
            env = (n - i) / fade_len
        val = math.sin(2 * math.pi * freq * t)
        buf[i] = int(volume * 0.7 * env * 32767 * val)
    return pygame.mixer.Sound(buffer=buf.tobytes())

def _make_chirp(volume=0.5):
    """吃食物: 短促上升音"""
    return _make_sweep(600, 1200, 80, volume)

def _make_game_over_sound(volume=0.5):
    """游戏结束: 下降音"""
    return _make_sweep(400, 80, 600, volume)

def _make_click(volume=0.5):
    """菜单点击"""
    return _make_tone(1000, 30, volume * 0.3)

def _make_confirm(volume=0.5):
    """确认"""
    return _make_sweep(500, 800, 120, volume)

def _make_victory(volume=0.5):
    """胜利: 两个上升音"""
    n = int(SAMPLE_RATE * 250 / 1000)
    buf = array.array('h', [0]) * n
    tones = [(523, n // 2), (784, n - n // 2)]  # C5 → G5
    pos = 0
    for freq, length in tones:
        fade = min(length // 8, 50)
        for i in range(length):
            t = (pos + i) / SAMPLE_RATE
            env = 1.0
            if i < fade:
                env = i / fade
            if i > length - fade:
                env = (length - i) / fade
            val = math.sin(2 * math.pi * freq * t)
            buf[pos + i] = int(volume * 0.6 * env * 32767 * val)
        pos += length
    return pygame.mixer.Sound(buffer=buf.tobytes())

def _make_countdown(volume=0.5):
    """准备倒计时"""
    return _make_tone(880, 100, volume * 0.4)

def _make_start(volume=0.5):
    """游戏开始"""
    n = int(SAMPLE_RATE * 300 / 1000)
    buf = array.array('h', [0]) * n
    tones = [(440, n // 3), (554, n // 3), (659, n - 2 * (n // 3))]
    pos = 0
    for freq, length in tones:
        fade = min(length // 10, 40)
        for i in range(length):
            t = (pos + i) / SAMPLE_RATE
            env = 1.0
            if i < fade:
                env = i / fade
            if i > length - fade:
                env = (length - i) / fade
            val = math.sin(2 * math.pi * freq * t)
            buf[pos + i] = int(volume * 0.5 * env * 32767 * val)
        pos += length
    return pygame.mixer.Sound(buffer=buf.tobytes())


# ═══════════════════════════════════════════════════════════════
# SettingsManager —— 设置持久化
# ═══════════════════════════════════════════════════════════════
DEFAULT_SETTINGS = {
    # Classic mode
    "classic_speed_idx": 2,
    "classic_walls": True,
    # PVP collision mode
    "pvp_collision_speed_idx": 2,
    "pvp_collision_init_len": 3,
    "pvp_collision_walls": True,
    "pvp_collision_food": 3,
    "pvp_collision_grid_size": 40,
    # PVP battle mode
    "pvp_battle_speed_idx": 2,
    "pvp_battle_init_len": 3,
    "pvp_battle_food": 3,
    "pvp_battle_grid_size": 40,
    "pvp_battle_lives": 3,
    "battle_length_advantage": 6,
    # Visual
    "snake_style": 0,
    # Audio
    "sound_enabled": True,
    "sound_volume": 0.7,
    "music_enabled": True,
    "music_volume": 0.5,
}
INITIAL_LENGTH_MIN = 1
INITIAL_LENGTH_MAX = 50
FOOD_COUNT_MIN = 1
FOOD_COUNT_MAX = 50
BATTLE_ADVANTAGE_MIN = 3
BATTLE_ADVANTAGE_MAX = 10
CLASSIC_INIT_LEN = 3  # 经典模式固定初始长度

SNAKE_STYLE_LABELS = ["经典方块", "圆形拼接", "分段胶囊"]
SNAKE_STYLE_COUNT = len(SNAKE_STYLE_LABELS)

class SettingsManager:
    def __init__(self, filename=SETTINGS_FILE):
        self.filename = filename
        self.data = dict(DEFAULT_SETTINGS)
        self._load()

    def _path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), self.filename)

    def _load(self):
        path = self._path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except (ValueError, OSError):
                pass

    def _save(self):
        path = self._path()
        try:
            with open(path, "w") as f:
                json.dump(self.data, f, indent=2)
        except OSError:
            pass

    def get(self, key):
        return self.data.get(key, DEFAULT_SETTINGS[key])

    def set(self, key, value):
        self.data[key] = value

    def get_speed_fps(self, key="classic_speed_idx"):
        idx = self.get(key)
        idx = max(0, min(idx, len(SPEED_PRESETS) - 1))
        return SPEED_PRESETS[idx][1]

    def get_speed_label(self, key="classic_speed_idx"):
        idx = self.get(key)
        idx = max(0, min(idx, len(SPEED_PRESETS) - 1))
        return SPEED_PRESETS[idx][0]


# ═══════════════════════════════════════════════════════════════
# SoundManager —— 音效管理
# ═══════════════════════════════════════════════════════════════
class SoundManager:
    def __init__(self, settings_mgr):
        self.settings = settings_mgr
        self.sounds = {}
        self.mixer_ok = False
        self._init_mixer()

    def _init_mixer(self):
        try:
            # 有些 Windows 环境没有音频设备
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1)
            self.mixer_ok = True
            self._load_sounds()
        except (pygame.error, Exception):
            self.mixer_ok = False

    def _load_sounds(self):
        vol = self.settings.get("sound_volume")
        self.sounds = {
            "eat":        _make_chirp(vol),
            "game_over":  _make_game_over_sound(vol),
            "click":      _make_click(vol),
            "confirm":    _make_confirm(vol),
            "victory":    _make_victory(vol),
            "countdown":  _make_countdown(vol),
            "start":      _make_start(vol),
        }

    def play(self, name):
        if not self.mixer_ok:
            return
        if not self.settings.get("sound_enabled"):
            return
        sound = self.sounds.get(name)
        if sound:
            vol = self.settings.get("sound_volume")
            sound.set_volume(vol)
            sound.play()

    def reload_volumes(self):
        """设置改变后重新调整音量"""
        vol = self.settings.get("sound_volume")
        for name, sound in self.sounds.items():
            sound.set_volume(vol)


# ═══════════════════════════════════════════════════════════════
# HighScoreManager —— 最高分管理
# ═══════════════════════════════════════════════════════════════
class HighScoreManager:
    def __init__(self, filename=HIGH_SCORE_FILE):
        self.filename = filename
        self.high_score = self._load()

    def _path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), self.filename)

    def _load(self):
        path = self._path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return int(f.read().strip())
            except (ValueError, OSError):
                pass
        return 0

    def _save(self):
        path = self._path()
        try:
            with open(path, "w") as f:
                f.write(str(self.high_score))
        except OSError:
            pass

    def add_score(self, score):
        if score > self.high_score:
            self.high_score = score
            self._save()

    def get_high_score(self):
        return self.high_score


# ═══════════════════════════════════════════════════════════════
# Snake 类
# ═══════════════════════════════════════════════════════════════
class Snake:
    # 输入队列最大长度 — 允许快速连续按键不被吞掉,
    # 但限制上限防止输入堆积 (比如切出去回来一堆方向)
    MAX_INPUT_QUEUE = 3

    def __init__(self, body, direction, grid_size, color, name="", style=0):
        self.body = list(body)
        self.direction = direction
        self.grid_size = grid_size
        self.color = color
        self.name = name
        self.style = style
        self.grow_flag = False
        self.dir_queue = []  # 方向输入缓冲队列

    def set_direction(self, new_dir):
        """
        把方向变化加入缓冲队列, 而不是直接应用。
        每条 move() 消费一个方向, 保证快速连续按键不丢失。

        反向检测: 跟队列最后一个方向比 (而不是当前 direction),
        这样即使队列里有未消费的方向, 也不会产生"原地掉头"。
        """
        last = self.dir_queue[-1] if self.dir_queue else self.direction
        if (new_dir[0] + last[0], new_dir[1] + last[1]) == (0, 0):
            return  # 反向 → 丢弃
        if len(self.dir_queue) >= self.MAX_INPUT_QUEUE:
            return  # 队列满了 → 丢弃最旧的? 不, 直接丢弃新的
        self.dir_queue.append(new_dir)

    def move(self, wrap=False):
        """消费一个排队的方向, 然后移动。wrap=True 时穿墙从对面出现"""
        if self.dir_queue:
            self.direction = self.dir_queue.pop(0)

        hx, hy = self.body[-1]
        dx, dy = self.direction
        nh = (hx + dx, hy + dy)
        if wrap:
            nh = (nh[0] % self.grid_size, nh[1] % self.grid_size)
        if self.grow_flag:
            self.body.append(nh)
            self.grow_flag = False
        else:
            self.body.append(nh)
            self.body.pop(0)

    def grow(self):
        self.grow_flag = True

    def check_wall_collision(self):
        x, y = self.body[-1]
        return not (0 <= x < self.grid_size and 0 <= y < self.grid_size)

    def check_self_collision(self):
        return self.body[-1] in self.body[:-1]

    def _seg_color(self, i):
        """第 i 段的颜色（i=0 尾, i=len-1 头）"""
        ratio = i / len(self.body)
        darken = max(0.4, 1.0 - ratio * 0.5)
        c = self.color
        return (int(c[0] * darken), int(c[1] * darken), int(c[2] * darken))

    def _draw_style_rect(self, screen, cell_size):
        """造型 0: 经典方块 — 等宽圆角矩形 + 转弯关节"""
        # 先画关节线（底层），再画分段矩形（上层），
        # 这样转弯处关节不会压暗蛇头颜色
        if len(self.body) >= 2:
            for i in range(len(self.body) - 1):
                x1, y1 = self.body[i]
                x2, y2 = self.body[i + 1]
                if abs(x1 - x2) > 1 or abs(y1 - y2) > 1:
                    continue
                cx1 = x1 * cell_size + cell_size // 2
                cy1 = y1 * cell_size + cell_size // 2
                cx2 = x2 * cell_size + cell_size // 2
                cy2 = y2 * cell_size + cell_size // 2
                sc = self._seg_color(i)
                thickness = max(2, cell_size * 2 // 3)
                pygame.draw.line(screen, sc, (cx1, cy1), (cx2, cy2), thickness)

        for i, seg in enumerate(self.body):
            x, y = seg
            px = x * cell_size
            py = y * cell_size
            size = cell_size - 1
            rect = pygame.Rect(px, py, size, size)
            if i == len(self.body) - 1:
                pygame.draw.rect(screen, self.color, rect,
                                 border_radius=cell_size // 4)
                self._draw_eyes(screen, cell_size, px, py)
            else:
                pygame.draw.rect(screen, self._seg_color(i), rect,
                                 border_radius=cell_size // 6)

    def _draw_style_circle(self, screen, cell_size):
        """造型 1: 圆形拼接 — 重叠圆 + 转弯关节"""
        # 先画关节线（底层），再画圆形（上层），避免关节线压暗蛇头
        if len(self.body) >= 2:
            for i in range(len(self.body) - 1):
                x1, y1 = self.body[i]
                x2, y2 = self.body[i + 1]
                if abs(x1 - x2) > 1 or abs(y1 - y2) > 1:
                    continue
                cx1 = x1 * cell_size + cell_size // 2
                cy1 = y1 * cell_size + cell_size // 2
                cx2 = x2 * cell_size + cell_size // 2
                cy2 = y2 * cell_size + cell_size // 2
                sc = self._seg_color(i)
                thickness = max(2, cell_size * 2 // 3)
                pygame.draw.line(screen, sc, (cx1, cy1), (cx2, cy2), thickness)

        r = max(2, cell_size // 2)
        for i, seg in enumerate(self.body):
            x, y = seg
            cx = x * cell_size + cell_size // 2
            cy = y * cell_size + cell_size // 2
            if i == len(self.body) - 1:
                pygame.draw.circle(screen, self.color, (cx, cy), r)
                self._draw_eyes(screen, cell_size,
                                x * cell_size, y * cell_size)
            else:
                pygame.draw.circle(screen, self._seg_color(i), (cx, cy), r)

    def _draw_style_capsule(self, screen, cell_size):
        """造型 2: 分段胶囊 — 粗线连接 + 每段圆形填充"""
        r = max(2, cell_size // 2)
        # 先画连接线（底层），再画每段圆形（上层），
        # 转弯处圆形覆盖线端缺口，形成连续胶囊链
        if len(self.body) >= 2:
            for i in range(len(self.body) - 1):
                x1, y1 = self.body[i]
                x2, y2 = self.body[i + 1]
                if abs(x1 - x2) > 1 or abs(y1 - y2) > 1:
                    continue
                cx1 = x1 * cell_size + cell_size // 2
                cy1 = y1 * cell_size + cell_size // 2
                cx2 = x2 * cell_size + cell_size // 2
                cy2 = y2 * cell_size + cell_size // 2
                sc = self._seg_color(i)
                thickness = cell_size - 2
                pygame.draw.line(screen, sc, (cx1, cy1), (cx2, cy2), thickness)

        for i, seg in enumerate(self.body):
            x, y = seg
            cx = x * cell_size + cell_size // 2
            cy = y * cell_size + cell_size // 2
            if i == len(self.body) - 1:
                pygame.draw.circle(screen, self.color, (cx, cy), r)
                self._draw_eyes(screen, cell_size, x * cell_size, y * cell_size)
            else:
                pygame.draw.circle(screen, self._seg_color(i), (cx, cy), r)

    def draw(self, screen, cell_size):
        if self.style == 1:
            self._draw_style_circle(screen, cell_size)
        elif self.style == 2:
            self._draw_style_capsule(screen, cell_size)
        else:
            self._draw_style_rect(screen, cell_size)

    def _draw_eyes(self, screen, cell_size, px, py):
        dx, dy = self.direction
        cx = px + cell_size // 2
        cy = py + cell_size // 2
        r = max(2, cell_size // 7)
        pr = max(1, cell_size // 12)
        off = cell_size // 4

        if dx != 0:
            e1 = (cx + dx * off, cy - off)
            e2 = (cx + dx * off, cy + off)
        else:
            e1 = (cx - off, cy + dy * off)
            e2 = (cx + off, cy + dy * off)

        for ex, ey in [e1, e2]:
            pygame.draw.circle(screen, WHITE, (int(ex), int(ey)), r)
            pygame.draw.circle(screen, BLACK,
                               (int(ex + dx * pr * 0.5),
                                int(ey + dy * pr * 0.5)), pr)

    def get_head(self):
        return self.body[-1]


# ═══════════════════════════════════════════════════════════════
# Food 类
# ═══════════════════════════════════════════════════════════════
class Food:
    def __init__(self, grid_size):
        self.grid_size = grid_size
        self.position = (0, 0)

    def randomize(self, *snake_bodies, extra_occupied=None):
        occupied = set()
        for b in snake_bodies:
            occupied.update(b)
        if extra_occupied:
            occupied.update(extra_occupied)
        if len(occupied) >= self.grid_size * self.grid_size:
            return
        while True:
            pos = (random.randint(0, self.grid_size - 1),
                   random.randint(0, self.grid_size - 1))
            if pos not in occupied:
                self.position = pos
                break

    def draw(self, screen, cell_size):
        x, y = self.position
        cx = x * cell_size + cell_size // 2
        cy = y * cell_size + cell_size // 2
        r = cell_size // 2 - 2

        # 脉冲发光: 半径以 ~4Hz 振荡 ±12%
        t = pygame.time.get_ticks() / 1000.0
        pulse = 1.0 + 0.12 * math.sin(t * 4.0)

        glow = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
        for i in range(3, 0, -1):
            pr = max(1, int((r + i * 2) * pulse))
            pygame.draw.circle(glow, (*RED, 55 // i),
                               (cell_size // 2, cell_size // 2), pr)
        screen.blit(glow, (x * cell_size, y * cell_size))

        pygame.draw.circle(screen, RED, (cx, cy), r)
        pygame.draw.circle(screen, (255, 200, 200),
                           (cx - r // 3, cy - r // 3), r // 3)


# ═══════════════════════════════════════════════════════════════
# Bullet 类 (战斗模式)
# ═══════════════════════════════════════════════════════════════
class Bullet:
    def __init__(self, position, direction, grid_size, color):
        self.position = position
        self.direction = direction
        self.grid_size = grid_size
        self.color = color
        self.active = True
        self._glow = None
        self._glow_cell = 0

    def move(self):
        """移动 3 格/帧 (蛇速的 3 倍)"""
        if not self.active:
            return
        x, y = self.position
        dx, dy = self.direction
        for _ in range(3):
            x, y = x + dx, y + dy
            if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
                self.active = False
                return
        self.position = (x, y)

    def draw(self, screen, cell_size):
        if not self.active:
            return
        x, y = self.position
        cx = x * cell_size + cell_size // 2
        cy = y * cell_size + cell_size // 2
        r = max(2, cell_size // 4)
        pygame.draw.circle(screen, self.color, (cx, cy), r)
        if self._glow_cell != cell_size:
            glow_r = r + 2
            self._glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(self._glow, (*self.color, 80),
                               (glow_r, glow_r), glow_r)
            self._glow_cell = cell_size
        glow_r = r + 2
        screen.blit(self._glow, (cx - glow_r, cy - glow_r))


# ═══════════════════════════════════════════════════════════════
# ScorePopup —— 得分浮动文字
# ═══════════════════════════════════════════════════════════════
class ScorePopup:
    def __init__(self, x, y, text="+1", color=(255, 240, 100), lifetime=20):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.lifetime = lifetime
        self.max_life = lifetime
        self._raw = None

    def update(self):
        self.lifetime -= 1
        return self.lifetime > 0

    def draw(self, screen, font):
        if self._raw is None:
            self._raw = font.render(self.text, True, self.color)
        elapsed = self.max_life - self.lifetime
        py = int(self.y - elapsed * 1.8)
        alpha = int(255 * self.lifetime / self.max_life)
        surf = pygame.Surface(self._raw.get_size(), pygame.SRCALPHA)
        surf.blit(self._raw, (0, 0))
        surf.set_alpha(alpha)
        rect = surf.get_rect(center=(self.x, py))
        screen.blit(surf, rect)


# ═══════════════════════════════════════════════════════════════
# Menu 类 —— 菜单渲染
# ═══════════════════════════════════════════════════════════════
class Menu:
    def __init__(self, font_large, font_small, font_medium):
        self.font_large = font_large
        self.font_medium = font_medium
        self.font_small = font_small
        self.main_options = ["经典模式", "AI 观赏", "PVP对战", "游戏说明", "设置", "最高分记录", "退出"]
        self._option_anim_start = 0
        self.help_scroll_offset = 0
        self.mode_scroll_offset = 0

    # ── 装饰辅助 ──
    def _draw_border(self, screen, color=BORDER_COLOR, margin=8):
        """画装饰边框"""
        pygame.draw.rect(screen, color,
                         (margin, margin,
                          WINDOW_WIDTH - margin * 2,
                          WINDOW_HEIGHT - margin * 2), 2)
        # 四角装饰
        for cx, cy in [(margin + 2, margin + 2),
                       (WINDOW_WIDTH - margin - 2, margin + 2),
                       (margin + 2, WINDOW_HEIGHT - margin - 2),
                       (WINDOW_WIDTH - margin - 2, WINDOW_HEIGHT - margin - 2)]:
            pygame.draw.circle(screen, color, (cx, cy), 3)

    def _draw_title(self, screen, text, y, color=DARK_GREEN, shadow=True):
        """带阴影的标题"""
        if shadow:
            s = self.font_large.render(text, True, DARK_GREEN2)
            sr = s.get_rect(center=(WINDOW_WIDTH // 2 + 2, y + 2))
            screen.blit(s, sr)
        t = self.font_large.render(text, True, color)
        tr = t.get_rect(center=(WINDOW_WIDTH // 2, y))
        screen.blit(t, tr)
        # 下划线
        line_y = y + tr.height // 2 + 8
        for i in range(3):
            alpha = 180 - i * 40
            pygame.draw.line(screen, (*DARK_GREEN, alpha),
                             (WINDOW_WIDTH // 2 - 80 + i * 5, line_y + i),
                             (WINDOW_WIDTH // 2 + 80 - i * 5, line_y + i), 2)

    def _draw_options(self, screen, options, selected_idx, start_y, spacing=55):
        """通用选项列表（带动画颜色过渡和圆角面板）"""
        ANIM_DURATION = 300  # ms
        if self._option_anim_start == 0:
            self._option_anim_start = pygame.time.get_ticks()
        a = min(1.0, (pygame.time.get_ticks() - self._option_anim_start) / ANIM_DURATION)

        for i, opt in enumerate(options):
            is_sel = (i == selected_idx)
            target_color = BLUE_BRIGHT if is_sel else GRAY
            from_color = (GRAY[0], GRAY[1], GRAY[2])
            if is_sel:
                hc = (int(from_color[0] + (target_color[0] - from_color[0]) * a),
                      int(from_color[1] + (target_color[1] - from_color[1]) * a),
                      int(from_color[2] + (target_color[2] - from_color[2]) * a))
            else:
                hc = target_color

            # 选中项: 圆角卡片背景
            if is_sel:
                card_w, card_h = 340, 48
                cx = WINDOW_WIDTH // 2 - card_w // 2
                cy = start_y + i * spacing - card_h // 2
                card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
                alpha_bg = int(30 * a)
                alpha_border = int(70 * a)
                pygame.draw.rect(card, (*BLUE, alpha_bg), card.get_rect(), border_radius=14)
                pygame.draw.rect(card, (*BLUE_BRIGHT, alpha_border),
                                 card.get_rect(), border_radius=14, width=1)
                screen.blit(card, (cx, cy))

                # 发光文字
                glow_color = (BLUE[0], BLUE[1], BLUE[2], int(60 * a))
                glow = self.font_medium.render(opt, True, glow_color)
                gr = glow.get_rect(center=(WINDOW_WIDTH // 2 + 1, start_y + i * spacing + 1))
                screen.blit(glow, gr)

                # 箭头
                arrow = self.font_small.render("▶ ", True, hc)
                surf = self.font_medium.render(opt, True, hc)
                rect = surf.get_rect(center=(WINDOW_WIDTH // 2, start_y + i * spacing))
                arr_rect = arrow.get_rect(right=rect.left - 12, centery=rect.centery)
                screen.blit(arrow, arr_rect)
            else:
                surf = self.font_medium.render(opt, True, hc)
                rect = surf.get_rect(center=(WINDOW_WIDTH // 2, start_y + i * spacing))
            screen.blit(surf, rect)

    def draw_main(self, screen, selected_idx):
        """主菜单"""
        screen.fill(DARK_BG)
        self._draw_border(screen)

        # 装饰: 角落蛇形点阵
        r2, g2, b2 = DARK_GREEN2
        r1, g1, b1 = GREEN
        for i in range(6):
            t = i / 5.0
            c = (int(r2 + (r1 - r2) * t),
                 int(g2 + (g1 - g2) * t),
                 int(b2 + (b1 - b2) * t))
            pygame.draw.circle(screen, c,
                               (30 + i * 12, 35 + (i % 2) * 6), 3)
            pygame.draw.circle(screen, c,
                               (WINDOW_WIDTH - 30 - i * 12,
                                WINDOW_HEIGHT - 35 - (i % 2) * 6), 3)

        self._draw_title(screen, "贪 吃 蛇", 110)
        self._draw_options(screen, self.main_options, selected_idx, 240, 58)

        hint = self.font_small.render("↑↓ 选择  Enter 确认", True, GRAY_DARK)
        hr = hint.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 50))
        screen.blit(hint, hr)

    def draw_high_score(self, screen, score):
        """最高分界面"""
        screen.fill(DARK_BG)
        self._draw_border(screen)
        self._draw_title(screen, "最高分记录", 110)

        if score > 0:
            t = self.font_large.render(f"🏆 {score}", True, BLUE_BRIGHT)
            tr = t.get_rect(center=(WINDOW_WIDTH // 2, 280))
            screen.blit(t, tr)
        else:
            t = self.font_medium.render("暂无记录，开始一局游戏吧!", True, GRAY)
            tr = t.get_rect(center=(WINDOW_WIDTH // 2, 280))
            screen.blit(t, tr)

        hint = self.font_small.render("按 ESC 返回主菜单", True, GRAY_DARK)
        hr = hint.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 50))
        screen.blit(hint, hr)

    # ── 游戏说明界面 ──
    def draw_help(self, screen):
        screen.fill(DARK_BG)
        self._draw_border(screen)
        self._draw_title(screen, "游戏说明", 90 + self.help_scroll_offset)

        sections = [
            ("经典模式",
             [
                 "方向键 ↑↓←→  控制蛇的移动方向",
                 "R 键  重新开始游戏",
                 "吃食物变长，撞墙或撞到自己则游戏结束",
                 "可在游戏设置中开启/关闭围墙（穿墙模式）",
             ]),
            ("PVP 碰撞模式",
             [
                 "P1: 方向键 ↑↓←→    P2: W A S D",
                 "双方按 P / R 键准备，都准备好后游戏开始",
                 "R 键可随时重新开始本局",
                 "蛇头撞到对方蛇身 → 对方获胜",
                 "撞墙或撞到自己也会死亡",
                 "可在游戏设置中配置围墙、初始长度、食物数量",
             ]),
            ("PVP 战斗模式",
             [
                 "基本操作同上（方向键 + WASD）",
                 "P1 按 \\ 键发射子弹    P2 按 F 键发射子弹",
                 "发射消耗自身一格身体（只剩蛇头无法发射）",
                 "子弹速度为蛇的 3 倍，命中对方扣一条命",
                 "每方 3 条命，命耗尽或撞墙/撞自己则失败",
                 "一方比另一方长出 N 格直接获胜（可配置 3-10）",
             ]),
        ]

        content_h = 0
        for _, lines in sections:
            content_h += 40 + len(lines) * 26 + 10
        max_scroll = max(0, 150 + content_h - (WINDOW_HEIGHT - 80))
        if self.help_scroll_offset < -max_scroll:
            self.help_scroll_offset = -max_scroll
        elif self.help_scroll_offset > 0:
            self.help_scroll_offset = 0

        y = 150 + self.help_scroll_offset
        title_color = DARK_GREEN

        for mode_name, lines in sections:
            t = self.font_small.render(mode_name, True, title_color)
            tr = t.get_rect(midleft=(60, y))
            screen.blit(t, tr)
            pygame.draw.line(screen, (*DARK_GREEN, 120),
                             (60, tr.bottom + 2),
                             (60 + tr.width, tr.bottom + 2), 2)
            y += 40

            for line in lines:
                lt = self.font_small.render(line, True, GRAY)
                lr = lt.get_rect(midleft=(80, y))
                screen.blit(lt, lr)
                y += 26
            y += 10

        hint = self.font_small.render("ESC 返回  滚轮滚动", True, GRAY_DARK)
        hr = hint.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 35))
        screen.blit(hint, hr)

    # ── 设置界面 ──
    SETTINGS_ROWS = [
        ("游戏设置", "game_settings"),
        ("蛇身造型", "snake_style"),
        ("音效开关", "sound_toggle"),
        ("音效大小", "sound_vol"),
        ("音乐开关", "music_toggle"),
        ("音乐大小", "music_vol"),
    ]

    GAME_SETTINGS_ROWS = [
        ("经典模式设置", "classic_mode"),
        ("PVP碰撞模式设置", "pvp_collision_mode"),
        ("PVP战斗模式设置", "pvp_battle_mode"),
    ]

    CLASSIC_SETTINGS_ROWS = [
        ("蛇移动速度", "speed"),
        ("四周围墙", "walls"),
    ]

    PVP_COLLISION_SETTINGS_ROWS = [
        ("蛇移动速度", "speed"),
        ("蛇初始长度", "init_len"),
        ("四周围墙", "walls"),
        ("食物数量", "food"),
        ("地图大小", "grid_size"),
    ]

    PVP_BATTLE_SETTINGS_ROWS = [
        ("蛇移动速度", "speed"),
        ("蛇初始长度", "init_len"),
        ("食物数量", "food"),
        ("地图大小", "grid_size"),
        ("生命数量", "lives"),
        ("胜利长度差", "length_advantage"),
    ]

    _MODE_ROWS_MAP = {
        "classic": CLASSIC_SETTINGS_ROWS,
        "pvp_collision": PVP_COLLISION_SETTINGS_ROWS,
        "pvp_battle": PVP_BATTLE_SETTINGS_ROWS,
    }

    def draw_settings(self, screen, settings_mgr, cursor):
        """设置界面"""
        screen.fill(DARK_BG)
        self._draw_border(screen)
        self._draw_title(screen, "设 置", 100)

        settings = settings_mgr
        row_h = 58
        start_y = 175

        for i, (label, key) in enumerate(self.SETTINGS_ROWS):
            y = start_y + i * row_h
            is_sel = (i == cursor)

            # 标签
            label_color = BLUE_BRIGHT if is_sel else WHITE
            lbl = self.font_medium.render(label, True, label_color)
            lbl_rect = lbl.get_rect(midleft=(80, y))
            screen.blit(lbl, lbl_rect)

            # 值
            if key == "game_settings":
                color = BLUE_BRIGHT if is_sel else GRAY
                txt = "[ 进入 > ]"
                surf = self.font_medium.render(txt, True, color)
                srect = surf.get_rect(midright=(WINDOW_WIDTH - 80, y))
                screen.blit(surf, srect)
                if is_sel:
                    hint = self.font_small.render("Enter 进入", True, GRAY_DARK)
                    hrect = hint.get_rect(midleft=(srect.right + 10, y))
                    screen.blit(hint, hrect)

            elif key == "snake_style":
                idx = settings.get("snake_style")
                txt = f"[ {SNAKE_STYLE_LABELS[idx]} ]"
                color = BLUE_BRIGHT if is_sel else GRAY
                surf = self.font_medium.render(txt, True, color)
                srect = surf.get_rect(midright=(WINDOW_WIDTH - 80, y))
                screen.blit(surf, srect)
                if is_sel:
                    hint = self.font_small.render("◄ ► 切换造型", True, GRAY_DARK)
                    hrect = hint.get_rect(midleft=(srect.right + 10, y))
                    screen.blit(hint, hrect)

            elif key == "sound_toggle":
                on = settings.get("sound_enabled")
                txt = "[  开  ]" if on else "[  关  ]"
                color = GREEN if (on and is_sel) else (RED if not on else GRAY)
                if not is_sel:
                    color = GREEN if on else RED
                surf = self.font_medium.render(txt, True, color)
                srect = surf.get_rect(midright=(WINDOW_WIDTH - 80, y))
                screen.blit(surf, srect)
                if is_sel:
                    hint = self.font_small.render("Enter 切换", True, GRAY_DARK)
                    hrect = hint.get_rect(midleft=(srect.right + 10, y))
                    screen.blit(hint, hrect)

            elif key == "music_toggle":
                on = settings.get("music_enabled")
                txt = "[  开  ]" if on else "[  关  ]"
                color = GREEN if (on and is_sel) else (RED if not on else GRAY)
                if not is_sel:
                    color = GREEN if on else RED
                surf = self.font_medium.render(txt, True, color)
                srect = surf.get_rect(midright=(WINDOW_WIDTH - 80, y))
                screen.blit(surf, srect)
                if is_sel:
                    hint = self.font_small.render("Enter 切换", True, GRAY_DARK)
                    hrect = hint.get_rect(midleft=(srect.right + 10, y))
                    screen.blit(hint, hrect)

            elif key == "sound_vol":
                vol = settings.get("sound_volume")
                self._draw_volume_bar(screen, vol, y, is_sel)

            elif key == "music_vol":
                vol = settings.get("music_volume")
                self._draw_volume_bar(screen, vol, y, is_sel)

        hint = self.font_small.render("↑↓ 选择  Enter 进入子菜单  ESC 返回", True, GRAY_DARK)
        hr = hint.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 45))
        screen.blit(hint, hr)

    def draw_game_settings(self, screen, cursor):
        """游戏设置子界面 — 三个模式入口"""
        screen.fill(DARK_BG)
        self._draw_border(screen)
        self._draw_title(screen, "游戏设置", 100)

        row_h = 58
        start_y = 240

        for i, (label, key) in enumerate(self.GAME_SETTINGS_ROWS):
            y = start_y + i * row_h
            is_sel = (i == cursor)

            label_color = BLUE_BRIGHT if is_sel else WHITE
            lbl = self.font_small.render(label, True, label_color)
            lbl_rect = lbl.get_rect(midleft=(80, y))
            screen.blit(lbl, lbl_rect)

            color = BLUE_BRIGHT if is_sel else GRAY
            txt = "[ 进入 > ]"
            surf = self.font_small.render(txt, True, color)
            srect = surf.get_rect(midright=(WINDOW_WIDTH - 80, y))
            screen.blit(surf, srect)
            if is_sel:
                hint = self.font_small.render("Enter 进入", True, GRAY_DARK)
                hrect = hint.get_rect(midleft=(srect.right + 10, y))
                screen.blit(hint, hrect)

        hint = self.font_small.render("↑↓ 选择  Enter 进入  ESC 返回", True, GRAY_DARK)
        hr = hint.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 45))
        screen.blit(hint, hr)

    def draw_mode_settings(self, screen, settings_mgr, cursor, mode):
        """各模式独立设置界面"""
        screen.fill(DARK_BG)
        rows = self._MODE_ROWS_MAP[mode]
        title_map = {
            "classic": "经典模式设置",
            "pvp_collision": "PVP碰撞模式设置",
            "pvp_battle": "PVP战斗模式设置",
        }
        self._draw_border(screen)
        self._draw_title(screen, title_map[mode], 100)

        settings = settings_mgr
        row_h = 58
        content_h = len(rows) * row_h
        max_scroll = max(0, 175 + content_h - (WINDOW_HEIGHT - 80))
        if self.mode_scroll_offset < -max_scroll:
            self.mode_scroll_offset = -max_scroll
        elif self.mode_scroll_offset > 0:
            self.mode_scroll_offset = 0
        start_y = 175 + self.mode_scroll_offset
        speed_key = mode + "_speed_idx"

        for i, (label, key) in enumerate(rows):
            y = start_y + i * row_h
            is_sel = (i == cursor)

            label_color = BLUE_BRIGHT if is_sel else WHITE
            lbl = self.font_small.render(label, True, label_color)
            lbl_rect = lbl.get_rect(midleft=(80, y))
            screen.blit(lbl, lbl_rect)

            if key == "speed":
                idx = settings.get(speed_key)
                val = SPEED_PRESETS[idx][0]
                color = BLUE_BRIGHT if is_sel else GRAY
                txt = f"[ {val} ]"
                surf = self.font_small.render(txt, True, color)
                srect = surf.get_rect(midright=(WINDOW_WIDTH - 80, y))
                screen.blit(surf, srect)
                if is_sel:
                    hint = self.font_small.render("◄ ►", True, GRAY_DARK)
                    hrect = hint.get_rect(midleft=(srect.right + 10, y))
                    screen.blit(hint, hrect)

            elif key == "init_len":
                val = settings.get(mode + "_init_len")
                color = BLUE_BRIGHT if is_sel else GRAY
                txt = f"[ {val} 节 ]"
                surf = self.font_small.render(txt, True, color)
                srect = surf.get_rect(midright=(WINDOW_WIDTH - 80, y))
                screen.blit(surf, srect)
                if is_sel:
                    hint = self.font_small.render("◄ ►", True, GRAY_DARK)
                    hrect = hint.get_rect(midleft=(srect.right + 10, y))
                    screen.blit(hint, hrect)

            elif key == "walls":
                walls_key = mode + "_walls" if mode != "pvp_battle" else None
                if walls_key:
                    on = settings.get(walls_key)
                else:
                    on = True  # battle mode always has walls
                txt = "[  有墙  ]" if on else "[  无墙  ]"
                color = GREEN if (on and is_sel) else (RED if not on else GRAY)
                if not is_sel:
                    color = GREEN if on else RED
                surf = self.font_small.render(txt, True, color)
                srect = surf.get_rect(midright=(WINDOW_WIDTH - 80, y))
                screen.blit(surf, srect)
                if is_sel:
                    hint = self.font_small.render("Enter 切换", True, GRAY_DARK)
                    hrect = hint.get_rect(midleft=(srect.right + 10, y))
                    screen.blit(hint, hrect)

            elif key == "food":
                val = settings.get(mode + "_food")
                color = BLUE_BRIGHT if is_sel else GRAY
                txt = f"[ {val} 个 ]"
                surf = self.font_small.render(txt, True, color)
                srect = surf.get_rect(midright=(WINDOW_WIDTH - 80, y))
                screen.blit(surf, srect)
                if is_sel:
                    hint = self.font_small.render("◄ ►", True, GRAY_DARK)
                    hrect = hint.get_rect(midleft=(srect.right + 10, y))
                    screen.blit(hint, hrect)

            elif key == "grid_size":
                val = settings.get(mode + "_grid_size")
                color = BLUE_BRIGHT if is_sel else GRAY
                txt = f"[ {val}x{val} ]"
                surf = self.font_small.render(txt, True, color)
                srect = surf.get_rect(midright=(WINDOW_WIDTH - 80, y))
                screen.blit(surf, srect)
                if is_sel:
                    hint = self.font_small.render("◄ ►", True, GRAY_DARK)
                    hrect = hint.get_rect(midleft=(srect.right + 10, y))
                    screen.blit(hint, hrect)

            elif key == "lives":
                val = settings.get(mode + "_lives")
                color = BLUE_BRIGHT if is_sel else GRAY
                txt = f"[ {val} 条命 ]"
                surf = self.font_small.render(txt, True, color)
                srect = surf.get_rect(midright=(WINDOW_WIDTH - 80, y))
                screen.blit(surf, srect)
                if is_sel:
                    hint = self.font_small.render("◄ ►", True, GRAY_DARK)
                    hrect = hint.get_rect(midleft=(srect.right + 10, y))
                    screen.blit(hint, hrect)

            elif key == "length_advantage":
                val = settings.get("battle_length_advantage")
                color = BLUE_BRIGHT if is_sel else GRAY
                txt = f"[ {val} 格 ]"
                surf = self.font_small.render(txt, True, color)
                srect = surf.get_rect(midright=(WINDOW_WIDTH - 80, y))
                screen.blit(surf, srect)
                if is_sel:
                    hint = self.font_small.render("◄ ►", True, GRAY_DARK)
                    hrect = hint.get_rect(midleft=(srect.right + 10, y))
                    screen.blit(hint, hrect)

        hint = self.font_small.render("↑↓ 选择  ◄ ► 调整  Enter 切换  ESC 返回", True, GRAY_DARK)
        hr = hint.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 45))
        screen.blit(hint, hr)

    def _draw_volume_bar(self, screen, vol, y, is_sel):
        """画音量条 [█████░░░░░]"""
        bar_x = WINDOW_WIDTH - 230
        bar_w = 140
        bar_h = 12
        fill_w = int(bar_w * vol)

        # 背景
        bg_color = BLUE if is_sel else GRAY_DARK
        pygame.draw.rect(screen, (50, 50, 60),
                         (bar_x, y - bar_h // 2, bar_w, bar_h),
                         border_radius=3)
        if fill_w > 0:
            pygame.draw.rect(screen, bg_color,
                             (bar_x, y - bar_h // 2, fill_w, bar_h),
                             border_radius=3)

        # 百分比
        pct = self.font_small.render(f"{int(vol * 100)}%", True,
                                     BLUE_BRIGHT if is_sel else GRAY)
        prect = pct.get_rect(midleft=(bar_x + bar_w + 15, y))
        screen.blit(pct, prect)

        if is_sel:
            hint = self.font_small.render("◄ ►", True, GRAY_DARK)
            hrect = hint.get_rect(midleft=(prect.right + 8, y))
            screen.blit(hint, hrect)


# ═══════════════════════════════════════════════════════════════
# Game 类 —— 游戏主控
# ═══════════════════════════════════════════════════════════════
#
# 【架构说明】
#
# 新增模块:
#   SettingsManager — JSON 持久化, 管理速度/音效/音乐设置
#   SoundManager    — 程序化音效合成 (不依赖外部音频文件),
#                     管理播放/音量/开关
#
# 新增状态: SETTINGS
#   MENU → SETTINGS → MENU
#   设置界面用 ↑↓←→ Enter ESC 操作
#
# 速度控制:
#   clock.tick() 不再使用模块常量 FPS,
#   而是从 SettingsManager 读取 speed_idx 对应的 FPS.
#   玩家选"快速"→ speed_idx=3 → FPS=16 → 蛇移动更快.
#
# 音效触发时机:
#   · 吃食物        → sound_mgr.play("eat")
#   · 游戏结束      → sound_mgr.play("game_over")
#   · PVP 胜利      → sound_mgr.play("victory")
#   · 菜单/确认     → sound_mgr.play("click") / "confirm"
#   · PVP 准备确认  → sound_mgr.play("countdown")
#   · 游戏开始      → sound_mgr.play("start")
#
# 音效是"发后即忘"的, 不阻塞游戏循环。
class Game:
    MENU = "menu"
    CLASSIC = "classic"
    CLASSIC_AI = "classic_ai"
    PVP_SUBMENU = "pvp_submenu"
    PVP = "pvp"
    PVP_BATTLE = "pvp_battle"
    GAME_OVER = "game_over"
    HIGH_SCORES = "high_scores"
    SETTINGS = "settings"
    GAME_SETTINGS = "game_settings"
    MODE_SETTINGS = "mode_settings"
    HELP = "help"

    PVP_READY = "ready"
    PVP_PLAYING = "playing"

    P1_KEYS = {
        pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1),
        pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0),
    }
    P2_KEYS = {
        pygame.K_w: (0, -1), pygame.K_s: (0, 1),
        pygame.K_a: (-1, 0), pygame.K_d: (1, 0),
    }

    def __init__(self):
        pygame.init()
        self.is_fullscreen = False
        self.win_w = WINDOW_WIDTH
        self.win_h = WINDOW_HEIGHT
        self.screen = pygame.display.set_mode((self.win_w, self.win_h))
        pygame.display.set_caption("贪吃蛇 Snake Game")
        self.clock = pygame.time.Clock()

        self.font_large = _get_chinese_font(72)
        self.font_medium = _get_chinese_font(42)
        self.font_small = _get_chinese_font(30)

        # 设置管理器 (必须先加载, 因为音效需要音量参数)
        self.settings = SettingsManager()
        self.sound_mgr = SoundManager(self.settings)
        self.high_score_mgr = HighScoreManager()
        self.menu = Menu(self.font_large, self.font_small, self.font_medium)

        self.selected_idx = 0
        self.settings_cursor = 0
        self.game_settings_cursor = 0
        self.mode_settings_cursor = 0
        self.settings_mode = None  # "classic", "pvp_collision", "pvp_battle"
        self.pvp_sub_cursor = 0
        self.score_popups = []
        self.game_over_bg = None
        self._game_just_ended = False
        self.transition_alpha = 0
        self.transition_target = None

        self.state = Game.MENU
        self.mode = None
        self.grid_size = GRID_CLASSIC
        self.cell_size = WINDOW_WIDTH // self.grid_size

        self.p1_score = 0
        self.p2_score = 0
        self.winner = None

        # 战斗模式属性
        self.pvp_phase = None
        self.p1_ready = False
        self.p2_ready = False
        self.p1_lives = BATTLE_LIVES_DEFAULT
        self.p2_lives = BATTLE_LIVES_DEFAULT
        self.p1_bullets = []
        self.p2_bullets = []
        self.p1_cooldown = 0
        self.p2_cooldown = 0

    # ═══════════════════════════════════════════
    # 重置
    # ═══════════════════════════════════════════
    def reset(self):
        if self.mode == Game.CLASSIC:
            self._reset_classic()
        elif self.mode == Game.CLASSIC_AI:
            self._reset_classic()
        elif self.mode == Game.PVP:
            self._reset_pvp()
        elif self.mode == Game.PVP_BATTLE:
            self._reset_pvp_battle()

    def _reset_classic(self):
        self._game_just_ended = False
        self._resize_window(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.grid_size = GRID_CLASSIC
        self.cell_size = self.win_w // self.grid_size
        mid = self.grid_size // 2
        body = [(mid - (CLASSIC_INIT_LEN - 1 - i), mid) for i in range(CLASSIC_INIT_LEN)]
        self.snake = Snake(
            body=body, direction=(1, 0),
            grid_size=self.grid_size, color=GREEN, name="Snake",
            style=self.settings.get("snake_style"),
        )
        self.food = Food(self.grid_size)
        self.food.randomize(self.snake.body)
        self.score = 0

    def _init_pvp_common(self, init_len, food_count, grid_size):
        """PVP 通用初始化: 窗口、蛇、食物"""
        self.grid_size = grid_size
        self.cell_size = WINDOW_PVP_WIDTH // grid_size
        win_size = self.cell_size * grid_size
        self._resize_window(win_size, win_size)
        gs = self.grid_size
        p1_body = [(6 - (init_len - 1 - i), 6) for i in range(init_len)]
        p2_body = [(gs - 7 + (init_len - 1 - i), gs - 7) for i in range(init_len)]
        st = self.settings.get("snake_style")
        self.snake1 = Snake(
            body=p1_body, direction=(1, 0),
            grid_size=gs, color=ORANGE, name="P1", style=st,
        )
        self.snake2 = Snake(
            body=p2_body, direction=(-1, 0),
            grid_size=gs, color=PURPLE, name="P2", style=st,
        )
        self.foods = [Food(gs) for _ in range(food_count)]
        self._foods_randomize()
        self.p1_score = 0
        self.p2_score = 0
        self.winner = None
        self.pvp_phase = Game.PVP_READY
        self.p1_ready = False
        self.p2_ready = False

    def _foods_randomize(self):
        """PVP 多食物随机放置，互不重叠"""
        extra = set()
        for f in self.foods:
            f.randomize(self.snake1.body, self.snake2.body, extra_occupied=extra)
            extra.add(f.position)

    def _reset_pvp(self):
        self._game_just_ended = False
        self._init_pvp_common(
            init_len=self.settings.get("pvp_collision_init_len"),
            food_count=self.settings.get("pvp_collision_food"),
            grid_size=self.settings.get("pvp_collision_grid_size"),
        )

    def _reset_pvp_battle(self):
        self._game_just_ended = False
        self._init_pvp_common(
            init_len=self.settings.get("pvp_battle_init_len"),
            food_count=self.settings.get("pvp_battle_food"),
            grid_size=self.settings.get("pvp_battle_grid_size"),
        )
        lives = self.settings.get("pvp_battle_lives")
        self.p1_lives = lives
        self.p2_lives = lives
        self.p1_bullets = []
        self.p2_bullets = []
        self.p1_cooldown = 0
        self.p2_cooldown = 0

    # ═══════════════════════════════════════════
    # ① 输入处理
    # ═══════════════════════════════════════════
    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                # F11: 全屏切换 (在所有状态下生效)
                if event.key == pygame.K_F11:
                    self._toggle_fullscreen()
                elif self.state == Game.MENU:
                    self._handle_menu_input(event)
                elif self.state == Game.PVP_SUBMENU:
                    self._handle_pvp_submenu_input(event)
                elif self.state == Game.CLASSIC:
                    self._handle_classic_input(event)
                elif self.state == Game.CLASSIC_AI:
                    self._handle_classic_ai_input(event)
                elif self.state == Game.PVP:
                    self._handle_pvp_input(event)
                elif self.state == Game.PVP_BATTLE:
                    self._handle_pvp_battle_input(event)
                elif self.state == Game.GAME_OVER:
                    self._handle_gameover_input(event)
                elif self.state == Game.HIGH_SCORES:
                    self._handle_highscores_input(event)
                elif self.state == Game.HELP:
                    self._handle_help_input(event)
                elif self.state == Game.SETTINGS:
                    self._handle_settings_input(event)
                elif self.state == Game.GAME_SETTINGS:
                    self._handle_game_settings_input(event)
                elif self.state == Game.MODE_SETTINGS:
                    self._handle_mode_settings_input(event)

            if event.type == pygame.MOUSEWHEEL:
                if self.state == Game.HELP:
                    self.menu.help_scroll_offset += event.y * 30
                elif self.state == Game.MODE_SETTINGS:
                    self.menu.mode_scroll_offset += event.y * 30

        return True

    def _handle_menu_input(self, event):
        if event.key == pygame.K_UP:
            self.selected_idx = (self.selected_idx - 1) % len(self.menu.main_options)
            self.sound_mgr.play("click")
        elif event.key == pygame.K_DOWN:
            self.selected_idx = (self.selected_idx + 1) % len(self.menu.main_options)
            self.sound_mgr.play("click")
        elif event.key == pygame.K_RETURN:
            self.sound_mgr.play("confirm")
            if self.selected_idx == 0:          # 经典模式
                self.mode = Game.CLASSIC
                self.reset()
                self.sound_mgr.play("start")
                self._change_screen(Game.CLASSIC)
            elif self.selected_idx == 1:        # AI 观赏
                self.mode = Game.CLASSIC_AI
                self.reset()
                self.sound_mgr.play("start")
                self._change_screen(Game.CLASSIC_AI)
            elif self.selected_idx == 2:        # PVP → 子菜单
                self.pvp_sub_cursor = 0
                self._change_screen(Game.PVP_SUBMENU)
            elif self.selected_idx == 3:        # 游戏说明
                self._change_screen(Game.HELP)
            elif self.selected_idx == 4:        # 设置
                self.settings_cursor = 0
                self._change_screen(Game.SETTINGS)
            elif self.selected_idx == 5:        # 最高分
                self._change_screen(Game.HIGH_SCORES)
            elif self.selected_idx == 6:        # 退出
                sys.exit()

    def _handle_help_input(self, event):
        if event.key == pygame.K_ESCAPE:
            self.sound_mgr.play("click")
            self.selected_idx = 3
            self._change_screen(Game.MENU)

    def _handle_pvp_submenu_input(self, event):
        if event.key == pygame.K_ESCAPE:
            self.sound_mgr.play("click")
            self.selected_idx = 2
            self._change_screen(Game.MENU)
        elif event.key == pygame.K_UP or event.key == pygame.K_DOWN:
            self.pvp_sub_cursor = 1 - self.pvp_sub_cursor
            self.sound_mgr.play("click")
        elif event.key == pygame.K_RETURN:
            self.sound_mgr.play("confirm")
            if self.pvp_sub_cursor == 0:     # 碰撞模式
                self.mode = Game.PVP
                self.reset()
                self._change_screen(Game.PVP)
            else:                             # 战斗模式
                self.mode = Game.PVP_BATTLE
                self.reset()
                self.sound_mgr.play("start")
                self._change_screen(Game.PVP_BATTLE)

    def _handle_classic_input(self, event):
        if event.key == pygame.K_ESCAPE:
            self.sound_mgr.play("click")
            self._change_screen(Game.MENU)
            return
        if event.key in self.P1_KEYS:
            self.snake.set_direction(self.P1_KEYS[event.key])
        if event.key == pygame.K_r:
            self.sound_mgr.play("start")
            self._reset_classic()

    def _handle_classic_ai_input(self, event):
        if event.key == pygame.K_ESCAPE:
            self.sound_mgr.play("click")
            self._change_screen(Game.MENU)
            return
        if event.key == pygame.K_r:
            self.sound_mgr.play("start")
            self._reset_classic()
            self.score = 0

    def _handle_pvp_input(self, event):
        if event.key == pygame.K_ESCAPE:
            self.sound_mgr.play("click")
            self._change_screen(Game.MENU)
            return
        if self.pvp_phase == Game.PVP_READY:
            if event.key == pygame.K_p:
                self.p1_ready = True
                self.sound_mgr.play("countdown")
            if event.key == pygame.K_r:
                self.p2_ready = True
                self.sound_mgr.play("countdown")
            if self.p1_ready and self.p2_ready:
                self.pvp_phase = Game.PVP_PLAYING
                self.sound_mgr.play("start")
        else:
            if event.key in self.P1_KEYS:
                self.snake1.set_direction(self.P1_KEYS[event.key])
            if event.key in self.P2_KEYS:
                self.snake2.set_direction(self.P2_KEYS[event.key])
            if event.key == pygame.K_r:
                self._reset_pvp()

    def _handle_pvp_battle_input(self, event):
        if event.key == pygame.K_ESCAPE:
            self.sound_mgr.play("click")
            self._change_screen(Game.MENU)
            return
        if self.pvp_phase == Game.PVP_READY:
            if event.key == pygame.K_p:
                self.p1_ready = True
                self.sound_mgr.play("countdown")
            if event.key == pygame.K_r:
                self.p2_ready = True
                self.sound_mgr.play("countdown")
            if self.p1_ready and self.p2_ready:
                self.pvp_phase = Game.PVP_PLAYING
                self.sound_mgr.play("start")
        else:
            if event.key in self.P1_KEYS:
                self.snake1.set_direction(self.P1_KEYS[event.key])
            if event.key in self.P2_KEYS:
                self.snake2.set_direction(self.P2_KEYS[event.key])
            if event.key == pygame.K_BACKSLASH and self.p1_cooldown <= 0:
                self._shoot(self.snake1, self.p1_bullets, self.snake1.color)
                self.p1_cooldown = BULLET_COOLDOWN
            if event.key == pygame.K_f and self.p2_cooldown <= 0:
                self._shoot(self.snake2, self.p2_bullets, self.snake2.color)
                self.p2_cooldown = BULLET_COOLDOWN
            if event.key == pygame.K_r:
                self._reset_pvp_battle()

    def _shoot(self, snake, bullet_list, color):
        if len(snake.body) <= 1:
            return  # 只剩蛇头，无法发射
        head = snake.get_head()
        hx, hy = head
        dx, dy = snake.direction
        bx, by = hx + dx, hy + dy
        gs = snake.grid_size
        if 0 <= bx < gs and 0 <= by < gs:
            bullet_list.append(Bullet((bx, by), snake.direction, gs, color))
            snake.body.pop(0)  # 消耗尾部一格
            self.sound_mgr.play("click")

    def _handle_gameover_input(self, event):
        if event.key == pygame.K_SPACE:
            self.sound_mgr.play("click")
            self.selected_idx = 0
            self._resize_window(WINDOW_WIDTH, WINDOW_HEIGHT)
            self.cell_size = WINDOW_WIDTH // GRID_CLASSIC
            self.grid_size = GRID_CLASSIC
            self.game_over_bg = None
            self._change_screen(Game.MENU)
        elif event.key == pygame.K_r:
            self.game_over_bg = None
            if self.mode == Game.CLASSIC:
                self._reset_classic()
                self.sound_mgr.play("start")
                self._change_screen(Game.CLASSIC)
            elif self.mode == Game.CLASSIC_AI:
                self._reset_classic()
                self.sound_mgr.play("start")
                self._change_screen(Game.CLASSIC_AI)
            elif self.mode == Game.PVP:
                self._reset_pvp()
                self._change_screen(Game.PVP)
            elif self.mode == Game.PVP_BATTLE:
                self._reset_pvp_battle()
                self._change_screen(Game.PVP_BATTLE)
        elif event.key == pygame.K_q:
            sys.exit()

    def _handle_highscores_input(self, event):
        if event.key == pygame.K_ESCAPE:
            self.sound_mgr.play("click")
            self.selected_idx = 0
            self._change_screen(Game.MENU)

    def _toggle_fullscreen(self):
        """F11 全屏/窗口切换"""
        self.is_fullscreen = not self.is_fullscreen
        try:
            if self.is_fullscreen:
                self.screen = pygame.display.set_mode(
                    (self.win_w, self.win_h),
                    pygame.FULLSCREEN | pygame.SCALED,
                )
            else:
                self.screen = pygame.display.set_mode(
                    (self.win_w, self.win_h))
        except pygame.error:
            self.is_fullscreen = not self.is_fullscreen

    def _resize_window(self, width, height):
        """切换游戏模式时调整窗口尺寸"""
        self.win_w = width
        self.win_h = height
        if self.is_fullscreen:
            self.screen = pygame.display.set_mode(
                (width, height),
                pygame.FULLSCREEN | pygame.SCALED,
            )
        else:
            self.screen = pygame.display.set_mode((width, height))

    def _handle_settings_input(self, event):
        rows = Menu.SETTINGS_ROWS
        if event.key == pygame.K_ESCAPE:
            self.sound_mgr.play("click")
            self.settings._save()
            self.selected_idx = 0
            self._change_screen(Game.MENU)
            return

        if event.key == pygame.K_UP:
            self.settings_cursor = (self.settings_cursor - 1) % len(rows)
            self.sound_mgr.play("click")
        elif event.key == pygame.K_DOWN:
            self.settings_cursor = (self.settings_cursor + 1) % len(rows)
            self.sound_mgr.play("click")

        key = rows[self.settings_cursor][1]

        if key == "game_settings":
            if event.key == pygame.K_RETURN:
                self.sound_mgr.play("confirm")
                self.game_settings_cursor = 0
                self._change_screen(Game.GAME_SETTINGS)

        elif key == "snake_style":
            if event.key == pygame.K_LEFT:
                idx = (self.settings.get("snake_style") - 1) % SNAKE_STYLE_COUNT
                self.settings.set("snake_style", idx)
                self.sound_mgr.play("click")
            elif event.key == pygame.K_RIGHT:
                idx = (self.settings.get("snake_style") + 1) % SNAKE_STYLE_COUNT
                self.settings.set("snake_style", idx)
                self.sound_mgr.play("click")

        elif key == "sound_toggle":
            if event.key == pygame.K_RETURN:
                v = not self.settings.get("sound_enabled")
                self.settings.set("sound_enabled", v)
                self.sound_mgr.play("confirm" if v else "click")

        elif key == "sound_vol":
            if event.key == pygame.K_LEFT:
                v = max(0.0, self.settings.get("sound_volume") - 0.1)
                self.settings.set("sound_volume", round(v, 1))
                self.sound_mgr.reload_volumes()
                self.sound_mgr.play("click")
            elif event.key == pygame.K_RIGHT:
                v = min(1.0, self.settings.get("sound_volume") + 0.1)
                self.settings.set("sound_volume", round(v, 1))
                self.sound_mgr.reload_volumes()
                self.sound_mgr.play("click")

        elif key == "music_toggle":
            if event.key == pygame.K_RETURN:
                v = not self.settings.get("music_enabled")
                self.settings.set("music_enabled", v)
                self.sound_mgr.play("confirm" if v else "click")

        elif key == "music_vol":
            if event.key == pygame.K_LEFT:
                v = max(0.0, self.settings.get("music_volume") - 0.1)
                self.settings.set("music_volume", round(v, 1))
                self.sound_mgr.play("click")
            elif event.key == pygame.K_RIGHT:
                v = min(1.0, self.settings.get("music_volume") + 0.1)
                self.settings.set("music_volume", round(v, 1))
                self.sound_mgr.play("click")

    def _handle_game_settings_input(self, event):
        rows = Menu.GAME_SETTINGS_ROWS
        if event.key == pygame.K_ESCAPE:
            self.sound_mgr.play("click")
            self.settings._save()
            self.settings_cursor = 0
            self._change_screen(Game.SETTINGS)
            return

        if event.key == pygame.K_UP:
            self.game_settings_cursor = (self.game_settings_cursor - 1) % len(rows)
            self.sound_mgr.play("click")
        elif event.key == pygame.K_DOWN:
            self.game_settings_cursor = (self.game_settings_cursor + 1) % len(rows)
            self.sound_mgr.play("click")
        elif event.key == pygame.K_RETURN:
            key = rows[self.game_settings_cursor][1]
            mode_map = {
                "classic_mode": "classic",
                "pvp_collision_mode": "pvp_collision",
                "pvp_battle_mode": "pvp_battle",
            }
            self.settings_mode = mode_map[key]
            self.mode_settings_cursor = 0
            self.sound_mgr.play("confirm")
            self._change_screen(Game.MODE_SETTINGS)

    def _handle_mode_settings_input(self, event):
        mode = self.settings_mode
        rows = Menu._MODE_ROWS_MAP[mode]
        if event.key == pygame.K_ESCAPE:
            self.sound_mgr.play("click")
            self.settings._save()
            self._change_screen(Game.GAME_SETTINGS)
            return

        if event.key == pygame.K_UP:
            self.mode_settings_cursor = (self.mode_settings_cursor - 1) % len(rows)
            self.sound_mgr.play("click")
        elif event.key == pygame.K_DOWN:
            self.mode_settings_cursor = (self.mode_settings_cursor + 1) % len(rows)
            self.sound_mgr.play("click")

        key = rows[self.mode_settings_cursor][1]

        if key == "speed":
            sk = mode + "_speed_idx"
            if event.key == pygame.K_LEFT:
                idx = self.settings.get(sk) - 1
                self.settings.set(sk, max(0, idx))
                self.sound_mgr.play("click")
            elif event.key == pygame.K_RIGHT:
                idx = self.settings.get(sk) + 1
                self.settings.set(sk, min(len(SPEED_PRESETS) - 1, idx))
                self.sound_mgr.play("click")

        elif key == "init_len":
            ik = mode + "_init_len"
            if event.key == pygame.K_LEFT:
                val = self.settings.get(ik) - 1
                self.settings.set(ik, max(INITIAL_LENGTH_MIN, val))
                self.sound_mgr.play("click")
            elif event.key == pygame.K_RIGHT:
                val = self.settings.get(ik) + 1
                self.settings.set(ik, min(INITIAL_LENGTH_MAX, val))
                self.sound_mgr.play("click")

        elif key == "walls":
            wk = mode + "_walls"
            if event.key == pygame.K_RETURN:
                v = not self.settings.get(wk)
                self.settings.set(wk, v)
                self.sound_mgr.play("confirm" if v else "click")

        elif key == "food":
            fk = mode + "_food"
            if event.key == pygame.K_LEFT:
                val = self.settings.get(fk) - 1
                self.settings.set(fk, max(FOOD_COUNT_MIN, val))
                self.sound_mgr.play("click")
            elif event.key == pygame.K_RIGHT:
                val = self.settings.get(fk) + 1
                self.settings.set(fk, min(FOOD_COUNT_MAX, val))
                self.sound_mgr.play("click")

        elif key == "grid_size":
            gk = mode + "_grid_size"
            if event.key == pygame.K_LEFT:
                val = self.settings.get(gk) - 1
                self.settings.set(gk, max(GRID_PVP_MIN, val))
                self.sound_mgr.play("click")
            elif event.key == pygame.K_RIGHT:
                val = self.settings.get(gk) + 1
                self.settings.set(gk, min(GRID_PVP_MAX, val))
                self.sound_mgr.play("click")

        elif key == "lives":
            lk = mode + "_lives"
            if event.key == pygame.K_LEFT:
                val = self.settings.get(lk) - 1
                self.settings.set(lk, max(BATTLE_LIVES_MIN, val))
                self.sound_mgr.play("click")
            elif event.key == pygame.K_RIGHT:
                val = self.settings.get(lk) + 1
                self.settings.set(lk, min(BATTLE_LIVES_MAX, val))
                self.sound_mgr.play("click")

        elif key == "length_advantage":
            if event.key == pygame.K_LEFT:
                val = self.settings.get("battle_length_advantage") - 1
                self.settings.set("battle_length_advantage",
                                  max(BATTLE_ADVANTAGE_MIN, val))
                self.sound_mgr.play("click")
            elif event.key == pygame.K_RIGHT:
                val = self.settings.get("battle_length_advantage") + 1
                self.settings.set("battle_length_advantage",
                                  min(BATTLE_ADVANTAGE_MAX, val))
                self.sound_mgr.play("click")

    # ═══════════════════════════════════════════
    # ② AI 寻路 (观赏模式)
    # ═══════════════════════════════════════════
    # 方向常量 (避免重复创建)
    _DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def _ai_simulate_body(self, body, next_pos):
        """模拟移动一步后的蛇身"""
        new_body = list(body)
        new_body.append(next_pos)
        if not self.snake.grow_flag:
            new_body.pop(0)
        return new_body

    def _ai_simulate_eating(self, body, path):
        """模拟沿 path 走到终点并吃掉食物后的蛇身"""
        sim = list(body)
        for i in range(1, len(path)):
            sim.append(path[i])
            sim.pop(0)
        sim.append(path[-1])  # 吃掉食物, 增长
        return sim

    def _ai_bfs(self, start, target, body, gs, wrap):
        """BFS 寻路: 返回从 start 到 target 的最短路径 (含起点), 找不到返回 None"""
        queue = deque([[start]])
        visited = {start}
        body_set = set(body)
        tail = body[0]
        tail_free = not self.snake.grow_flag  # tail 即将离开

        while queue:
            path = queue.popleft()
            pos = path[-1]
            if pos == target:
                return path

            for dx, dy in self._DIRS:
                nx, ny = pos[0] + dx, pos[1] + dy
                if wrap:
                    nx %= gs
                    ny %= gs
                elif not (0 <= nx < gs and 0 <= ny < gs):
                    continue
                nxt = (nx, ny)
                if nxt in visited:
                    continue
                if nxt in body_set and not (tail_free and nxt == tail):
                    continue
                visited.add(nxt)
                queue.append(path + [nxt])
        return None

    def _ai_flood_fill(self, start, body, gs, wrap):
        """返回从 start 出发能到达的空格数 (BFS flood fill)"""
        queue = deque([start])
        visited = {start}
        body_set = set(body)

        while queue:
            x, y = queue.popleft()
            for dx, dy in self._DIRS:
                nx, ny = x + dx, y + dy
                if wrap:
                    nx %= gs
                    ny %= gs
                elif not (0 <= nx < gs and 0 <= ny < gs):
                    continue
                nxt = (nx, ny)
                if nxt in visited or nxt in body_set:
                    continue
                visited.add(nxt)
                queue.append(nxt)
        return len(visited)

    def _ai_is_path_safe(self, body, path, gs, wrap, space_margin=1.2):
        """两阶段安全检测:
        1. 快速检查: 吃掉食物后, 可达空格数 >= 蛇身长度 * space_margin
        2. 动态模拟: 模拟蛇在 len(body) 步内不会撞死"""
        if len(path) < 2:
            return True

        sim_body = self._ai_simulate_eating(body, path)
        head = sim_body[-1]
        body_len = len(sim_body)

        # 阶段 1: 空间储备检查
        if self._ai_flood_fill(head, sim_body, gs, wrap) < int(body_len * space_margin):
            return False

        # 阶段 2: 动态模拟 — 每步朝最开阔方向走 body_len 步
        test = list(sim_body)
        for _ in range(body_len):
            h = test[-1]
            best_pos = None
            best_free = -1
            for dx, dy in self._DIRS:
                nx, ny = h[0] + dx, h[1] + dy
                if wrap:
                    nx %= gs
                    ny %= gs
                elif not (0 <= nx < gs and 0 <= ny < gs):
                    continue
                nxt = (nx, ny)
                if nxt in test:
                    continue
                f = self._ai_flood_fill(nxt, test, gs, wrap)
                if f > best_free:
                    best_free = f
                    best_pos = nxt
            if best_pos is None:
                return False
            test.append(best_pos)
            test.pop(0)
        return True

    def _ai_get_tail_dir(self, head, body, gs, wrap, valid_moves):
        """计算跟随尾巴的方向。优先追 body[1] (tail 下一步),
        追不到则尝试 body[0] (当前 tail)。返回方向或 None。"""
        if len(body) < 3:
            return None
        for tail_target in (body[1], body[0]):
            tpath = self._ai_bfs(head, tail_target, body, gs, wrap)
            if tpath and len(tpath) > 1:
                tpos = tpath[1]
                tdir = (tpos[0] - head[0], tpos[1] - head[1])
                if any(d == tdir for d, _ in valid_moves):
                    return tdir
        return None

    def _ai_get_food_dir(self, head, food, body, gs, wrap, valid_moves):
        """计算安全吃食物的方向。两道检查:
        1. BFS 路径存在
        2. 两阶段安全检测通过 (动态模拟, 含空间余量)
        返回 (direction, path) 或 (None, None)。"""
        path = self._ai_bfs(head, food, body, gs, wrap)
        if not path or len(path) < 2:
            return None, None

        if not self._ai_is_path_safe(body, path, gs, wrap):
            return None, None

        target_pos = path[1]
        target_dir = (target_pos[0] - head[0], target_pos[1] - head[1])
        if any(d == target_dir for d, _ in valid_moves):
            return target_dir, path
        return None, None

    @staticmethod
    def _ai_wrap_dist(a, b, gs):
        """计算 wrap 模式下的曼哈顿距离"""
        dx = min(abs(a[0] - b[0]), gs - abs(a[0] - b[0]))
        dy = min(abs(a[1] - b[1]), gs - abs(a[1] - b[1]))
        return dx + dy

    def _ai_would_seal(self, body_set, next_pos, gs):
        """检查移动到 next_pos 是否会封死一整行或一整列。
        蛇身占满一行/列 = 形成不可穿越的墙 = 空间被割裂。"""
        nx, ny = next_pos
        # 行检查
        if all((x, ny) in body_set for x in range(gs)):
            return True
        # 列检查
        if all((nx, y) in body_set for y in range(gs)):
            return True
        return False

    def _ai_decide_direction(self):
        """AI 决策 — 保命优先:
        1. 默认跟随尾巴 (最安全)
        2. 食物安全且有余量时, 概率性出击 (观赏性)
        3. 追不到尾巴时, 朝开阔方向走"""
        head = self.snake.get_head()
        food = self.food.position
        gs = self.grid_size
        wrap = not self.settings.get("classic_walls")
        body = self.snake.body
        cd = self.snake.direction
        grow = self.snake.grow_flag
        reverse = (-cd[0], -cd[1])

        # ── 收集合法移动, 区分是否会封行/列 ──
        valid = []   # 不封行/列的移动
        sealed = []  # 会封行/列的 (迫不得已才用)
        body_set = set(body)  # 预先计算, _ai_would_seal 复用

        for d in self._DIRS:
            if d == reverse:
                continue
            nx, ny = head[0] + d[0], head[1] + d[1]
            if wrap:
                nx %= gs
                ny %= gs
            elif not (0 <= nx < gs and 0 <= ny < gs):
                continue
            nxt = (nx, ny)
            if nxt in body_set and not (not grow and nxt == body[0]):
                continue

            # 构建移动后的 body_set 检查封行/列
            test_set = body_set | {nxt}
            if not grow:
                test_set.discard(body[0])
            if self._ai_would_seal(test_set, nxt, gs):
                sealed.append((d, nxt))
            else:
                valid.append((d, nxt))

        moves = valid if valid else sealed
        if not moves:
            return

        # ── 计算两个核心方向 ──
        tail_dir = self._ai_get_tail_dir(head, body, gs, wrap, moves)
        food_dir, _ = self._ai_get_food_dir(head, food, body, gs, wrap, moves)

        # ── 决策: 二者皆安全时优先吃食, 尾巴是保底 ──
        if food_dir is not None and tail_dir is not None:
            # 两者都可达: 70% 出击吃食, 30% 跟尾巴 (观赏变化)
            if random.random() < 0.7:
                self.snake.set_direction(food_dir)
            else:
                self.snake.set_direction(tail_dir)
            return

        if tail_dir is not None:
            self.snake.set_direction(tail_dir)
            return

        # ── 追不到尾巴 ──
        if food_dir is not None:
            self.snake.set_direction(food_dir)
            return

        # ── 兜底: 朝最开阔方向 ──
        best_dir = moves[0][0]
        best_score = -1
        for d, pos in moves:
            sim = self._ai_simulate_body(body, pos)
            free = self._ai_flood_fill(pos, sim, gs, wrap)
            score = free * 100 + (gs * gs - self._ai_wrap_dist(pos, food, gs))
            if score > best_score:
                best_score = score
                best_dir = d

        self.snake.set_direction(best_dir)

    # ═══════════════════════════════════════════
    # ③ 更新逻辑
    # ═══════════════════════════════════════════
    def update(self):
        if self.state == Game.CLASSIC:
            self._update_classic()
        elif self.state == Game.CLASSIC_AI:
            self._update_classic_ai()
        elif self.state == Game.PVP:
            self._update_pvp()
        elif self.state == Game.PVP_BATTLE:
            self._update_pvp_battle()

    def _update_classic(self):
        wrap = not self.settings.get("classic_walls")
        self.snake.move(wrap=wrap)

        if self.snake.get_head() == self.food.position:
            self.snake.grow()
            self.score += 1
            self.sound_mgr.play("eat")
            fx, fy = self.food.position
            px = fx * self.cell_size + self.cell_size // 2
            py = fy * self.cell_size + self.cell_size // 2
            self.score_popups.append(ScorePopup(px, py))
            self.food.randomize(self.snake.body)

        dead = False
        if not wrap and self.snake.check_wall_collision():
            dead = True
        if self.snake.check_self_collision():
            dead = True
        if dead:
            self.high_score_mgr.add_score(self.score)
            self.sound_mgr.play("game_over")
            self._game_just_ended = True

    def _update_classic_ai(self):
        self._ai_decide_direction()
        self._update_classic()

    def _update_pvp(self):
        if self.pvp_phase != Game.PVP_PLAYING:
            return

        wrap = not self.settings.get("pvp_collision_walls")
        self.snake1.move(wrap=wrap)
        self.snake2.move(wrap=wrap)

        h1 = self.snake1.get_head()
        h2 = self.snake2.get_head()

        for f in self.foods:
            if h1 == f.position:
                self.snake1.grow()
                self.p1_score += 1
                self.sound_mgr.play("eat")
                f.randomize(self.snake1.body, self.snake2.body,
                            extra_occupied={x.position for x in self.foods if x is not f})
            elif h2 == f.position:
                self.snake2.grow()
                self.p2_score += 1
                self.sound_mgr.play("eat")
                f.randomize(self.snake1.body, self.snake2.body,
                            extra_occupied={x.position for x in self.foods if x is not f})

        s1_dead = False
        s2_dead = False

        if not wrap:
            if self.snake1.check_wall_collision():
                s1_dead = True
            if self.snake2.check_wall_collision():
                s2_dead = True
        if not s1_dead and h1 in self.snake2.body:
            s1_dead = True
        if not s2_dead and h2 in self.snake1.body:
            s2_dead = True

        if s1_dead or s2_dead:
            if s1_dead and s2_dead:
                self.winner = 0
            elif s1_dead:
                self.winner = 2
            else:
                self.winner = 1
            self.sound_mgr.play("victory")
            self._game_just_ended = True

    def _update_pvp_battle(self):
        if self.pvp_phase != Game.PVP_PLAYING:
            return

        self.snake1.move()
        self.snake2.move()

        # 冷却递减
        if self.p1_cooldown > 0:
            self.p1_cooldown -= 1
        if self.p2_cooldown > 0:
            self.p2_cooldown -= 1

        # 移动子弹
        for b in self.p1_bullets:
            b.move()
        for b in self.p2_bullets:
            b.move()

        h1 = self.snake1.get_head()
        h2 = self.snake2.get_head()

        # 食物碰撞
        for f in self.foods:
            if h1 == f.position:
                self.snake1.grow()
                self.p1_score += 1
                self.sound_mgr.play("eat")
                f.randomize(self.snake1.body, self.snake2.body,
                            extra_occupied={x.position for x in self.foods if x is not f})
            elif h2 == f.position:
                self.snake2.grow()
                self.p2_score += 1
                self.sound_mgr.play("eat")
                f.randomize(self.snake1.body, self.snake2.body,
                            extra_occupied={x.position for x in self.foods if x is not f})

        # 长度碾压: 一方比另一方多 N 格则直接胜利
        advantage = self.settings.get("battle_length_advantage")
        len1, len2 = len(self.snake1.body), len(self.snake2.body)
        if len1 - len2 >= advantage:
            self.winner = 1
            self.sound_mgr.play("victory")
            self._game_just_ended = True
            return
        if len2 - len1 >= advantage:
            self.winner = 2
            self.sound_mgr.play("victory")
            self._game_just_ended = True
            return

        # 预转 set，O(1) 命中检测 (避免每颗子弹都 O(n) 扫描蛇身)
        s1_set = set(self.snake1.body)
        s2_set = set(self.snake2.body)

        # P1 子弹命中 P2 (检查中间位置防 3 倍速穿透)
        for b in self.p1_bullets:
            if not b.active:
                continue
            x, y = b.position
            dx, dy = b.direction
            if (x, y) in s2_set or (x - dx, y - dy) in s2_set or (x - dx * 2, y - dy * 2) in s2_set:
                b.active = False
                self.p2_lives -= 1
                self.sound_mgr.play("game_over")
        # P2 子弹命中 P1
        for b in self.p2_bullets:
            if not b.active:
                continue
            x, y = b.position
            dx, dy = b.direction
            if (x, y) in s1_set or (x - dx, y - dy) in s1_set or (x - dx * 2, y - dy * 2) in s1_set:
                b.active = False
                self.p1_lives -= 1
                self.sound_mgr.play("game_over")

        # 清理失效子弹
        self.p1_bullets = [b for b in self.p1_bullets if b.active]
        self.p2_bullets = [b for b in self.p2_bullets if b.active]

        # 胜利判定
        if self.p1_lives <= 0 and self.p2_lives <= 0:
            self.winner = 0
        elif self.p1_lives <= 0:
            self.winner = 2
        elif self.p2_lives <= 0:
            self.winner = 1
        else:
            # 蛇自身撞墙也算死亡
            s1_dead = self.snake1.check_wall_collision() or self.snake1.check_self_collision()
            s2_dead = self.snake2.check_wall_collision() or self.snake2.check_self_collision()
            if s1_dead and s2_dead:
                self.winner = 0
            elif s1_dead:
                self.winner = 2
            elif s2_dead:
                self.winner = 1
            else:
                return
        self.sound_mgr.play("victory")
        self._game_just_ended = True

    # ═══════════════════════════════════════════
    # ④ 渲染
    # ═══════════════════════════════════════════
    def _change_screen(self, new_state):
        if self.transition_alpha > 0:
            return
        self.menu._option_anim_start = 0
        if new_state == Game.HELP:
            self.menu.help_scroll_offset = 0
        elif new_state == Game.MODE_SETTINGS:
            self.menu.mode_scroll_offset = 0
        if new_state not in (Game.CLASSIC, Game.CLASSIC_AI, Game.PVP, Game.PVP_BATTLE):
            if self.win_w != WINDOW_WIDTH or self.win_h != WINDOW_HEIGHT:
                self._resize_window(WINDOW_WIDTH, WINDOW_HEIGHT)
            self.transition_alpha = 1
            self.transition_target = new_state
        else:
            # 游戏状态立即生效，确保按键处理不被过渡动画阻塞
            self.state = new_state
            self.transition_alpha = 0
            self.transition_target = None

    def _draw_state(self, state):
        """渲染指定状态到 self.screen"""
        if state == Game.MENU:
            self.menu.draw_main(self.screen, self.selected_idx)
        elif state == Game.PVP_SUBMENU:
            self._draw_pvp_submenu()
        elif state == Game.CLASSIC:
            self._draw_classic()
        elif state == Game.CLASSIC_AI:
            self._draw_classic()
        elif state == Game.PVP:
            self._draw_pvp()
        elif state == Game.PVP_BATTLE:
            self._draw_pvp_battle()
        elif state == Game.GAME_OVER:
            self._draw_game_over()
        elif state == Game.HIGH_SCORES:
            self.menu.draw_high_score(self.screen,
                                      self.high_score_mgr.get_high_score())
        elif state == Game.HELP:
            self.menu.draw_help(self.screen)
        elif state == Game.SETTINGS:
            self.menu.draw_settings(self.screen, self.settings,
                                    self.settings_cursor)
        elif state == Game.GAME_SETTINGS:
            self.menu.draw_game_settings(self.screen,
                                         self.game_settings_cursor)
        elif state == Game.MODE_SETTINGS:
            self.menu.draw_mode_settings(self.screen, self.settings,
                                         self.mode_settings_cursor,
                                         self.settings_mode)

    def _draw_game_mode(self):
        """渲染当前游戏模式画面（不含 HUD 之上的覆盖层）"""
        if self.mode == Game.CLASSIC:
            self._draw_classic()
        elif self.mode == Game.CLASSIC_AI:
            self._draw_classic()
        elif self.mode == Game.PVP:
            self._draw_pvp()
        elif self.mode == Game.PVP_BATTLE:
            self._draw_pvp_battle()

    def draw(self, dt):
        # 游戏结束捕获当前画面
        if self._game_just_ended:
            self._draw_game_mode()
            self.game_over_bg = self.screen.copy()
            self._game_just_ended = False
            self.state = Game.GAME_OVER
            self._draw_game_over()
            pygame.display.flip()
            return

        # 淡入淡出过渡 (时间驱动, 目标 300ms)
        if self.transition_alpha > 0 and self.transition_alpha < 255:
            TRANSITION_DURATION = 300  # ms
            self._draw_state(self.state)
            temp = pygame.Surface((self.win_w, self.win_h))
            saved = self.screen
            self.screen = temp
            self._draw_state(self.transition_target)
            self.screen = saved
            old_frame = self.screen.copy()
            self.screen.blit(old_frame, (0, 0))
            step = (255.0 / TRANSITION_DURATION) * dt
            self.transition_alpha += step
            if self.transition_alpha >= 255:
                self.state = self.transition_target
                self.transition_alpha = 0
                self.transition_target = None
                self._draw_state(self.state)
            else:
                temp.set_alpha(int(self.transition_alpha))
                self.screen.blit(temp, (0, 0))
            pygame.display.flip()
            return

        self._draw_state(self.state)
        pygame.display.flip()

    def _draw_pvp_submenu(self):
        w, h = self.win_w, self.win_h
        self.screen.fill(DARK_BG)
        pygame.draw.rect(self.screen, BORDER_COLOR,
                         (8, 8, w - 16, h - 16), 2)
        for cx, cy in [(10, 10), (w - 10, 10),
                       (10, h - 10), (w - 10, h - 10)]:
            pygame.draw.circle(self.screen, BORDER_COLOR, (cx, cy), 3)
        t = self.font_large.render("PVP 模式选择", True, DARK_GREEN)
        tr = t.get_rect(center=(w // 2, 160))
        self.screen.blit(t, tr)

        options = ["碰撞模式 — 蛇身碰撞即死亡", "战斗模式 — 发射子弹对战"]
        for i, opt in enumerate(options):
            y = 310 + i * 80
            if i == self.pvp_sub_cursor:
                color = BLUE_BRIGHT
                arrow = self.font_medium.render("▶ ", True, BLUE_BRIGHT)
                surf = self.font_medium.render(opt, True, color)
                rect = surf.get_rect(center=(w // 2, y))
                arr_rect = arrow.get_rect(right=rect.left - 12, centery=rect.centery)
                self.screen.blit(arrow, arr_rect)
            else:
                color = GRAY
                surf = self.font_medium.render(opt, True, color)
                rect = surf.get_rect(center=(w // 2, y))
            self.screen.blit(surf, rect)

        hint = self.font_small.render("↑↓ 选择  Enter 确认  ESC 返回", True, GRAY_DARK)
        hr = hint.get_rect(center=(w // 2, h - 60))
        self.screen.blit(hint, hr)

    def _draw_grid(self):
        w, h = self.win_w, self.win_h
        for x in range(0, w, self.cell_size):
            pygame.draw.line(self.screen, GRID_COLOR, (x, 0), (x, h), 1)
        for y in range(0, h, self.cell_size):
            pygame.draw.line(self.screen, GRID_COLOR, (0, y), (w, y), 1)

    def _draw_hud_bg(self):
        bar_h = 32
        s = pygame.Surface((self.win_w, bar_h), pygame.SRCALPHA)
        s.fill((*PANEL_BG, 180))
        self.screen.blit(s, (0, 0))
        self.screen.blit(s, (0, self.win_h - bar_h))

    def _draw_classic(self):
        self.screen.fill(DARK_BG)
        self._draw_grid()
        self.snake.draw(self.screen, self.cell_size)
        self.food.draw(self.screen, self.cell_size)

        for p in self.score_popups[:]:
            if not p.update():
                self.score_popups.remove(p)
            else:
                p.draw(self.screen, self.font_small)

        self._draw_hud_bg()
        sc_text = f"分数: {self.score}"
        if self.state == Game.CLASSIC_AI:
            sc_text += "  [AI 观赏中]"
        sc = self.font_small.render(sc_text, True, WHITE)
        self.screen.blit(sc, (10, 3))
        hs = self.font_small.render(f"最高分: {self.high_score_mgr.get_high_score()}",
                                     True, GRAY)
        hr = hs.get_rect(topright=(self.win_w - 10, 3))
        self.screen.blit(hs, hr)
        hint = self.font_small.render("R 重开", True, GRAY_DARK)
        hr2 = hint.get_rect(topright=(self.win_w - 10, self.win_h - 26))
        self.screen.blit(hint, hr2)

    def _draw_pvp(self):
        self.screen.fill(DARK_BG)
        self._draw_grid()
        self.snake1.draw(self.screen, self.cell_size)
        self.snake2.draw(self.screen, self.cell_size)
        for f in self.foods:
            f.draw(self.screen, self.cell_size)

        self._draw_hud_bg()
        self._draw_pvp_hud()

        if self.pvp_phase == Game.PVP_READY:
            self._draw_ready_overlay()

    def _draw_pvp_hud(self):
        w, h = self.win_w, self.win_h
        i1 = pygame.Surface((14, 14))
        i1.fill(ORANGE)
        self.screen.blit(i1, (10, 9))
        p1 = self.font_small.render(f"P1: {self.p1_score}", True, ORANGE)
        self.screen.blit(p1, (28, 5))

        i2 = pygame.Surface((14, 14))
        i2.fill(PURPLE)
        i2r = i2.get_rect(topright=(w - 10, 9))
        self.screen.blit(i2, i2r)
        p2 = self.font_small.render(f"P2: {self.p2_score}", True, PURPLE)
        p2r = p2.get_rect(topright=(w - 28, 5))
        self.screen.blit(p2, p2r)

        if self.pvp_phase != Game.PVP_READY:
            h1 = self.font_small.render("P1: ↑↓←→", True, ORANGE)
            self.screen.blit(h1, (10, h - 26))
            h2 = self.font_small.render("P2: WASD  R重开", True, PURPLE)
            h2r = h2.get_rect(topright=(w - 10, h - 26))
            self.screen.blit(h2, h2r)

    def _draw_ready_overlay(self, battle=False):
        w, h = self.win_w, self.win_h
        ov = pygame.Surface((w, h))
        ov.set_alpha(155)
        ov.fill(BLACK)
        self.screen.blit(ov, (0, 0))

        if battle:
            t = self.font_large.render("战 斗 模 式", True, WHITE)
            tr = t.get_rect(center=(w // 2, 130))
            self.screen.blit(t, tr)
            lives = self.p1_lives  # 双方生命数相同
            sub = self.font_small.render(f"每人 {lives} 条命 · 子弹命中对方扣 1 命", True, GRAY)
            sr = sub.get_rect(center=(w // 2, 190))
            self.screen.blit(sub, sr)
            p1_y, p2_y, wait_y, hint_y = 260, 320, 390, 500
            hint_text = "P1 射击: [\\] 键  |  P2 射击: [F] 键"
        else:
            t = self.font_large.render("等 待 准 备", True, WHITE)
            tr = t.get_rect(center=(w // 2, 180))
            self.screen.blit(t, tr)
            p1_y, p2_y, wait_y, hint_y = 280, 340, 410, 520
            hint_text = "准备好后按对应键确认"

        i1 = pygame.Surface((22, 22))
        i1.fill(ORANGE)
        self.screen.blit(i1, (w // 2 - 140, p1_y))
        p1t = "已准备 ✓" if self.p1_ready else "按 P 准备"
        p1c = GREEN if self.p1_ready else GRAY
        p1s = self.font_medium.render(f"P1: {p1t}", True, p1c)
        self.screen.blit(p1s, (w // 2 - 110, p1_y - 4))

        i2 = pygame.Surface((22, 22))
        i2.fill(PURPLE)
        self.screen.blit(i2, (w // 2 - 140, p2_y))
        p2t = "已准备 ✓" if self.p2_ready else "按 R 准备"
        p2c = GREEN if self.p2_ready else GRAY
        p2s = self.font_medium.render(f"P2: {p2t}", True, p2c)
        self.screen.blit(p2s, (w // 2 - 110, p2_y - 4))

        if self.p1_ready and not self.p2_ready:
            wt = self.font_small.render("等待 P2 准备...", True, GRAY)
            wr = wt.get_rect(center=(w // 2, wait_y))
            self.screen.blit(wt, wr)
        elif self.p2_ready and not self.p1_ready:
            wt = self.font_small.render("等待 P1 准备...", True, GRAY)
            wr = wt.get_rect(center=(w // 2, wait_y))
            self.screen.blit(wt, wr)

        hint = self.font_small.render(hint_text, True, GRAY_DARK)
        hr = hint.get_rect(center=(w // 2, hint_y))
        self.screen.blit(hint, hr)

    def _draw_pvp_battle(self):
        self.screen.fill(DARK_BG)
        self._draw_grid()
        self.snake1.draw(self.screen, self.cell_size)
        self.snake2.draw(self.screen, self.cell_size)
        for f in self.foods:
            f.draw(self.screen, self.cell_size)
        for b in self.p1_bullets + self.p2_bullets:
            b.draw(self.screen, self.cell_size)

        self._draw_hud_bg()
        self._draw_battle_hud()

        if self.pvp_phase == Game.PVP_READY:
            self._draw_ready_overlay(battle=True)

    def _draw_battle_hud(self):
        w, h = self.win_w, self.win_h
        # P1 信息
        i1 = pygame.Surface((14, 14))
        i1.fill(ORANGE)
        self.screen.blit(i1, (10, 9))
        p1 = self.font_small.render(
            f"P1: {self.p1_score}分", True, ORANGE)
        self.screen.blit(p1, (28, 5))
        # P1 生命
        for i in range(self.p1_lives):
            lx = 28 + p1.get_width() + 10 + i * 18
            pygame.draw.rect(self.screen, ORANGE, (lx, 10, 12, 12),
                             border_radius=3)

        # P2 信息
        i2 = pygame.Surface((14, 14))
        i2.fill(PURPLE)
        i2r = i2.get_rect(topright=(w - 10, 9))
        self.screen.blit(i2, i2r)
        p2 = self.font_small.render(f"P2: {self.p2_score}分", True, PURPLE)
        p2r = p2.get_rect(topright=(w - 28, 5))
        self.screen.blit(p2, p2r)
        # P2 生命
        for i in range(self.p2_lives):
            lx = w - 28 - p2.get_width() - 16 - (self.p2_lives - i) * 18
            pygame.draw.rect(self.screen, PURPLE, (lx, 10, 12, 12),
                             border_radius=3)

        if self.pvp_phase != Game.PVP_READY:
            h1 = self.font_small.render("P1: ↑↓←→ 射击[\\]", True, ORANGE)
            self.screen.blit(h1, (10, h - 26))
            h2 = self.font_small.render("P2: WASD 射击[F]  R重开", True, PURPLE)
            h2r = h2.get_rect(topright=(w - 10, h - 26))
            self.screen.blit(h2, h2r)

    def _draw_game_over(self):
        w, h = self.win_w, self.win_h
        if self.game_over_bg and self.game_over_bg.get_size() == (w, h):
            self.screen.blit(self.game_over_bg, (0, 0))
            veil = pygame.Surface((w, h), pygame.SRCALPHA)
            veil.fill((0, 0, 0, 170))
            self.screen.blit(veil, (0, 0))
        else:
            self.screen.fill(DARK_BG)

        if self.mode in (Game.CLASSIC, Game.CLASSIC_AI):
            go = self.font_large.render("Game Over", True, RED)
            go_r = go.get_rect(center=(w // 2, h // 2 - 100))
            self.screen.blit(go, go_r)

            sc = self.font_medium.render(f"得分: {self.score}", True, WHITE)
            sc_r = sc.get_rect(center=(w // 2, h // 2 - 30))
            self.screen.blit(sc, sc_r)

            hs = self.font_small.render(
                f"最高分: {self.high_score_mgr.get_high_score()}", True, GRAY)
            hs_r = hs.get_rect(center=(w // 2, h // 2 + 10))
            self.screen.blit(hs, hs_r)
        else:
            if self.winner == 0:
                msg, clr = "平 局 !", WHITE
            elif self.winner == 1:
                msg, clr = "P1 胜 利 !", ORANGE
            else:
                msg, clr = "P2 胜 利 !", PURPLE

            win = self.font_large.render(msg, True, clr)
            win_r = win.get_rect(center=(w // 2, h // 2 - 100))
            self.screen.blit(win, win_r)

            info = self.font_medium.render(
                f"P1 {self.p1_score}  :  {self.p2_score} P2", True, WHITE)
            info_r = info.get_rect(center=(w // 2, h // 2 - 35))
            self.screen.blit(info, info_r)

            if self.mode == Game.PVP_BATTLE:
                lives_info = self.font_small.render(
                    f"P1 剩余生命: {max(0, self.p1_lives)}    "
                    f"P2 剩余生命: {max(0, self.p2_lives)}", True, GRAY)
                lr = lives_info.get_rect(center=(w // 2, h // 2 + 5))
                self.screen.blit(lives_info, lr)

        lines = [
            "SPACE 返回菜单    R 重新开始    Q 退出",
        ]
        for i, line in enumerate(lines):
            ht = self.font_small.render(line, True, WHITE)
            hr = ht.get_rect(center=(w // 2, h // 2 + 80 + i * 30))
            self.screen.blit(ht, hr)

    # ═══════════════════════════════════════════
    # 主游戏循环
    # ═══════════════════════════════════════════
    def _get_speed_key(self):
        if self.mode == Game.PVP:
            return "pvp_collision_speed_idx"
        elif self.mode == Game.PVP_BATTLE:
            return "pvp_battle_speed_idx"
        elif self.mode == Game.CLASSIC_AI:
            return "classic_speed_idx"
        return "classic_speed_idx"

    def run(self):
        running = True
        RENDER_FPS = 60
        last_time = pygame.time.get_ticks()
        accumulator = 0.0

        while running:
            current_time = pygame.time.get_ticks()
            dt = current_time - last_time
            last_time = current_time

            running = self.handle_input()

            # 游戏逻辑以设定速度运行，渲染和输入始终 60 FPS
            if self.state in (Game.CLASSIC, Game.CLASSIC_AI, Game.PVP, Game.PVP_BATTLE):
                speed_fps = self.settings.get_speed_fps(self._get_speed_key())
                move_interval = 1000.0 / speed_fps
                accumulator += dt
                if accumulator > 500:  # 防止切窗回来瞬间跳帧
                    accumulator = 500.0
                while accumulator >= move_interval:
                    self.update()
                    accumulator -= move_interval

            self.draw(dt)
            self.clock.tick(RENDER_FPS)

        pygame.quit()
        sys.exit()


# ═══════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    game = Game()
    game.run()
