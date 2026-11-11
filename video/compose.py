"""Join intro + live demo + outro into the final MP4s and write the voice-over script with timestamps.

    python compose.py            -> out/vouch_demo_captions.mp4, out/vouch_demo_clean.mp4, SCRIPT.md, out/captions.srt
"""

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
FADE = 0.6
LEAD = 0.3  # the slide recorder starts ~0.3 s before the timeline starts


def frames(p: Path) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return int(r.stdout.strip())


def normalise(src: Path) -> tuple[Path, float]:
    dst = src.with_suffix(".cfr.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "16",
                    "-preset", "fast", str(dst)], check=True)
    return dst, frames(dst) / 30.0


def join(parts: list[Path], out: Path) -> list[float]:
    norm = [normalise(p) for p in parts]
    (a, da), (b, db), (c, _) = norm
    off1 = da - FADE
    off2 = off1 + db - FADE
    fc = (f"[0:v][1:v]xfade=transition=fade:duration={FADE}:offset={off1:.3f}[v01];"
          f"[v01][2:v]xfade=transition=fade:duration={FADE}:offset={off2:.3f}[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(a), "-i", str(b), "-i", str(c),
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-filter_complex", fc, "-map", "[v]", "-map", "3:a", "-shortest",
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "30",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)], check=True)
    return [0.0, off1, off2]


def ts(t: float, srt: bool = False) -> str:
    m, s = divmod(max(0.0, t), 60)
    if srt:
        h, m = divmod(int(m), 60)
        return f"{h:02d}:{m:02d}:{int(s):02d},{int((s % 1) * 1000):03d}"
    return f"{int(m)}:{s:04.1f}"


def main() -> None:
    import sys
    if "--script-only" in sys.argv:  # reuse the encoded parts
        da, db = frames(OUT / "intro.cfr.mp4") / 30.0, frames(OUT / "demo.cfr.mp4") / 30.0
        offs = [0.0, da - FADE, da - FADE + db - FADE]
        return write_script(offs)
    offs = join([OUT / "intro.webm", OUT / "demo.webm", OUT / "outro.webm"], OUT / "vouch_demo_captions.mp4")
    if all((OUT / f"{p}-clean.webm").exists() for p in ("intro", "demo", "outro")):
        join([OUT / f"{p}-clean.webm" for p in ("intro", "demo", "outro")], OUT / "vouch_demo_clean.mp4")
    write_script(offs)


def write_script(offs: list[float]) -> None:
    lines = []
    for part, off, lead in (("intro", offs[0], LEAD), ("demo", offs[1], 0.0), ("outro", offs[2], LEAD)):
        for x in json.loads((OUT / f"{part}.timeline.json").read_text(encoding="utf-8")):
            lines.append((off + lead + x["start"], off + lead + x["end"], x["scene"], x["text"]))
    total = frames(OUT / "vouch_demo_captions.mp4") / 30.0
    srt = "\n".join(f"{i}\n{ts(a, True)} --> {ts(b, True)}\n{t}\n" for i, (a, b, _, t) in enumerate(lines, 1))
    (OUT / "captions.srt").write_text(srt, encoding="utf-8")
    md = ["# Vouch demo video: voice-over script", "",
          f"Video: `video/out/vouch_demo_captions.mp4` (captions burned in, read along) and `vouch_demo_clean.mp4` (same video, no captions), "
          f"1920×1080, 30 fps, {ts(total)} long, silent audio track for your voice-over. Captions as subtitles: `video/out/captions.srt`.", "",
          "Read each line when it appears. Pace: calm, about 140 words a minute; every line has room for a short pause.", "",
          "| Start | End | Scene | Say |", "|---|---|---|---|"]
    md += [f"| {ts(a)} | {ts(b)} | {s} | {t} |" for a, b, s, t in lines]
    (HERE / "SCRIPT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"total {ts(total)}; {len(lines)} lines; offsets {[round(o, 1) for o in offs]}")


if __name__ == "__main__":
    main()
