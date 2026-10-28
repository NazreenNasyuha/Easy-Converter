"""Image conversion, background removal, cropping, upscaling, and enhancement handlers."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

from core.config import ICO_SIZES
from core.converters.media_ops import run_ffmpeg
from core.converters.path_utils import get_safe_output_path

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    try:
        pillow_heif.register_avif_opener()
    except AttributeError:
        pass
except Exception:
    pass


IMAGE_ACTION_IDS: frozenset[str] = frozenset({
    # Shift Mode (Formats)
    "img_to_png",
    "img_to_jpg",
    "img_to_webp",
    "img_to_pdf",
    "img_to_ico",
    "img_to_avif",
    # Alt Mode (Daily Image Tools)
    "img_remove_bg",
    "img_crop_edit",
    "img_crop_square",
    "img_resize_50",
    "img_upscale_2x",
    "img_compress_web",
    "img_auto_enhance",
    "img_strip_exif",
    "img_grayscale",
    "img_rotate_90",
})


def flatten_to_rgb(
    img: Image.Image,
    bg_color: tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    """Flatten an image with alpha or palette transparency onto an opaque RGB background."""
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, bg_color)
        background.paste(rgba, mask=rgba.split()[3])
        return background
    return img.convert("RGB")


def pil_to_pdf_bytes(rgb_img: Image.Image) -> bytes:
    """Serialize a PIL RGB image to in-memory PDF bytes at 300 DPI."""
    buf = io.BytesIO()
    rgb_img.save(buf, format="PDF", resolution=300.0)
    return buf.getvalue()


def remove_image_background(img: Image.Image) -> Image.Image:
    """Remove image background and return a transparent RGBA `Image`.

    Uses `rembg` neural segmentation if installed; otherwise performs vectorized
    border-ring color-space clustering with soft alpha feathering via NumPy + Pillow.
    """
    rgba = ImageOps.exif_transpose(img).convert("RGBA")
    try:
        import rembg  # type: ignore[import-not-found]

        return rembg.remove(rgba)
    except Exception:
        pass

    arr = np.asarray(rgba, dtype=np.float32)
    rgb = arr[:, :, :3]
    orig_alpha = arr[:, :, 3]

    h, w, _ = rgb.shape
    border_px = max(2, min(h, w) // 25)
    top = rgb[:border_px, :, :].reshape(-1, 3)
    bottom = rgb[h - border_px :, :, :].reshape(-1, 3)
    left = rgb[:, :border_px, :].reshape(-1, 3)
    right = rgb[:, w - border_px :, :].reshape(-1, 3)
    border_samples = np.concatenate([top, bottom, left, right], axis=0)

    # Estimate dominant background color via median of perimeter pixels
    bg_color = np.median(border_samples, axis=0)
    dist = np.linalg.norm(rgb - bg_color, axis=2)

    # Adaptive threshold based on border color variance
    border_std = float(np.std(np.linalg.norm(border_samples - bg_color, axis=1)))
    low_thresh = max(18.0, border_std * 1.8)
    high_thresh = max(42.0, low_thresh + 26.0)

    # Smooth alpha ramp between low_thresh (transparent) and high_thresh (opaque foreground)
    alpha_mask = np.clip((dist - low_thresh) / (high_thresh - low_thresh), 0.0, 1.0)
    combined_alpha = (alpha_mask * (orig_alpha / 255.0) * 255.0).astype(np.uint8)

    alpha_img = Image.fromarray(combined_alpha, mode="L").filter(
        ImageFilter.GaussianBlur(radius=0.8)
    )
    out = rgba.copy()
    out.putalpha(alpha_img)
    return out


def auto_trim_borders(img: Image.Image) -> Image.Image:
    """Automatically trim uniform outer borders/whitespace from an image."""
    transposed = ImageOps.exif_transpose(img)
    bg = Image.new(transposed.mode, transposed.size, transposed.getpixel((0, 0)))
    diff = ImageChops.difference(transposed, bg)
    bbox = diff.getbbox()
    if bbox:
        # Leave a small 4% breathing margin if possible
        w, h = transposed.size
        if (bbox[2] - bbox[0]) >= w * 0.2 and (bbox[3] - bbox[1]) >= h * 0.2:
            return transposed.crop(bbox)
    # Fallback: 10% inset smart center crop
    w, h = transposed.size
    mx, my = int(w * 0.08), int(h * 0.08)
    if w > 20 and h > 20:
        return transposed.crop((mx, my, w - mx, h - my))
    return transposed


def run_image_action(action_id: str, src: Path) -> list[Path]:
    """Execute a single-file image conversion or daily image tool operation."""
    # --- Shift Mode: Format Conversions ---
    if action_id == "img_to_png":
        dst = get_safe_output_path(src, new_ext=".png")
        with Image.open(src) as img:
            transposed = ImageOps.exif_transpose(img)
            transposed.save(dst, format="PNG", optimize=True)
        return [dst]

    if action_id == "img_to_jpg":
        dst = get_safe_output_path(src, new_ext=".jpg")
        with Image.open(src) as img:
            rgb = flatten_to_rgb(img)
            rgb.save(dst, format="JPEG", quality=92, optimize=True)
        return [dst]

    if action_id == "img_to_webp":
        dst = get_safe_output_path(src, new_ext=".webp")
        with Image.open(src) as img:
            transposed = ImageOps.exif_transpose(img)
            transposed.save(dst, format="WEBP", quality=90, method=6)
        return [dst]

    if action_id == "img_to_pdf":
        dst = get_safe_output_path(src, new_ext=".pdf")
        with Image.open(src) as img:
            rgb = flatten_to_rgb(img)
            rgb.save(dst, format="PDF", resolution=300.0)
        return [dst]

    if action_id == "img_to_ico":
        dst = get_safe_output_path(src, new_ext=".ico")
        with Image.open(src) as img:
            rgba = ImageOps.exif_transpose(img).convert("RGBA")
            max_side = max(rgba.width, rgba.height, 256)
            square = Image.new("RGBA", (max_side, max_side), (0, 0, 0, 0))
            offset = ((max_side - rgba.width) // 2, (max_side - rgba.height) // 2)
            square.paste(rgba, offset)
            if max_side != 256:
                square = square.resize((256, 256), Image.Resampling.LANCZOS)
            square.save(dst, format="ICO", sizes=ICO_SIZES)
        return [dst]

    if action_id == "img_to_avif":
        dst = get_safe_output_path(src, new_ext=".avif")
        with Image.open(src) as img:
            transposed = ImageOps.exif_transpose(img)
            try:
                transposed.save(dst, format="AVIF", quality=85)
            except Exception:
                run_ffmpeg([
                    "-i", str(src),
                    "-c:v", "libaom-av1", "-still-picture", "1", "-crf", "30",
                    str(dst),
                ])
        return [dst]

    # --- Alt Mode: Daily Image Tools ---
    if action_id == "img_remove_bg":
        dst = get_safe_output_path(src, new_ext=".png", suffix="_nobg")
        with Image.open(src) as img:
            cutout = remove_image_background(img)
            cutout.save(dst, format="PNG", optimize=True)
        return [dst]

    if action_id == "img_crop_edit":
        out_ext = src.suffix if src.suffix.lower() not in (".heic", ".heif") else ".png"
        dst = get_safe_output_path(src, new_ext=out_ext, suffix="_cropped")
        with Image.open(src) as img:
            trimmed = auto_trim_borders(img)
            if dst.suffix.lower() in (".jpg", ".jpeg"):
                trimmed = flatten_to_rgb(trimmed)
            trimmed.save(dst, optimize=True)
        return [dst]

    if action_id == "img_crop_square":
        out_ext = src.suffix if src.suffix.lower() not in (".heic", ".heif") else ".png"
        dst = get_safe_output_path(src, new_ext=out_ext, suffix="_1x1")
        with Image.open(src) as img:
            transposed = ImageOps.exif_transpose(img)
            side = min(transposed.width, transposed.height)
            square = ImageOps.fit(
                transposed,
                (side, side),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            if dst.suffix.lower() in (".jpg", ".jpeg"):
                square = flatten_to_rgb(square)
            square.save(dst, optimize=True)
        return [dst]

    if action_id == "img_resize_50":
        out_ext = src.suffix if src.suffix.lower() not in (".heic", ".heif") else ".png"
        dst = get_safe_output_path(src, new_ext=out_ext, suffix="_50pct")
        with Image.open(src) as img:
            transposed = ImageOps.exif_transpose(img)
            new_size = (max(1, transposed.width // 2), max(1, transposed.height // 2))
            resized = transposed.resize(new_size, Image.Resampling.LANCZOS)
            if dst.suffix.lower() in (".jpg", ".jpeg"):
                resized = flatten_to_rgb(resized)
            resized.save(dst, optimize=True)
        return [dst]

    if action_id == "img_upscale_2x":
        out_ext = src.suffix if src.suffix.lower() not in (".heic", ".heif") else ".png"
        dst = get_safe_output_path(src, new_ext=out_ext, suffix="_2x")
        with Image.open(src) as img:
            transposed = ImageOps.exif_transpose(img)
            new_size = (transposed.width * 2, transposed.height * 2)
            upscaled = transposed.resize(new_size, Image.Resampling.LANCZOS)
            if upscaled.mode in ("RGB", "L"):
                upscaled = upscaled.filter(
                    ImageFilter.UnsharpMask(radius=1.4, percent=130, threshold=3)
                )
            elif upscaled.mode == "RGBA":
                rgb_part = upscaled.convert("RGB").filter(
                    ImageFilter.UnsharpMask(radius=1.4, percent=130, threshold=3)
                )
                rgb_part.putalpha(upscaled.getchannel("A"))
                upscaled = rgb_part
            if dst.suffix.lower() in (".jpg", ".jpeg"):
                upscaled = flatten_to_rgb(upscaled)
            upscaled.save(dst, optimize=True)
        return [dst]

    if action_id == "img_compress_web":
        out_ext = ".jpg" if src.suffix.lower() in (".jpg", ".jpeg", ".bmp", ".tiff", ".tif") else ".webp"
        dst = get_safe_output_path(src, new_ext=out_ext, suffix="_web")
        with Image.open(src) as img:
            transposed = ImageOps.exif_transpose(img)
            if out_ext == ".jpg":
                rgb = flatten_to_rgb(transposed)
                rgb.save(dst, format="JPEG", quality=80, optimize=True)
            else:
                transposed.save(dst, format="WEBP", quality=80, method=6)
        return [dst]

    if action_id == "img_auto_enhance":
        out_ext = src.suffix if src.suffix.lower() not in (".heic", ".heif") else ".png"
        dst = get_safe_output_path(src, new_ext=out_ext, suffix="_enhanced")
        with Image.open(src) as img:
            rgb = flatten_to_rgb(img)
            leveled = ImageOps.autocontrast(rgb, cutoff=1)
            vibrant = ImageEnhance.Color(leveled).enhance(1.14)
            crisp = ImageEnhance.Sharpness(vibrant).enhance(1.2)
            crisp.save(dst, optimize=True)
        return [dst]

    if action_id == "img_strip_exif":
        out_ext = src.suffix if src.suffix.lower() not in (".heic", ".heif") else ".jpg"
        dst = get_safe_output_path(src, new_ext=out_ext, suffix="_clean")
        with Image.open(src) as img:
            transposed = ImageOps.exif_transpose(img)
            clean = Image.frombytes(transposed.mode, transposed.size, transposed.tobytes())
            if dst.suffix.lower() in (".jpg", ".jpeg"):
                clean = flatten_to_rgb(clean)
                clean.save(dst, format="JPEG", quality=92, optimize=True)
            else:
                clean.save(dst)
        return [dst]

    if action_id == "img_grayscale":
        out_ext = src.suffix if src.suffix.lower() not in (".heic", ".heif") else ".png"
        dst = get_safe_output_path(src, new_ext=out_ext, suffix="_bw")
        with Image.open(src) as img:
            transposed = ImageOps.exif_transpose(img)
            gray = ImageOps.grayscale(transposed)
            gray.save(dst)
        return [dst]

    if action_id == "img_rotate_90":
        out_ext = src.suffix if src.suffix.lower() not in (".heic", ".heif") else ".png"
        dst = get_safe_output_path(src, new_ext=out_ext, suffix="_rot90")
        with Image.open(src) as img:
            transposed = ImageOps.exif_transpose(img).rotate(-90, expand=True)
            if dst.suffix.lower() in (".jpg", ".jpeg"):
                transposed = flatten_to_rgb(transposed)
            transposed.save(dst)
        return [dst]

    raise ValueError(f"Unknown image action_id: {action_id}")
