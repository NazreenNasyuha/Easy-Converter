"""Presentation / Slides conversion and daily slide deck tools (.pptx, .ppt, .odp)."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from core.converters.path_utils import format_saved_summary, get_safe_output_path
from core.models import ConversionResult

try:
    import pymupdf as fitz
except ImportError:
    import fitz


SLIDES_ACTION_IDS: frozenset[str] = frozenset({
    # Slides Formats (Shift Mode)
    "slides_to_pdf",
    "slides_to_png",
    "slides_to_jpg",
    "slides_to_txt",
    "slides_to_md",
    # Slides Daily Tools (Alt Mode)
    "slides_extract_media",
    "slides_export_notes",
    "slides_handout_pdf",
    "slides_compress",
    "slides_strip_notes",
    "slides_extract_links",
    "slides_stats",
})


@dataclass
class SlideContent:
    """Extracted text, notes, links, and image blobs for a single presentation slide."""

    index: int
    title: str
    bullets: list[str] = field(default_factory=list)
    notes: str = ""
    links: list[str] = field(default_factory=list)
    image_blobs: list[bytes] = field(default_factory=list)


def extract_slides_content(src: Path) -> list[SlideContent]:
    """Extract structured slide titles, body bullets, speaker notes, links, and images from `.pptx`."""
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    prs = Presentation(str(src))
    slides_data: list[SlideContent] = []

    for idx, slide in enumerate(prs.slides, start=1):
        title_text = ""
        if slide.shapes.title and slide.shapes.title.text:
            title_text = slide.shapes.title.text.strip()

        bullets: list[str] = []
        links: list[str] = []
        images: list[bytes] = []

        for shape in slide.shapes:
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                try:
                    images.append(shape.image.blob)
                except Exception:
                    pass
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    t = para.text.strip()
                    if t and t != title_text:
                        bullets.append(t)
                    for run in para.runs:
                        try:
                            if run.hyperlink and run.hyperlink.address:
                                links.append(run.hyperlink.address)
                        except Exception:
                            pass
            if shape.has_table:
                for row in shape.table.rows:
                    row_str = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                    if row_str:
                        bullets.append(row_str)

        notes_text = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes_text = slide.notes_slide.notes_text_frame.text.strip()

        for text_chunk in [title_text, *bullets, notes_text]:
            for url in re.findall(r"https?://[^\s<>\"')]+", text_chunk):
                if url not in links:
                    links.append(url)

        if not title_text:
            title_text = f"Slide {idx}"

        slides_data.append(
            SlideContent(
                index=idx,
                title=title_text,
                bullets=bullets,
                notes=notes_text,
                links=links,
                image_blobs=images,
            )
        )

    return slides_data


def _build_slides_pdf_doc(slides: list[SlideContent]) -> fitz.Document:
    """Render extracted `SlideContent` items into a 16:9 widescreen PyMuPDF `Document`."""
    doc = fitz.open()
    w, h = 960.0, 540.0

    for s in slides:
        page = doc.new_page(width=w, height=h)
        page.draw_rect(fitz.Rect(0, 0, w, h), color=(0.97, 0.98, 0.99), fill=(0.97, 0.98, 0.99))
        page.draw_rect(fitz.Rect(0, 0, w, 78), color=(0.12, 0.16, 0.24), fill=(0.12, 0.16, 0.24))

        page.insert_text(
            fitz.Point(44, 50),
            s.title[:80],
            fontsize=24,
            fontname="helv",
            color=(1.0, 1.0, 1.0),
        )

        text_right = 580.0 if s.image_blobs else (w - 48.0)
        y = 118.0
        for b in s.bullets:
            if y > h - 55.0:
                break
            line = f"•  {b}"
            page.insert_textbox(
                fitz.Rect(48.0, y, text_right, y + 60.0),
                line,
                fontsize=15,
                fontname="helv",
                color=(0.15, 0.20, 0.28),
            )
            y += 38.0 if len(line) < 65 else 62.0

        if s.image_blobs:
            try:
                img_rect = fitz.Rect(600.0, 110.0, w - 44.0, h - 60.0)
                page.insert_image(img_rect, stream=s.image_blobs[0], keep_proportion=True)
            except Exception:
                pass

        page.insert_text(
            fitz.Point(w - 90.0, h - 22.0),
            f"Slide {s.index}",
            fontsize=11,
            fontname="helv",
            color=(0.45, 0.50, 0.58),
        )

    return doc


def _build_handout_pdf_doc(slides: list[SlideContent], deck_title: str) -> fitz.Document:
    """Build a printable A4 2-up slide handout PDF with lined note boxes next to each slide."""
    doc = fitz.open()
    page_w, page_h = 595.0, 842.0  # A4 Portrait
    page = None

    for idx, s in enumerate(slides):
        slot = idx % 2
        if slot == 0:
            page = doc.new_page(width=page_w, height=page_h)
            page.insert_text(
                fitz.Point(40.0, 34.0),
                f"{deck_title} — Printable Handout",
                fontsize=12,
                fontname="helv",
                color=(0.25, 0.30, 0.38),
            )

        assert page is not None
        top_y = 56.0 + slot * 380.0
        slide_rect = fitz.Rect(40.0, top_y, 330.0, top_y + 180.0)
        page.draw_rect(slide_rect, color=(0.75, 0.80, 0.86), fill=(0.98, 0.99, 1.0), width=1.2)
        page.draw_rect(
            fitz.Rect(40.0, top_y, 330.0, top_y + 32.0),
            color=(0.12, 0.16, 0.24),
            fill=(0.12, 0.16, 0.24),
        )
        page.insert_text(
            fitz.Point(50.0, top_y + 21.0),
            f"{s.index}. {s.title[:40]}",
            fontsize=11,
            fontname="helv",
            color=(1.0, 1.0, 1.0),
        )

        by = top_y + 48.0
        for b in s.bullets[:4]:
            page.insert_textbox(
                fitz.Rect(50.0, by, 320.0, by + 28.0),
                f"• {b[:70]}",
                fontsize=9,
                fontname="helv",
                color=(0.15, 0.20, 0.28),
            )
            by += 28.0

        # Lined notes column on right + speaker notes below
        notes_x = 348.0
        page.insert_text(
            fitz.Point(notes_x, top_y + 14.0),
            "Notes:",
            fontsize=9.5,
            fontname="helv",
            color=(0.4, 0.45, 0.52),
        )
        for line_i in range(6):
            ly = top_y + 34.0 + line_i * 26.0
            page.draw_line(
                fitz.Point(notes_x, ly),
                fitz.Point(page_w - 40.0, ly),
                color=(0.82, 0.85, 0.90),
                width=0.8,
            )

        if s.notes:
            page.insert_textbox(
                fitz.Rect(40.0, top_y + 190.0, page_w - 40.0, top_y + 345.0),
                f"Speaker Notes: {s.notes}",
                fontsize=9,
                fontname="helv",
                color=(0.30, 0.35, 0.42),
            )

    return doc


def run_slides_action(
    action_id: str,
    action_label: str,
    src: Path,
) -> ConversionResult:
    """Execute a presentation format conversion or daily slide deck tool."""
    slides = extract_slides_content(src)

    if action_id == "slides_stats":
        all_words = " ".join(
            f"{s.title} {' '.join(s.bullets)} {s.notes}" for s in slides
        ).split()
        total_images = sum(len(s.image_blobs) for s in slides)
        speak_min = max(1, round(len(all_words) / 130))
        summary = f"{len(slides)} Slides | {len(all_words)} Words (~{speak_min} min talk) | {total_images} Images"
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(src)],
            clipboard_text=f"{src.name}: {summary}",
            summary_text=summary,
        )

    if action_id == "slides_to_pdf":
        dst = get_safe_output_path(src, new_ext=".pdf")
        pdf_doc = _build_slides_pdf_doc(slides)
        try:
            pdf_doc.save(str(dst), garbage=4, deflate=True)
        finally:
            pdf_doc.close()
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "slides_handout_pdf":
        dst = get_safe_output_path(src, new_ext=".pdf", suffix="_handout")
        pdf_doc = _build_handout_pdf_doc(slides, src.stem)
        try:
            pdf_doc.save(str(dst), garbage=4, deflate=True)
        finally:
            pdf_doc.close()
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id in ("slides_to_png", "slides_to_jpg"):
        is_png = action_id == "slides_to_png"
        ext = ".png" if is_png else ".jpg"
        created: list[Path] = []
        pdf_doc = _build_slides_pdf_doc(slides)
        try:
            zoom = 2.0
            mat = fitz.Matrix(zoom, zoom)
            page_count = len(pdf_doc)
            for idx, page in enumerate(pdf_doc, start=1):
                pix = page.get_pixmap(matrix=mat, alpha=False)
                suffix = "" if page_count == 1 else f"_slide_{idx}"
                dst = get_safe_output_path(src, new_ext=ext, suffix=suffix)
                if is_png:
                    pix.save(str(dst))
                else:
                    pix.pil_save(str(dst), format="JPEG", quality=92, optimize=True)
                created.append(dst)
        finally:
            pdf_doc.close()
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(p) for p in created],
            summary_text=format_saved_summary(created),
        )

    if action_id == "slides_to_txt":
        dst = get_safe_output_path(src, new_ext=".txt")
        blocks: list[str] = []
        for s in slides:
            lines = [f"=== Slide {s.index}: {s.title} ==="]
            lines.extend(f"  - {b}" for b in s.bullets)
            if s.notes:
                lines.append(f"  [Notes]: {s.notes}")
            blocks.append("\n".join(lines))
        dst.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "slides_to_md":
        dst = get_safe_output_path(src, new_ext=".md")
        md_blocks: list[str] = [f"# {src.stem}", ""]
        for s in slides:
            md_blocks.append(f"## Slide {s.index}: {s.title}")
            for b in s.bullets:
                md_blocks.append(f"- {b}")
            if s.notes:
                md_blocks.append(f"\n> **Speaker Notes:** {s.notes}")
            md_blocks.append("")
        dst.write_text("\n".join(md_blocks).strip() + "\n", encoding="utf-8")
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "slides_export_notes":
        dst = get_safe_output_path(src, new_ext=".txt", suffix="_notes")
        notes_list = [
            f"--- Slide {s.index}: {s.title} ---\n{s.notes if s.notes else '(No speaker notes)'}"
            for s in slides
        ]
        dst.write_text("\n\n".join(notes_list) + "\n", encoding="utf-8")
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "slides_strip_notes":
        from pptx import Presentation

        dst = get_safe_output_path(src, new_ext=".pptx", suffix="_clean")
        prs = Presentation(str(src))
        for slide in prs.slides:
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                slide.notes_slide.notes_text_frame.text = ""
        prs.save(str(dst))
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "slides_extract_links":
        all_links: list[str] = []
        for s in slides:
            for link in s.links:
                if link not in all_links:
                    all_links.append(link)
        dst = get_safe_output_path(src, new_ext=".txt", suffix="_links")
        body = "\n".join(all_links) if all_links else "(No hyperlinks found in slide deck)"
        dst.write_text(body + "\n", encoding="utf-8")
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            clipboard_text=body,
            summary_text=f"Extracted {len(all_links)} link{'s' if len(all_links) != 1 else ''}",
        )

    if action_id == "slides_extract_media":
        media_dir = src.parent / f"{src.stem}_media"
        extracted: list[Path] = []
        if zipfile.is_zipfile(src):
            with zipfile.ZipFile(src, "r") as zf:
                for member in zf.namelist():
                    if member.startswith("ppt/media/"):
                        media_dir.mkdir(parents=True, exist_ok=True)
                        out_file = get_safe_output_path(media_dir / Path(member).name)
                        out_file.write_bytes(zf.read(member))
                        extracted.append(out_file)
        if not extracted:
            return ConversionResult(
                success=True,
                action_id=action_id,
                action_label=action_label,
                output_paths=[str(src)],
                summary_text="No embedded slide media found",
            )
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(p) for p in extracted],
            summary_text=f"Extracted {len(extracted)} media file{'s' if len(extracted) > 1 else ''}",
        )

    if action_id == "slides_compress":
        dst = get_safe_output_path(src, new_ext=".pptx", suffix="_compressed")
        with zipfile.ZipFile(src, "r") as zin, zipfile.ZipFile(
            dst, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as zout:
            for item in zin.infolist():
                zout.writestr(item, zin.read(item.filename))
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    raise ValueError(f"Unknown slides action_id: {action_id}")
