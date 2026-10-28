"""Archive extraction, format conversion, junk cleanup, flattening, and verification handlers."""

from __future__ import annotations

import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

from core.converters.path_utils import format_saved_summary, get_safe_output_path
from core.models import ConversionResult

ARCHIVE_ACTION_IDS: frozenset[str] = frozenset({
    # Archive Formats (Shift Mode)
    "arch_extract_folder",
    "arch_to_zip",
    "arch_to_targz",
    "arch_to_tar",
    # Archive Daily Tools (Alt Mode)
    "arch_recompress_max",
    "arch_flatten_extract",
    "arch_clean_junk",
    "arch_list_contents",
    "arch_verify",
})

JUNK_PATTERNS = (
    ".ds_store",
    "thumbs.db",
    "desktop.ini",
    "__macosx",
    ".pyc",
)


def _is_junk_path(rel_path: str) -> bool:
    lower = rel_path.lower().replace("\\", "/")
    parts = lower.split("/")
    return any(p in JUNK_PATTERNS or p.startswith("._") for p in parts)


def _safe_extract_archive(src: Path, target_dir: Path) -> list[Path]:
    """Safely extract `.zip` or `.tar*` archive into `target_dir` preventing path traversal."""
    target_dir.mkdir(parents=True, exist_ok=True)
    target_root = target_dir.resolve()

    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src, "r") as zf:
            for member in zf.infolist():
                resolved = (target_root / member.filename).resolve()
                if not str(resolved).startswith(str(target_root)):
                    raise RuntimeError(f"Unsafe archive member blocked: {member.filename}")
                zf.extract(member, path=str(target_root))
    elif tarfile.is_tarfile(src):
        with tarfile.open(src, "r:*") as tf:
            for member in tf.getmembers():
                resolved = (target_root / member.name).resolve()
                if not str(resolved).startswith(str(target_root)):
                    raise RuntimeError(f"Unsafe tar member blocked: {member.name}")
                tf.extract(member, path=str(target_root))
    else:
        shutil.unpack_archive(str(src), str(target_root))

    return [p for p in target_root.rglob("*") if p.is_file()]


def _list_archive_entries(src: Path) -> list[tuple[str, int]]:
    """Return `(filename, size_bytes)` entries inside an archive."""
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src, "r") as zf:
            return [(i.filename, i.file_size) for i in zf.infolist() if not i.is_dir()]
    if tarfile.is_tarfile(src):
        with tarfile.open(src, "r:*") as tf:
            return [(m.name, m.size) for m in tf.getmembers() if m.isfile()]
    raise ValueError(f"Unsupported archive format: {src.suffix}")


def _pack_directory_to_zip(
    source_dir: Path,
    dst_zip: Path,
    compresslevel: int = 6,
    skip_junk: bool = False,
) -> Path:
    with zipfile.ZipFile(
        dst_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=compresslevel
    ) as zf:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                rel = str(file_path.relative_to(source_dir))
                if skip_junk and _is_junk_path(rel):
                    continue
                zf.write(file_path, arcname=rel)
    return dst_zip


def _pack_directory_to_tar(source_dir: Path, dst_tar: Path, mode: str = "w") -> Path:
    with tarfile.open(dst_tar, mode) as tf:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                rel = file_path.relative_to(source_dir)
                tf.add(file_path, arcname=str(rel))
    return dst_tar


def _clean_archive_stem(src: Path) -> str:
    """Strip compound `.tar.gz` / `.tar.bz2` / `.tar.xz` suffixes cleanly."""
    name = src.name
    for compound in (".tar.gz", ".tar.bz2", ".tar.xz"):
        if name.lower().endswith(compound):
            return name[: -len(compound)]
    return src.stem


def run_archive_action(
    action_id: str,
    action_label: str,
    src: Path,
) -> ConversionResult:
    """Execute an archive extraction, conversion, cleanup, or inspection task."""
    base_stem = _clean_archive_stem(src)

    if action_id == "arch_extract_folder":
        out_dir = src.parent / base_stem
        idx = 1
        while out_dir.exists():
            out_dir = src.parent / f"{base_stem} ({idx})"
            idx += 1
        files = _safe_extract_archive(src, out_dir)
        first_target = str(files[0]) if files else str(out_dir)
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[first_target],
            summary_text=f"Extracted {len(files)} file{'s' if len(files) != 1 else ''} → {out_dir.name}/",
        )

    if action_id == "arch_flatten_extract":
        out_dir = src.parent / f"{base_stem}_flat"
        idx = 1
        while out_dir.exists():
            out_dir = src.parent / f"{base_stem}_flat ({idx})"
            idx += 1
        out_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="easy_conv_flat_") as tmp:
            extracted = _safe_extract_archive(src, Path(tmp))
            flat_files: list[Path] = []
            for f in extracted:
                if _is_junk_path(f.name):
                    continue
                dst_f = get_safe_output_path(out_dir / f.name)
                shutil.copy2(f, dst_f)
                flat_files.append(dst_f)
        first_target = str(flat_files[0]) if flat_files else str(out_dir)
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[first_target],
            summary_text=f"Flattened {len(flat_files)} files → {out_dir.name}/",
        )

    if action_id == "arch_list_contents":
        entries = _list_archive_entries(src)
        dst = get_safe_output_path(src.parent / f"{base_stem}_manifest.txt", new_ext=".txt")
        total_bytes = sum(sz for _, sz in entries)
        lines = [
            f"Archive Manifest: {src.name}",
            f"Total Files: {len(entries)} | Uncompressed Size: {total_bytes:,} bytes",
            "-" * 60,
            *[f"{sz:>12,} B  {name}" for name, sz in entries],
        ]
        dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(dst)],
            summary_text=format_saved_summary([dst]),
        )

    if action_id == "arch_verify":
        if zipfile.is_zipfile(src):
            with zipfile.ZipFile(src, "r") as zf:
                bad_file = zf.testzip()
                if bad_file is not None:
                    raise RuntimeError(f"Corrupted CRC on entry: {bad_file}")
                count = len(zf.infolist())
        elif tarfile.is_tarfile(src):
            with tarfile.open(src, "r:*") as tf:
                members = tf.getmembers()
                count = len(members)
        else:
            raise ValueError(f"Cannot verify archive type: {src.suffix}")

        msg = f"Archive OK ({count} entries verified)"
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=[str(src)],
            clipboard_text=f"{src.name}: {msg}",
            summary_text=msg,
        )

    # Archive Format Conversions / Recompression / Junk Cleanup via staging directory
    with tempfile.TemporaryDirectory(prefix="easy_conv_arch_") as tmp:
        stage_dir = Path(tmp)
        _safe_extract_archive(src, stage_dir)

        if action_id == "arch_to_zip":
            dst = get_safe_output_path(src.parent / f"{base_stem}.zip", new_ext=".zip")
            _pack_directory_to_zip(stage_dir, dst, compresslevel=6)
        elif action_id == "arch_recompress_max":
            dst = get_safe_output_path(src.parent / f"{base_stem}_max.zip", new_ext=".zip")
            _pack_directory_to_zip(stage_dir, dst, compresslevel=9)
        elif action_id == "arch_clean_junk":
            dst = get_safe_output_path(src.parent / f"{base_stem}_clean.zip", new_ext=".zip")
            _pack_directory_to_zip(stage_dir, dst, compresslevel=9, skip_junk=True)
        elif action_id == "arch_to_targz":
            dst = get_safe_output_path(src.parent / f"{base_stem}.tar.gz", new_ext=".gz")
            _pack_directory_to_tar(stage_dir, dst, mode="w:gz")
        elif action_id == "arch_to_tar":
            dst = get_safe_output_path(src.parent / f"{base_stem}.tar", new_ext=".tar")
            _pack_directory_to_tar(stage_dir, dst, mode="w")
        else:
            raise ValueError(f"Unknown archive action_id: {action_id}")

    return ConversionResult(
        success=True,
        action_id=action_id,
        action_label=action_label,
        output_paths=[str(dst)],
        summary_text=format_saved_summary([dst]),
    )
