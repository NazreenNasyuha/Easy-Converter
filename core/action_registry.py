"""Action registry mapping `(file_extensions, ModifierMode)` to `SliceAction` descriptors.

Supports all 9 primary file categories in both Shift (Format Conversion) and Alt (Daily Tools) modes:
1. Images      2. Video       3. Audio
4. PDF         5. Document    6. Slides
7. Spreadsheet 8. Archives    9. Drawing
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from core.config import (
    ARCHIVE_EXTS,
    AUDIO_EXTS,
    DOCUMENT_EXTS,
    DRAWING_EXTS,
    IMAGE_EXTS,
    PDF_EXTS,
    SLIDES_EXTS,
    SPREADSHEET_EXTS,
    VIDEO_EXTS,
)
from core.models import ModifierMode, SliceAction

__all__ = [
    "ARCHIVE_EXTS",
    "AUDIO_EXTS",
    "DOCUMENT_EXTS",
    "DRAWING_EXTS",
    "IMAGE_EXTS",
    "ModifierMode",
    "PDF_EXTS",
    "SLIDES_EXTS",
    "SPREADSHEET_EXTS",
    "SliceAction",
    "VIDEO_EXTS",
    "format_center_badge",
    "get_actions_for_files",
    "get_ctrl_actions",
    "normalize_ext",
]


def normalize_ext(ext: str) -> str:
    """Normalize equivalent file extensions for source-extension filtering."""
    ext = ext.lower()
    mapping = {
        ".jpeg": ".jpg",
        ".tif": ".tiff",
        ".heif": ".heic",
        ".htm": ".html",
        ".markdown": ".md",
        ".doc": ".docx",
        ".ppt": ".pptx",
        ".xls": ".xlsx",
        ".tgz": ".gz",
    }
    return mapping.get(ext, ext)


def format_center_badge(file_paths: Sequence[str]) -> str:
    """Return the center deadzone badge text (e.g. `.HEIC` or `3 Files`)."""
    if not file_paths:
        return "DEMO"
    if len(file_paths) == 1:
        ext = Path(file_paths[0]).suffix.upper()
        return ext if ext else "FILE"
    return f"{len(file_paths)} Files"


def get_ctrl_actions() -> list[SliceAction]:
    """Return Ctrl Mode quick utility actions (compatible with any file type)."""
    return [
        SliceAction("util_copy_path", "Copy Path", "To Clipboard", mode=ModifierMode.CTRL),
        SliceAction("util_copy_name", "Copy Name", "Filename Only", mode=ModifierMode.CTRL),
        SliceAction("util_duplicate", "Duplicate", "Copy in Folder", mode=ModifierMode.CTRL),
        SliceAction("pack_zip", "Pack .ZIP", "Archive Files", target_ext=".zip", mode=ModifierMode.CTRL),
        SliceAction("util_sha256", "SHA-256", "Copy Checksum", mode=ModifierMode.CTRL),
    ]


def _filter_source_ext(
    candidates: list[SliceAction],
    norm_exts: set[str],
    min_slices: int = 3,
) -> list[SliceAction]:
    """Filter out the source file's own extension if all inputs share one normalized extension."""
    if len(norm_exts) == 1:
        only_ext = next(iter(norm_exts))
        filtered = [c for c in candidates if normalize_ext(c.target_ext or "") != only_ext]
        if len(filtered) >= min_slices:
            return filtered
    return candidates


def get_actions_for_files(
    file_paths: Sequence[str],
    mode: ModifierMode = ModifierMode.SHIFT,
) -> list[SliceAction]:
    """Determine the radial menu slices (`3 <= N <= 8`) for the given files and modifier mode."""
    if mode is ModifierMode.CTRL:
        return get_ctrl_actions()

    if not file_paths:
        file_paths = ["sample_photo.heic"]

    raw_exts = [Path(p).suffix.lower() for p in file_paths]
    norm_exts = {normalize_ext(e) for e in raw_exts}
    is_multi = len(file_paths) > 1

    all_images = all(e in IMAGE_EXTS for e in raw_exts)
    all_videos = all(e in VIDEO_EXTS for e in raw_exts)
    all_audio = all(e in AUDIO_EXTS for e in raw_exts)
    all_pdfs = all(e in PDF_EXTS for e in raw_exts)
    all_docs = all(e in DOCUMENT_EXTS for e in raw_exts)
    all_slides = all(e in SLIDES_EXTS for e in raw_exts)
    all_sheets = all(e in SPREADSHEET_EXTS for e in raw_exts)
    all_archives = all(e in ARCHIVE_EXTS for e in raw_exts)
    all_drawings = all(e in DRAWING_EXTS for e in raw_exts)
    all_img_or_pdf = all((e in IMAGE_EXTS or e in PDF_EXTS) for e in raw_exts)

    if mode is ModifierMode.ALT:
        return _get_alt_actions(
            all_images=all_images,
            all_videos=all_videos,
            all_audio=all_audio,
            all_pdfs=all_pdfs,
            all_docs=all_docs,
            all_slides=all_slides,
            all_sheets=all_sheets,
            all_archives=all_archives,
            all_drawings=all_drawings,
            all_img_or_pdf=all_img_or_pdf,
            is_multi=is_multi,
        )

    return _get_shift_actions(
        norm_exts=norm_exts,
        all_images=all_images,
        all_videos=all_videos,
        all_audio=all_audio,
        all_pdfs=all_pdfs,
        all_docs=all_docs,
        all_slides=all_slides,
        all_sheets=all_sheets,
        all_archives=all_archives,
        all_drawings=all_drawings,
        all_img_or_pdf=all_img_or_pdf,
        is_multi=is_multi,
    )


def _get_alt_actions(
    *,
    all_images: bool,
    all_videos: bool,
    all_audio: bool,
    all_pdfs: bool,
    all_docs: bool,
    all_slides: bool,
    all_sheets: bool,
    all_archives: bool,
    all_drawings: bool,
    all_img_or_pdf: bool,
    is_multi: bool,
) -> list[SliceAction]:
    """Build slice descriptors for Alt Mode (Daily Life Tools across all 9 categories)."""
    # 1. Images (8 Daily Image Tools: Remove BG, Crop & Edit Studio, 1:1 Crop, Resize, Upscale, Compress, Enhance, EXIF)
    if all_images:
        return [
            SliceAction("img_remove_bg", "Remove BG", "Transparent PNG", target_ext=".png", mode=ModifierMode.ALT),
            SliceAction("img_crop_edit", "Crop & Edit", "Interactive Studio", mode=ModifierMode.ALT),
            SliceAction("img_crop_square", "Square 1:1", "Center Avatar", mode=ModifierMode.ALT),
            SliceAction("img_resize_50", "Resize 50%", "Half Dimensions", mode=ModifierMode.ALT),
            SliceAction("img_upscale_2x", "Upscale 2x", "200% Super-Res", mode=ModifierMode.ALT),
            SliceAction("img_compress_web", "Compress Web", "80% Quality", mode=ModifierMode.ALT),
            SliceAction("img_auto_enhance", "Auto Enhance", "Fix Color/Contrast", mode=ModifierMode.ALT),
            SliceAction("img_strip_exif", "Strip EXIF", "Privacy Clean", mode=ModifierMode.ALT),
        ]

    # 2. Video (8 Daily Video Tools)
    if all_videos:
        return [
            SliceAction("vid_compress_50", "Compress 50%", "CRF 28 H.264", mode=ModifierMode.ALT),
            SliceAction("vid_downscale_720p", "720p Scale", "HD Downscale", mode=ModifierMode.ALT),
            SliceAction("vid_1080p", "1080p FullHD", "Normalize 1080p", mode=ModifierMode.ALT),
            SliceAction("vid_trim_10s", "Trim 10s", "First 10 Secs", mode=ModifierMode.ALT),
            SliceAction("vid_speed_2x", "Speed 2x", "Fast Forward", mode=ModifierMode.ALT),
            SliceAction("vid_reverse", "Reverse Clip", "Play Backwards", mode=ModifierMode.ALT),
            SliceAction("vid_mute", "Mute Audio", "Remove Sound", mode=ModifierMode.ALT),
            SliceAction("vid_thumbnails", "Thumbnail", "Extract Frame", target_ext=".jpg", mode=ModifierMode.ALT),
        ]

    # 3. Audio (7 Daily Audio Tools)
    if all_audio:
        return [
            SliceAction("aud_denoise", "Denoise Voice", "Speech Cleanup", mode=ModifierMode.ALT),
            SliceAction("aud_normalize", "Normalize Vol", "Loudnorm -16", mode=ModifierMode.ALT),
            SliceAction("aud_remove_silence", "Trim Silence", "Strip Dead Air", mode=ModifierMode.ALT),
            SliceAction("aud_compress_128k", "Compress 128k", "Small MP3", target_ext=".mp3", mode=ModifierMode.ALT),
            SliceAction("aud_trim_30s", "Trim 30s", "Ringtone Clip", mode=ModifierMode.ALT),
            SliceAction("aud_speed_1_5x", "Speed 1.5x", "Fast Podcast", mode=ModifierMode.ALT),
            SliceAction("aud_to_mono", "Mono Mix", "Single Channel", mode=ModifierMode.ALT),
        ]

    # 4. PDF (8 Daily PDF Tools — iLovePDF style)
    if all_pdfs:
        return [
            SliceAction("pdf_compress", "Compress PDF", "Shrink Size", target_ext=".pdf", mode=ModifierMode.ALT),
            SliceAction("batch_merge_pdf", "Merge PDFs", "Combine Files", target_ext=".pdf", mode=ModifierMode.ALT),
            SliceAction("pdf_split_pages", "Split Pages", "1 PDF / Page", target_ext=".pdf", mode=ModifierMode.ALT),
            SliceAction("pdf_autocrop", "Auto-Crop", "Trim Margins", target_ext=".pdf", mode=ModifierMode.ALT),
            SliceAction("pdf_rotate_90", "Rotate 90°", "Fix Orientation", target_ext=".pdf", mode=ModifierMode.ALT),
            SliceAction("pdf_add_page_numbers", "Page Numbers", "Stamp Footer", target_ext=".pdf", mode=ModifierMode.ALT),
            SliceAction("pdf_grayscale", "Grayscale PDF", "B&W Print Ready", target_ext=".pdf", mode=ModifierMode.ALT),
            SliceAction("pdf_strip_meta", "Clean Metadata", "Strip PDF Info", target_ext=".pdf", mode=ModifierMode.ALT),
        ]

    # 5. Document (7 Daily Document Tools)
    if all_docs:
        return [
            SliceAction("doc_clean_text", "Clean Format", "Fix Whitespace", mode=ModifierMode.ALT),
            SliceAction("doc_extract_images", "Extract Media", "Save Images", mode=ModifierMode.ALT),
            SliceAction("doc_extract_links", "Extract Links", "URLs & Emails", target_ext=".txt", mode=ModifierMode.ALT),
            SliceAction("doc_extract_outline", "Outline / TOC", "Headings Summary", target_ext=".md", mode=ModifierMode.ALT),
            SliceAction("doc_redact_pii", "Redact PII", "Mask Emails/Tel", mode=ModifierMode.ALT),
            SliceAction("doc_to_pdf_bw", "Grayscale PDF", "Compact B&W", target_ext=".pdf", mode=ModifierMode.ALT),
            SliceAction("doc_word_count", "Word Stats", "Reading Time", mode=ModifierMode.ALT),
        ]

    # 6. Slides (7 Daily Presentation Tools)
    if all_slides:
        return [
            SliceAction("slides_extract_media", "Extract Media", "Save Slide Images", mode=ModifierMode.ALT),
            SliceAction("slides_export_notes", "Speaker Notes", "Notes to .txt", target_ext=".txt", mode=ModifierMode.ALT),
            SliceAction("slides_handout_pdf", "Handout PDF", "2-Up Printable", target_ext=".pdf", mode=ModifierMode.ALT),
            SliceAction("slides_compress", "Compress Deck", "Shrink PPTX", target_ext=".pptx", mode=ModifierMode.ALT),
            SliceAction("slides_strip_notes", "Clean Notes", "Remove Notes", target_ext=".pptx", mode=ModifierMode.ALT),
            SliceAction("slides_extract_links", "Extract Links", "All Slide URLs", target_ext=".txt", mode=ModifierMode.ALT),
            SliceAction("slides_stats", "Deck Stats", "Talk Time & Count", mode=ModifierMode.ALT),
        ]

    # 7. Spreadsheet (8 Daily Data/Excel Tools)
    if all_sheets:
        return [
            SliceAction("sheet_deduplicate", "Deduplicate", "Unique Rows", mode=ModifierMode.ALT),
            SliceAction("sheet_trim_clean", "Clean Cells", "Trim & Drop Empty", mode=ModifierMode.ALT),
            SliceAction("sheet_transpose", "Transpose", "Swap Rows/Cols", mode=ModifierMode.ALT),
            SliceAction("sheet_sort_asc", "Sort A → Z", "Sort by 1st Col", mode=ModifierMode.ALT),
            SliceAction("sheet_autofit_xlsx", "Styled XLSX", "Freeze & Auto-Fit", target_ext=".xlsx", mode=ModifierMode.ALT),
            SliceAction("sheet_split_sheets", "Split Sheets", "1 CSV / Sheet", target_ext=".csv", mode=ModifierMode.ALT),
            SliceAction("sheet_column_stats", "Summary Stats", "Min/Max/Mean .md", target_ext=".md", mode=ModifierMode.ALT),
            SliceAction("sheet_stats", "Table Info", "Rows/Cols to Clip", mode=ModifierMode.ALT),
        ]

    # 8. Archives (6 Daily Archive Tools)
    if all_archives:
        return [
            SliceAction("arch_extract_folder", "Smart Extract", "Unpack Subfolder", mode=ModifierMode.ALT),
            SliceAction("arch_recompress_max", "Max Compress", "Level-9 .ZIP", target_ext=".zip", mode=ModifierMode.ALT),
            SliceAction("arch_flatten_extract", "Flatten Files", "All to 1 Folder", mode=ModifierMode.ALT),
            SliceAction("arch_clean_junk", "Clean Junk", "Strip .DS_Store", target_ext=".zip", mode=ModifierMode.ALT),
            SliceAction("arch_list_contents", "File Manifest", "Tree List .txt", target_ext=".txt", mode=ModifierMode.ALT),
            SliceAction("arch_verify", "Verify Archive", "CRC Checksum", mode=ModifierMode.ALT),
        ]

    # 9. Drawing (7 Daily Vector & CAD Tools)
    if all_drawings:
        return [
            SliceAction("draw_render_hd", "Render 600 DPI", "Ultra-HD PNG", target_ext=".png", mode=ModifierMode.ALT),
            SliceAction("draw_transparent_png", "Alpha Cutout", "Transparent PNG", target_ext=".png", mode=ModifierMode.ALT),
            SliceAction("draw_blueprint_pdf", "Blueprint PDF", "Dark CAD Theme", target_ext=".pdf", mode=ModifierMode.ALT),
            SliceAction("draw_optimize", "Clean / Minify", "Optimize Vector", mode=ModifierMode.ALT),
            SliceAction("draw_grayscale", "Grayscale PNG", "Monochrome", target_ext=".png", mode=ModifierMode.ALT),
            SliceAction("draw_extract_layers", "Layer Report", "Entities to .txt", target_ext=".txt", mode=ModifierMode.ALT),
            SliceAction("draw_inspect_info", "Drawing Info", "Bounds to Clip", mode=ModifierMode.ALT),
        ]

    if all_img_or_pdf and is_multi:
        return [
            SliceAction("batch_merge_pdf", "Merge to PDF", "Combine All", target_ext=".pdf", mode=ModifierMode.ALT),
            SliceAction("pack_zip", "Pack to .ZIP", "Archive Batch", target_ext=".zip", mode=ModifierMode.ALT),
            SliceAction("util_duplicate", "Duplicate", "Copy in Folder", mode=ModifierMode.ALT),
            SliceAction("util_copy_path", "Copy Paths", "To Clipboard", mode=ModifierMode.ALT),
        ]

    return [
        SliceAction("pack_zip", "Pack to .ZIP", "Compress Archive", target_ext=".zip", mode=ModifierMode.ALT),
        SliceAction("util_duplicate", "Duplicate", "Backup Copy", mode=ModifierMode.ALT),
        SliceAction("util_copy_path", "Copy Path", "To Clipboard", mode=ModifierMode.ALT),
        SliceAction("util_sha256", "SHA-256", "Hash to Clipboard", mode=ModifierMode.ALT),
    ]


def _get_shift_actions(
    *,
    norm_exts: set[str],
    all_images: bool,
    all_videos: bool,
    all_audio: bool,
    all_pdfs: bool,
    all_docs: bool,
    all_slides: bool,
    all_sheets: bool,
    all_archives: bool,
    all_drawings: bool,
    all_img_or_pdf: bool,
    is_multi: bool,
) -> list[SliceAction]:
    """Build slice descriptors for Shift Mode (Format Conversion)."""
    # 1. Images
    if all_images:
        candidates = [
            SliceAction("img_to_png", "PNG", "Lossless", target_ext=".png", mode=ModifierMode.SHIFT),
            SliceAction("img_to_jpg", "JPG", "Compact Photo", target_ext=".jpg", mode=ModifierMode.SHIFT),
            SliceAction("img_to_webp", "WEBP", "Modern Web", target_ext=".webp", mode=ModifierMode.SHIFT),
            SliceAction("img_to_pdf", "PDF", "Document", target_ext=".pdf", mode=ModifierMode.SHIFT),
            SliceAction("img_to_ico", "ICO", "App Icon", target_ext=".ico", mode=ModifierMode.SHIFT),
            SliceAction("img_to_avif", "AVIF", "Next-Gen", target_ext=".avif", mode=ModifierMode.SHIFT),
        ]
        candidates = _filter_source_ext(candidates, norm_exts)
        if is_multi:
            candidates.append(
                SliceAction("batch_merge_pdf", "Merge to PDF", "Single PDF", target_ext=".pdf", mode=ModifierMode.SHIFT)
            )
            candidates.append(
                SliceAction("pack_zip", "Pack to .ZIP", "Zip Archive", target_ext=".zip", mode=ModifierMode.SHIFT)
            )
        return candidates[:8]

    # 2. Video
    if all_videos:
        candidates = [
            SliceAction("vid_to_mp4", "MP4", "H.264 Video", target_ext=".mp4", mode=ModifierMode.SHIFT),
            SliceAction("vid_to_gif", "GIF", "High FPS", target_ext=".gif", mode=ModifierMode.SHIFT),
            SliceAction("vid_to_mp3", "MP3", "Extract Audio", target_ext=".mp3", mode=ModifierMode.SHIFT),
            SliceAction("vid_to_wav", "WAV", "Lossless Audio", target_ext=".wav", mode=ModifierMode.SHIFT),
            SliceAction("vid_to_webm", "WEBM", "VP9 Web", target_ext=".webm", mode=ModifierMode.SHIFT),
        ]
        candidates = _filter_source_ext(candidates, norm_exts)
        if is_multi:
            candidates.append(
                SliceAction("pack_zip", "Pack to .ZIP", "Zip Archive", target_ext=".zip", mode=ModifierMode.SHIFT)
            )
        return candidates[:8]

    # 3. Audio
    if all_audio:
        candidates = [
            SliceAction("aud_to_mp3", "MP3", "320kbps Audio", target_ext=".mp3", mode=ModifierMode.SHIFT),
            SliceAction("aud_to_wav", "WAV", "PCM Lossless", target_ext=".wav", mode=ModifierMode.SHIFT),
            SliceAction("aud_to_flac", "FLAC", "Studio Lossless", target_ext=".flac", mode=ModifierMode.SHIFT),
            SliceAction("aud_to_m4a", "M4A", "AAC Audio", target_ext=".m4a", mode=ModifierMode.SHIFT),
            SliceAction("aud_to_ogg", "OGG", "Vorbis Audio", target_ext=".ogg", mode=ModifierMode.SHIFT),
        ]
        candidates = _filter_source_ext(candidates, norm_exts)
        if is_multi:
            candidates.append(
                SliceAction("pack_zip", "Pack to .ZIP", "Zip Archive", target_ext=".zip", mode=ModifierMode.SHIFT)
            )
        return candidates[:8]

    # 4. PDF
    if all_pdfs:
        candidates = [
            SliceAction("pdf_to_png", "PNG (Pages)", "300 DPI Render", target_ext=".png", mode=ModifierMode.SHIFT),
            SliceAction("pdf_to_jpg", "JPG (Pages)", "300 DPI Render", target_ext=".jpg", mode=ModifierMode.SHIFT),
            SliceAction("pdf_to_docx", "DOCX", "Word Document", target_ext=".docx", mode=ModifierMode.SHIFT),
            SliceAction("pdf_to_txt", "Extract Text", "Plain .txt", target_ext=".txt", mode=ModifierMode.SHIFT),
            SliceAction("pdf_to_svg", "SVG (Pages)", "Vector Pages", target_ext=".svg", mode=ModifierMode.SHIFT),
        ]
        if is_multi:
            candidates.insert(
                0,
                SliceAction("batch_merge_pdf", "Merge to PDF", "Combine PDFs", target_ext=".pdf", mode=ModifierMode.SHIFT),
            )
            candidates.append(
                SliceAction("pack_zip", "Pack to .ZIP", "Zip Archive", target_ext=".zip", mode=ModifierMode.SHIFT)
            )
        return candidates[:8]

    # 5. Document
    if all_docs:
        candidates = [
            SliceAction("doc_to_pdf", "PDF", "Print Document", target_ext=".pdf", mode=ModifierMode.SHIFT),
            SliceAction("doc_to_docx", "DOCX", "Word Document", target_ext=".docx", mode=ModifierMode.SHIFT),
            SliceAction("doc_to_txt", "TXT", "Plain Text", target_ext=".txt", mode=ModifierMode.SHIFT),
            SliceAction("doc_to_md", "Markdown", "Clean .md", target_ext=".md", mode=ModifierMode.SHIFT),
            SliceAction("doc_to_html", "HTML", "Web Document", target_ext=".html", mode=ModifierMode.SHIFT),
        ]
        candidates = _filter_source_ext(candidates, norm_exts)
        if is_multi:
            candidates.append(
                SliceAction("pack_zip", "Pack to .ZIP", "Zip Archive", target_ext=".zip", mode=ModifierMode.SHIFT)
            )
        return candidates[:8]

    # 6. Slides
    if all_slides:
        candidates = [
            SliceAction("slides_to_pdf", "PDF", "Slide Deck PDF", target_ext=".pdf", mode=ModifierMode.SHIFT),
            SliceAction("slides_to_png", "PNG (Slides)", "HD Slide Cards", target_ext=".png", mode=ModifierMode.SHIFT),
            SliceAction("slides_to_jpg", "JPG (Slides)", "Compact Cards", target_ext=".jpg", mode=ModifierMode.SHIFT),
            SliceAction("slides_to_txt", "TXT", "All Slide Text", target_ext=".txt", mode=ModifierMode.SHIFT),
            SliceAction("slides_to_md", "Markdown", "Slide Outline", target_ext=".md", mode=ModifierMode.SHIFT),
        ]
        if is_multi:
            candidates.append(
                SliceAction("pack_zip", "Pack to .ZIP", "Zip Archive", target_ext=".zip", mode=ModifierMode.SHIFT)
            )
        return candidates[:8]

    # 7. Spreadsheet
    if all_sheets:
        candidates = [
            SliceAction("sheet_to_xlsx", "XLSX", "Excel Workbook", target_ext=".xlsx", mode=ModifierMode.SHIFT),
            SliceAction("sheet_to_csv", "CSV", "Comma Table", target_ext=".csv", mode=ModifierMode.SHIFT),
            SliceAction("sheet_to_tsv", "TSV", "Tab Table", target_ext=".tsv", mode=ModifierMode.SHIFT),
            SliceAction("sheet_to_json", "JSON", "Records Array", target_ext=".json", mode=ModifierMode.SHIFT),
            SliceAction("sheet_to_pdf", "PDF", "Table Report", target_ext=".pdf", mode=ModifierMode.SHIFT),
            SliceAction("sheet_to_md", "Markdown", "MD Table", target_ext=".md", mode=ModifierMode.SHIFT),
        ]
        candidates = _filter_source_ext(candidates, norm_exts)
        if is_multi:
            candidates.append(
                SliceAction("pack_zip", "Pack to .ZIP", "Zip Archive", target_ext=".zip", mode=ModifierMode.SHIFT)
            )
        return candidates[:8]

    # 8. Archives
    if all_archives:
        candidates = [
            SliceAction("arch_extract_folder", "Extract Here", "Unpack Folder", mode=ModifierMode.SHIFT),
            SliceAction("arch_to_zip", "ZIP", "Standard .zip", target_ext=".zip", mode=ModifierMode.SHIFT),
            SliceAction("arch_to_targz", "TAR.GZ", "Gzipped Tarball", target_ext=".gz", mode=ModifierMode.SHIFT),
            SliceAction("arch_to_tar", "TAR", "Uncompressed Tar", target_ext=".tar", mode=ModifierMode.SHIFT),
        ]
        candidates = _filter_source_ext(candidates, norm_exts)
        return candidates[:8]

    # 9. Drawing
    if all_drawings:
        candidates = [
            SliceAction("draw_to_png", "PNG", "300 DPI Raster", target_ext=".png", mode=ModifierMode.SHIFT),
            SliceAction("draw_to_pdf", "PDF", "Vector PDF", target_ext=".pdf", mode=ModifierMode.SHIFT),
            SliceAction("draw_to_svg", "SVG", "Scalable Vector", target_ext=".svg", mode=ModifierMode.SHIFT),
            SliceAction("draw_to_dxf", "DXF", "CAD Exchange", target_ext=".dxf", mode=ModifierMode.SHIFT),
            SliceAction("draw_to_jpg", "JPG", "White BG Raster", target_ext=".jpg", mode=ModifierMode.SHIFT),
            SliceAction("draw_to_webp", "WEBP", "Crisp WebP", target_ext=".webp", mode=ModifierMode.SHIFT),
        ]
        candidates = _filter_source_ext(candidates, norm_exts)
        if is_multi:
            candidates.append(
                SliceAction("pack_zip", "Pack to .ZIP", "Zip Archive", target_ext=".zip", mode=ModifierMode.SHIFT)
            )
        return candidates[:8]

    if all_img_or_pdf and is_multi:
        return [
            SliceAction("batch_merge_pdf", "Merge to PDF", "Combine All", target_ext=".pdf", mode=ModifierMode.SHIFT),
            SliceAction("pack_zip", "Pack to .ZIP", "Zip Archive", target_ext=".zip", mode=ModifierMode.SHIFT),
            SliceAction("img_to_png", "All to PNG", "Lossless Pages", target_ext=".png", mode=ModifierMode.SHIFT),
            SliceAction("img_to_jpg", "All to JPG", "Compact Pages", target_ext=".jpg", mode=ModifierMode.SHIFT),
        ]

    return [
        SliceAction("pack_zip", "Pack to .ZIP", "Zip Archive", target_ext=".zip", mode=ModifierMode.SHIFT),
        SliceAction("util_copy_path", "Copy Path", "To Clipboard", mode=ModifierMode.SHIFT),
        SliceAction("util_duplicate", "Duplicate", "Copy in Folder", mode=ModifierMode.SHIFT),
        SliceAction("util_sha256", "SHA-256", "Hash to Clipboard", mode=ModifierMode.SHIFT),
    ]
