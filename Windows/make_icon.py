"""
make_icon.py — Convert the Mac app's PNG icon set into a Windows .ico file.

Run this once before building:
    python make_icon.py

Requires Pillow:
    pip install Pillow
"""

import sys
import os
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillow is required. Run:  pip install Pillow")
    sys.exit(1)

# Sizes to include in the .ico (Windows uses all of these)
ICO_SIZES = [16, 32, 48, 64, 128, 256]

# Source icons from the Mac project
MAC_ICONS = Path(__file__).parent.parent / "Sources" / "Assets.xcassets" / "AppIcon.appiconset"

# Output
OUT = Path(__file__).parent / "icon.ico"


def main():
    images = []

    for size in ICO_SIZES:
        # Try to find an exact-size PNG first
        candidates = [
            MAC_ICONS / f"icon_{size}.png",
            MAC_ICONS / f"icon_{size * 2}.png",   # use 2x and scale down
            MAC_ICONS / "icon_256.png",             # fallback
        ]
        src = next((p for p in candidates if p.exists()), None)

        if src is None:
            print(f"  Warning: no source PNG found for {size}px — skipping")
            continue

        img = Image.open(src).convert("RGBA")
        if img.size != (size, size):
            img = img.resize((size, size), Image.LANCZOS)

        images.append(img)
        print(f"  ✓ {size}×{size}  (from {src.name})")

    if not images:
        print("Error: no source PNG files found.")
        print(f"Expected them at: {MAC_ICONS}")
        sys.exit(1)

    # Save as multi-size .ico
    images[0].save(
        OUT,
        format="ICO",
        sizes=[(img.width, img.height) for img in images],
        append_images=images[1:],
    )
    print(f"\n✓ Saved: {OUT}")


if __name__ == "__main__":
    print("Converting PNG icon set → icon.ico …")
    main()
