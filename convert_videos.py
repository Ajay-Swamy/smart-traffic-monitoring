from pathlib import Path
import subprocess
import imageio_ffmpeg

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

for src in Path("outputs").rglob("*_annotated.mp4"):
    dst = src.with_name(f"{src.stem}_h264{src.suffix}")
    print(f"Converting {src} -> {dst}")
    subprocess.run(
        [ffmpeg, "-y", "-i", str(src),
         "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(dst)],
        check=True,
    )