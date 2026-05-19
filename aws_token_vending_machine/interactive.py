"""Interactive remote-host / remote-folder picker for the creds command."""


import pathlib
import posixpath
import stat

import paramiko
import questionary


SSH_CONFIG_PATH = pathlib.Path.home() / ".ssh" / "config"


def load_ssh_hosts() -> list[str]:
    """Return host aliases declared in ~/.ssh/config (skip wildcard patterns)."""
    if not SSH_CONFIG_PATH.exists():
        return []
    hosts: list[str] = []
    for raw in SSH_CONFIG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.lower().startswith("host "):
            continue
        for name in line.split()[1:]:
            if any(ch in name for ch in "*?!"):
                continue
            if name not in hosts:
                hosts.append(name)
    return hosts


def _abort_on_cancel(value):
    if value is None:
        raise SystemExit("Cancelled.")
    return value


def pick_host() -> str:
    hosts = load_ssh_hosts()
    custom_label = "[type a custom host...]"
    if hosts:
        choice = _abort_on_cancel(
            questionary.select(
                "SSH host:",
                choices=[*hosts, questionary.Separator(), custom_label],
            ).ask()
        )
        if choice != custom_label:
            return choice
    typed = _abort_on_cancel(questionary.text("SSH host (user@host or alias):").ask()).strip()
    if not typed:
        raise SystemExit("Remote host is required")
    return typed


def _lookup_ssh_config(host: str) -> dict:
    if not SSH_CONFIG_PATH.exists():
        return {}
    cfg = paramiko.SSHConfig()
    with SSH_CONFIG_PATH.open(encoding="utf-8", errors="ignore") as handle:
        cfg.parse(handle)
    return cfg.lookup(host)


def open_ssh(host: str) -> paramiko.SSHClient:
    cfg = _lookup_ssh_config(host)
    client = paramiko.SSHClient()
    try:
        client.load_system_host_keys()
    except OSError:
        pass
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    target_host = cfg.get("hostname", host)
    if "@" in target_host and "user" not in cfg:
        user, target_host = target_host.split("@", 1)
        cfg = {**cfg, "user": user, "hostname": target_host}

    kwargs: dict = {"hostname": target_host, "port": int(cfg.get("port", 22))}
    if "user" in cfg:
        kwargs["username"] = cfg["user"]
    if "identityfile" in cfg:
        kwargs["key_filename"] = cfg["identityfile"]

    client.connect(**kwargs)
    return client


def pick_remote_folder(ssh: paramiko.SSHClient, host: str) -> str:
    sftp = ssh.open_sftp()
    try:
        current = sftp.normalize(".")
        show_hidden = False
        while True:
            entries = sftp.listdir_attr(current)
            all_dirs = sorted(e.filename for e in entries if stat.S_ISDIR(e.st_mode))
            visible = [d for d in all_dirs if not d.startswith(".")]
            hidden = [d for d in all_dirs if d.startswith(".")]

            shown = all_dirs if show_hidden else visible
            use_here = f"[write .env here: {current}/.env]"
            choices: list = [use_here, "../", *[f"{d}/" for d in shown]]

            reveal_label = None
            if hidden and not show_hidden:
                noun = "directory" if len(hidden) == 1 else "directories"
                reveal_label = f"[show {len(hidden)} hidden {noun}]"
                choices.append(reveal_label)

            choice = _abort_on_cancel(
                questionary.select(f"{host}:{current}", choices=choices).ask()
            )

            if reveal_label is not None and choice == reveal_label:
                show_hidden = True
                continue
            if choice == use_here:
                return current
            if choice == "../":
                current = posixpath.dirname(current.rstrip("/")) or "/"
                show_hidden = False
            else:
                current = posixpath.join(current, choice.rstrip("/"))
                show_hidden = False
    finally:
        sftp.close()


def prompt_remote_target() -> tuple[paramiko.SSHClient, str, str]:
    """Pick host + folder. Returns the open SSH client, host alias, and remote path."""
    host = pick_host()
    print(f"Connecting to {host}...")
    ssh = open_ssh(host)
    try:
        folder = pick_remote_folder(ssh, host)
    except Exception:
        ssh.close()
        raise
    return ssh, host, posixpath.join(folder, ".env")
