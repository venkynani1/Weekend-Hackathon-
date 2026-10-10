"""Generate favicon, app icons and the social preview image (run once; outputs are committed).

    python scripts/make_images.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "static" / "img"
FOREST, CORAL, PAPER, INK = (23, 63, 53), (211, 95, 66), (245, 246, 241), (23, 35, 32)
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def mark(size: int) -> Image.Image:
    """Three-bar brand mark on a forest square, matching the CSS logo."""
    img = Image.new("RGB", (size, size), FOREST)
    d = ImageDraw.Draw(img)
    w = max(2, round(size * 0.13))
    gap = max(1, round(size * 0.09))
    heights = [0.26, 0.56, 0.40]
    colors = [(170, 196, 186), (255, 255, 255), CORAL]
    total = 3 * w + 2 * gap
    x = (size - total) // 2
    base = round(size * 0.78)
    for h, c in zip(heights, colors):
        d.rectangle([x, base - round(size * h), x + w - 1, base], fill=c)
        x += w + gap
    return img


def save_png(img: Image.Image, name: str) -> None:
    img.save(OUT / name, optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    save_png(mark(32), "favicon-32.png")
    save_png(mark(180), "apple-touch-icon.png")
    save_png(mark(192), "icon-192.png")
    save_png(mark(512), "icon-512.png")
    mark(48).save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

    (OUT / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="TalentGuard">'
        '<rect width="32" height="32" fill="#173f35"/>'
        '<rect x="8" y="17" width="4" height="8" fill="#aac4ba"/>'
        '<rect x="14" y="7" width="4" height="18" fill="#fff"/>'
        '<rect x="20" y="12" width="4" height="13" fill="#d35f42"/></svg>',
        encoding="utf-8",
    )

    # Social preview 1200x630: all text is baked in so it reads in any feed.
    og = Image.new("RGB", (1200, 630), PAPER)
    d = ImageDraw.Draw(og)
    d.rectangle([0, 0, 1200, 14], fill=FOREST)
    og.paste(mark(72), (80, 70))
    d.text((172, 84), "TalentGuard", font=font(SANS_BOLD, 40), fill=INK)
    d.text((80, 200), "44 of the 50 employees", font=font(SERIF, 72), fill=INK)
    d.text((80, 285), "we flagged really left.", font=font(SERIF, 72), fill=CORAL)
    d.text((80, 410), "Top-50 retention watch list for HR, with the top three", font=font(SANS, 30), fill=(83, 97, 93))
    d.text((80, 452), "reasons per person and an approval-gated action plan.", font=font(SANS, 30), fill=(83, 97, 93))
    d.rectangle([80, 530, 1120, 532], fill=(220, 225, 218))
    d.text((80, 552), "5.5x better than random   |   PR-AUC 0.587   |   No leakage", font=font(SANS_BOLD, 24), fill=FOREST)
    og.save(OUT / "og-image.png", optimize=True)

    for f in sorted(OUT.iterdir()):
        print(f"{f.name:22s} {f.stat().st_size / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
