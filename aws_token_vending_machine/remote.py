"""Merge env updates into a remote file over SSH by piping JSON into python3 -c."""


import json
import shlex
import subprocess


REMOTE_UPDATE_SCRIPT = r"""
import json
import pathlib
import sys


def update_env_lines(existing_lines, updates):
    remaining = dict(updates)
    output = []

    for line in existing_lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue

        key = line.split("=", 1)[0].strip()
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)

    if remaining and output and output[-1] != "":
        output.append("")
    for key, value in remaining.items():
        output.append(f"{key}={value}")

    return output


payload = json.load(sys.stdin)
path = pathlib.Path(payload["path"]).expanduser()
updates = payload["updates"]
existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("\n".join(update_env_lines(existing, updates)) + "\n", encoding="utf-8", newline="\n")
path.chmod(0o600)
"""

REMOTE_VERIFY_SCRIPT = r"""
import json
import pathlib
import sys

path = pathlib.Path(json.load(sys.stdin)["path"]).expanduser()
lines = path.read_text(encoding="utf-8").splitlines()
print(f"{len(lines)} {path}")
for line in lines:
    if line and not line.lstrip().startswith("#") and "=" in line:
        print(line.split("=", 1)[0].strip())
"""


def update_remote_env_file(remote_host: str, remote_path: str, updates: dict[str, str]) -> None:
    payload = json.dumps({"path": remote_path, "updates": updates})
    command = f"python3 -c {shlex.quote(REMOTE_UPDATE_SCRIPT)}"
    subprocess.run(["ssh", remote_host, command], input=payload, text=True, check=True)


def verify_remote(remote_host: str, remote_path: str) -> None:
    payload = json.dumps({"path": remote_path})
    command = f"python3 -c {shlex.quote(REMOTE_VERIFY_SCRIPT)}"
    subprocess.run(["ssh", remote_host, command], input=payload, text=True, check=True)
