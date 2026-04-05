#!/usr/bin/env python3
"""CLI app that displays claude /usage with auto-refresh."""

import io
import shutil
import time
import os
import sys
import argparse
import re
from datetime import datetime

import pexpect
import pyte


COLS = 120
ROWS = 50


def render_screen(raw_text):
    """Feed raw terminal output through pyte to get clean text."""
    screen = pyte.Screen(COLS, ROWS)
    stream = pyte.Stream(screen)
    stream.feed(raw_text)

    lines = [screen.display[i].rstrip() for i in range(ROWS)]
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


BAR_WIDTH = 50
# Dim/dark color for unused portion (ANSI 256-color dark gray)
DIM = "\033[38;5;238m"
BOLD = "\033[1m"
LIGHT = "\033[38;5;250m"
RESET = "\033[0m"
BLOCK_FULL = "█"
BLOCK_CHARS = set("█▉▊▋▌▍▎▏▐▛▜▝▞▟▗▖▘▙▚▀▄▌▐")


def colorize_bars(text):
    """Re-render usage bar lines with a dim-colored unused portion."""
    lines = text.split("\n")
    result = []
    for line in lines:
        # Detect lines that contain block characters and "% used"
        if "% used" in line:
            match = re.match(r"^(.*?)(([█▉▊▋▌▍▎▏▐▛▜▝▞▟▗▖▘▙▚▀▄▌▐\s]*[█▉▊▋▌▍▎▏▐▛▜▝▞▟▗▖▘▙▚▀▄▌▐]+))\s+(\d+% used)$", line)
            if match:
                prefix = match.group(1)
                bar = match.group(2)
                pct_text = match.group(4)
                pct = int(re.search(r"(\d+)", pct_text).group(1))

                # Build a new bar with colored unused portion
                filled = round(BAR_WIDTH * pct / 100)
                unfilled = BAR_WIDTH - filled
                new_bar = BLOCK_FULL * filled + DIM + BLOCK_FULL * unfilled + RESET
                result.append(f"  {new_bar}  {LIGHT}{pct_text}{RESET}")
                continue
        # Also handle a bare bar line (no "% used" on the same line)
        if any(c in line for c in "█▉▊▋▌") and "% used" not in line and "Resets" not in line:
            # Skip standalone bar lines since we rebuild them above
            has_block = sum(1 for c in line if c in BLOCK_CHARS)
            if has_block > 5:
                continue
        # Bold section headers
        if "Current session" in line or "Current week" in line:
            result.append(f"  {BOLD}{line}{RESET}")
            continue
        # Dim the "Resets" lines
        if "Resets" in line:
            result.append(f"  {LIGHT}{line}{RESET}")
            continue
        result.append(f"  {line}")
    return "\n".join(result)


def extract_usage(text):
    """Extract the usage section from screen text."""
    lines = text.split("\n")
    result = []
    capture = False
    resets_count = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if capture:
                result.append("")
            continue

        if "Status" in stripped and "Usage" in stripped:
            capture = True
            continue  # skip the tab header row

        if capture:
            result.append(stripped)
            if "Resets" in stripped:
                resets_count += 1
                if resets_count >= 2:
                    break

    if not result:
        return ""

    cleaned = "\n".join(result)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = colorize_bars(cleaned.strip())
    return cleaned


def get_usage():
    """Run claude interactively, send /usage, and capture output."""
    claude_path = shutil.which("claude")
    if not claude_path:
        claude_path = os.path.expanduser("~/.local/bin/claude")

    env = os.environ.copy()
    env.setdefault("TERM", "xterm-256color")

    log = io.StringIO()
    child = pexpect.spawn(claude_path, encoding="utf-8", timeout=30, env=env,
                          dimensions=(ROWS, COLS))
    child.logfile_read = log

    # Wait for the input prompt
    child.expect(r"❯|>", timeout=15)
    time.sleep(1)

    # Type /usage and press Enter
    child.send("/usage")
    time.sleep(0.5)
    child.send("\r")

    # Wait for usage content to render
    try:
        child.expect(r"Resets|only available|% used", timeout=15)
        time.sleep(3)
    except pexpect.TIMEOUT:
        time.sleep(2)

    # Drain remaining output
    try:
        while True:
            child.read_nonblocking(4096, timeout=1)
    except (pexpect.TIMEOUT, pexpect.EOF):
        pass

    # Exit claude
    child.send("\x1b")
    time.sleep(0.3)
    child.sendcontrol("c")
    time.sleep(0.3)
    child.sendcontrol("c")
    child.close()

    # Render through pyte for clean text
    text = render_screen(log.getvalue())
    usage = extract_usage(text)
    if usage:
        return usage

    # Fallback
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def main():
    parser = argparse.ArgumentParser(description="Auto-refreshing Claude usage display")
    parser.add_argument(
        "-n", "--interval", type=int, default=60,
        help="Refresh interval in seconds (default: 60)",
    )
    parser.add_argument(
        "--once", action="store_true", help="Run once and exit",
    )
    args = parser.parse_args()

    try:
        while True:
            output = get_usage()
            clear_screen()
            print()
            print()
            print(output)
            now = datetime.now().strftime("%I:%M:%S %p")
            print(f"\n  {LIGHT}Last updated: {now}{RESET}")
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nBye!")
    except pexpect.exceptions.TIMEOUT:
        print("Error: claude command timed out", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
