"""Video and audio conversion and daily processing handlers powered by FFmpeg."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from core.converters.path_utils import get_safe_output_path

MEDIA_ACTION_IDS: frozenset[str] = frozenset({
    # Video & Audio Formats (Shift Mode)
    "vid_to_mp4",
    "vid_to_gif",
    "vid_to_mp3",
    "vid_to_wav",
    "vid_to_webm",
    "aud_to_mp3",
    "aud_to_wav",
    "aud_to_flac",
    "aud_to_m4a",
    "aud_to_ogg",
    # Video Daily Tools (Alt Mode)
    "vid_compress_50",
    "vid_downscale_720p",
    "vid_1080p",
    "vid_mute",
    "vid_trim_10s",
    "vid_speed_2x",
    "vid_reverse",
    "vid_thumbnails",
    # Audio Daily Tools (Alt Mode)
    "aud_denoise",
    "aud_normalize",
    "aud_remove_silence",
    "aud_compress_128k",
    "aud_trim_30s",
    "aud_speed_1_5x",
    "aud_to_mono",
})


def resolve_ffmpeg_exe() -> str:
    """Resolve the FFmpeg binary path from `imageio-ffmpeg` or system `PATH`."""
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    raise RuntimeError("FFmpeg executable not found via imageio-ffmpeg or system PATH.")


def run_ffmpeg(args: list[str]) -> None:
    """Execute FFmpeg headless without spawning a visible console window on Windows."""
    exe = resolve_ffmpeg_exe()
    cmd = [exe, "-y", "-hide_banner", "-loglevel", "error", *args]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
        check=False,
    )
    if result.returncode != 0:
        err_msg = (result.stderr or result.stdout or "Unknown FFmpeg error").strip()
        raise RuntimeError(f"FFmpeg failed: {err_msg}")


def run_media_action(action_id: str, src: Path) -> list[Path]:
    """Execute a single-file video or audio conversion or daily tool task."""
    # --- Video & Audio Format Conversions ---
    if action_id == "vid_to_mp4":
        dst = get_safe_output_path(src, new_ext=".mp4")
        run_ffmpeg([
            "-i", str(src),
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            str(dst),
        ])
        return [dst]

    if action_id == "vid_to_gif":
        dst = get_safe_output_path(src, new_ext=".gif")
        vf = (
            "fps=15,scale='min(640,iw)':-1:flags=lanczos,"
            "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
        )
        run_ffmpeg(["-i", str(src), "-vf", vf, "-loop", "0", str(dst)])
        return [dst]

    if action_id in ("vid_to_mp3", "aud_to_mp3"):
        dst = get_safe_output_path(src, new_ext=".mp3")
        run_ffmpeg(["-i", str(src), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(dst)])
        return [dst]

    if action_id in ("vid_to_wav", "aud_to_wav"):
        dst = get_safe_output_path(src, new_ext=".wav")
        run_ffmpeg(["-i", str(src), "-vn", "-c:a", "pcm_s16le", str(dst)])
        return [dst]

    if action_id == "vid_to_webm":
        dst = get_safe_output_path(src, new_ext=".webm")
        run_ffmpeg([
            "-i", str(src),
            "-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0",
            "-c:a", "libopus",
            str(dst),
        ])
        return [dst]

    if action_id == "aud_to_flac":
        dst = get_safe_output_path(src, new_ext=".flac")
        run_ffmpeg(["-i", str(src), "-vn", "-c:a", "flac", str(dst)])
        return [dst]

    if action_id == "aud_to_m4a":
        dst = get_safe_output_path(src, new_ext=".m4a")
        run_ffmpeg(["-i", str(src), "-vn", "-c:a", "aac", "-b:a", "256k", str(dst)])
        return [dst]

    if action_id == "aud_to_ogg":
        dst = get_safe_output_path(src, new_ext=".ogg")
        run_ffmpeg(["-i", str(src), "-vn", "-c:a", "libvorbis", "-q:a", "5", str(dst)])
        return [dst]

    # --- Video Daily Tools (Alt Mode) ---
    if action_id == "vid_compress_50":
        dst = get_safe_output_path(src, new_ext=".mp4", suffix="_compressed")
        run_ffmpeg([
            "-i", str(src),
            "-c:v", "libx264", "-preset", "medium", "-crf", "28",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            str(dst),
        ])
        return [dst]

    if action_id == "vid_downscale_720p":
        dst = get_safe_output_path(src, new_ext=".mp4", suffix="_720p")
        run_ffmpeg([
            "-i", str(src),
            "-vf", "scale=-2:720",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k",
            str(dst),
        ])
        return [dst]

    if action_id == "vid_1080p":
        dst = get_safe_output_path(src, new_ext=".mp4", suffix="_1080p")
        run_ffmpeg([
            "-i", str(src),
            "-vf", "scale=-2:1080",
            "-c:v", "libx264", "-preset", "fast", "-crf", "21",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            str(dst),
        ])
        return [dst]

    if action_id == "vid_mute":
        dst = get_safe_output_path(src, new_ext=src.suffix, suffix="_muted")
        run_ffmpeg(["-i", str(src), "-c:v", "copy", "-an", str(dst)])
        return [dst]

    if action_id == "vid_trim_10s":
        dst = get_safe_output_path(src, new_ext=src.suffix, suffix="_10s")
        run_ffmpeg([
            "-i", str(src),
            "-t", "10",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac",
            str(dst),
        ])
        return [dst]

    if action_id == "vid_speed_2x":
        dst = get_safe_output_path(src, new_ext=".mp4", suffix="_2x")
        run_ffmpeg([
            "-i", str(src),
            "-vf", "setpts=0.5*PTS",
            "-af", "atempo=2.0",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac",
            str(dst),
        ])
        return [dst]

    if action_id == "vid_reverse":
        dst = get_safe_output_path(src, new_ext=".mp4", suffix="_reversed")
        run_ffmpeg([
            "-i", str(src),
            "-vf", "reverse",
            "-af", "areverse",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac",
            str(dst),
        ])
        return [dst]

    if action_id == "vid_thumbnails":
        dst = get_safe_output_path(src, new_ext=".jpg", suffix="_frame")
        run_ffmpeg([
            "-i", str(src),
            "-vf", "thumbnail,scale=1280:-1",
            "-frames:v", "1",
            str(dst),
        ])
        return [dst]

    # --- Audio Daily Tools (Alt Mode) ---
    if action_id == "aud_denoise":
        dst = get_safe_output_path(src, new_ext=src.suffix, suffix="_denoised")
        run_ffmpeg([
            "-i", str(src),
            "-af", "highpass=f=80,lowpass=f=12000,afftdn=nf=-25",
            str(dst),
        ])
        return [dst]

    if action_id == "aud_normalize":
        dst = get_safe_output_path(src, new_ext=src.suffix, suffix="_norm")
        run_ffmpeg(["-i", str(src), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", str(dst)])
        return [dst]

    if action_id == "aud_remove_silence":
        dst = get_safe_output_path(src, new_ext=src.suffix, suffix="_trimmed")
        run_ffmpeg([
            "-i", str(src),
            "-af", "silenceremove=start_periods=1:start_silence=0.2:start_threshold=-45dB:"
            "stop_periods=-1:stop_silence=0.4:stop_threshold=-45dB",
            str(dst),
        ])
        return [dst]

    if action_id == "aud_compress_128k":
        dst = get_safe_output_path(src, new_ext=".mp3", suffix="_128k")
        run_ffmpeg(["-i", str(src), "-vn", "-c:a", "libmp3lame", "-b:a", "128k", str(dst)])
        return [dst]

    if action_id == "aud_trim_30s":
        dst = get_safe_output_path(src, new_ext=src.suffix, suffix="_30s")
        run_ffmpeg(["-i", str(src), "-t", "30", "-c", "copy", str(dst)])
        return [dst]

    if action_id == "aud_speed_1_5x":
        dst = get_safe_output_path(src, new_ext=src.suffix, suffix="_1_5x")
        run_ffmpeg(["-i", str(src), "-af", "atempo=1.5", str(dst)])
        return [dst]

    if action_id == "aud_to_mono":
        dst = get_safe_output_path(src, new_ext=src.suffix, suffix="_mono")
        run_ffmpeg(["-i", str(src), "-ac", "1", str(dst)])
        return [dst]

    raise ValueError(f"Unknown media action_id: {action_id}")
