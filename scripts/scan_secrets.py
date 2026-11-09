"""Inspect tracked content without printing secret values."""

from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
files = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
known = []
env = root / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        if line.startswith("FRED_API_KEY=") and line.partition("=")[2].strip():
            known.append(line.partition("=")[2].strip().strip("\"'"))
bad = []
for name in filter(None, files):
    path = root / name
    if not path.is_file():
        continue
    content = path.read_bytes()
    if path.name == ".env" or path.suffix in {".db", ".sqlite", ".sqlite3"} or any(key.encode() in content for key in known):
        bad.append(name)
    if re.search(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})", content):
        bad.append(name)
if bad:
    print("Sensitive tracked content found in: " + ", ".join(sorted(set(bad))))
    sys.exit(1)
print("Tracked-file secret scan passed; no local API key, token pattern, .env, or database is tracked.")
