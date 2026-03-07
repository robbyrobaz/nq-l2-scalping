#!/usr/bin/env python3
"""CLI tool to ingest a YouTube trading video into a new strategy folder.

Usage:
    python3 pipeline/process_video.py --url <youtube_url> --strategy-id 004 --name "My Strategy"
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def download_subtitles(url, tmp_dir="/tmp"):
    """Download auto-generated subtitles using yt-dlp."""
    out_template = f"{tmp_dir}/strategy_video"
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--write-auto-sub", "--sub-format", "vtt",
        "--skip-download",
        "-o", out_template,
        url,
    ]
    print(f"Downloading subtitles: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"yt-dlp stderr: {result.stderr}")
        print("Warning: subtitle download failed. Creating empty transcript.")
        return None

    # Find the VTT file
    import glob
    vtt_files = glob.glob(f"{tmp_dir}/strategy_video*.vtt")
    if not vtt_files:
        print("No VTT file found. Creating empty transcript.")
        return None

    return vtt_files[0]


def parse_vtt(vtt_path):
    """Parse VTT subtitle file into clean transcript text."""
    with open(vtt_path) as f:
        content = f.read()

    # Remove VTT header
    lines = content.split('\n')
    text_lines = []
    seen = set()

    for line in lines:
        line = line.strip()
        # Skip timestamps, headers, empty lines
        if not line:
            continue
        if line.startswith("WEBVTT"):
            continue
        if line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if re.match(r'^\d{2}:\d{2}', line):
            continue
        if '-->' in line:
            continue
        if line.startswith("NOTE"):
            continue

        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', line)
        clean = clean.strip()

        if clean and clean not in seen:
            seen.add(clean)
            text_lines.append(clean)

    return ' '.join(text_lines)


def create_strategy_folder(strategy_id, name, url, transcript):
    """Create strategy folder with template files."""
    slug = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
    folder = REPO_ROOT / "strategies" / f"{strategy_id}_{slug}"
    folder.mkdir(parents=True, exist_ok=True)

    # source_video.txt
    (folder / "source_video.txt").write_text(f"{url}\n")

    # transcript.txt
    (folder / "transcript.txt").write_text(transcript or "No transcript available.\n")

    # strategy_spec.md template
    spec = f"""# Strategy {strategy_id}: {name}

**Source:** {url}
**Concept:** [FILL IN - describe the core trading concept from the video]

## Logic

[FILL IN - step-by-step strategy logic extracted from the transcript]

## Signal Rules

**Long Entry:**
- [condition 1]
- [condition 2]

**Short Entry:**
- [condition 1]
- [condition 2]

## Parameters to Optimize
- `take_profit_ticks`: (default: 8)
- `stop_loss_ticks`: (default: 12)
- `session_filter`: RTH only

## Transcript

{transcript or 'No transcript available.'}

## Implementation Notes
- Use DuckDB: `nq_feed.duckdb` tables `nq_ticks`, `nq_quotes`
- Delta = inferred from trade price vs bid/ask
"""
    (folder / "strategy_spec.md").write_text(spec)

    return folder


def main():
    parser = argparse.ArgumentParser(description="Ingest a trading video into a strategy folder")
    parser.add_argument("--url", required=True, help="YouTube video URL")
    parser.add_argument("--strategy-id", required=True, help="Strategy ID (e.g., 004)")
    parser.add_argument("--name", required=True, help="Strategy name")
    args = parser.parse_args()

    print(f"Processing video: {args.url}")
    print(f"Strategy: {args.strategy_id} - {args.name}")

    # Download subtitles
    vtt_path = download_subtitles(args.url)
    transcript = parse_vtt(vtt_path) if vtt_path else None

    # Create strategy folder
    folder = create_strategy_folder(args.strategy_id, args.name, args.url, transcript)

    print(f"\nStrategy folder created: {folder}")
    print(f"Files:")
    for f in sorted(folder.iterdir()):
        print(f"  {f.name}")

    print(f"\nNext steps:")
    print(f"  1. Review transcript: {folder}/transcript.txt")
    print(f"  2. Fill in strategy logic: {folder}/strategy_spec.md")
    print(f"  3. Implement backtest: {folder}/backtest.py")
    print(f"  4. Run: python3 {folder}/backtest.py")


if __name__ == "__main__":
    main()
