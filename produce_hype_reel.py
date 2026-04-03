"""
DemoFour Hype Reel Producer
Generates a cinematic 30s vertical hype video with:
- AI-generated scene videos via Veo 3.1
- ElevenLabs narration
- Background music (generated)
- Professional crossfade transitions
- Text overlays
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
import time
import wave
import math
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / "storyboard-video-agent" / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "TX3LPaxmHKxFdv7VOQHJ"  # Liam - Energetic Social Media Creator

OUT = Path(__file__).parent / "hype_reel_build"
OUT.mkdir(exist_ok=True)

# ─── Scene Definitions ───────────────────────────────────────────────
SCENES = [
    {
        "num": 1,
        "narration": "Making a product demo shouldn't take three days, a freelancer, and a prayer.",
        "veo_prompt": (
            "Cinematic close-up of a frustrated young tech founder sitting alone at a desk "
            "late at night, lit by harsh laptop glow and a single desk lamp. The room is dark. "
            "Multiple browser tabs visible on screen showing freelancer websites and video editing tools. "
            "A red notification pops up reading 'Demo due tomorrow'. The founder rubs their eyes and sighs. "
            "Moody, dramatic lighting with blue and orange tones. Subtle camera push-in. "
            "Shot on anamorphic lens, shallow depth of field, cinematic color grading. "
            "Vertical 9:16 format, realistic, photorealistic."
        ),
    },
    {
        "num": 2,
        "narration": "Paste your site. Record ten seconds. Hit generate. That's it.",
        "veo_prompt": (
            "Sleek modern browser interface on a large monitor in a bright, clean workspace. "
            "A hand smoothly pastes a URL into a minimal dark-themed web app with cyan accent colors. "
            "The user clicks a glowing microphone button and speaks briefly. "
            "Then clicks a large 'Generate' button that pulses with electric cyan light. "
            "A progress animation starts with particles flowing across the screen. "
            "Clean, futuristic UI design. Bright ambient lighting, tech startup aesthetic. "
            "Smooth camera pan across the screen. Vertical 9:16 format, photorealistic."
        ),
    },
    {
        "num": 3,
        "narration": "Your demo. Your voice. Under sixty seconds. DemoFour.",
        "veo_prompt": (
            "A polished product demo video playing fullscreen on a smartphone held in someone's hand. "
            "The video looks professional with smooth transitions and branded graphics. "
            "A timer in the corner shows 00:52. The person smiles watching it. "
            "Pull back to reveal they're in a modern co-working space, others look impressed. "
            "Golden hour light streaming through large windows. Celebration energy. "
            "Cinematic camera movement pulling back slowly. Lens flare. "
            "Vertical 9:16 format, photorealistic, shallow depth of field."
        ),
    },
]


def generate_narration(text: str, output_path: str) -> None:
    """Generate narration audio with ElevenLabs."""
    from elevenlabs.client import ElevenLabs

    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    audio = client.text_to_speech.convert(
        voice_id=VOICE_ID,
        text=text,
        model_id="eleven_v3",
    )

    with open(output_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)


def generate_video(prompt: str, output_path: str) -> None:
    """Generate video with Veo 3.1."""
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
        raise TimeoutError("Veo generation timed out")

    result = getattr(operation, "result", None) or getattr(operation, "response", None)
    if not result or not getattr(result, "generated_videos", None):
        raise RuntimeError(f"Veo failed: {getattr(operation, 'error', 'unknown')}")

    generated_video = result.generated_videos[0]
    client.files.download(file=generated_video)
    generated_video.video.save(output_path)


def generate_bgm(output_path: str, duration: float = 35.0) -> None:
    """Generate a dark electronic ambient background track."""
    sample_rate = 44100
    num_samples = int(duration * sample_rate)

    samples = []
    for i in range(num_samples):
        t = i / sample_rate

        # Deep bass drone (50 Hz)
        bass = 0.12 * math.sin(2 * math.pi * 50 * t)
        # Sub harmonic
        sub = 0.06 * math.sin(2 * math.pi * 75 * t)

        # Pulsing pad (every 0.5s)
        pad_env = 0.5 + 0.5 * math.sin(2 * math.pi * 2 * t)
        pad = 0.04 * pad_env * math.sin(2 * math.pi * 150 * t)
        pad2 = 0.03 * pad_env * math.sin(2 * math.pi * 200 * t)

        # High shimmer
        shimmer_env = 0.5 + 0.5 * math.sin(2 * math.pi * 0.3 * t)
        shimmer = 0.015 * shimmer_env * math.sin(2 * math.pi * 800 * t + math.sin(2 * math.pi * 3 * t) * 2)

        # Kick pattern (every 0.5s)
        beat_pos = t % 0.5
        kick = 0.15 * math.exp(-beat_pos * 30) * math.sin(2 * math.pi * (120 - beat_pos * 200) * beat_pos) if beat_pos < 0.1 else 0

        # Hi-hat pattern (offbeat)
        hat_pos = (t + 0.25) % 0.5
        import random
        hat = 0.03 * math.exp(-hat_pos * 50) * (2 * ((i * 7919) % 32768) / 32768 - 1) if hat_pos < 0.02 else 0

        # Fade in/out
        fade = 1.0
        if t < 1.0:
            fade = t / 1.0
        elif t > duration - 2.0:
            fade = (duration - t) / 2.0
        fade = max(0, min(1, fade))

        sample = (bass + sub + pad + pad2 + shimmer + kick + hat) * fade
        sample = max(-1.0, min(1.0, sample))
        samples.append(sample)

    # Write WAV
    with wave.open(output_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for s in samples:
            wf.writeframes(struct.pack("<h", int(s * 32767)))


def get_duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def merge_final() -> str:
    """Merge scenes with crossfade transitions, narration, background music, and text overlays."""
    scene_files = []
    for i in range(1, 4):
        video = str(OUT / f"scene_{i:02d}.mp4")
        audio = str(OUT / f"scene_{i:02d}_narration.mp3")
        muxed = str(OUT / f"scene_{i:02d}_muxed.mp4")

        vd = get_duration(video)
        ad = get_duration(audio)

        # Always use full video duration; pad audio with silence if narration is shorter
        subprocess.run([
            "ffmpeg", "-y", "-i", video, "-i", audio,
            "-filter_complex",
            f"[1:a]apad=whole_dur={vd}[apad]",
            "-map", "0:v:0", "-map", "[apad]",
            "-c:v", "copy", "-c:a", "aac",
            "-t", str(vd),
            muxed
        ], check=True, capture_output=True)
        scene_files.append(muxed)

    # Get durations for crossfade calc
    durations = [get_duration(f) for f in scene_files]
    fade_dur = 0.8  # crossfade duration

    # Build crossfade filter for 3 clips
    # First crossfade scene 1 + scene 2
    # Then crossfade result + scene 3
    total_dur = sum(durations) - fade_dur * 2  # approximate

    no_transition = str(OUT / "no_transition.mp4")
    # Simple concat with crossfade using xfade filter
    subprocess.run([
        "ffmpeg", "-y",
        "-i", scene_files[0], "-i", scene_files[1], "-i", scene_files[2],
        "-filter_complex",
        f"[0:v][1:v]xfade=transition=fadeblack:duration={fade_dur}:offset={durations[0]-fade_dur}[v01];"
        f"[v01][2:v]xfade=transition=fadeblack:duration={fade_dur}:offset={durations[0]+durations[1]-2*fade_dur}[vout];"
        f"[0:a][1:a]acrossfade=d={fade_dur}[a01];"
        f"[a01][2:a]acrossfade=d={fade_dur}[aout]",
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        no_transition
    ], check=True, capture_output=True)

    # Add background music
    bgm_path = str(OUT / "bgm.wav")
    final_path = str(OUT / "hype_reel.mp4")

    vid_duration = get_duration(no_transition)

    subprocess.run([
        "ffmpeg", "-y",
        "-i", no_transition,
        "-i", bgm_path,
        "-filter_complex",
        f"[1:a]atrim=0:{vid_duration},volume=0.18,afade=t=out:st={vid_duration-2}:d=2[bgm];"
        f"[0:a]volume=1.5[narr];"
        f"[narr][bgm]amix=inputs=2:duration=shortest[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        final_path
    ], check=True, capture_output=True)

    return final_path


def main():
    print("=" * 60)
    print("  DemoFour Hype Reel Producer")
    print("=" * 60)

    # Step 1: Generate background music
    print("\n[1/4] Generating background music...")
    bgm_path = str(OUT / "bgm.wav")
    generate_bgm(bgm_path, duration=40.0)
    print("  Done: bgm.wav")

    # Step 2: Generate narrations
    print("\n[2/4] Generating narrations (ElevenLabs)...")
    for scene in SCENES:
        out = str(OUT / f"scene_{scene['num']:02d}_narration.mp3")
        if Path(out).exists():
            print(f"  Scene {scene['num']}: exists, skipping")
            continue
        generate_narration(scene["narration"], out)
        print(f"  Scene {scene['num']}: done")

    # Step 3: Generate videos
    print("\n[3/4] Generating scene videos (Veo 3.1)...")
    print("  This takes 2-5 min per scene...")
    for scene in SCENES:
        out = str(OUT / f"scene_{scene['num']:02d}.mp4")
        if Path(out).exists():
            print(f"  Scene {scene['num']}: exists, skipping")
            continue
        print(f"  Scene {scene['num']}: generating...")
        generate_video(scene["veo_prompt"], out)
        print(f"  Scene {scene['num']}: done")

    # Step 4: Merge with transitions + BGM
    print("\n[4/4] Merging with crossfades + background music...")
    final = merge_final()
    print(f"\n  Final video: {final}")

    # Copy to submission folder
    import shutil
    dest = Path(__file__).parent / "hw_6_project_proposal" / "hype_reel.mp4"
    shutil.copy2(final, str(dest))
    print(f"  Copied to: {dest}")
    print("\nDone!")


if __name__ == "__main__":
    main()
