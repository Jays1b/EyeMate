"""Generate EyeMate brand icons and splash screen assets.

Creates:
  - assets/icon.png: 512x512 master app icon (Google Play & desktop)
  - assets/icon_fg.png: 512x512 Android adaptive icon foreground
  - assets/icon_bg.png: 512x512 Android adaptive icon background
  - assets/icon.ico: Windows multi-resolution icon (16..256px)
  - assets/presplash.png: 1024x1024 Android launch/presplash screen
"""
from __future__ import annotations

import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# Canvas dimensions for supersampling (4x)
SIZE = 2048
CENTER = (SIZE // 2, SIZE // 2)


def lerp_color(c1, c2, t):
    """Linear interpolate between two RGB(A) tuples."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def draw_vertical_gradient(width, height, top_color, bot_color):
    """Create a vertical gradient image."""
    base = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(base)
    for y in range(height):
        t = y / (height - 1)
        col = lerp_color(top_color, bot_color, t)
        draw.line([(0, y), (width, y)], fill=col)
    return base


def draw_radial_glow(size, center, radius, color):
    """Create a soft radial glow image."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = center
    steps = 48
    r_max = radius
    for i in range(steps, 0, -1):
        t = i / steps
        r = r_max * t
        alpha = int(color[3] * ((1.0 - t) ** 1.8))
        c = (color[0], color[1], color[2], alpha)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
    return img


def draw_four_point_star(draw, cx, cy, r_long, r_short, color):
    """Draw a shining 4-point star/sparkle."""
    points = [
        (cx, cy - r_long),
        (cx + r_short, cy - r_short),
        (cx + r_long, cy),
        (cx + r_short, cy + r_short),
        (cx, cy + r_long),
        (cx - r_short, cy + r_short),
        (cx - r_long, cy),
        (cx - r_short, cy - r_short),
    ]
    draw.polygon(points, fill=color)


def make_background():
    """Create background layer (2048x2048)."""
    # Deep oceanic sapphire to dark teal gradient
    bg = draw_vertical_gradient(
        SIZE,
        SIZE,
        top_color=(8, 18, 38, 255),    # Deep sapphire
        bot_color=(6, 38, 52, 255),    # Deep teal-navy
    )

    # Ambient radial glows
    glow1 = draw_radial_glow(SIZE, (SIZE // 2, SIZE // 2), 900, (0, 180, 220, 70))
    glow2 = draw_radial_glow(SIZE, (SIZE // 2 - 150, SIZE // 2 - 150), 600, (0, 245, 212, 50))
    bg = Image.alpha_composite(bg, glow1)
    bg = Image.alpha_composite(bg, glow2)

    # Subtle concentric radar/vision guidance arcs in the background
    overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx, cy = CENTER
    for r in (500, 700, 880):
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(0, 240, 255, 18),
            width=4,
        )
    bg = Image.alpha_composite(bg, overlay)
    return bg


def make_foreground():
    """Create the emblem / foreground layer (2048x2048, transparent)."""
    fg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    cx, cy = CENTER

    # 1. Subtle Sound/Voice waves emanating to upper-right (assistive speech)
    sound_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sound_layer)
    for idx, (r, w, alpha) in enumerate([
        (560, 18, 140),
        (660, 14, 100),
        (760, 10, 60),
    ]):
        bbox = [cx - r, cy - r, cx + r, cy + r]
        sdraw.arc(bbox, start=-40, end=10, fill=(0, 245, 212, alpha), width=w)
    fg = Image.alpha_composite(fg, sound_layer)

    # 2. Outer Eye Contour (streamlined almond shape)
    # Parametric curve with gradient fill
    eye_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    edraw = ImageDraw.Draw(eye_layer)

    w_half = 530
    h_top = 280
    h_bot = 270
    thickness = 36

    # Sample points along top and bottom curves
    n_pts = 120
    top_outer, top_inner = [], []
    bot_outer, bot_inner = [], []

    for i in range(n_pts + 1):
        t = (i / n_pts) * 2.0 - 1.0  # -1.0 to 1.0
        x = cx + t * w_half
        # Cosine bell curve for smooth organic eye
        factor = math.cos(t * math.pi * 0.5) ** 1.35
        # Top edge
        y_top = cy - factor * h_top
        top_outer.append((x, y_top - thickness * 0.5 * factor))
        top_inner.append((x, y_top + thickness * 0.5 * factor))
        # Bottom edge
        y_bot = cy + factor * h_bot
        bot_outer.append((x, y_bot + thickness * 0.5 * factor))
        bot_inner.append((x, y_bot - thickness * 0.5 * factor))

    # Connect to form filled ribbon polygons for top and bottom lids
    top_poly = top_outer + list(reversed(top_inner))
    bot_poly = bot_inner + list(reversed(bot_outer))

    # Gradient shader along the horizontal span
    for poly in (top_poly, bot_poly):
        edraw.polygon(poly, fill=(255, 255, 255, 255))

    # Colorize the eye contour with cyan -> sky-blue -> royal-azure gradient
    contour_grad = draw_vertical_gradient(
        SIZE, SIZE,
        top_color=(0, 245, 212, 255),    # Vibrant neon mint
        bot_color=(0, 180, 255, 255),    # Electric cyan-blue
    )
    # Mask contour
    colored_contour = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    colored_contour.paste(contour_grad, (0, 0), mask=eye_layer)

    # Add soft glow to eye contour
    bloom = colored_contour.filter(ImageFilter.GaussianBlur(radius=24))
    fg = Image.alpha_composite(fg, bloom)
    fg = Image.alpha_composite(fg, colored_contour)

    # 3. Outer Iris Ring (Camera Lens Aperture styling)
    iris_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    idraw = ImageDraw.Draw(iris_layer)

    r_iris = 230
    r_iris_inner = 180

    # Gradient ring for iris
    idraw.ellipse([cx - r_iris, cy - r_iris, cx + r_iris, cy + r_iris], fill=(0, 220, 255, 255))
    idraw.ellipse([cx - r_iris_inner, cy - r_iris_inner, cx + r_iris_inner, cy + r_iris_inner], fill=(0, 0, 0, 0))

    # Apply radial-like gradient / shading
    iris_grad = draw_vertical_gradient(
        SIZE, SIZE,
        top_color=(0, 245, 212, 255),  # Mint
        bot_color=(58, 134, 255, 255),  # Azure
    )
    colored_iris = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    colored_iris.paste(iris_grad, (0, 0), mask=iris_layer)

    iris_glow = colored_iris.filter(ImageFilter.GaussianBlur(radius=16))
    fg = Image.alpha_composite(fg, iris_glow)
    fg = Image.alpha_composite(fg, colored_iris)

    # 4. Concentric Aperture Ticks (Tech/Vision companion motif)
    tick_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(tick_layer)
    for deg in range(0, 360, 30):
        rad = math.radians(deg)
        x1 = cx + math.cos(rad) * (r_iris - 18)
        y1 = cy + math.sin(rad) * (r_iris - 18)
        x2 = cx + math.cos(rad) * (r_iris_inner + 12)
        y2 = cy + math.sin(rad) * (r_iris_inner + 12)
        tdraw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255, 160), width=6)
    fg = Image.alpha_composite(fg, tick_layer)

    # 5. Pupil (Deep high-contrast core with luminous cyan rim)
    pupil_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pupil_layer)
    r_pupil = 135

    # Core dark circle
    pdraw.ellipse([cx - r_pupil, cy - r_pupil, cx + r_pupil, cy + r_pupil], fill=(7, 14, 28, 255))
    # Glowing rim
    pdraw.ellipse(
        [cx - r_pupil, cy - r_pupil, cx + r_pupil, cy + r_pupil],
        outline=(0, 245, 212, 240),
        width=8,
    )
    fg = Image.alpha_composite(fg, pupil_layer)

    # 6. Central Camera Sensor Lens / Inner Core
    r_core = 60
    core_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(core_layer)
    cdraw.ellipse([cx - r_core, cy - r_core, cx + r_core, cy + r_core], fill=(0, 180, 240, 220))
    core_glow = core_layer.filter(ImageFilter.GaussianBlur(radius=12))
    fg = Image.alpha_composite(fg, core_glow)
    fg = Image.alpha_composite(fg, core_layer)

    # 7. Lens Flare & Star Sparkle (Clarity & Vision symbol)
    sparkle_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    spdraw = ImageDraw.Draw(sparkle_layer)

    # Primary spark at upper-left of center (camera specular catchlight)
    sx1, sy1 = cx - 45, cy - 45
    draw_four_point_star(spdraw, sx1, sy1, r_long=65, r_short=16, color=(255, 255, 255, 255))

    # Secondary smaller spark
    sx2, sy2 = cx + 55, cy + 50
    draw_four_point_star(spdraw, sx2, sy2, r_long=30, r_short=8, color=(0, 245, 212, 220))

    # Soft star glow
    sparkle_glow = sparkle_layer.filter(ImageFilter.GaussianBlur(radius=8))
    fg = Image.alpha_composite(fg, sparkle_glow)
    fg = Image.alpha_composite(fg, sparkle_layer)

    # 8. Corner connection dots / anchor beacons (left and right corner tips)
    dots_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ddraw = ImageDraw.Draw(dots_layer)
    for dot_x in (cx - w_half, cx + w_half):
        ddraw.ellipse([dot_x - 14, cy - 14, dot_x + 14, cy + 14], fill=(255, 255, 255, 255))
    fg = Image.alpha_composite(fg, dots_layer)

    return fg


def make_presplash(emblem_fg):
    """Create 1024x1024 splash screen with centered emblem and brand title."""
    splash_size = 1024
    splash = draw_vertical_gradient(
        splash_size,
        splash_size,
        top_color=(6, 14, 30, 255),
        bot_color=(4, 28, 40, 255),
    )

    # Ambient radial glow behind emblem
    glow = draw_radial_glow(splash_size, (splash_size // 2, 420), 450, (0, 210, 230, 75))
    splash = Image.alpha_composite(splash, glow)

    # Scaled emblem (420x420 centered at y=420)
    emblem_scaled = emblem_fg.resize((440, 440), Image.Resampling.LANCZOS)
    ex = (splash_size - 440) // 2
    ey = 170
    splash.alpha_composite(emblem_scaled, (ex, ey))

    # Typography
    draw = ImageDraw.Draw(splash)
    font_path = "C:/Windows/Fonts/segoeui.ttf"
    if not os.path.exists(font_path):
        font_path = "C:/Windows/Fonts/arial.ttf"

    try:
        title_font = ImageFont.truetype(font_path, 68)
        sub_font = ImageFont.truetype(font_path, 28)
    except Exception:
        title_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    # App title
    title_text = "EyeMate"
    tb = draw.textbbox((0, 0), title_text, font=title_font)
    tw = tb[2] - tb[0]
    tx = (splash_size - tw) // 2
    ty = 650

    # Title shadow + text
    draw.text((tx + 2, ty + 2), title_text, font=title_font, fill=(0, 0, 0, 160))
    draw.text((tx, ty), title_text, font=title_font, fill=(255, 255, 255, 255))

    # Subtitle
    sub_text = "VISION & VOICE ASSISTANT"
    sb = draw.textbbox((0, 0), sub_text, font=sub_font)
    sw = sb[2] - sb[0]
    sx = (splash_size - sw) // 2
    sy = 735

    draw.text((sx + 1, sy + 1), sub_text, font=sub_font, fill=(0, 0, 0, 140))
    draw.text((sx, sy), sub_text, font=sub_font, fill=(0, 245, 212, 230))

    # Bottom offline badge
    tag_text = "100% OFFLINE  *  ON-DEVICE INTELLIGENCE"
    try:
        tag_font = ImageFont.truetype(font_path, 20)
    except Exception:
        tag_font = ImageFont.load_default()
    tag_b = draw.textbbox((0, 0), tag_text, font=tag_font)
    tag_w = tag_b[2] - tag_b[0]
    draw.text(((splash_size - tag_w) // 2, 920), tag_text, font=tag_font, fill=(255, 255, 255, 110))

    return splash


def main():
    os.makedirs("assets", exist_ok=True)
    print("Generating EyeMate brand artwork at 2048x2048...")

    bg_2048 = make_background()
    fg_2048 = make_foreground()
    full_2048 = Image.alpha_composite(bg_2048, fg_2048)

    # 1. Master Icon (512x512) - for Google Play Store & Desktop
    print("Downsampling master icon to 512x512...")
    icon_512 = full_2048.resize((512, 512), Image.Resampling.LANCZOS)
    icon_512.save("assets/icon.png", format="PNG", optimize=True)

    # Also save standard 192x192
    icon_192 = full_2048.resize((192, 192), Image.Resampling.LANCZOS)
    icon_192.save("assets/icon-192.png", format="PNG", optimize=True)

    # 2. Android Adaptive Icon (Foreground + Background)
    print("Downsampling adaptive icon layers to 512x512...")
    bg_512 = bg_2048.resize((512, 512), Image.Resampling.LANCZOS)
    bg_512.save("assets/icon_bg.png", format="PNG", optimize=True)

    fg_512 = fg_2048.resize((512, 512), Image.Resampling.LANCZOS)
    fg_512.save("assets/icon_fg.png", format="PNG", optimize=True)

    # 3. Windows Multi-Resolution ICO
    print("Creating Windows multi-resolution icon (icon.ico)...")
    icon_512.save(
        "assets/icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    # 4. Android Presplash (Launch Screen)
    print("Creating presplash.png (1024x1024)...")
    splash = make_presplash(fg_2048)
    splash.save("assets/presplash.png", format="PNG", optimize=True)

    print("All assets successfully generated in assets/:")
    for f in os.listdir("assets"):
        sz = os.path.getsize(os.path.join("assets", f))
        print(f"  - assets/{f} ({sz:,} bytes)")


if __name__ == "__main__":
    main()
