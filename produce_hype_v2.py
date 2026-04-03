"""
DemoFour Hype Reel v2 — Narration-first pipeline.
1. Generate narrations first
2. Measure narration durations
3. Generate scene videos timed to narration
4. Merge with smooth transitions + BGM + outro
"""
from __future__ import annotations
import json, math, os, struct, subprocess, time, wave, shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / "storyboard-video-agent" / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "nPczCjzI2devNBz1zQrb"  # Brian — Deep, Resonant, Social Media, Classy

OUT = Path(__file__).parent / "hype_reel_build"
OUT.mkdir(exist_ok=True)

SCENES = [
    {
        "num": 1,
        "title": "The Problem",
        "narration": "Making a product demo... shouldn't take three days, a freelancer, and a prayer.",
        "veo_prompt": (
            "Cinematic close-up of a stressed young tech founder alone at a desk at 2 AM. "
            "Laptop screen casting harsh blue light on their tired face. Multiple browser tabs "
            "visible: freelancer marketplace, video editing software, an empty Google Doc. "
            "A phone notification flashes red: 'Demo Day Tomorrow'. The founder exhales and "
            "drops their head into their hands. Dark moody room, single warm desk lamp, "
            "shallow depth of field, anamorphic lens flare. Camera slowly pushes in on their face. "
            "Photorealistic, cinematic color grading, vertical 9:16 portrait format."
        ),
    },
    {
        "num": 2,
        "title": "Enter DemoFour",
        "narration": "Paste your site. Say ten words. Hit generate. That's it.",
        "veo_prompt": (
            "Bright clean modern workspace. A person's hands on a keyboard, typing a URL into "
            "a sleek dark-themed web application with glowing cyan accent elements. "
            "The interface shows a large URL input field, a pulsing cyan microphone button, "
            "and a prominent 'Generate' button. The person clicks the microphone, speaks briefly, "
            "then clicks Generate. A beautiful loading animation fills the screen with flowing "
            "cyan light particles. Clean minimal UI, premium tech product aesthetic. "
            "Bright natural window light, shallow depth of field on the hands and screen. "
            "Camera is steady, slight dolly towards the screen. "
            "Photorealistic, vertical 9:16 portrait format."
        ),
    },
    {
        "num": 3,
        "title": "Your Demo, Ready",
        "narration": "Your demo. Your voice. Under sixty seconds. DemoFour.",
        "veo_prompt": (
            "A polished professional product demo video playing on a large smartphone screen. "
            "The video shows smooth branded transitions, crisp typography, and product screenshots. "
            "A timer overlay reads '00:52'. The person holding the phone smiles with satisfaction. "
            "Camera slowly pulls back to reveal a modern bright co-working space. A colleague "
            "nearby looks impressed and gives a thumbs up. Golden hour sunlight streams through "
            "floor-to-ceiling windows, lens flare. Warm triumphant feeling. "
            "Shallow depth of field, cinematic, vertical 9:16 portrait format."
        ),
    },
]


def get_duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def generate_narration(text: str, output_path: str) -> float:
    """Generate narration, return duration in seconds."""
    import httpx
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    body = {
        "text": text,
        "model_id": "eleven_v3",
        "voice_settings": {
            "stability": 0.35,
            "similarity_boost": 0.80,
            "style": 0.6,
            "use_speaker_boost": True
        }
    }
    resp = httpx.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(resp.content)
    return get_duration(output_path)


def generate_video(prompt: str, output_path: str, duration: int = 8) -> None:
    """Generate video with Veo 3.1."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY.strip())
    config = types.GenerateVideosConfig(
        aspect_ratio="9:16",
        number_of_videos=1,
        duration_seconds=duration,
        resolution="720p",
        person_generation="allow_all",
    )
    operation = client.models.generate_videos(
        model="veo-3.1-generate-preview",
        prompt=prompt,
        config=config,
    )
    elapsed = 0
    while not operation.done and elapsed < 600:
        time.sleep(10)
        elapsed += 10
        operation = client.operations.get(operation)
    if not operation.done:
        raise TimeoutError("Veo timed out")
    result = getattr(operation, "result", None) or getattr(operation, "response", None)
    if not result or not getattr(result, "generated_videos", None):
        raise RuntimeError(f"Veo failed: {getattr(operation, 'error', 'unknown')}")
    gv = result.generated_videos[0]
    client.files.download(file=gv)
    gv.video.save(output_path)


def generate_bgm(output_path: str, duration: float = 40.0) -> None:
    """Dark electronic ambient beat."""
    sr = 44100
    n = int(duration * sr)
    samples = []
    for i in range(n):
        t = i / sr
        # Deep sub bass
        bass = 0.10 * math.sin(2*math.pi*55*t)
        # Warm pad
        pad_env = 0.5 + 0.5 * math.sin(2*math.pi*1.5*t)
        pad = 0.035 * pad_env * math.sin(2*math.pi*165*t)
        pad2 = 0.025 * pad_env * math.sin(2*math.pi*220*t + 0.5)
        # Soft kick every beat (BPM ~100)
        beat = 0.6  # seconds per beat
        bp = t % beat
        kick = 0.12 * math.exp(-bp*25) * math.sin(2*math.pi*(100 - bp*180)*bp) if bp < 0.08 else 0
        # Shimmering high
        sh_env = 0.5 + 0.5 * math.sin(2*math.pi*0.25*t)
        shimmer = 0.012 * sh_env * math.sin(2*math.pi*1200*t + math.sin(2*math.pi*2*t)*3)
        # Fade envelope
        fade = 1.0
        if t < 1.5: fade = t / 1.5
        elif t > duration - 2.5: fade = (duration - t) / 2.5
        fade = max(0, min(1, fade))

        s = (bass + pad + pad2 + kick + shimmer) * fade
        samples.append(max(-1.0, min(1.0, s)))

    with wave.open(output_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for s in samples:
            wf.writeframes(struct.pack("<h", int(s * 32767)))


def create_outro(output_path: str, duration: float = 4.0) -> None:
    """Create branded outro video with logo + motto."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 720, 1280
    img = Image.new("RGB", (W, H), (3, 6, 13))
    draw = ImageDraw.Draw(img)

    # Subtle center glow
    for r in range(300, 0, -1):
        a = int(r / 300 * 8)
        draw.ellipse([W//2-r, H//2-r-80, W//2+r, H//2+r-80], fill=(0+a, 6+a, 13+a*2))

    # Logo
    logo_path = Path(__file__).parent / "hw_6_project_proposal" / "logo.png"
    logo = Image.open(str(logo_path)).convert("RGBA")
    lw = 420
    lh = int(logo.height * lw / logo.width)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    img.paste(logo, ((W-lw)//2, H//2 - lh//2 - 100), logo)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
        font_sm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except:
        font = ImageFont.load_default()
        font_sm = font

    motto_lines = [
        "Paste your website. Record your voice.",
        "Get a demo in under 60 seconds."
    ]
    y = H//2 + lh//2 - 60
    for line in motto_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((W-tw)//2, y), line, fill=(148, 163, 184), font=font)
        y += 38

    # Cyan accent line
    draw.rectangle([(W-100)//2, y+16, (W+100)//2, y+18], fill=(0, 229, 255))

    # URL
    tag = "demofour.com"
    bbox = draw.textbbox((0, 0), tag, font=font_sm)
    draw.text(((W - bbox[2] + bbox[0])//2, y+40), tag, fill=(0, 229, 255), font=font_sm)

    frame_path = str(OUT / "outro_frame.png")
    img.save(frame_path)

    # Create video from frame with fade-in
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", frame_path, "-t", str(duration),
        "-vf", "fade=in:0:30",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-r", "24", str(OUT / "outro_video.mp4")
    ], check=True, capture_output=True)

    # Add silent audio
    subprocess.run([
        "ffmpeg", "-y", "-i", str(OUT / "outro_video.mp4"),
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", str(duration), "-c:v", "copy", "-c:a", "aac", "-shortest",
        output_path
    ], check=True, capture_output=True)


def mux_scene(video: str, narration: str, output: str) -> None:
    """Mux video + narration. Narration starts after 0.8s delay. Video runs full length."""
    vd = get_duration(video)
    nd = get_duration(narration)

    # Add 0.8s silence before narration so it doesn't start instantly
    delay_ms = 800
    subprocess.run([
        "ffmpeg", "-y",
        "-i", video,
        "-i", narration,
        "-filter_complex",
        f"[1:a]adelay={delay_ms}|{delay_ms},apad=whole_dur={vd}[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac",
        "-t", str(vd),
        output
    ], check=True, capture_output=True)


def merge_all(scene_files: list, outro: str, bgm: str, output: str) -> None:
    """Merge all scenes + outro with crossfade transitions and background music."""
    all_clips = scene_files + [outro]
    durations = [get_duration(f) for f in all_clips]
    fade = 0.6

    # Build xfade chain
    n = len(all_clips)
    vfilters = []
    afilters = []
    offset = 0

    # First pair
    offset = durations[0] - fade
    vfilters.append(f"[0:v][1:v]xfade=transition=smoothleft:duration={fade}:offset={offset:.3f}[v01]")
    afilters.append(f"[0:a][1:a]acrossfade=d={fade}[a01]")

    # Second pair
    offset += durations[1] - fade
    vfilters.append(f"[v01][2:v]xfade=transition=smoothright:duration={fade}:offset={offset:.3f}[v012]")
    afilters.append(f"[a01][2:a]acrossfade=d={fade}[a012]")

    # Third pair (to outro) — use fade to black for final
    offset += durations[2] - fade
    vfilters.append(f"[v012][3:v]xfade=transition=fade:duration={fade}:offset={offset:.3f}[vout]")
    afilters.append(f"[a012][3:a]acrossfade=d={fade}[aout]")

    filter_str = ";".join(vfilters + afilters)

    no_bgm = str(OUT / "no_bgm.mp4")
    inputs = []
    for f in all_clips:
        inputs += ["-i", f]

    subprocess.run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_str,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        no_bgm
    ], check=True, capture_output=True)

    # Mix in background music
    vid_dur = get_duration(no_bgm)
    fade_out_start = vid_dur - 2.5

    subprocess.run([
        "ffmpeg", "-y",
        "-i", no_bgm,
        "-i", bgm,
        "-filter_complex",
        f"[1:a]atrim=0:{vid_dur},volume=0.15,afade=t=in:d=1,afade=t=out:st={fade_out_start:.1f}:d=2.5[bgm];"
        f"[0:a]volume=1.6[narr];"
        f"[narr][bgm]amix=inputs=2:duration=shortest:dropout_transition=2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", output
    ], check=True, capture_output=True)


def main():
    print("=" * 60)
    print("  DemoFour Hype Reel v2 — Narration-First Pipeline")
    print("=" * 60)

    # Step 1: Narrations
    print("\n[1/5] Generating narrations (Brian voice)...")
    narration_durs = {}
    for sc in SCENES:
        out = str(OUT / f"scene_{sc['num']:02d}_narration.mp3")
        print(f"  Scene {sc['num']}: \"{sc['narration']}\"")
        dur = generate_narration(sc["narration"], out)
        narration_durs[sc["num"]] = dur
        print(f"    -> {dur:.1f}s")

    # Step 2: Scene videos (each 8s to give room for narration + breathing space)
    print("\n[2/5] Generating scene videos (Veo 3.1)...")
    print("  ~2-5 min per scene...")
    for sc in SCENES:
        out = str(OUT / f"scene_{sc['num']:02d}.mp4")
        if Path(out).exists():
            print(f"  Scene {sc['num']}: exists, skipping")
            continue
        print(f"  Scene {sc['num']}: generating...")
        generate_video(sc["veo_prompt"], out, duration=8)
        print(f"  Scene {sc['num']}: done")

    # Step 3: Mux narration onto video with proper timing
    print("\n[3/5] Muxing narration onto scenes...")
    muxed = []
    for sc in SCENES:
        video = str(OUT / f"scene_{sc['num']:02d}.mp4")
        narr = str(OUT / f"scene_{sc['num']:02d}_narration.mp3")
        out = str(OUT / f"scene_{sc['num']:02d}_muxed.mp4")
        mux_scene(video, narr, out)
        d = get_duration(out)
        print(f"  Scene {sc['num']}: {d:.1f}s")
        muxed.append(out)

    # Step 4: Create outro + BGM
    print("\n[4/5] Creating outro card + background music...")
    outro = str(OUT / "outro.mp4")
    create_outro(outro, duration=4.0)
    print("  Outro: 4.0s")

    bgm = str(OUT / "bgm.wav")
    generate_bgm(bgm, duration=42.0)
    print("  BGM: 42.0s")

    # Step 5: Final merge
    print("\n[5/5] Final merge with transitions + BGM...")
    final = str(OUT / "hype_reel.mp4")
    merge_all(muxed, outro, bgm, final)

    dur = get_duration(final)
    print(f"\n  Final: {final} ({dur:.1f}s)")

    # Copy to submission
    dest = Path(__file__).parent / "hw_6_project_proposal" / "hype_reel.mp4"
    shutil.copy2(final, str(dest))
    print(f"  Copied to: {dest}")
    print("\nDone!")


if __name__ == "__main__":
    main()
