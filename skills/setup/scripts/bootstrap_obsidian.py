#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


CONFIG_ENV_VAR = "CONCIERGE_CONFIG"
DEFAULT_CONFIG_PATH = Path("~/.concierge.json").expanduser()
TEMPLATE_RELATIVE_PATH = Path("references/vault-root-readme.md.tmpl")
SENTINEL = "<!-- concierge-managed:"


@dataclass
class CloneTarget:
    key: str
    folder_name: str
    url: str
    relative_path: Path

    @property
    def label(self) -> str:
        return str(self.relative_path)


@dataclass
class Recorder:
    cloned: list[str] = field(default_factory=list)
    verified: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def default_vault() -> Path:
    raw = os.environ.get("MAIN_OBSIDIAN_ROOT") or os.environ.get("OBSIDIAN_VAULT") or "~/notes/work"
    return Path(raw).expanduser().resolve()


def load_config() -> dict:
    raw = os.environ.get(CONFIG_ENV_VAR)
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"ERROR invalid JSON in ${CONFIG_ENV_VAR}: {exc}", file=sys.stderr)
            sys.exit(2)
    if DEFAULT_CONFIG_PATH.exists():
        try:
            return json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"ERROR invalid JSON in {DEFAULT_CONFIG_PATH}: {exc}", file=sys.stderr)
            sys.exit(2)
    print(
        f"ERROR no config found. Set ${CONFIG_ENV_VAR} or create {DEFAULT_CONFIG_PATH}.",
        file=sys.stderr,
    )
    sys.exit(2)


def capitalize_key(key: str) -> str:
    if not key:
        return key
    if key[0].isupper():
        return key
    return key[0].upper() + key[1:]


def build_targets(config: dict) -> list[CloneTarget]:
    user_url = config.get("user")
    if not user_url or not isinstance(user_url, str):
        print("ERROR config: 'user' is required and must be a git URL string", file=sys.stderr)
        sys.exit(2)

    targets: list[CloneTarget] = []

    shared = config.get("shared") or {}
    if not isinstance(shared, dict):
        print("ERROR config: 'shared' must be an object mapping name to URL", file=sys.stderr)
        sys.exit(2)
    for raw_key, url in shared.items():
        if not isinstance(url, str) or not url:
            print(f"ERROR config: shared.{raw_key} must be a git URL string", file=sys.stderr)
            sys.exit(2)
        folder = capitalize_key(str(raw_key))
        targets.append(
            CloneTarget(
                key=str(raw_key),
                folder_name=folder,
                url=url,
                relative_path=Path("Shared") / folder,
            )
        )

    targets.append(
        CloneTarget(
            key="user",
            folder_name="User",
            url=user_url,
            relative_path=Path("User"),
        )
    )

    return targets


def remote_origin(repo_path: Path) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def remotes_match(a: str, b: str) -> bool:
    return normalize_remote(a) == normalize_remote(b)


def normalize_remote(url: str) -> str:
    value = url.strip()
    if value.endswith(".git"):
        value = value[:-4]
    return value.lower()


def ensure_target(vault: Path, target: CloneTarget, recorder: Recorder) -> None:
    dest = vault / target.relative_path
    if dest.exists():
        if not (dest / ".git").exists():
            recorder.errors.append(
                f"{target.label} exists but is not a git repository — resolve manually"
            )
            return
        actual = remote_origin(dest)
        if actual is None:
            recorder.errors.append(
                f"{target.label} exists but has no 'origin' remote — resolve manually"
            )
            return
        if not remotes_match(actual, target.url):
            recorder.errors.append(
                f"{target.label} origin is {actual} but config expects {target.url} — resolve manually"
            )
            return
        recorder.verified.append(f"{target.label} ({target.url})")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"CLONE {target.label} <- {target.url}")
    proc = subprocess.run(
        ["git", "clone", target.url, str(dest)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if proc.returncode != 0:
        recorder.errors.append(
            f"{target.label} clone failed: {proc.stdout.strip() or 'unknown error'}"
        )
        return
    recorder.cloned.append(f"{target.label} ({target.url})")


def render_tree(targets: list[CloneTarget]) -> str:
    shared = [t for t in targets if t.key != "user"]
    lines: list[str] = []
    if shared:
        lines.append("├── Shared/")
        for idx, target in enumerate(shared):
            connector = "└──" if idx == len(shared) - 1 else "├──"
            lines.append(f"│   {connector} {target.folder_name}/ -> {target.url}")
    lines.append(f"└── User/ -> {next(t for t in targets if t.key == 'user').url}")
    return "\n".join(lines)


def render_shared_sections(targets: list[CloneTarget]) -> str:
    shared = [t for t in targets if t.key != "user"]
    if not shared:
        return ""
    chunks: list[str] = []
    for target in shared:
        chunks.append(
            f"### [Shared/{target.folder_name}](Shared/{target.folder_name}/README.md)\n\n"
            f"Shared knowledge vault.\n\n"
            f"- **Source:** {target.url}\n"
            f"- **Commit policy:** follow the repository's own contribution rules.\n"
            f"- **Content:** see `Shared/{target.folder_name}/README.md` for the vault's own description.\n\n"
        )
    return "".join(chunks)


def template_path() -> Path:
    return Path(__file__).resolve().parent.parent / TEMPLATE_RELATIVE_PATH


def render_readme(vault: Path, targets: list[CloneTarget]) -> str:
    readme = vault / "README.md"
    if readme.exists():
        existing = readme.read_text(encoding="utf-8")
        if SENTINEL not in existing:
            return f"SKIPPED_README {readme} (user-owned; no concierge sentinel)"
    tmpl_file = template_path()
    if not tmpl_file.exists():
        raise FileNotFoundError(f"vault README template missing: {tmpl_file}")
    body = tmpl_file.read_text(encoding="utf-8")
    body = body.replace("{{STRUCTURE_TREE}}", render_tree(targets))
    body = body.replace("{{SHARED_SECTIONS}}", render_shared_sections(targets))
    readme.write_text(body, encoding="utf-8")
    return f"WROTE {readme}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a composed Obsidian vault from a JSON config.")
    parser.add_argument("vault", nargs="?", help="Vault root path. Defaults to MAIN_OBSIDIAN_ROOT or OBSIDIAN_VAULT.")
    parser.add_argument("--apply", action="store_true", help="Apply changes (clone missing repos). Without this flag, only prints the plan.")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve() if args.vault else default_vault()
    config = load_config()
    targets = build_targets(config)

    print(f"vault={vault}")
    print(f"targets={len(targets)}")
    for target in targets:
        print(f"PLAN {target.label} <- {target.url}")

    if not args.apply:
        return 0

    vault.mkdir(parents=True, exist_ok=True)

    recorder = Recorder()
    for target in targets:
        ensure_target(vault, target, recorder)

    if recorder.errors:
        for msg in recorder.errors:
            print(f"ERROR {msg}", file=sys.stderr)
        return 1

    readme_status = render_readme(vault, targets)

    for item in recorder.cloned:
        print(f"CLONED {item}")
    for item in recorder.verified:
        print(f"VERIFIED {item}")
    print(readme_status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
