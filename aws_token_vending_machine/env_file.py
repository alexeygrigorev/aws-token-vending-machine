"""Merge KEY=value assignments into an env file, preserving unrelated lines."""


import pathlib


def update_env_lines(existing_lines: list[str], updates: dict[str, str]) -> list[str]:
    remaining = dict(updates)
    output: list[str] = []

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


def update_env_file(path: pathlib.Path, updates: dict[str, str]) -> None:
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated_lines = update_env_lines(existing_lines, updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(updated_lines) + "\n")
    try:
        path.chmod(0o600)
    except (NotImplementedError, OSError):
        pass
