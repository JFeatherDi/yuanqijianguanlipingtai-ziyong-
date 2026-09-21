"""登录验证码：服务端生成图片，答案只留在服务端内存里。

为什么不用 Pillow：部署机按 requirements.txt 只装 flask/openpyxl/waitress，
镜像源也不保证可达，为了一个验证码引入图像库不划算。所以这里自带一套
5x7 点阵字模，PNG 用 zlib + struct 手写（PNG 的 IDAT 就是 zlib 流，够用了）。

为什么答案不放进 Flask 会话：Flask 的会话 cookie 只签名不加密，客户端能直接
解出里面的内容。把答案写进会话等于把答案发给客户端，脚本读一下自己的 cookie
就绕过了。所以会话里只放一个随机 id，答案留在进程内存里（security.py 的
失败计数也是同一套思路）。waitress 是单进程多线程，内存字典足够。

输出尺寸是前端的 2 倍（前端按 112x36 显示），缩小绘制的插值顺便充当抗锯齿，
省掉在纯 Python 里做超采样。
"""
from __future__ import annotations

import hmac
import math
import random
import secrets
import struct
import threading
import time
import zlib

from flask import session

# 剔掉了 0/O、1/I/L 这类容易看错的字符：4 位 × 31 个字符约 92 万种组合
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LENGTH = 4
TTL_SECONDS = 180
SESSION_KEY = "captcha_id"

WIDTH = 224  # 前端按 112 显示
HEIGHT = 72  # 前端按 36 显示
CELL = 6  # 字模 1 格 -> 6 像素
BG = (247, 250, 254)

# 单色描画的干扰线：太亮会盖住字，太暗又起不到干扰作用
VEIL = (178, 203, 231)
DUST = (200, 219, 240)

# 逐字取色，让四个字有轻微的深浅差
INKS = ((43, 106, 176), (31, 88, 150), (58, 132, 202), (36, 99, 168))

# 字模尺寸：5x7 格，每格 CELL 像素
GLYPH_W = 5 * CELL
GLYPH_H = 7 * CELL

# 5x7 点阵字模，'#' 为实体
GLYPHS = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "D": ("###..", "#..#.", "#...#", "#...#", "#...#", "#..#.", "###.."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "M": ("#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#...#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": ("..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."),
}

# ---------------------------------------------------------------- 画布

_lock = threading.Lock()
# id -> (答案小写, 签发时间)。只存在于进程内存，不落盘、不进 cookie
_entries: dict[str, tuple[str, float]] = {}


def _put(buf: bytearray, x: int, y: int, color) -> None:
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        i = (y * WIDTH + x) * 3
        buf[i] = color[0]
        buf[i + 1] = color[1]
        buf[i + 2] = color[2]


def _line(buf, x0, y0, x1, y1, color, brush=1) -> None:
    steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for i in range(steps + 1):
        t = i / steps
        x = int(x0 + (x1 - x0) * t)
        y = int(y0 + (y1 - y0) * t)
        for dx in range(brush):
            for dy in range(brush):
                _put(buf, x + dx, y + dy, color)


def _draw_glyph(buf, glyph, cx: float, cy: float, angle: float, color) -> None:
    """以 (cx, cy) 为中心，把字模按 angle 度旋转后画上去。

    做法是反向采样：遍历旋转后包围盒里的每个画布像素，转回字模坐标系看它
    落不落在实体格上。比正向变换简单，也不会在旋转后留下空洞。
    """
    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    reach = int(math.ceil((abs(cos_a) * GLYPH_W + abs(sin_a) * GLYPH_H) / 2)) + 1

    for py in range(int(cy) - reach, int(cy) + reach + 1):
        if not 0 <= py < HEIGHT:
            continue
        for px in range(int(cx) - reach, int(cx) + reach + 1):
            if not 0 <= px < WIDTH:
                continue
            dx, dy = px + 0.5 - cx, py + 0.5 - cy
            lx = dx * cos_a + dy * sin_a + GLYPH_W / 2
            ly = -dx * sin_a + dy * cos_a + GLYPH_H / 2
            if not (0 <= lx < GLYPH_W and 0 <= ly < GLYPH_H):
                continue
            if glyph[int(ly // CELL)][int(lx // CELL)] == "#":
                _put(buf, px, py, color)


def _encode_png(width: int, height: int, buf: bytearray) -> bytes:
    """手写 PNG：8 位真彩，无行间滤波。"""
    stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # 每行前置一个 filter type
        raw += buf[y * stride : (y + 1) * stride]

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


def _render_tile(code: str) -> bytearray:
    """把 4 个字符画进一块 WIDTH x HEIGHT 的 RGB 缓冲。"""
    rng = random.Random()
    buf = bytearray(BG * (WIDTH * HEIGHT))

    # 4 个字均分画布，各自抖一点位置和角度。摆位按「旋转后的外接框」夹一次，
    # 否则斜过来的字会被画布边缘切掉一角。
    slot = WIDTH / len(code)
    for index, char in enumerate(code):
        angle = rng.uniform(-26, 26)
        rad = math.radians(angle)
        cos_a, sin_a = abs(math.cos(rad)), abs(math.sin(rad))
        half_w = (cos_a * GLYPH_W + sin_a * GLYPH_H) / 2
        half_h = (sin_a * GLYPH_W + cos_a * GLYPH_H) / 2
        cx = min(max(slot * (index + 0.5) + rng.uniform(-3, 3), half_w + 2), WIDTH - half_w - 2)
        cy = min(max(HEIGHT / 2 + rng.uniform(-6, 6), half_h + 2), HEIGHT - half_h - 2)
        _draw_glyph(buf, GLYPHS[char], cx, cy, angle, rng.choice(INKS))

    # 干扰线：折成 4 段，看起来比直线更像手划的
    for _ in range(3):
        x, y = 0, rng.uniform(6, HEIGHT - 6)
        for _ in range(4):
            nx = x + WIDTH / 4
            ny = min(max(y + rng.uniform(-22, 22), 2), HEIGHT - 3)
            _line(buf, x, y, nx, ny, VEIL, brush=2)
            x, y = nx, ny

    # 噪点只撒在字的空隙里：落在字上会把笔画吃掉
    for _ in range(70):
        _put(buf, rng.randrange(WIDTH), rng.randrange(HEIGHT), DUST)

    return buf


def render(code: str) -> bytes:
    """把 4 个字符画成一张 PNG。"""
    return _encode_png(WIDTH, HEIGHT, _render_tile(code))


# ---------------------------------------------------------------- 签发与校验


def issue() -> tuple[str, bytes]:
    """签发一张新验证码：返回 (明文, PNG)，明文留在服务端。"""
    code = "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
    token = secrets.token_urlsafe(16)
    now = time.time()

    with _lock:
        # 顺手清掉过期条目，长期运行的进程内存不会只涨不落
        for key in [k for k, (_, ts) in _entries.items() if now - ts > TTL_SECONDS]:
            _entries.pop(key, None)
        _entries[token] = (code.lower(), now)
        # 同一会话重复取图时丢掉上一张，避免攒下用不到的条目
        previous = session.get(SESSION_KEY)
        if previous:
            _entries.pop(previous, None)

    session[SESSION_KEY] = token
    return code, render(code)


def verify(answer: str) -> bool:
    """校验并作废当前验证码：无论对错都只能消费一次，防重放。"""
    token = session.pop(SESSION_KEY, None)
    if not token:
        return False
    with _lock:
        entry = _entries.pop(token, None)
    if not entry:
        return False
    code, issued_at = entry
    if time.time() - issued_at > TTL_SECONDS:
        return False
    return hmac.compare_digest(code, (answer or "").strip().lower())
