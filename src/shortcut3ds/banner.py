import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat

WIDTH, HEIGHT = 256, 128


def _mix(a: tuple[int, ...], b: tuple[int, ...], t: float) -> tuple[int, ...]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and draw.textlength(f"{lines[-1]} {word}", font=font) <= width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines[:3]


def render(icon: Image.Image, title: str, publisher: str) -> Image.Image:
    accent = tuple(round(c) for c in ImageStat.Stat(icon.convert("RGB")).mean)
    top, bottom = _mix(accent, (255, 255, 255), 0.55), _mix(accent, (0, 0, 0), 0.35)
    img = Image.new("RGBA", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        draw.line([(0, y), (WIDTH, y)], fill=_mix(top, bottom, y / (HEIGHT - 1)) + (255,))

    draw.rounded_rectangle([12, 14, 112, 114], radius=12, fill=(255, 255, 255, 235))
    img.paste(icon.convert("RGBA").resize((96, 96), Image.NEAREST), (14, 16))

    title_font = ImageFont.load_default(size=17)
    small_font = ImageFont.load_default(size=11)
    lines = _wrap(draw, title, title_font, WIDTH - 130)
    y = 64 - (len(lines) * 21 + (14 if publisher else 0)) // 2
    for line in lines:
        draw.text((124, y), line, font=title_font, fill="white", stroke_width=2, stroke_fill=bottom)
        y += 21
    if publisher:
        draw.text((124, y + 2), publisher, font=small_font, fill=(255, 255, 255, 220))
    return img


def write_silence(path: Path, seconds: float = 0.5, rate: int = 22050) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\0\0" * int(rate * seconds))
