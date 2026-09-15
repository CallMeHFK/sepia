#!/usr/bin/env python3
"""Sync upstream sepia skills into the QwenPaw plugin bundle (byte parity).

Copies the six skill directories (canonical router + five operation
shells) from the upstream repo's ``skills/`` into
``.qwenpaw-plugin/skills/``, then verifies byte parity (relative paths +
sha256). Idempotent: re-running yields identical output. Exits non-zero
if the upstream tree is missing or a verification mismatch is found, so
CI (``.github/workflows/qwenpaw-sync.yml``) blocks on drift between the
QwenPaw bundle and the upstream source of truth.

Standard library only, by design — matching sepia's own tooling
(``scripts/check_versions.py``).

    python3 .qwenpaw-plugin/sync_skills.py           # sync, then verify
    python3 .qwenpaw-plugin/sync_skills.py --check   # verify only, no writes
    python3 .qwenpaw-plugin/sync_skills.py --upstream /path/to/sepia/skills
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

SKILL_DIRS = (
    "sepia",
    "sepia-write",
    "sepia-review",
    "sepia-refactor",
    "sepia-recreate",
    "sepia-hemingway",
)

PLUGIN_DIR = Path(__file__).resolve().parent


def tree_files(root: Path) -> dict[str, str]:
    """Map relative POSIX path -> sha256 for every file under ``root``."""
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Sync upstream sepia skills into the QwenPaw bundle."
    )
    ap.add_argument(
        "--upstream",
        type=Path,
        default=PLUGIN_DIR.parent / "skills",
        help="upstream skills/ directory (default: <repo>/skills)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=PLUGIN_DIR / "skills",
        help="plugin bundle skills/ directory (default: .qwenpaw-plugin/skills)",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="verify byte parity only; write nothing",
    )
    args = ap.parse_args()

    upstream, out = args.upstream, args.out

    missing = [
        d for d in SKILL_DIRS if not (upstream / d / "SKILL.md").is_file()
    ]
    if missing:
        print(
            "ERROR: upstream skills missing SKILL.md for: "
            f"{', '.join(missing)} (looked under {upstream})",
            file=sys.stderr,
        )
        return 1

    if not args.check:
        for d in SKILL_DIRS:
            dst = out / d
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(upstream / d, dst)
            print(f"synced {d}: {len(tree_files(upstream / d))} files")

    problems: list[str] = []
    for d in SKILL_DIRS:
        src_tree = tree_files(upstream / d)
        dst_tree = tree_files(out / d) if (out / d).is_dir() else {}
        for rel, digest in src_tree.items():
            if dst_tree.get(rel) != digest:
                problems.append(f"{d}/{rel}: missing or differs")
        for rel in dst_tree:
            if rel not in src_tree:
                problems.append(f"{d}/{rel}: extra file not in upstream")
    if problems:
        print("ERROR: byte-parity check failed:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    total = sum(len(tree_files(upstream / d)) for d in SKILL_DIRS)
    print(
        f"byte parity OK: {total} files across {len(SKILL_DIRS)} skills "
        f"({upstream} -> {out})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
