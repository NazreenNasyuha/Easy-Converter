"""PDF rendering, compression, splitting, auto-cropping, numbering, and merging via PyMuPDF."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PIL import Image

from core.converters.image_ops import flatten_to_rgb, pil_to_pdf_bytes
from core.converters.path_utils import get_safe_output_path

try:
    import pymupdf as fitz  # PyMuPDF 2.0+
except ImportError:
    import fitz  # PyMuPDF <2.0


PDF_ACTION_IDS: frozenset[str] = frozenset({
    # PDF Formats (Shift Mode)
    "pdf_to_png",
    "pdf_to_jpg",
    "pdf_to_docx",
    "pdf_to_txt",
    "pdf_to_svg",
    # PDF Daily Tools (Alt Mode)
    "pdf_compress",
    "pdf_split_pages",
    "pdf_autocrop",
    "pdf_rotate_90",
    "pdf_add_page_numbers",
    "pdf_grayscale",
    "pdf_strip_meta",
})


def merge_files_to_pdf(paths: Sequence[str | Path]) -> Path:
    """Combine multiple PDF documents and/or images into a single merged PDF."""
    first = Path(paths[0])
    out_pdf = get_safe_output_path(first, new_ext=".pdf", suffix="_merged")
    merged_doc = fitz.open()
    try:
        for p in paths:
            src = Path(p)
            if src.suffix.lower() == ".pdf":
                with fitz.open(src) as pdf_part:
                    merged_doc.insert_pdf(pdf_part)
            else:
                with Image.open(src) as img:
                    rgb = flatten_to_rgb(img)
                    temp_bytes = pil_to_pdf_bytes(rgb)
                    with fitz.open("pdf", temp_bytes) as img_pdf:
                        merged_doc.insert_pdf(img_pdf)
        merged_doc.save(str(out_pdf), garbage=4, deflate=True)
    finally:
        merged_doc.close()
    return out_pdf


def run_pdf_action(action_id: str, src: Path) -> list[Path]:
    """Execute a single-file PDF conversion or daily PDF manipulation task."""
    if action_id in ("pdf_to_png", "pdf_to_jpg"):
        is_png = action_id == "pdf_to_png"
        ext = ".png" if is_png else ".jpg"
        created: list[Path] = []
        zoom = 300.0 / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        with fitz.open(src) as doc:
            page_count = len(doc)
            for idx, page in enumerate(doc):
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                suffix = "" if page_count == 1 else f"_page_{idx + 1}"
                dst = get_safe_output_path(src, new_ext=ext, suffix=suffix)
                if is_png:
                    pix.save(str(dst))
                else:
                    pix.pil_save(str(dst), format="JPEG", quality=92, optimize=True)
                created.append(dst)
        return created

    if action_id == "pdf_to_svg":
        created = []
        with fitz.open(src) as doc:
            page_count = len(doc)
            for idx, page in enumerate(doc):
                svg_text = page.get_svg_image()
                suffix = "" if page_count == 1 else f"_page_{idx + 1}"
                dst = get_safe_output_path(src, new_ext=".svg", suffix=suffix)
                dst.write_text(svg_text, encoding="utf-8")
                created.append(dst)
        return created

    if action_id == "pdf_to_docx":
        from docx import Document

        dst = get_safe_output_path(src, new_ext=".docx")
        word_doc = Document()
        word_doc.add_heading(src.stem, level=1)
        with fitz.open(src) as doc:
            for idx, page in enumerate(doc):
                if idx > 0:
                    word_doc.add_page_break()
                blocks = page.get_text("blocks")
                for b in blocks:
                    paragraph_text = str(b[4]).strip()
                    if paragraph_text:
                        word_doc.add_paragraph(paragraph_text)
        word_doc.save(str(dst))
        return [dst]

    if action_id == "pdf_compress":
        dst = get_safe_output_path(src, new_ext=".pdf", suffix="_compressed")
        with fitz.open(src) as doc:
            doc.save(
                str(dst),
                garbage=4,
                deflate=True,
                deflate_images=True,
                deflate_fonts=True,
                clean=True,
            )
        return [dst]

    if action_id == "pdf_to_txt":
        dst = get_safe_output_path(src, new_ext=".txt")
        chunks: list[str] = []
        with fitz.open(src) as doc:
            for idx, page in enumerate(doc):
                text = page.get_text("text").strip()
                if len(doc) > 1:
                    chunks.append(f"--- Page {idx + 1} ---\n{text}")
                else:
                    chunks.append(text)
        dst.write_text("\n\n".join(chunks), encoding="utf-8")
        return [dst]

    if action_id == "pdf_split_pages":
        created = []
        with fitz.open(src) as doc:
            for idx in range(len(doc)):
                single = fitz.open()
                try:
                    single.insert_pdf(doc, from_page=idx, to_page=idx)
                    dst = get_safe_output_path(src, new_ext=".pdf", suffix=f"_page_{idx + 1}")
                    single.save(str(dst), garbage=3, deflate=True)
                    created.append(dst)
                finally:
                    single.close()
        return created

    if action_id == "pdf_autocrop":
        dst = get_safe_output_path(src, new_ext=".pdf", suffix="_cropped")
        with fitz.open(src) as doc:
            for page in doc:
                rect = page.rect
                blocks = page.get_text("blocks")
                drawings = page.get_drawings()
                bbox = fitz.Rect()
                for b in blocks:
                    bbox |= fitz.Rect(b[:4])
                for d in drawings:
                    if d.get("rect"):
                        bbox |= fitz.Rect(d["rect"])
                if not bbox.is_empty and bbox.width > 20 and bbox.height > 20:
                    pad = 14.0
                    cropped = fitz.Rect(
                        max(rect.x0, bbox.x0 - pad),
                        max(rect.y0, bbox.y0 - pad),
                        min(rect.x1, bbox.x1 + pad),
                        min(rect.y1, bbox.y1 + pad),
                    )
                    page.set_cropbox(cropped)
            doc.save(str(dst), garbage=4, deflate=True)
        return [dst]

    if action_id == "pdf_rotate_90":
        dst = get_safe_output_path(src, new_ext=".pdf", suffix="_rot90")
        with fitz.open(src) as doc:
            for page in doc:
                page.set_rotation((page.rotation + 90) % 360)
            doc.save(str(dst), garbage=3, deflate=True)
        return [dst]

    if action_id == "pdf_add_page_numbers":
        dst = get_safe_output_path(src, new_ext=".pdf", suffix="_numbered")
        with fitz.open(src) as doc:
            total = len(doc)
            for idx, page in enumerate(doc, start=1):
                r = page.rect
                footer = f"Page {idx} of {total}"
                page.insert_text(
                    fitz.Point(r.width / 2.0 - 28.0, r.height - 18.0),
                    footer,
                    fontsize=9.5,
                    fontname="helv",
                    color=(0.35, 0.38, 0.44),
                )
            doc.save(str(dst), garbage=3, deflate=True)
        return [dst]

    if action_id == "pdf_grayscale":
        dst = get_safe_output_path(src, new_ext=".pdf", suffix="_bw")
        zoom = 200.0 / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        out_doc = fitz.open()
        try:
            with fitz.open(src) as doc:
                for page in doc:
                    pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY, alpha=False)
                    new_page = out_doc.new_page(width=page.rect.width, height=page.rect.height)
                    new_page.insert_image(page.rect, pixmap=pix)
            out_doc.save(str(dst), garbage=4, deflate=True)
        finally:
            out_doc.close()
        return [dst]

    if action_id == "pdf_strip_meta":
        dst = get_safe_output_path(src, new_ext=".pdf", suffix="_clean")
        with fitz.open(src) as doc:
            doc.set_metadata({})
            doc.del_xml_metadata()
            doc.save(str(dst), garbage=4, deflate=True, clean=True)
        return [dst]

    raise ValueError(f"Unknown PDF action_id: {action_id}")
