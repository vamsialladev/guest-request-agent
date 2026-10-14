"""Render real command output as a terminal-style PNG for the README (same style as the existing images).

  python -m eval.run_eval > out.txt
  python scripts/render_terminal.py out.txt docs/images/eval-retrieval.png --command "python -m eval.run_eval" \
      --title "guest-request-agent: eval"

The text is taken verbatim from the file; only colors are added (✓ green, ✗ red, summary lines brass).
"""

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BG, BODY, BAR, TEXT = (225, 229, 227), (20, 32, 28), (31, 46, 41), (217, 227, 223)
GREEN, RED, BRASS, PROMPT, DIM = (93, 187, 114), (240, 122, 110), (231, 194, 122), (126, 201, 156), (150, 168, 160)
DOTS = [(229, 101, 90), (229, 185, 78), (93, 187, 114)]
SUMMARY = re.compile(
    r"^(Request coverage|Fact grounding|Correct tool|Escalation|False-escalation|Injection|No forbidden|Task routing|"
    r"Citation|Key facts|Reply in|First-email|Greetings|Real emails|Retrieval|Answer accuracy|Time to first|"
    r"Latency|Tokens|Cost|TOTAL|\d+ passed|Required test coverage)"
)
NOISE = re.compile(r"Loading weights|HF Hub|HF_TOKEN|Batches:|^\s*$|Report saved|Raw answers saved")


def font(names, size):
    for name in names:
        for folder in ("C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", "/Library/Fonts"):
            path = Path(folder) / name
            if path.exists():
                return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size)


def render(lines, out, title, command, scale=2):
    mono = font(["DejaVuSansMono.ttf", "consola.ttf", "Menlo.ttc"], 13 * scale)
    bold = font(["DejaVuSansMono-Bold.ttf", "consolab.ttf", "Menlo.ttc"], 13 * scale)
    sym = font(["seguisym.ttf", "DejaVuSans.ttf"], 13 * scale)
    ui = font(["segoeui.ttf", "DejaVuSans.ttf"], 13 * scale)
    lh, pad, bar = 22 * scale, 22 * scale, 34 * scale
    rows = [("prompt", f"PS> {command}")] + [("text", line) for line in lines]
    width = max(900 * scale, int(max(mono.getlength(t) for _, t in rows)) + 2 * pad)
    height = bar + pad + lh * len(rows) + pad
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, width - 1, height - 1], radius=10 * scale, fill=BODY)
    d.rounded_rectangle([0, 0, width - 1, bar], radius=10 * scale, fill=BAR)
    d.rectangle([0, bar - 10 * scale, width - 1, bar], fill=BAR)
    for i, color in enumerate(DOTS):
        cx = 20 * scale + i * 20 * scale
        d.ellipse([cx - 6 * scale, bar // 2 - 6 * scale, cx + 6 * scale, bar // 2 + 6 * scale], fill=color)
    d.text((84 * scale, bar // 2), title, font=ui, fill=TEXT, anchor="lm")
    y = bar + pad
    for kind, line in rows:
        x, base = pad, y + int(lh * 0.7)  # draw on a shared baseline so symbols line up with text
        if kind == "prompt":
            d.text((x, base), line, font=mono, fill=PROMPT, anchor="ls")
        elif SUMMARY.match(line.strip()):
            d.text((x, base), line, font=bold, fill=BRASS, anchor="ls")
        else:
            for part in re.split(r"(✅|❌|✓|✗)", line):
                if part in ("✅", "✓"):
                    d.text((x, base), "✓", font=sym, fill=GREEN, anchor="ls")
                    x += mono.getlength("x")
                elif part in ("❌", "✗"):
                    d.text((x, base), "✗", font=sym, fill=RED, anchor="ls")
                    x += mono.getlength("x")
                elif part:
                    d.text((x, base), part, font=mono, fill=DIM if line.startswith("Setup") else TEXT, anchor="ls")
                    x += mono.getlength(part)
        y += lh
    img.save(out, optimize=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source")
    p.add_argument("out")
    p.add_argument("--command", required=True)
    p.add_argument("--title", required=True)
    a = p.parse_args()
    text = Path(a.source).read_text(encoding="utf-8", errors="replace")
    lines = [line.rstrip() for line in text.splitlines() if not NOISE.search(line)]
    render(lines, a.out, a.title, a.command)
    print("saved", a.out)


if __name__ == "__main__":
    main()
