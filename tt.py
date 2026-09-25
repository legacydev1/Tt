"""
Ultimate ASCII / ANSI Studio Bot — Complete Edition
---------------------------------------------------
- Auto pip-installs dependencies on first run
- Prints clear /start instructions to the terminal
- 33 named colors, each with its own inline button
- Custom hex color input support
- Gradient color mode with direction control
- Catbox image link sent on /start
- Text → Banner (500+ FIGlet fonts)
- Image → Art (4 styles, 4 color modes)
- Full size control (width, scale, aspect, contrast, invert)
- Export: .txt / .html / .ansi / .png

Programmer : Jason
Channel    : @eliteworks1
"""

from __future__ import annotations

import subprocess
import sys
import importlib
import pkgutil


# ===========================================================================
#  AUTO-INSTALL DEPENDENCIES
# ===========================================================================

REQUIRED = {
    "telegram": "python-telegram-bot==21.6",
    "PIL":      "Pillow==10.4.0",
    "pyfiglet": "pyfiglet==1.0.2",
}


def _ensure(pkg_import: str, pip_spec: str) -> None:
    """Install pip_spec if pkg_import is not importable."""
    if pkgutil.find_loader(pkg_import) is not None:
        return
    print(f"\n[INSTALL] {pip_spec} ...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", pip_spec]
        )
    except subprocess.CalledProcessError:
        print(f"\n[ERROR] Failed to install {pip_spec}")
        print("Run manually:")
        print(f"  {sys.executable} -m pip install {pip_spec}\n")
        sys.exit(1)


print("[CHECK] Verifying dependencies ...")
for imp, spec in REQUIRED.items():
    _ensure(imp, spec)
importlib.invalidate_caches()


# ---------------------------------------------------------------------------
#  Imports (all available now)
# ---------------------------------------------------------------------------

import html
import io
import logging
import re
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

try:
    import pyfiglet
    from pyfiglet import Figlet, FigletFont
    HAS_FIGLET = True
except ImportError:
    HAS_FIGLET = False


# ===========================================================================
#  CONFIGURATION
# ===========================================================================

BOT_TOKEN = "8245360364:AAGB1xYGpUIN9OsdS9RjUQyouHX0eQTPC_c"   # <-- your bot token here
ALLOWED_CHAT_ID = "7669164275"                                  # <-- your chat id (empty = allow all)

# Catbox image link sent on /start (leave empty to skip)
CATBOX_IMAGE_URL = "https://files.catbox.moe/61tqb5.png"

CATBOX_CAPTION = (
    "🎨 *Welcome to ASCII / ANSI Studio!*\n\n"
    "This bot converts text and images into ASCII art.\n"
    "Use the menu below to get started 👇\n\n"
    "👨‍💻 *Jason*  •  📢 @eliteworks1"
)


# ===========================================================================
#  COLOR PALETTE — 33 named colors
# ===========================================================================

COLORS = {
    # Basic
    "white":    (255, 255, 255),
    "black":    (0, 0, 0),
    "gray":     (128, 128, 128),
    "silver":   (192, 192, 192),
    "darkgray": (64, 64, 64),

    # Red family
    "red":      (255, 0, 0),
    "crimson":  (220, 20, 60),
    "maroon":   (128, 0, 0),
    "salmon":   (250, 128, 114),
    "pink":     (255, 105, 180),

    # Orange / Yellow
    "orange":   (255, 165, 0),
    "gold":     (255, 215, 0),
    "yellow":   (255, 255, 0),
    "amber":    (255, 191, 0),

    # Green family
    "green":    (0, 255, 0),
    "lime":     (50, 205, 50),
    "matrix":   (0, 255, 120),
    "emerald":  (80, 200, 120),
    "olive":    (128, 128, 0),
    "teal":     (0, 128, 128),

    # Cyan / Blue
    "cyan":     (0, 255, 255),
    "skyblue":  (135, 206, 235),
    "blue":     (0, 100, 255),
    "navy":     (0, 0, 128),
    "royal":    (65, 105, 225),
    "indigo":   (75, 0, 130),
    "violet":   (138, 43, 226),

    # Purple / Magenta
    "purple":   (160, 32, 240),
    "magenta":  (255, 0, 255),
    "fuchsia":  (255, 119, 255),

    # Warm
    "brown":    (139, 69, 19),
    "tan":      (210, 180, 140),
    "beige":    (245, 245, 220),
}


# ===========================================================================
#  GLOBAL DEFAULTS
# ===========================================================================

DEFAULT_BANNER_FONT = "standard"
DEFAULT_IMAGE_STYLE = "density"
DEFAULT_COLOR_MODE = "gray"
DEFAULT_FORMAT = "ansi"

MAX_PREVIEW = 3800

STYLES = ("density", "binary", "block", "braille")
COLOR_MODES = ("gray", "mono", "rgb", "gradient")
FORMATS = ("txt", "html", "ansi", "png")

ANSI_GRAY_START = 232
ANSI_GRAY_END = 255

RAMP_DENSITY = " .:•●⬤"
RAMP_BINARY = ". "
RAMP_BLOCK = " ░▒▓█"
RAMP_BRAILLE = " ⠁⠉⠋⠛⠟⠿⡿⣿"

MIN_WIDTH, MAX_WIDTH = 40, 400
MIN_BANNER_WIDTH, MAX_BANNER_WIDTH = 40, 300
MIN_SCALE, MAX_SCALE = 1, 4
MIN_ASPECT, MAX_ASPECT = 0.3, 1.2
MIN_CONTRAST, MAX_CONTRAST = 0.5, 3.0


# ===========================================================================
#  PER-USER STATE
# ===========================================================================

@dataclass
class UserState:
    # Banner
    banner_font: str = DEFAULT_BANNER_FONT
    banner_width: int = 200
    banner_scale: int = 1
    banner_color: str = "matrix"

    # Image
    image_style: str = DEFAULT_IMAGE_STYLE
    color_mode: str = DEFAULT_COLOR_MODE
    image_color: str = "matrix"
    image_color2: str = "cyan"
    gradient_dir: str = "vertical"
    width: int = 140
    scale: int = 1
    aspect: float = 0.5
    contrast: float = 1.0
    invert: bool = False

    # Export
    fmt: str = DEFAULT_FORMAT

    # Mode
    mode: str = "idle"


USERS: dict[int, UserState] = {}


def get_user(uid: int) -> UserState:
    if uid not in USERS:
        USERS[uid] = UserState()
    return USERS[uid]


# ===========================================================================
#  LOGGING
# ===========================================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger("studio")


# ===========================================================================
#  FIGLET
# ===========================================================================

def all_figlet_fonts() -> list[str]:
    if not HAS_FIGLET:
        return []
    try:
        return sorted(FigletFont.getFonts())
    except Exception:
        return []


ALL_FONTS = all_figlet_fonts()
FONT_COUNT = len(ALL_FONTS)


def find_fonts(query: str) -> list[str]:
    q = query.lower().strip()
    if not q:
        return ALL_FONTS
    return [f for f in ALL_FONTS if q in f.lower()]


def render_banner(text: str, font: str, width: int, scale: int) -> str:
    if not HAS_FIGLET:
        raise RuntimeError("pyfiglet is not installed")
    try:
        fig = Figlet(font=font, width=max(40, width))
        raw = fig.renderText(text)
    except Exception as exc:
        raise ValueError(f"Font '{font}' failed to render: {exc}") from exc
    if scale > 1:
        raw = _scale_text(raw, scale)
    return raw


def _scale_text(text: str, scale: int) -> str:
    if scale <= 1:
        return text
    lines = text.split("\n")
    out = []
    for line in lines:
        stretched = "".join(ch * scale for ch in line)
        for _ in range(scale):
            out.append(stretched)
    return "\n".join(out)


# ===========================================================================
#  COLOR HELPERS
# ===========================================================================

HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def parse_hex(s: str):
    s = s.strip().lstrip("#")
    if not HEX_RE.match(s):
        return None
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def resolve_color(name: str, fallback=(0, 255, 120)):
    if not name:
        return fallback
    key = name.lower().strip().lstrip("#")
    if key in COLORS:
        return COLORS[key]
    hx = parse_hex(key)
    if hx:
        return hx
    return fallback


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_color(c1, c2, x, y, w, h, direction: str):
    if direction == "horizontal":
        t = x / max(1, w - 1)
    elif direction == "diagonal":
        t = (x + y) / max(1, (w - 1) + (h - 1))
    else:
        t = y / max(1, h - 1)
    return lerp(c1, c2, t)


# ===========================================================================
#  IMAGE → GRID
# ===========================================================================

def image_to_grid(image_bytes: bytes, width: int, style: str,
                  invert: bool = False, contrast: float = 1.0,
                  aspect: float = 0.5, scale: int = 1):
    img = Image.open(io.BytesIO(image_bytes))
    img.load()

    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)

    rgb_img = img
    gray_img = img.convert("L")
    if invert:
        gray_img = ImageOps.invert(gray_img)

    orig_w, orig_h = gray_img.size
    if orig_w <= 0 or orig_h <= 0:
        raise ValueError("Image has zero dimensions")

    ar = orig_h / orig_w
    new_w = max(1, int(width))
    new_h = max(1, int(new_w * ar * aspect))

    gray_img = gray_img.resize((new_w, new_h), Image.LANCZOS)
    rgb_img = rgb_img.resize((new_w, new_h), Image.LANCZOS)

    gp = list(gray_img.getdata())
    rp = list(rgb_img.getdata())

    ramps = {
        "density": RAMP_DENSITY,
        "binary":  RAMP_BINARY,
        "block":   RAMP_BLOCK,
        "braille": RAMP_BRAILLE,
    }
    ramp = ramps.get(style, RAMP_DENSITY)
    rl = len(ramp)

    grid = []
    for y in range(new_h):
        row = []
        base = y * new_w
        for x in range(new_w):
            v = gp[base + x]
            rgb = rp[base + x]
            idx = ((255 - v) * (rl - 1)) // 255
            row.append((ramp[idx], v, rgb))

        if scale > 1:
            expanded = []
            for cell in row:
                expanded.extend([cell] * scale)
            row = expanded

        for _ in range(scale):
            grid.append(list(row))
    return grid


# ===========================================================================
#  EXPORTERS
# ===========================================================================

def _gray_to_ansi(v: int) -> int:
    inv = 255 - v
    span = ANSI_GRAY_END - ANSI_GRAY_START
    idx = int(round((inv / 255.0) * span)) + ANSI_GRAY_START
    return max(ANSI_GRAY_START, min(ANSI_GRAY_END, idx))


def _rgb_to_ansi(rgb) -> int:
    r, g, b = rgb
    ri = round(r / 255 * 5)
    gi = round(g / 255 * 5)
    bi = round(b / 255 * 5)
    return 16 + 36 * ri + 6 * gi + bi


def _apply_color_mode(grid, color_mode: str, c1, c2, direction: str):
    if not grid:
        return grid
    h = len(grid)
    w = max(len(r) for r in grid)

    out = []
    for y, row in enumerate(grid):
        new_row = []
        for x, (ch, v, rgb) in enumerate(row):
            if color_mode == "rgb":
                final = rgb
            elif color_mode == "mono":
                brightness = (255 - v) / 255.0
                final = tuple(int(c * brightness) for c in c1)
            elif color_mode == "gradient":
                base = gradient_color(c1, c2, x, y, w, h, direction)
                brightness = (255 - v) / 255.0
                final = tuple(int(c * brightness) for c in base)
            else:
                g = 255 - v
                final = (g, g, g)
            new_row.append((ch, v, final))
        out.append(new_row)
    return out


def export_txt(grid) -> bytes:
    lines = ["".join(c[0] for c in row) for row in grid]
    return ("\n".join(lines) + "\n").encode("utf-8")


def export_html(grid, title: str = "ASCII Art") -> bytes:
    rows_html = []
    for row in grid:
        spans = []
        for ch, _v, rgb in row:
            safe = "&nbsp;" if ch == " " else html.escape(ch)
            r, g, b = rgb
            spans.append(f'<span style="color:rgb({r},{g},{b})">{safe}</span>')
        rows_html.append("".join(spans))
    body = "\n".join(rows_html)
    doc = (
        "<!DOCTYPE html>\n<html lang='en'><head>\n"
        "<meta charset='utf-8'>\n"
        f"<title>{html.escape(title)}</title>\n"
        "<style>\n"
        "html,body{margin:0;padding:0;background:#000;color:#eee;"
        "font-family:'Consolas','Menlo','DejaVu Sans Mono',monospace;"
        "font-size:10px;line-height:1.0;}\n"
        "pre{margin:0;padding:12px;white-space:pre;display:inline-block;}\n"
        ".meta{color:#666;font-size:11px;padding:8px 12px;"
        "font-family:sans-serif;}\n"
        "</style></head><body>\n"
        '<div class="meta">ASCII Studio · @eliteworks1 · Jason</div>\n'
        f"<pre>{body}</pre></body></html>\n"
    )
    return doc.encode("utf-8")


def export_ansi(grid) -> bytes:
    out_lines = []
    for row in grid:
        chunks = []
        cur = None
        for ch, _v, rgb in row:
            if ch == " ":
                chunks.append(" ")
                continue
            idx = _rgb_to_ansi(rgb)
            if idx != cur:
                chunks.append(f"\x1b[38;5;{idx}m")
                cur = idx
            chunks.append(ch)
        chunks.append("\x1b[0m")
        out_lines.append("".join(chunks))
    return ("\n".join(out_lines) + "\n").encode("utf-8")


def _load_font(size):
    for path in (
        "DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "consola.ttf", "cour.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def export_png(grid, font_size: int = 14, bg=(0, 0, 0)) -> bytes:
    font = _load_font(font_size)
    if not grid:
        raise ValueError("Empty grid")

    try:
        bbox = font.getbbox("M")
        cw = bbox[2] - bbox[0] or font_size // 2
        ch = bbox[3] - bbox[1] or font_size
    except Exception:
        cw, ch = font_size // 2, font_size

    line_h = int(ch * 1.15)
    cols = max(len(r) for r in grid)
    rows = len(grid)

    img = Image.new("RGB", (cols * cw + 20, rows * line_h + 20), bg)
    draw = ImageDraw.Draw(img)

    for y, row in enumerate(grid):
        for x, (c, _v, rgb) in enumerate(row):
            if c == " ":
                continue
            draw.text((10 + x * cw, 10 + y * line_h), c, font=font, fill=rgb)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


def banner_to_grid(banner_text: str):
    grid = []
    for line in banner_text.split("\n"):
        row = []
        for ch in line:
            if ch == " ":
                row.append((ch, 255, (0, 0, 0)))
            else:
                row.append((ch, 0, (255, 255, 255)))
        grid.append(row)
    return grid


def _export_grid(grid, fmt: str):
    fmt = fmt.lower()
    if fmt == "txt":
        return export_txt(grid), "art.txt", "text/plain"
    if fmt == "html":
        return export_html(grid), "art.html", "text/html"
    if fmt == "ansi":
        return export_ansi(grid), "art.ansi", "text/plain"
    if fmt == "png":
        return export_png(grid), "art.png", "image/png"
    raise ValueError(f"Unknown format: {fmt}")


# ===========================================================================
#  UI HELPERS
# ===========================================================================

def _mark(active: bool, label: str) -> str:
    return f"✅ {label}" if active else label


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️  Text → Banner", callback_data="menu:banner")],
        [InlineKeyboardButton("🖼️  Image → Art",   callback_data="menu:image")],
        [InlineKeyboardButton("📐 Size Presets",  callback_data="menu:presets")],
        [InlineKeyboardButton("🎨 Colors",        callback_data="menu:colors")],
        [InlineKeyboardButton("📦 Export Format", callback_data="menu:format")],
    ])


def banner_menu_kb(u: UserState) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔤 Choose Font",  callback_data="ban:fonts:0")],
        [InlineKeyboardButton("🔍 Search Font",  callback_data="ban:search")],
        [InlineKeyboardButton(f"📏 Width: {u.banner_width}",
                              callback_data="ban:w:show")],
        [InlineKeyboardButton(f"📐 Scale: {u.banner_scale}x",
                              callback_data="ban:s:show")],
        [InlineKeyboardButton(f"🎨 Color: {u.banner_color}",
                              callback_data="menu:colors:banner")],
        [InlineKeyboardButton("📥 Export Format", callback_data="menu:format")],
        [InlineKeyboardButton("⬅️ Back",           callback_data="menu:main")],
    ])


def banner_width_kb(u: UserState) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("− 20", callback_data="ban:w:-20"),
         InlineKeyboardButton(f"{u.banner_width}", callback_data="ban:w:show"),
         InlineKeyboardButton("+ 20", callback_data="ban:w:+20")],
        [InlineKeyboardButton("− 50", callback_data="ban:w:-50"),
         InlineKeyboardButton("+ 50", callback_data="ban:w:+50")],
        [InlineKeyboardButton("✏️ Type exact value", callback_data="ban:w:type")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:banner")],
    ])


def banner_scale_kb(u: UserState) -> InlineKeyboardMarkup:
    row = []
    for s in range(MIN_SCALE, MAX_SCALE + 1):
        row.append(InlineKeyboardButton(
            _mark(u.banner_scale == s, f"{s}x"),
            callback_data=f"ban:s:{s}"))
    return InlineKeyboardMarkup([
        row,
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:banner")],
    ])


def image_menu_kb(u: UserState) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_mark(u.image_style == "density", "Density ●"),
                              callback_data="img:style:density"),
         InlineKeyboardButton(_mark(u.image_style == "binary", "Binary ."),
                              callback_data="img:style:binary")],
        [InlineKeyboardButton(_mark(u.image_style == "block", "Block ▓"),
                              callback_data="img:style:block"),
         InlineKeyboardButton(_mark(u.image_style == "braille", "Braille ⣿"),
                              callback_data="img:style:braille")],

        [InlineKeyboardButton(_mark(u.color_mode == "gray", "Gray"),
                              callback_data="img:color:gray"),
         InlineKeyboardButton(_mark(u.color_mode == "mono", "Mono"),
                              callback_data="img:color:mono")],
        [InlineKeyboardButton(_mark(u.color_mode == "rgb", "RGB 🌈"),
                              callback_data="img:color:rgb"),
         InlineKeyboardButton(_mark(u.color_mode == "gradient", "Gradient 🎨"),
                              callback_data="img:color:gradient")],

        [InlineKeyboardButton(f"🎨 Color 1: {u.image_color}",
                              callback_data="menu:colors:img1"),
         InlineKeyboardButton(f"🎨 Color 2: {u.image_color2}",
                              callback_data="menu:colors:img2")],
        [InlineKeyboardButton(f"↘️ Gradient: {u.gradient_dir}",
                              callback_data="img:gradir:show")],

        [InlineKeyboardButton(f"📏 Width: {u.width}",
                              callback_data="img:w:show"),
         InlineKeyboardButton(f"📐 Scale: {u.scale}x",
                              callback_data="img:s:show")],
        [InlineKeyboardButton(f"🧭 Aspect: {u.aspect:.1f}",
                              callback_data="img:a:show"),
         InlineKeyboardButton(f"🌗 Contrast: {u.contrast:.2f}",
                              callback_data="img:c:show")],
        [InlineKeyboardButton(_mark(u.invert, "Invert"),
                              callback_data="img:invert")],

        [InlineKeyboardButton("📦 Export Format", callback_data="menu:format")],
        [InlineKeyboardButton("⬅️ Back",           callback_data="menu:main")],
    ])


def image_width_kb(u: UserState) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("− 20", callback_data="img:w:-20"),
         InlineKeyboardButton(f"{u.width}", callback_data="img:w:show"),
         InlineKeyboardButton("+ 20", callback_data="img:w:+20")],
        [InlineKeyboardButton("− 60", callback_data="img:w:-60"),
         InlineKeyboardButton("+ 60", callback_data="img:w:+60")],
        [InlineKeyboardButton("✏️ Type exact value", callback_data="img:w:type")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:image")],
    ])


def image_scale_kb(u: UserState) -> InlineKeyboardMarkup:
    row = []
    for s in range(MIN_SCALE, MAX_SCALE + 1):
        row.append(InlineKeyboardButton(
            _mark(u.scale == s, f"{s}x"),
            callback_data=f"img:s:{s}"))
    return InlineKeyboardMarkup([
        row,
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:image")],
    ])


def image_aspect_kb(u: UserState) -> InlineKeyboardMarkup:
    row = []
    for a in [0.3, 0.4, 0.5, 0.6, 0.8, 1.0]:
        row.append(InlineKeyboardButton(
            _mark(abs(u.aspect - a) < 0.01, f"{a:.1f}"),
            callback_data=f"img:a:{a}"))
    return InlineKeyboardMarkup([
        row[:3], row[3:],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:image")],
    ])


def image_contrast_kb(u: UserState) -> InlineKeyboardMarkup:
    row = []
    for c in [0.5, 0.75, 1.0, 1.5, 2.0, 3.0]:
        row.append(InlineKeyboardButton(
            _mark(abs(u.contrast - c) < 0.01, f"{c:.2f}"),
            callback_data=f"img:c:{c}"))
    return InlineKeyboardMarkup([
        row[:3], row[3:],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:image")],
    ])


def image_gradir_kb(u: UserState) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_mark(u.gradient_dir == "vertical", "↓ Vertical"),
                              callback_data="img:gradir:vertical"),
         InlineKeyboardButton(_mark(u.gradient_dir == "horizontal", "→ Horizontal"),
                              callback_data="img:gradir:horizontal")],
        [InlineKeyboardButton(_mark(u.gradient_dir == "diagonal", "↘ Diagonal"),
                              callback_data="img:gradir:diagonal")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:image")],
    ])


def format_kb(u: UserState) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_mark(u.fmt == "txt", ".txt"),
                              callback_data="fmt:txt"),
         InlineKeyboardButton(_mark(u.fmt == "html", ".html"),
                              callback_data="fmt:html")],
        [InlineKeyboardButton(_mark(u.fmt == "ansi", ".ansi"),
                              callback_data="fmt:ansi"),
         InlineKeyboardButton(_mark(u.fmt == "png", "PNG"),
                              callback_data="fmt:png")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:main")],
    ])


def presets_kb(u: UserState) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Small (80w, 1x)",
                              callback_data="pre:small"),
         InlineKeyboardButton("🖥️ Medium (140w, 1x)",
                              callback_data="pre:medium")],
        [InlineKeyboardButton("🎞️ Large (220w, 1x)",
                              callback_data="pre:large"),
         InlineKeyboardButton("🖼️ Poster (200w, 2x)",
                              callback_data="pre:poster")],
        [InlineKeyboardButton("🐘 Huge (250w, 3x)",
                              callback_data="pre:huge")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:main")],
    ])


def color_menu_kb(target: str, current: str) -> InlineKeyboardMarkup:
    names = list(COLORS.keys())
    rows = []
    row = []
    for name in names:
        label = _mark(name == current, name)
        row.append(InlineKeyboardButton(
            label, callback_data=f"col:set:{target}:{name}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton(
        "✏️ Custom HEX (#RRGGBB)",
        callback_data=f"col:hex:{target}")])
    rows.append([InlineKeyboardButton(
        "⬅️ Back",
        callback_data="menu:banner" if target == "banner"
        else "menu:image")])
    return InlineKeyboardMarkup(rows)


# ===========================================================================
#  UI SCREENS
# ===========================================================================

def _header() -> str:
    return (
        "╔════════════════════════════════╗\n"
        "║   🎨  ASCII  /  ANSI  STUDIO   ║\n"
        "╚════════════════════════════════╝"
    )


def _footer() -> str:
    return "👨‍💻 *Jason*  •  📢 @eliteworks1"


def welcome_text(u: UserState) -> str:
    fc = FONT_COUNT if HAS_FIGLET else 0
    return (
        f"{_header()}\n\n"
        "One *all-in-one* tool — convert text or images\n"
        "into ASCII / ANSI art. Every size and color is\n"
        "fully customizable. 🚀\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✍️  *Text → Banner*\n"
        f"   • {fc}+ FIGlet fonts\n"
        "   • Custom width and scale\n"
        "   • 33 colors + custom hex\n\n"
        "🖼️  *Image → Art*\n"
        "   • 4 styles: density / binary / block / braille\n"
        "   • 4 color modes: gray / mono / rgb / gradient\n"
        "   • 33 colors + custom hex\n"
        "   • Width 40–400, Scale 1x–4x\n"
        "   • Aspect, contrast, invert\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Format: *{u.fmt.upper()}*   "
        f"🎨 Color: *{u.image_color}*   "
        f"📏 Width: *{u.width}*\n\n"
        "Choose a tool below 👇\n\n"
        f"{_footer()}"
    )


def banner_screen(u: UserState) -> str:
    return (
        "✍️ *Text → Banner*\n\n"
        "Send your text — I will convert it into a banner.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔤 Font  : `{u.banner_font}`\n"
        f"📏 Width : `{u.banner_width}`\n"
        f"📐 Scale : `{u.banner_scale}x`\n"
        f"🎨 Color : `{u.banner_color}`\n"
        f"📦 Format: `{u.fmt.upper()}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Adjust settings with the buttons, then send your text:"
    )


def image_screen(u: UserState) -> str:
    return (
        "🖼️ *Image → Art*\n\n"
        "Send your image — I will convert it into ASCII art.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎨 Style     : `{u.image_style}`\n"
        f"🌈 Color mode: `{u.color_mode}`\n"
        f"🎨 Color 1   : `{u.image_color}`\n"
        f"🎨 Color 2   : `{u.image_color2}`  (gradient)\n"
        f"↘️ Gradient  : `{u.gradient_dir}`\n"
        f"📏 Width     : `{u.width}`\n"
        f"📐 Scale     : `{u.scale}x`\n"
        f"🧭 Aspect    : `{u.aspect:.1f}`\n"
        f"🌗 Contrast  : `{u.contrast:.2f}`\n"
        f"🔄 Invert    : `{u.invert}`\n"
        f"📦 Format    : `{u.fmt.upper()}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Adjust settings with the buttons, then send your image:"
    )


def colors_hub_screen(u: UserState) -> str:
    return (
        "🎨 *Colors Hub*\n\n"
        "Choose which color to configure:\n\n"
        f"✍️ Banner color    : `{u.banner_color}`\n"
        f"🖼️ Image color 1   : `{u.image_color}`\n"
        f"🖼️ Image color 2   : `{u.image_color2}`\n"
        f"↘️ Gradient dir    : `{u.gradient_dir}`"
    )


def colors_hub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Banner Color",
                              callback_data="menu:colors:banner")],
        [InlineKeyboardButton("🖼️ Image Color 1 (mono/gradient)",
                              callback_data="menu:colors:img1")],
        [InlineKeyboardButton("🖼️ Image Color 2 (gradient end)",
                              callback_data="menu:colors:img2")],
        [InlineKeyboardButton("↘️ Gradient Direction",
                              callback_data="img:gradir:show")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:main")],
    ])


# ===========================================================================
#  COMMANDS
# ===========================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = get_user(update.effective_user.id)
    u.mode = "idle"

    if CATBOX_IMAGE_URL and CATBOX_IMAGE_URL.startswith("http"):
        try:
            await update.message.reply_photo(
                photo=CATBOX_IMAGE_URL,
                caption=CATBOX_CAPTION,
                parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramError as exc:
            log.warning("Catbox image send failed: %s", exc)

    await update.message.reply_text(
        welcome_text(u),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_kb(),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def cmd_banner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = get_user(update.effective_user.id)
    u.mode = "awaiting_banner_text"
    await update.message.reply_text(
        banner_screen(u),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=banner_menu_kb(u),
    )


async def cmd_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = get_user(update.effective_user.id)
    u.mode = "awaiting_image"
    await update.message.reply_text(
        image_screen(u),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=image_menu_kb(u),
    )


async def cmd_fonts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = get_user(update.effective_user.id)
    await update.message.reply_text(
        f"🔤 *FIGlet Fonts*  ({FONT_COUNT} available)\n\n"
        f"Current: `{u.banner_font}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=font_list_kb(0),
    )


async def cmd_font(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = get_user(update.effective_user.id)
    args = context.args or []
    if not args:
        await cmd_fonts(update, context)
        return
    q = " ".join(args).strip()
    matches = find_fonts(q)
    if not matches:
        await update.message.reply_text(f"❌ No font matched `{q}`.",
                                        parse_mode=ParseMode.MARKDOWN)
        return
    exact = [f for f in matches if f.lower() == q.lower()]
    if exact:
        u.banner_font = exact[0]
        await update.message.reply_text(
            f"✅ Font set: `{u.banner_font}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    await update.message.reply_text(
        f"🔎 `{q}` → {len(matches)} fonts:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=font_list_kb(0, query=q),
    )


async def cmd_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = get_user(update.effective_user.id)
    args = context.args or []
    if not args:
        await update.message.reply_text(
            f"🎨 Current colors:\n"
            f"  Banner : `{u.banner_color}`\n"
            f"  Image1 : `{u.image_color}`\n"
            f"  Image2 : `{u.image_color2}`\n\n"
            "Usage: `/color red`  or  `/color #ff00aa`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    val = args[0].lower().lstrip("#") if args[0].startswith("#") else args[0].lower()
    if val not in COLORS and not parse_hex(val):
        await update.message.reply_text(
            f"❌ `{val}` is not a valid color.\n"
            "Try: `red`, `cyan`, `matrix`, `orange`, or `#ff00aa`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    u.banner_color = val
    u.image_color = val
    await update.message.reply_text(f"✅ Color set: `{val}`",
                                    parse_mode=ParseMode.MARKDOWN)


async def cmd_width(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = get_user(update.effective_user.id)
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            f"📏 Current width: `{u.width}`\n"
            f"Range: {MIN_WIDTH}–{MAX_WIDTH}\n"
            "Usage: `/width 200`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    u.width = max(MIN_WIDTH, min(MAX_WIDTH, int(args[0])))
    await update.message.reply_text(f"✅ Width: `{u.width}`",
                                    parse_mode=ParseMode.MARKDOWN)


async def cmd_scale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = get_user(update.effective_user.id)
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            f"📐 Current scale: `{u.scale}x`\n"
            "Usage: `/scale 2`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    u.scale = max(MIN_SCALE, min(MAX_SCALE, int(args[0])))
    await update.message.reply_text(f"✅ Scale: `{u.scale}x`",
                                    parse_mode=ParseMode.MARKDOWN)


async def cmd_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = get_user(update.effective_user.id)
    await update.message.reply_text(
        f"📦 *Export Format*\n\nCurrent: `{u.fmt.upper()}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=format_kb(u),
    )


async def cmd_colors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = get_user(update.effective_user.id)
    await update.message.reply_text(
        colors_hub_screen(u),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=colors_hub_kb(),
    )


# ===========================================================================
#  FONT LIST
# ===========================================================================

def font_list_kb(page: int, query: str = "") -> InlineKeyboardMarkup:
    fonts = find_fonts(query)
    per_page = 12
    start = page * per_page
    chunk = fonts[start:start + per_page]

    rows = []
    for i in range(0, len(chunk), 2):
        pair = chunk[i:i + 2]
        rows.append([
            InlineKeyboardButton(f, callback_data=f"ban:setfont:{f}")
            for f in pair
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev",
                                        callback_data=f"ban:fonts:{page-1}"))
    if start + per_page < len(fonts):
        nav.append(InlineKeyboardButton("Next ➡️",
                                        callback_data=f"ban:fonts:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("⬅️ Back",
                                      callback_data="menu:banner")])
    return InlineKeyboardMarkup(rows)


# ===========================================================================
#  CALLBACK HANDLER
# ===========================================================================

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if q is None or not q.data:
        return
    u = get_user(q.from_user.id)
    data = q.data

    if data == "noop":
        await q.answer()
        return

    await q.answer()

    # ---------- MAIN MENU ----------
    if data == "menu:main":
        u.mode = "idle"
        await q.edit_message_text(welcome_text(u),
                                  parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=main_menu_kb())
        return

    if data == "menu:banner":
        u.mode = "awaiting_banner_text"
        await q.edit_message_text(banner_screen(u),
                                  parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=banner_menu_kb(u))
        return

    if data == "menu:image":
        u.mode = "awaiting_image"
        await q.edit_message_text(image_screen(u),
                                  parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=image_menu_kb(u))
        return

    if data == "menu:format":
        await q.edit_message_text(
            f"📦 *Export Format*\n\nCurrent: `{u.fmt.upper()}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=format_kb(u),
        )
        return

    if data == "menu:presets":
        await q.edit_message_text(
            "📐 *Size Presets*\n\nQuickly apply width + scale:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=presets_kb(u),
        )
        return

    # ---------- COLORS HUB ----------
    if data == "menu:colors":
        await q.edit_message_text(
            colors_hub_screen(u),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=colors_hub_kb(),
        )
        return

    if data in ("menu:colors:banner", "menu:colors:img1", "menu:colors:img2"):
        target = data.rsplit(":", 1)[1]
        current = {
            "banner": u.banner_color,
            "img1":   u.image_color,
            "img2":   u.image_color2,
        }[target]
        label = {
            "banner": "Banner",
            "img1":   "Image Color 1",
            "img2":   "Image Color 2 (gradient end)",
        }[target]
        await q.edit_message_text(
            f"🎨 *{label}* — choose a color\n\n"
            f"Current: `{current}`\n\n"
            "33 colors + custom hex 👇",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=color_menu_kb(target, current),
        )
        return

    if data.startswith("col:set:"):
        _, _, target, name = data.split(":", 3)
        if target == "banner":
            u.banner_color = name
        elif target == "img1":
            u.image_color = name
        elif target == "img2":
            u.image_color2 = name
        await q.edit_message_text(
            f"✅ Color set: `{name}`\n\n"
            "Choose another or go back:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=color_menu_kb(target, name),
        )
        return

    if data.startswith("col:hex:"):
        _, _, target = data.split(":", 2)
        u.mode = f"awaiting_hex:{target}"
        await q.edit_message_text(
            "✏️ Send a HEX color (e.g. `#ff8800` or `ff8800`):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back",
                                     callback_data=f"menu:colors:{target}")
            ]]),
        )
        return

    # ---------- PRESETS ----------
    if data.startswith("pre:"):
        p = data.split(":", 1)[1]
        if p == "small":
            u.width, u.scale, u.aspect = 80, 1, 0.5
        elif p == "medium":
            u.width, u.scale, u.aspect = 140, 1, 0.5
        elif p == "large":
            u.width, u.scale, u.aspect = 220, 1, 0.5
        elif p == "poster":
            u.width, u.scale, u.aspect = 200, 2, 0.5
        elif p == "huge":
            u.width, u.scale, u.aspect = 250, 3, 0.5
        await q.edit_message_text(
            f"✅ Preset *{p}* applied\n\n"
            f"📏 Width: `{u.width}`\n"
            f"📐 Scale: `{u.scale}x`\n"
            "Now send your image!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🖼️ Image menu",
                                     callback_data="menu:image"),
                InlineKeyboardButton("⬅️ Back", callback_data="menu:main"),
            ]]),
        )
        return

    # ---------- BANNER ----------
    if data == "ban:fonts:0":
        await q.edit_message_text(
            f"🔤 *Fonts* — {FONT_COUNT} available\n\n"
            f"Current: `{u.banner_font}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=font_list_kb(0),
        )
        return

    if data.startswith("ban:fonts:"):
        page = int(data.rsplit(":", 1)[1])
        await q.edit_message_reply_markup(reply_markup=font_list_kb(page))
        return

    if data == "ban:search":
        u.mode = "awaiting_font_search"
        await q.edit_message_text(
            "🔍 *Font Search*\n\nSend a search term (e.g. `big`, `slant`, `3d`):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data="menu:banner")
            ]]),
        )
        return

    if data.startswith("ban:setfont:"):
        font = data.split(":", 2)[2]
        u.banner_font = font
        await q.edit_message_text(
            f"✅ Font set: `{font}`\n\nNow send your text to build the banner.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=banner_menu_kb(u),
        )
        return

    if data.startswith("ban:w:"):
        op = data.split(":", 2)[2]
        if op == "show":
            await q.edit_message_text(
                f"📏 *Banner Width*\n\n"
                f"Current: `{u.banner_width}`  "
                f"(range {MIN_BANNER_WIDTH}–{MAX_BANNER_WIDTH})",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=banner_width_kb(u),
            )
            return
        if op == "type":
            u.mode = "awaiting_banner_width"
            await q.edit_message_text(
                f"✏️ Type the exact banner width "
                f"({MIN_BANNER_WIDTH}–{MAX_BANNER_WIDTH}):",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back", callback_data="menu:banner")
                ]]),
            )
            return
        if op.startswith("+"):
            u.banner_width = min(MAX_BANNER_WIDTH, u.banner_width + int(op[1:]))
        elif op.startswith("-"):
            u.banner_width = max(MIN_BANNER_WIDTH, u.banner_width - int(op[1:]))
        await q.edit_message_reply_markup(reply_markup=banner_width_kb(u))
        return

    if data.startswith("ban:s:"):
        val = data.split(":", 2)[2]
        if val == "show":
            await q.edit_message_text(
                f"📐 *Banner Scale*\n\nCurrent: `{u.banner_scale}x`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=banner_scale_kb(u),
            )
            return
        u.banner_scale = max(MIN_SCALE, min(MAX_SCALE, int(val)))
        await q.edit_message_reply_markup(reply_markup=banner_scale_kb(u))
        return

    # ---------- IMAGE ----------
    if data.startswith("img:style:"):
        u.image_style = data.split(":", 2)[2]
        await q.edit_message_text(image_screen(u),
                                  parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=image_menu_kb(u))
        return

    if data.startswith("img:color:"):
        u.color_mode = data.split(":", 2)[2]
        await q.edit_message_text(image_screen(u),
                                  parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=image_menu_kb(u))
        return

    if data.startswith("img:w:"):
        op = data.split(":", 2)[2]
        if op == "show":
            await q.edit_message_text(
                f"📏 *Image Width*\n\n"
                f"Current: `{u.width}`  (range {MIN_WIDTH}–{MAX_WIDTH})",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=image_width_kb(u),
            )
            return
        if op == "type":
            u.mode = "awaiting_width"
            await q.edit_message_text(
                f"✏️ Type the exact width ({MIN_WIDTH}–{MAX_WIDTH}):",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back", callback_data="menu:image")
                ]]),
            )
            return
        if op.startswith("+"):
            u.width = min(MAX_WIDTH, u.width + int(op[1:]))
        elif op.startswith("-"):
            u.width = max(MIN_WIDTH, u.width - int(op[1:]))
        await q.edit_message_reply_markup(reply_markup=image_width_kb(u))
        return

    if data.startswith("img:s:"):
        val = data.split(":", 2)[2]
        if val == "show":
            await q.edit_message_text(
                f"📐 *Image Scale*\n\nCurrent: `{u.scale}x`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=image_scale_kb(u),
            )
            return
        u.scale = max(MIN_SCALE, min(MAX_SCALE, int(val)))
        await q.edit_message_reply_markup(reply_markup=image_scale_kb(u))
        return

    if data.startswith("img:a:"):
        val = data.split(":", 2)[2]
        if val == "show":
            await q.edit_message_text(
                f"🧭 *Aspect*\n\nCurrent: `{u.aspect:.1f}`\n\n"
                "0.5 = normal. 0.3 = wider, 1.0 = taller.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=image_aspect_kb(u),
            )
            return
        u.aspect = float(val)
        await q.edit_message_reply_markup(reply_markup=image_aspect_kb(u))
        return

    if data.startswith("img:c:"):
        val = data.split(":", 2)[2]
        if val == "show":
            await q.edit_message_text(
                f"🌗 *Contrast*\n\nCurrent: `{u.contrast:.2f}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=image_contrast_kb(u),
            )
            return
        u.contrast = float(val)
        await q.edit_message_reply_markup(reply_markup=image_contrast_kb(u))
        return

    if data.startswith("img:gradir:"):
        val = data.split(":", 2)[2]
        if val == "show":
            await q.edit_message_text(
                f"↘️ *Gradient Direction*\n\nCurrent: `{u.gradient_dir}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=image_gradir_kb(u),
            )
            return
        u.gradient_dir = val
        await q.edit_message_reply_markup(reply_markup=image_gradir_kb(u))
        return

    if data == "img:invert":
        u.invert = not u.invert
        await q.edit_message_reply_markup(reply_markup=image_menu_kb(u))
        return

    # ---------- FORMAT ----------
    if data.startswith("fmt:"):
        u.fmt = data.split(":", 1)[1]
        await q.edit_message_reply_markup(reply_markup=format_kb(u))
        return


# ===========================================================================
#  TEXT HANDLER
# ===========================================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None or not msg.text:
        return
    u = get_user(update.effective_user.id)
    text = msg.text.strip()

    if text.startswith("/"):
        return

    if u.mode == "awaiting_width":
        if not text.isdigit():
            await msg.reply_text(
                f"❌ Please send a number ({MIN_WIDTH}–{MAX_WIDTH}).")
            return
        u.width = max(MIN_WIDTH, min(MAX_WIDTH, int(text)))
        u.mode = "awaiting_image"
        await msg.reply_text(f"✅ Width set: `{u.width}`\n\nNow send your image!",
                             parse_mode=ParseMode.MARKDOWN)
        return

    if u.mode == "awaiting_banner_width":
        if not text.isdigit():
            await msg.reply_text(
                f"❌ Please send a number "
                f"({MIN_BANNER_WIDTH}–{MAX_BANNER_WIDTH}).")
            return
        u.banner_width = max(MIN_BANNER_WIDTH, min(MAX_BANNER_WIDTH, int(text)))
        u.mode = "awaiting_banner_text"
        await msg.reply_text(
            f"✅ Banner width set: `{u.banner_width}`\n\nNow send your text!",
            parse_mode=ParseMode.MARKDOWN)
        return

    if u.mode.startswith("awaiting_hex:"):
        target = u.mode.split(":", 1)[1]
        hx = parse_hex(text)
        if not hx:
            await msg.reply_text(
                "❌ Invalid hex. Format: `#RRGGBB` or `RRGGBB`",
                parse_mode=ParseMode.MARKDOWN)
            return
        val = text.lstrip("#").lower()
        COLORS[val] = hx
        if target == "banner":
            u.banner_color = val
        elif target == "img1":
            u.image_color = val
        elif target == "img2":
            u.image_color2 = val
        u.mode = "idle"
        await msg.reply_text(
            f"✅ Custom color set: `#{val}` = `{hx}`",
            parse_mode=ParseMode.MARKDOWN)
        return

    if u.mode == "awaiting_font_search":
        matches = find_fonts(text)
        if not matches:
            await msg.reply_text(f"❌ No font matched `{text}`.",
                                 parse_mode=ParseMode.MARKDOWN)
            return
        u.mode = "idle"
        await msg.reply_text(
            f"🔎 `{text}` → {len(matches)} fonts:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=font_list_kb(0, query=text),
        )
        return

    if not HAS_FIGLET:
        await msg.reply_text("❌ pyfiglet is not installed.",
                             parse_mode=ParseMode.MARKDOWN)
        return
    await _send_banner(msg, u, text)


async def _send_banner(msg, u: UserState, text: str) -> None:
    status = await msg.reply_text(
        f"✍️ *Rendering banner…*\n\n"
        f"  🔤 Font  : `{u.banner_font}`\n"
        f"  📏 Width : `{u.banner_width}`\n"
        f"  📐 Scale : `{u.banner_scale}x`\n"
        f"  🎨 Color : `{u.banner_color}`\n"
        f"  📦 Format: `{u.fmt.upper()}`",
        parse_mode=ParseMode.MARKDOWN,
    )
    try:
        banner = render_banner(text, u.banner_font,
                               u.banner_width, u.banner_scale)

        if u.fmt == "txt":
            await msg.reply_document(
                document=io.BytesIO(banner.encode("utf-8")),
                filename=f"banner_{u.banner_font}.txt",
                caption=f"✅ Font: `{u.banner_font}` · Scale: `{u.banner_scale}x`",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            grid = banner_to_grid(banner)
            c1 = resolve_color(u.banner_color)
            grid = _apply_color_mode(grid, "mono", c1, c1, "vertical")
            file_bytes, filename, _ = _export_grid(grid, u.fmt)
            await msg.reply_document(
                document=io.BytesIO(file_bytes),
                filename=f"banner_{u.banner_font}.{u.fmt}",
                caption=f"✅ Font: `{u.banner_font}` · Color: `{u.banner_color}`",
                parse_mode=ParseMode.MARKDOWN,
            )

        if len(banner) <= MAX_PREVIEW:
            await msg.reply_text(f"<pre>{html.escape(banner)}</pre>",
                                 parse_mode=ParseMode.HTML)
        else:
            await msg.reply_text(
                f"<pre>{html.escape(banner[:MAX_PREVIEW])}</pre>\n…(truncated)",
                parse_mode=ParseMode.HTML,
            )
        await status.delete()
    except Exception as exc:
        log.exception("Banner render failed")
        try:
            await status.edit_text(f"❌ Error: `{exc}`",
                                   parse_mode=ParseMode.MARKDOWN)
        except TelegramError:
            pass


# ===========================================================================
#  IMAGE HANDLER
# ===========================================================================

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return
    if ALLOWED_CHAT_ID and str(msg.chat_id) != str(ALLOWED_CHAT_ID):
        return

    u = get_user(msg.from_user.id)

    await context.bot.send_chat_action(
        chat_id=msg.chat_id, action=ChatAction.UPLOAD_DOCUMENT)

    status = await msg.reply_text(
        f"⏳ *Processing…*\n\n"
        f"  🎨 Style : `{u.image_style}`\n"
        f"  🌈 Color : `{u.color_mode}`\n"
        f"  🎨 Color1: `{u.image_color}`\n"
        f"  🎨 Color2: `{u.image_color2}`\n"
        f"  📏 Width : `{u.width}`\n"
        f"  📐 Scale : `{u.scale}x`\n"
        f"  📦 Format: `{u.fmt.upper()}`",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        if msg.photo:
            tg_file = await msg.photo[-1].get_file()
        elif msg.document:
            tg_file = await msg.document.get_file()
        else:
            await status.edit_text("❌ Please send an image.")
            return

        image_bytes = bytes(await tg_file.download_as_bytearray())
        if not image_bytes:
            await status.edit_text("❌ Received an empty file.")
            return

        await status.edit_text("🎨 *Rendering…*",
                               parse_mode=ParseMode.MARKDOWN)
        grid = image_to_grid(
            image_bytes,
            width=u.width,
            style=u.image_style,
            invert=u.invert,
            contrast=u.contrast,
            aspect=u.aspect,
            scale=u.scale,
        )

        await status.edit_text("🌈 *Applying colors…*",
                               parse_mode=ParseMode.MARKDOWN)
        c1 = resolve_color(u.image_color)
        c2 = resolve_color(u.image_color2, fallback=c1)
        grid = _apply_color_mode(grid, u.color_mode, c1, c2, u.gradient_dir)

        await status.edit_text("📦 *Exporting…*",
                               parse_mode=ParseMode.MARKDOWN)
        file_bytes, filename, _ = _export_grid(grid, u.fmt)

        await msg.reply_document(
            document=io.BytesIO(file_bytes),
            filename=filename,
            caption=(
                f"✅ *Done!*\n\n"
                f"  🎨 Style  : `{u.image_style}`\n"
                f"  🌈 Color  : `{u.color_mode}`\n"
                f"  🎨 Color1 : `{u.image_color}`\n"
                f"  🎨 Color2 : `{u.image_color2}`\n"
                f"  📏 Width  : `{u.width}`\n"
                f"  📐 Scale  : `{u.scale}x`\n"
                f"  📦 Format : `{u.fmt.upper()}`\n\n"
                f"{_footer()}"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

        if u.fmt in ("txt", "ansi"):
            txt = file_bytes.decode("utf-8", errors="replace")
            if len(txt) <= MAX_PREVIEW:
                await msg.reply_text(f"<pre>{html.escape(txt)}</pre>",
                                     parse_mode=ParseMode.HTML)
            else:
                await msg.reply_text(
                    f"<pre>{html.escape(txt[:MAX_PREVIEW])}</pre>\n…(truncated)",
                    parse_mode=ParseMode.HTML,
                )
        await status.delete()
    except Exception as exc:
        log.exception("Image processing failed")
        try:
            await status.edit_text(f"❌ Error: `{exc}`",
                                   parse_mode=ParseMode.MARKDOWN)
        except TelegramError:
            pass


# ===========================================================================
#  TERMINAL INSTRUCTIONS
# ===========================================================================

def print_instructions() -> None:
    fig = FONT_COUNT if HAS_FIGLET else 0
    print("\n" + "=" * 62)
    print("   ASCII / ANSI STUDIO BOT  -  READY")
    print("=" * 62)
    print(f"   FIGlet fonts loaded : {fig}")
    print(f"   Colors available    : {len(COLORS)}")
    print(f"   Export formats      : txt / html / ansi / png")
    print(f"   Catbox image        : "
          f"{'YES' if CATBOX_IMAGE_URL.startswith('http') else 'NO'}")
    print("-" * 62)
    print("   NEXT STEP:")
    print("     Open Telegram and send the /start command")
    print("     to your bot to begin.")
    print("")
    print("   Commands:")
    print("     /start    - Main menu")
    print("     /banner   - Text -> Banner")
    print("     /image    - Image -> Art")
    print("     /colors   - Color hub")
    print("     /fonts    - 500+ fonts")
    print("     /format   - Export format")
    print("     /width N  - Set width")
    print("     /scale N  - Set scale")
    print("     /color X  - Set color (name or #hex)")
    print("")
    token_ok = bool(BOT_TOKEN) and not BOT_TOKEN.startswith("123456789:")
    print(f"   Bot token set       : {'YES' if token_ok else 'NO'}")
    print("   Stop the bot        : Ctrl+C")
    print("=" * 62 + "\n")


# ===========================================================================
#  ENTRY POINT
# ===========================================================================

def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN.startswith("123456789:"):
        print("\n[ERROR] BOT_TOKEN is not set.")
        print("        Set BOT_TOKEN at the top of bot.py.")
        print("        Get a token from @BotFather.\n")
        sys.exit(1)

    if not HAS_FIGLET:
        log.warning("pyfiglet not loaded — banner feature disabled.")

    print_instructions()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("banner", cmd_banner))
    app.add_handler(CommandHandler("image", cmd_image))
    app.add_handler(CommandHandler("colors", cmd_colors))
    app.add_handler(CommandHandler("fonts", cmd_fonts))
    app.add_handler(CommandHandler("font", cmd_font))
    app.add_handler(CommandHandler("color", cmd_color))
    app.add_handler(CommandHandler("width", cmd_width))
    app.add_handler(CommandHandler("scale", cmd_scale))
    app.add_handler(CommandHandler("format", cmd_format))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    log.info("Bot running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped.\n")
