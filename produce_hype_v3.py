"""
DemoFour Hype Reel v3 — Final Production
Fixes: universal codec compatibility, real BGM, better voice, proper sync.
"""
from __future__ import annotations
import math, os, struct, subprocess, time, wave, shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / "storyboard-video-agent" / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George — Warm, Captivating Storyteller, British

OUT = Path(__file__).parent / "hype_reel_build"
OUT.mkdir(exist_ok=True)

# Each scene: narration is short + punchy, video prompt is cinematic
SCENES = [
    {
        "num": 1,
        "narration": "Making a product demo... shouldn't take three days, a freelancer, and a prayer.",
        "veo_prompt": (
            "Cinematic close-up of a young tech startup founder sitting at a cluttered desk "
            "at 2 AM in a dark room. Only the laptop screen illuminates their tired, frustrated face. "
            "Multiple browser tabs glow on screen showing video editing tools and freelancer websites. "
            "Their phone buzzes with a notification. They sigh and drop their head into their hands. "
            "Moody blue-orange lighting from the laptop and a warm desk lamp. "
            "Slow cinematic push-in camera movement towards their face. "
            "Shot on 35mm, shallow depth of field, film grain. "
            "Photorealistic, vertical 9:16 portrait orientation."
        ),
    },
    {
        "num": 2,
        "narration": "Paste your site. Say ten words. Hit generate. That's it.",
        "veo_prompt": (
            "Bright modern tech workspace. Close-up of hands confidently typing on a sleek keyboard. "
            "On a large monitor: a beautiful dark-themed web app with a URL input bar, "
            "a glowing cyan microphone icon button, and a large cyan 'Generate' button. "
            "The person pastes a URL, clicks the mic button which pulses, speaks briefly into it, "
            "then clicks Generate. Cyan particle animation radiates from the button across the screen. "
            "Clean, minimal, premium SaaS product aesthetic. Bright natural daylight from windows. "
            "Smooth steady camera, slight slow push towards the screen. "
            "Photorealistic, vertical 9:16 portrait orientation."
        ),
    },
    {
        "num": 3,
        "narration": "Your demo. Your voice. Under sixty seconds. DemoFour.",
        "veo_prompt": (
            "A smiling young professional in a modern co-working space holding up a smartphone "
            "showing a polished product demo video playing on screen. The demo looks professional "
            "with smooth transitions and clean design. A small timer shows 00:52. "
            "Golden hour sunlight pours through floor-to-ceiling windows behind them. "
            "Warm triumphant atmosphere. A colleague in the background gives a thumbs up. "
            "Camera slowly pulls back and slightly upward, revealing the beautiful workspace. "
            "Lens flare from the sun. Cinematic shallow depth of field. "
            "Photorealistic, vertical 9:16 portrait orientation."
        ),
    },
]


def get_duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def generate_narration(text: str, output_path: str) -> float:
    """Generate narration with George voice — warm storyteller."""
    import httpx
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    body = {
        "text": text,
        "model_id": "eleven_v3",
        "voice_settings": {
            "stability": 0.40,
            "similarity_boost": 0.75,
            "style": 0.65,
            "use_speaker_boost": True
        }
    }
    resp = httpx.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(resp.content)
    return get_duration(output_path)


def generate_video(prompt: str, output_path: str) -> None:
    """Generate video with Veo 3.1 full quality."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY.strip())
    config = types.GenerateVideosConfig(
        aspect_ratio="9:16",
        number_of_videos=1,
        duration_seconds=8,
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

    # Immediately re-encode to yuv420p for compatibility
    tmp = output_path + ".tmp.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-i", output_path,
        "-c:v", "libx264", "-profile:v", "main", "-pix_fmt", "yuv420p",
        "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-movflags", "+faststart",
        tmp
    ], check=True, capture_output=True)
    shutil.move(tmp, output_path)


def generate_bgm(output_path: str, duration: float = 45.0) -> None:
    """Generate a cinematic dark electronic beat — 100 BPM."""
    sr = 44100
    n = int(duration * sr)
    bpm = 100
    beat = 60.0 / bpm  # 0.6s per beat

    samples = []
    for i in range(n):
        t = i / sr
        beat_pos = t % beat
        bar_pos = t % (beat * 4)

        # Sub bass — root note pulsing with kick
        bass_env = max(0, 1 - beat_pos * 4) if beat_pos < 0.25 else 0
        bass = 0.18 * bass_env * math.sin(2 * math.pi * 45 * t)

        # Kick drum — punchy
        kick = 0.22 * math.exp(-beat_pos * 35) * math.sin(
            2 * math.pi * (150 - beat_pos * 300) * beat_pos
        ) if beat_pos < 0.08 else 0

        # Snare on beats 2 and 4
        snare_pos = (t + beat) % (beat * 2)
        snare_hit = snare_pos < 0.04
        snare = 0.08 * math.exp(-snare_pos * 60) * (
            math.sin(2 * math.pi * 200 * snare_pos) +
            0.5 * ((i * 31337 % 65536) / 32768 - 1)
        ) if snare_hit else 0

        # Hi-hat — 8th notes
        hh_pos = t % (beat / 2)
        hh = 0.04 * math.exp(-hh_pos * 80) * (
            (i * 7919 % 32768) / 16384 - 1
        ) if hh_pos < 0.015 else 0

        # Warm synth pad — slow chord
        pad_env = 0.5 + 0.5 * math.sin(2 * math.pi * 0.25 * t)
        pad = 0.04 * pad_env * (
            math.sin(2 * math.pi * 130.81 * t) +  # C3
            0.7 * math.sin(2 * math.pi * 164.81 * t) +  # E3
            0.5 * math.sin(2 * math.pi * 196.00 * t)  # G3
        )

        # Arpeggio — 16th notes cycling C-E-G-C5
        arp_notes = [261.63, 329.63, 392.00, 523.25]
        arp_idx = int((t / (beat / 4)) % 4)
        arp_pos = t % (beat / 4)
        arp_env = max(0, 1 - arp_pos * 12)
        arp = 0.025 * arp_env * math.sin(2 * math.pi * arp_notes[arp_idx] * t)

        # Atmospheric shimmer
        shimmer = 0.008 * math.sin(2 * math.pi * 1800 * t + math.sin(2 * math.pi * 1.5 * t) * 4)

        # Master fade envelope
        fade = 1.0
        if t < 2.0:
            fade = t / 2.0
        elif t > duration - 3.0:
            fade = (duration - t) / 3.0
        fade = max(0, min(1, fade))

        s = (bass + kick + snare + hh + pad + arp + shimmer) * fade * 0.85
        samples.append(max(-1.0, min(1.0, s)))

    with wave.open(output_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for s in samples:
            wf.writeframes(struct.pack("<h", int(s * 32767)))


def create_outro(output_path: str, duration: float = 4.5) -> None:
    """Branded outro card with logo + motto."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 720, 1280
    img = Image.new("RGB", (W, H), (3, 6, 13))
    draw = ImageDraw.Draw(img)

    # Subtle glow
    for r in range(350, 0, -1):
        a = int(r / 350 * 10)
        draw.ellipse([W//2-r, H//2-r-80, W//2+r, H//2+r-80],
                     fill=(0+a, 6+a, 13+a*2))

    # Logo
    logo_path = Path(__file__).parent / "assets" / "logo.png"
    if logo_path.exists():
        logo = Image.open(str(logo_path)).convert("RGBA")
        lw = 400
        lh = int(logo.height * lw / logo.width)
        logo = logo.resize((lw, lh), Image.LANCZOS)
        img.paste(logo, ((W-lw)//2, H//2 - lh//2 - 100), logo)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
        font_sm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except:
        font = ImageFont.load_default()
        font_sm = font

    lines = ["Paste your website. Record your voice.", "Get a demo in under 60 seconds."]
    y = H//2 + 60
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        draw.text(((W - bbox[2] + bbox[0])//2, y), line, fill=(148, 163, 184), font=font)
        y += 38

    draw.rectangle([(W-100)//2, y+16, (W+100)//2, y+18], fill=(0, 229, 255))
    tag = "demofour.com"
    bbox = draw.textbbox((0, 0), tag, font=font_sm)
    draw.text(((W - bbox[2] + bbox[0])//2, y+40), tag, fill=(0, 229, 255), font=font_sm)

    frame_path = str(OUT / "outro_frame.png")
    img.save(frame_path)

    # Create video — compatible codec
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", frame_path,
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", str(duration),
        "-vf", "fade=in:0:30,fade=out:st={:.1f}:d=1".format(duration - 1),
        "-c:v", "libx264", "-profile:v", "main", "-pix_fmt", "yuv420p",
        "-preset", "fast", "-crf", "18", "-r", "24",
        "-c:a", "aac",
        "-shortest",
        output_path
    ], check=True, capture_output=True)


def mux_scene(video: str, narration: str, output: str) -> None:
    """Mux video + narration with 1s delay before narration starts. Full video length."""
    vd = get_duration(video)
    subprocess.run([
        "ffmpeg", "-y", "-i", video, "-i", narration,
        "-filter_complex",
        f"[1:a]adelay=1000|1000,apad=whole_dur={vd}[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-profile:v", "main", "-pix_fmt", "yuv420p",
        "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-ar", "44100", "-ac", "2",
        "-t", str(vd),
        "-movflags", "+faststart",
        output
    ], check=True, capture_output=True)


def merge_all(scene_files: list, outro: str, bgm: str, output: str) -> None:
    """Merge clips with smooth transitions + BGM. Output universally compatible."""
    durations = [get_duration(f) for f in scene_files]
    outro_dur = get_duration(outro)
    fade = 0.7

    all_clips = scene_files + [outro]

    # Compute offsets
    o1 = durations[0] - fade
    o2 = o1 + durations[1] - fade
    o3 = o2 + durations[2] - fade

    inputs = []
    for f in all_clips:
        inputs += ["-i", f]

    no_bgm = str(OUT / "no_bgm.mp4")
    subprocess.run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex",
        f"[0:v][1:v]xfade=transition=smoothleft:duration={fade}:offset={o1:.3f}[v01];"
        f"[v01][2:v]xfade=transition=smoothright:duration={fade}:offset={o2:.3f}[v012];"
        f"[v012][3:v]xfade=transition=fade:duration={fade}:offset={o3:.3f}[vout];"
        f"[0:a][1:a]acrossfade=d={fade}[a01];"
        f"[a01][2:a]acrossfade=d={fade}[a012];"
        f"[a012][3:a]acrossfade=d={fade}[aout]",
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-profile:v", "main", "-pix_fmt", "yuv420p",
        "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-ar", "44100", "-ac", "2",
        no_bgm
    ], check=True, capture_output=True)

    # Mix background music
    vid_dur = get_duration(no_bgm)
    fade_out = vid_dur - 3.0

    subprocess.run([
        "ffmpeg", "-y",
        "-i", no_bgm, "-i", bgm,
        "-filter_complex",
        f"[1:a]atrim=0:{vid_dur},aformat=sample_rates=44100:channel_layouts=stereo,"
        f"volume=0.22,afade=t=in:d=1.5,afade=t=out:st={fade_out:.1f}:d=3[bgm];"
        f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=1.8[narr];"
        f"[narr][bgm]amix=inputs=2:duration=first:dropout_transition=3[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        "-movflags", "+faststart",
        output
    ], check=True, capture_output=True)


def main():
    print("=" * 60)
    print("  DemoFour Hype Reel v3 — Final Production")
    print("=" * 60)

    # 1. Background music
    print("\n[1/5] Generating background music (100 BPM cinematic beat)...")
    bgm = str(OUT / "bgm.wav")
    generate_bgm(bgm, duration=45.0)
    print("  Done")

    # 2. Narrations
    print("\n[2/5] Generating narrations (George — warm storyteller)...")
    for sc in SCENES:
        out = str(OUT / f"scene_{sc['num']:02d}_narration.mp3")
        print(f"  Scene {sc['num']}: \"{sc['narration']}\"")
        dur = generate_narration(sc["narration"], out)
        print(f"    -> {dur:.1f}s")

    # 3. Scene videos
    print("\n[3/5] Generating scene videos (Veo 3.1)...")
    print("  ~2-5 min per scene...")
    for sc in SCENES:
        out = str(OUT / f"scene_{sc['num']:02d}.mp4")
        if Path(out).exists():
            print(f"  Scene {sc['num']}: exists, skipping")
            continue
        print(f"  Scene {sc['num']}: generating...")
        generate_video(sc["veo_prompt"], out)
        print(f"  Scene {sc['num']}: done")

    # 4. Mux + Outro
    print("\n[4/5] Muxing scenes + creating outro...")
    muxed = []
    for sc in SCENES:
        v = str(OUT / f"scene_{sc['num']:02d}.mp4")
        n = str(OUT / f"scene_{sc['num']:02d}_narration.mp3")
        o = str(OUT / f"scene_{sc['num']:02d}_muxed.mp4")
        mux_scene(v, n, o)
        d = get_duration(o)
        print(f"  Scene {sc['num']}: {d:.1f}s")
        muxed.append(o)

    outro = str(OUT / "outro.mp4")
    create_outro(outro, duration=4.5)
    print(f"  Outro: {get_duration(outro):.1f}s")

    # 5. Final merge
    print("\n[5/5] Final merge — transitions + BGM...")
    final = str(OUT / "hype_reel.mp4")
    merge_all(muxed, outro, bgm, final)

    dur = get_duration(final)
    print(f"\n  Final: {final} ({dur:.1f}s)")

    # Verify codec compatibility
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,profile,pix_fmt",
         "-of", "csv=p=0", final],
        capture_output=True, text=True)
    print(f"  Codecs: {probe.stdout.strip()}")

    # Copy to submission
    dest = Path(__file__).parent / "hw_6_project_proposal" / "hype_reel.mp4"
    shutil.copy2(final, str(dest))
    print(f"  Copied to: {dest}")
    print("\nDone!")


if __name__ == "__main__":
    main()
