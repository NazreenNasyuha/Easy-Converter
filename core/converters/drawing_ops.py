"""Vector & CAD Drawing conversion and daily engineering tools (.svg, .dxf, .eps, .emf, .wmf)."""

from __future__ import annotations

import io
import re
from pathlib import Path

from PIL import Image, ImageOps

from core.converters.image_ops import flatten_to_rgb, remove_image_background
from core.converters.path_utils import format_saved_summary, get_safe_output_path
from core.models import ConversionResult

try:
    import pymupdf as fitz
except ImportError:
    import fitz


DRAWING_ACTION_IDS: frozenset[str] = frozenset({
    # Drawing Formats (Shift Mode)
    "draw_to_png",
    "draw_to_pdf",
    "draw_to_svg",
    "draw_to_dxf",
    "draw_to_jpg",
    "draw_to_webp",
    # Drawing Daily Tools (Alt Mode)
    "draw_render_hd",
    "draw_transparent_png",
    "draw_blueprint_pdf",
    "draw_optimize",
    "draw_grayscale",
    "draw_extract_layers",
    "draw_inspect_info",
})


def _dxf_to_svg_string(
    src: Path,
    bg_hex: str = "#ffffff",
    stroke_hex: str = "#0f172a",
    transparent_bg: bool = False,
) -> tuple[str, int, tuple[float, float, float, float]]:
    """Convert a `.dxf` CAD file into a standalone SVG string and return `(svg, count, bbox)`."""
    import ezdxf

    doc = ezdxf.readfile(str(src))
    msp = doc.modelspace()

    segments: list[tuple[float, float, float, float]] = []
    circles: list[tuple[float, float, float]] = []

    for entity in msp:
        dxftype = entity.dxftype()
        if dxftype == "LINE":
            s = entity.dxf.start
            e = entity.dxf.end
            segments.append((float(s.x), float(s.y), float(e.x), float(e.y)))
        elif dxftype in ("LWPOLYLINE", "POLYLINE"):
            try:
                pts = [(float(p[0]), float(p[1])) for p in entity.get_points()]
            except Exception:
                pts = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in entity.vertices]
            for i in range(len(pts) - 1):
                segments.append((pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]))
            if getattr(entity, "closed", False) and len(pts) > 2:
                segments.append((pts[-1][0], pts[-1][1], pts[0][0], pts[0][1]))
        elif dxftype == "CIRCLE":
            c = entity.dxf.center
            r = float(entity.dxf.radius)
            circles.append((float(c.x), float(c.y), r))

    xs: list[float] = []
    ys: list[float] = []
    for x1, y1, x2, y2 in segments:
        xs.extend((x1, x2))
        ys.extend((y1, y2))
    for cx, cy, r in circles:
        xs.extend((cx - r, cx + r))
        ys.extend((cy - r, cy + r))

    if not xs or not ys:
        xs, ys = [0.0, 200.0], [0.0, 200.0]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)
    pad = max(span_x, span_y) * 0.06
    vb_x = min_x - pad
    vb_y = min_y - pad
    vb_w = span_x + 2 * pad
    vb_h = span_y + 2 * pad
    stroke_w = max(vb_w, vb_h) * 0.0035

    svg_elems: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb_x:.3f} {vb_y:.3f} {vb_w:.3f} {vb_h:.3f}" '
        f'width="800" height="600">',
    ]
    if not transparent_bg:
        svg_elems.append(
            f'<rect x="{vb_x:.3f}" y="{vb_y:.3f}" width="{vb_w:.3f}" height="{vb_h:.3f}" fill="{bg_hex}"/>'
        )
    svg_elems.append(
        f'<g stroke="{stroke_hex}" stroke-width="{stroke_w:.4f}" fill="none" stroke-linecap="round">'
    )
    for x1, y1, x2, y2 in segments:
        sy1 = max_y + min_y - y1
        sy2 = max_y + min_y - y2
        svg_elems.append(f'<line x1="{x1:.3f}" y1="{sy1:.3f}" x2="{x2:.3f}" y2="{sy2:.3f}"/>')
    for cx, cy, r in circles:
        scy = max_y + min_y - cy
        svg_elems.append(f'<circle cx="{cx:.3f}" cy="{scy:.3f}" r="{r:.3f}"/>')
    svg_elems.append("</g></svg>")

    total_entities = len(segments) + len(circles)
    return "\n".join(svg_elems), total_entities, (min_x, min_y, max_x, max_y)


def _render_drawing_to_pixmap(
    src: Path,
    dpi: float = 300.0,
    alpha: bool = False,
) -> fitz.Pixmap:
    """Render `.svg`, `.dxf`, or vector drawing file to a PyMuPDF `Pixmap` at `dpi`."""
    ext = src.suffix.lower()
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    if ext == ".dxf":
        svg_str, _, _ = _dxf_to_svg_string(src, transparent_bg=alpha)
        with fitz.open(stream=svg_str.encode("utf-8"), filetype="svg") as doc:
            return doc[0].get_pixmap(matrix=mat, alpha=alpha)

    if ext == ".svg":
        with fitz.open(str(src)) as doc:
            return doc[0].get_pixmap(matrix=mat, alpha=alpha)

    with Image.open(src) as img:
        rgb = flatten_to_rgb(img)
        buf = io.BytesIO()
        rgb.save(buf, format="PNG")
        return fitz.Pixmap(buf.getvalue())


def _export_to_dxf(src: Path, dst: Path) -> Path:
    """Convert a drawing (`.svg`, etc.) into a `.dxf` CAD file with bounding geometry & polylines."""
    import ezdxf

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    if src.suffix.lower() == ".svg":
        raw = src.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(
            r'<line[^>]*x1="([\d.-]+)"[^>]*y1="([\d.-]+)"[^>]*x2="([\d.-]+)"[^>]*y2="([\d.-]+)"',
            raw,
        ):
            x1, y1, x2, y2 = (float(match.group(i)) for i in range(1, 5))
            msp.add_line((x1, -y1), (x2, -y2))

        for match in re.finditer(
            r'<circle[^>]*cx="([\d.-]+)"[^>]*cy="([\d.-]+)"[^>]*r="([\d.-]+)"',
            raw,
        ):
            cx, cy, r = (float(match.group(i)) for i in range(1, 4))
            msp.add_circle((cx, -cy), r)

    if len(msp) == 0:
        pix = _render_drawing_to_pixmap(src, dpi=72.0)
        w, h = float(pix.width), float(pix.height)
        msp.add_lwpolyline([(0, 0), (w, 0), (w, h), (0, h), (0, 0)], close=True)

    doc.saveas(str(dst))
    return dst


def run_drawing_action(
    action_id: str,
    action_label: str,
    src: Path,
) -> ConversionResult:
    """Execute a vector/CAD drawing conversion or daily engineering tool operation."""
    ext = src.suffix.lower()

    if action_id == "draw_inspect_info":
        if ext == ".dxf":
            _, count, (min_x, min_y, max_x, max_y) = _dxf_to_svg_string(src)
            summary = f"DXF: {count} Entities | Bounds: {max_x - min_x:.1f} × {max_y - min_y:.1f}"
        else:
            pix = _render_drawing_to_pixmap(src, dpi=72.0)
            summary = f"Vector {ext.upper()}: {pix.width} × {pix.height} pt"
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(src)],
            clipboard_text=f"{src.name} — {summary}",
            summary_text=summary,
        )

    if action_id == "draw_extract_layers":
        dst = get_safe_output_path(src, new_ext=".txt", suffix="_layers")
        lines = [f"=== Drawing Layer & Entity Report: {src.name} ==="]
        if ext == ".dxf":
            import ezdxf

            doc = ezdxf.readfile(str(src))
            layer_counts: dict[str, int] = {}
            type_counts: dict[str, int] = {}
            for e in doc.modelspace():
                lyr = getattr(e.dxf, "layer", "0")
                layer_counts[lyr] = layer_counts.get(lyr, 0) + 1
                dt = e.dxftype()
                type_counts[dt] = type_counts.get(dt, 0) + 1
            lines.append(f"Total Layers: {len(doc.layers)} | Active Entities: {sum(type_counts.values())}")
            lines.append("\n[By Layer]:")
            for k, v in sorted(layer_counts.items()):
                lines.append(f"  • {k}: {v} entities")
            lines.append("\n[By Entity Type]:")
            for k, v in sorted(type_counts.items()):
                lines.append(f"  • {k}: {v}")
        else:
            raw = src.read_text(encoding="utf-8", errors="replace")
            tags = re.findall(r"<(path|rect|circle|line|polygon|polyline|text|g)\b", raw)
            counts: dict[str, int] = {}
            for t in tags:
                counts[t] = counts.get(t, 0) + 1
            lines.append(f"Total Vector Elements: {len(tags)}")
            for k, v in sorted(counts.items()):
                lines.append(f"  • <{k}>: {v}")
        dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id in ("draw_to_png", "draw_render_hd"):
        is_hd = action_id == "draw_render_hd"
        dpi = 600.0 if is_hd else 300.0
        dst = get_safe_output_path(src, new_ext=".png", suffix="_600dpi" if is_hd else "")
        pix = _render_drawing_to_pixmap(src, dpi=dpi, alpha=False)
        pix.save(str(dst))
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "draw_transparent_png":
        dst = get_safe_output_path(src, new_ext=".png", suffix="_alpha")
        pix = _render_drawing_to_pixmap(src, dpi=300.0, alpha=True)
        png_bytes = pix.tobytes("png")
        with Image.open(io.BytesIO(png_bytes)) as img:
            rgba = img.convert("RGBA")
            # If opaque background existed in SVG, strip background color cleanly
            cutout = remove_image_background(rgba)
            cutout.save(dst, format="PNG", optimize=True)
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "draw_blueprint_pdf":
        dst = get_safe_output_path(src, new_ext=".pdf", suffix="_blueprint")
        if ext == ".dxf":
            svg_str, _, _ = _dxf_to_svg_string(src, bg_hex="#0b2545", stroke_hex="#64dfdf")
            with fitz.open(stream=svg_str.encode("utf-8"), filetype="svg") as svg_doc:
                dst.write_bytes(svg_doc.convert_to_pdf())
        else:
            pix = _render_drawing_to_pixmap(src, dpi=300.0)
            out_doc = fitz.open()
            page = out_doc.new_page(width=pix.width, height=pix.height)
            page.draw_rect(page.rect, color=(0.04, 0.15, 0.27), fill=(0.04, 0.15, 0.27))
            page.insert_image(page.rect, pixmap=pix)
            out_doc.save(str(dst), garbage=4, deflate=True)
            out_doc.close()
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "draw_to_jpg":
        dst = get_safe_output_path(src, new_ext=".jpg")
        pix = _render_drawing_to_pixmap(src, dpi=300.0)
        if pix.alpha:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        pix.pil_save(str(dst), format="JPEG", quality=92, optimize=True)
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "draw_to_webp":
        dst = get_safe_output_path(src, new_ext=".webp")
        pix = _render_drawing_to_pixmap(src, dpi=300.0)
        pix.pil_save(str(dst), format="WEBP", quality=90)
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "draw_grayscale":
        dst = get_safe_output_path(src, new_ext=".png", suffix="_bw")
        pix = _render_drawing_to_pixmap(src, dpi=300.0)
        png_bytes = pix.tobytes("png")
        with Image.open(io.BytesIO(png_bytes)) as img:
            gray = ImageOps.grayscale(flatten_to_rgb(img))
            gray.save(dst, format="PNG", optimize=True)
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "draw_to_svg":
        dst = get_safe_output_path(src, new_ext=".svg")
        if ext == ".dxf":
            svg_str, _, _ = _dxf_to_svg_string(src)
            dst.write_text(svg_str, encoding="utf-8")
        else:
            with fitz.open(str(src)) as doc:
                dst.write_text(doc[0].get_svg_image(), encoding="utf-8")
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "draw_to_pdf":
        dst = get_safe_output_path(src, new_ext=".pdf")
        if ext == ".dxf":
            svg_str, _, _ = _dxf_to_svg_string(src)
            with fitz.open(stream=svg_str.encode("utf-8"), filetype="svg") as svg_doc:
                pdf_bytes = svg_doc.convert_to_pdf()
            dst.write_bytes(pdf_bytes)
        elif ext == ".svg":
            with fitz.open(str(src)) as svg_doc:
                pdf_bytes = svg_doc.convert_to_pdf()
            dst.write_bytes(pdf_bytes)
        else:
            pix = _render_drawing_to_pixmap(src, dpi=300.0)
            out_doc = fitz.open()
            page = out_doc.new_page(width=pix.width, height=pix.height)
            page.insert_image(page.rect, pixmap=pix)
            out_doc.save(str(dst), garbage=4, deflate=True)
            out_doc.close()
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "draw_to_dxf":
        dst = get_safe_output_path(src, new_ext=".dxf")
        _export_to_dxf(src, dst)
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "draw_optimize":
        if ext == ".svg":
            dst = get_safe_output_path(src, new_ext=".svg", suffix="_min")
            raw = src.read_text(encoding="utf-8", errors="replace")
            no_comments = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
            minified = re.sub(r">\s+<", "><", no_comments).strip()
            dst.write_text(minified, encoding="utf-8")
        elif ext == ".dxf":
            import ezdxf

            dst = get_safe_output_path(src, new_ext=".dxf", suffix="_clean")
            doc = ezdxf.readfile(str(src))
            doc.saveas(str(dst))
        else:
            dst = get_safe_output_path(src, new_ext=src.suffix, suffix="_clean")
            dst.write_bytes(src.read_bytes())
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    raise ValueError(f"Unknown drawing action_id: {action_id}")
