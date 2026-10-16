"""Pixel-measured, zero-truncation compact pages for visual AI consumption.

Visual layout coverage is checked against metadata; it cannot promise OCR accuracy.
"""
from __future__ import annotations
from dataclasses import dataclass
import csv
import json
import math
import os
from pathlib import Path
import re
from typing import Any
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
from .model import Snapshot, DbObject
from .exports import write_json

PALETTES = {
    "light": {"bg": "#FFFFFF", "text": "#17212B", "muted": "#465667", "line": "#CFD7DF",
              "head": "#E9EFF5", "tagT": "#164F87", "tagV": "#7C3B8A"},
    "dark": {"bg": "#11161C", "text": "#F0F4F8", "muted": "#B3BFCA", "line": "#46525E",
             "head": "#293441", "tagT": "#8ABEFF", "tagV": "#E4AEFF"},
}

PRESETS = {
    "balanced": {"width": 2400, "height": 3200, "columns": 3, "font_size": 20},
    "dense": {"width": 2800, "height": 3600, "columns": 4, "font_size": 18},
    "readable": {"width": 2000, "height": 2800, "columns": 2, "font_size": 22},
}


@dataclass(frozen=True)
class Config:
    width: int = 2400
    height: int = 3200
    columns: int = 3
    font_size: int = 20
    theme: str = "light"
    font_path: str | None = None

    def __post_init__(self):
        if not (900 <= self.width <= 6000 and 900 <= self.height <= 8000):
            raise ValueError("Image width must be 900-6000 and height 900-8000")
        if not (1 <= self.columns <= 6):
            raise ValueError("Columns must be 1-6")
        if not (12 <= self.font_size <= 40):
            raise ValueError("Font must be 12-40 px")
        if self.theme not in PALETTES:
            raise ValueError("Unknown image theme")
        usable = self.width - 2 * 24 - (self.columns - 1) * 18
        if usable // self.columns < 240:
            raise ValueError("Too many columns for image width")


@dataclass(frozen=True)
class FieldLine:
    text: str
    indexes: tuple[int, ...]


@dataclass
class Block:
    object_index: int
    part: int
    start_line: int
    end_line: int
    page: int
    column: int
    x: int
    y: int
    height: int


def load_font(size: int, custom: str | None) -> ImageFont.FreeTypeFont:
    candidates = [custom] if custom else []
    if os.name == "nt":
        candidates += [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\arial.ttf",
                       r"C:\Windows\Fonts\segoeui.ttf"]
    candidates += ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                   "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                   "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    for p in candidates:
        if p and Path(p).is_file():
            return ImageFont.truetype(p, size)
    raise RuntimeError("No scalable TrueType font found. Supply --font-path (e.g. C:\\Windows\\Fonts\\msyh.ttc)")


def _font_width(font: ImageFont.FreeTypeFont, text: str) -> float:
    return font.getlength(text)


def visual_ident(name: str) -> str:
    """Compact names remain literal; bracket special names to reveal boundaries.

    The lossless exact identifier is always present in structured exports.
    """
    if re.fullmatch(r"[\w$#@]+", name, re.UNICODE):
        return name
    escaped = name.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return "[" + escaped.replace("]", "]]") + "]"


def _split_long(text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    """Split at grapheme-ish units with a continuation prefix, never ellipsize.

    Combining marks are kept with the preceding codepoint where possible.
    """
    from unicodedata import combining
    units: list[str] = []
    for char in text:
        if combining(char) and units:
            units[-1] += char
        else:
            units.append(char)
    pieces: list[str] = []
    current = ""
    for unit in units:
        pref = "↳" if pieces else ""
        if current and _font_width(font, pref + current + unit) > width:
            pieces.append(pref + current)
            current = ""
        current += unit
        if _font_width(font, ("↳" if pieces else "") + current) > width:
            # A single character/glyph cannot be safely rendered at this width.
            raise ValueError(f"Single identifier glyph wider than column width: {unit!r}")
    if current:
        pieces.append(("↳" if pieces else "") + current)
    return pieces


def lines_for_object(obj: DbObject, font: ImageFont.FreeTypeFont, max_width: int) -> list[FieldLine]:
    """Inline-pack field identifiers; each field is included in full, in ordinal order."""
    if not obj.columns:
        return [FieldLine("(no visible fields)", ())]
    out: list[FieldLine] = []
    text = ""
    indexes: list[int] = []
    sep = "  ·  "
    for idx, col in enumerate(obj.columns):
        label = visual_ident(col.name)
        trial = text + (sep if text else "") + label
        if _font_width(font, trial) <= max_width:
            text = trial
            indexes.append(idx)
            continue
        if text:
            out.append(FieldLine(text, tuple(indexes)))
            text, indexes = "", []
        if _font_width(font, label) <= max_width:
            text, indexes = label, [idx]
        else:
            pieces = _split_long(label, font, max_width)
            for piece in pieces:
                out.append(FieldLine(piece, (idx,)))
    if text:
        out.append(FieldLine(text, tuple(indexes)))
    return out


def _draw_plain(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
                font: ImageFont.FreeTypeFont, fill: str, max_width: int) -> None:
    if _font_width(font, text) > max_width + 0.01:
        raise AssertionError(f"Unexpected text overflow: {text[:100]}")
    draw.text(xy, text, font=font, fill=fill, anchor="lt")


def render(snapshot: Snapshot, outdir: Path, cfg: Config) -> dict[str, Any]:
    """Render images, image/object manifests and coverage report; no field is dropped."""
    outdir.mkdir(parents=True, exist_ok=True)
    pal = PALETTES[cfg.theme]
    body_font = load_font(cfg.font_size, cfg.font_path)
    title_font = load_font(cfg.font_size + 1, cfg.font_path)
    top_font = load_font(max(18, cfg.font_size + 3), cfg.font_path)
    small_font = load_font(max(14, cfg.font_size - 3), cfg.font_path)
    margin = 24
    gap = 18
    inner = 9
    top = 78
    bottom = cfg.height - 46
    col_width = (cfg.width - 2 * margin - (cfg.columns - 1) * gap) // cfg.columns
    text_width = col_width - 2 * inner
    line_height = int(math.ceil(cfg.font_size * 1.42))
    title_height = int(math.ceil((cfg.font_size + 1) * 1.55))
    tail_height = 7
    buffer = 8
    if bottom - top < title_height + line_height + tail_height + buffer:
        raise ValueError("Image too short for object header and field")
    lines = [lines_for_object(o, body_font, text_width) for o in snapshot.objects]
    names = [f"{visual_ident(o.schema)}.{visual_ident(o.name)}" for o in snapshot.objects]
    long_names = [_font_width(title_font, s) > col_width - inner*2 - 45 for s in names]
    for i, too_long in enumerate(long_names):
        if too_long:
            # Put every character of an unusually long object name into the body;
            # the header uses a stable numeric ID for continuations and the manifest
            # retains the original name without any change.
            lines[i] = [FieldLine(t, ()) for t in _split_long("Object name: " + names[i], body_font, text_width)] + lines[i]
    layout: list[Block] = []
    y = top
    page = 1
    col = 0
    block_counts = [0] * len(snapshot.objects)
    def advance() -> None:
        nonlocal y, page, col
        col += 1
        if col == cfg.columns:
            page += 1
            col = 0
        y = top
    for i, o in enumerate(snapshot.objects):
        pos = 0
        while pos < len(lines[i]):
            # Ensure there is enough space for the card header and at least one field line.
            space = bottom - y
            fit = (space - title_height - tail_height - buffer) // line_height
            if fit < 1:
                advance()
                continue
            n = min(len(lines[i]) - pos, int(fit))
            # Avoid fragmenting a new small object when next column can fit all of it.
            if pos == 0 and y != top and n < len(lines[i]) and len(lines[i]) <= 16:
                advance()
                continue
            block_height = title_height + n * line_height + tail_height
            block_counts[i] += 1
            layout.append(Block(i, block_counts[i], pos, pos+n, page, col,
                                margin + col*(col_width + gap), y, block_height))
            y += block_height + buffer
            pos += n
    count_pages = max((b.page for b in layout), default=1)
    pages: list[list[Block]] = [[] for _ in range(count_pages)]
    for b in layout:
        pages[b.page - 1].append(b)
    objects_by_image: dict[int, dict[int, set[int]]] = {i: {} for i in range(1, count_pages+1)}
    seen_fields: set[tuple[int, int]] = set()
    all_expected = {(i, j) for i, obj in enumerate(snapshot.objects) for j in range(len(obj.columns))}
    for pg_idx, blocks in enumerate(pages, 1):
        # Last page is cropped vertically to avoid wasting visual-model space.
        # Full pages retain the requested dimensions; the footer is redrawn at the
        # actual bottom so the crop never discards any field or page information.
        effective_height = cfg.height
        if pg_idx == count_pages and blocks:
            furthest = max(b.y + b.height for b in blocks)
            effective_height = min(cfg.height, max(240, furthest + 68))
        im = Image.new("RGB", (cfg.width, effective_height), pal["bg"])
        draw = ImageDraw.Draw(im)
        hdr = f"SQL Schema   {visual_ident(snapshot.database)}"
        hdr_max = cfg.width - margin*2 - 210
        if _font_width(top_font, hdr) > hdr_max:
            raise ValueError("Database name exceeds PNG header width. Use a smaller --font-size "
                             "or wider --width; nothing will be truncated.")
        _draw_plain(draw, (margin, 14), hdr, top_font, pal["text"], hdr_max)
        _draw_plain(draw, (cfg.width - margin - 172, 19), f"Page {pg_idx:03d}/{count_pages:03d}",
                    small_font, pal["muted"], 172)
        draw.line((margin, 65, cfg.width - margin, 65), fill=pal["line"], width=2)
        for b in blocks:
            obj = snapshot.objects[b.object_index]
            # Include zero-field tables/views in image_manifest.csv as well.
            objects_by_image[pg_idx].setdefault(b.object_index, set())
            src_lines = lines[b.object_index][b.start_line:b.end_line]
            x, iy = b.x, b.y
            draw.rectangle((x, iy, x+col_width, iy+b.height), outline=pal["line"], width=1)
            draw.rectangle((x+1, iy+1, x+col_width-1, iy+title_height-1), fill=pal["head"])
            tag = obj.kind
            _draw_plain(draw, (x+inner, iy+7), tag, title_font, pal["tagT" if tag=="T" else "tagV"], 30)
            title_width = col_width - inner*2 - 45
            title = names[b.object_index]
            if long_names[b.object_index]:
                title = f"Object #{b.object_index+1}"
            if b.part > 1:
                title += f"  [cont. {b.part}]"
            # For exceptionally high part numbers, shorten marker but never the real name.
            if _font_width(title_font, title) > title_width:
                title = f"#{b.object_index+1} [cont. {b.part}]"
            _draw_plain(draw, (x+inner+32, iy+7), title, title_font, pal["text"], title_width)
            for line_index, line in enumerate(src_lines):
                fy = iy + title_height + line_index * line_height + 4
                _draw_plain(draw, (x+inner, fy), line.text, body_font, pal["text"], text_width)
                for idx in line.indexes:
                    seen_fields.add((b.object_index, idx))
                    objects_by_image[pg_idx].setdefault(b.object_index, set()).add(idx)
            if b.end_line < len(lines[b.object_index]):
                # The continuation is explicit in the next segment header.
                pass
        footer = f"T {sum(o.kind=='T' for o in snapshot.objects)}  |  V {sum(o.kind=='V' for o in snapshot.objects)}  |  Fields {len(all_expected)}"
        _draw_plain(draw, (margin, effective_height-34), footer, small_font, pal["muted"], cfg.width - 2*margin)
        dest = outdir / f"schema_{pg_idx:03d}.png"
        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("Database", snapshot.database)
        pnginfo.add_text("Page", str(pg_idx))
        pnginfo.add_text("Notice", "Names only; see data/schema_snapshot.json for authoritative exact identifiers")
        im.save(dest, format="PNG", pnginfo=pnginfo, optimize=True)
        im.close()
    missing = all_expected - seen_fields
    extra = seen_fields - all_expected
    objects_seen = {b.object_index for b in layout}
    objects_expected = set(range(len(snapshot.objects)))
    if missing or extra or objects_seen != objects_expected:
        raise AssertionError(f"Incomplete coverage: missing {len(missing)}, extra {len(extra)}, "
                             f"objects missing {len(objects_expected - objects_seen)}")
    manifest_rows: list[dict[str, Any]] = []
    for image_num, indexed in objects_by_image.items():
        for oi in sorted(indexed):
            obj = snapshot.objects[oi]
            occurrences = sorted(indexed[oi])
            manifest_rows.append({"image": f"schema_{image_num:03d}.png", "type": obj.kind,
                                  "schema": obj.schema, "object_name": obj.name,
                                  "field_count_in_image": len(occurrences),
                                  "field_ordinals": ";".join(str(obj.columns[j].ordinal) for j in occurrences)})
    with (outdir / "image_manifest.csv").open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=["image", "type", "schema", "object_name",
                                                    "field_count_in_image", "field_ordinals"])
        writer.writeheader()
        writer.writerows(manifest_rows)
    report = {
        "status": "PASS", "database": snapshot.database,
        "tables": sum(o.kind == "T" for o in snapshot.objects),
        "views": sum(o.kind == "V" for o in snapshot.objects),
        "objects": len(snapshot.objects),
        "source_fields": len(all_expected), "layout_fields_covered": len(seen_fields),
        "images": count_pages, "missing_fields": 0,
        "render_config": {"width": cfg.width, "height": cfg.height,
                          "columns": cfg.columns, "font_size": cfg.font_size, "theme": cfg.theme},
        "note": "Logical layout coverage only; visual-model transcription accuracy is not guaranteed."
    }
    write_json(outdir / "render_report.json", report)
    return report
