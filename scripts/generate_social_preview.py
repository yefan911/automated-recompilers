#!/usr/bin/env python3
"""Create share images from the bundled homebrew's native PPM snapshot.

First run: python recompile.py roms/test/hello_gba.gba
Then: build/hello_gba.exe --headless --framebuffer build/hello_gba.ppm
Finally: python scripts/generate_social_preview.py
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def font(size, *, bold=False):
    names = (
        "C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for name in names:
        if Path(name).is_file():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framebuffer", type=Path, default=ROOT / "build/hello_gba.ppm")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/demo")
    args = parser.parse_args()
    with Image.open(args.framebuffer) as source:
        if source.format != "PPM" or source.size != (240, 160):
            parser.error("Expected the native 240x160 GBA PPM framebuffer")
        frame = source.convert("RGB")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame.save(args.output_dir / "homebrew_framebuffer.png")

    preview = Image.new("RGB", (1200, 630), "#090d16")
    draw = ImageDraw.Draw(preview)
    draw.rounded_rectangle((32, 32, 1168, 598), radius=22, fill="#131c2e", outline="#22324e", width=2)
    draw.text((64, 62), "AUTOMATED GAME ROM RECOMPILER", font=font(26, bold=True), fill="#38bdf8")
    draw.text((64, 154), "Console ROMs", font=font(48, bold=True), fill="#f1f5f9")
    draw.text((64, 218), "to native C", font=font(48, bold=True), fill="#f1f5f9")
    draw.text((64, 306), "Experimental static recompilation", font=font(23), fill="#94a3b8")
    draw.text((64, 348), "ARM / Thumb / MIPS / 65816", font=font(23), fill="#94a3b8")
    draw.text((64, 420), "Explore the CFG and hex-to-C demo", font=font(23), fill="#4ade80")
    draw.text((64, 460), "github.com/yefan911/automated-recompilers", font=font(20), fill="#94a3b8")
    draw.text((640, 156), "Native GBA homebrew framebuffer", font=font(23), fill="#f1f5f9")
    draw.rectangle((638, 198, 1122, 522), outline="#38bdf8", width=2)
    preview.paste(frame.resize((480, 320), Image.Resampling.NEAREST), (640, 200))
    draw.text((64, 546), "ROM  →  Control flow graph  →  C source  →  Native binary", font=font(24, bold=True), fill="#38bdf8")
    preview.save(args.output_dir / "social-preview.png")
    print(f"Generated framebuffer and 1200x630 social preview in {args.output_dir}")


if __name__ == "__main__":
    main()
