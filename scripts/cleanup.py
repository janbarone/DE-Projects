"""Conservative cleanup for the DOTA project.

Default is a dry run. It removes only regenerable caches, old pg_dump files, and
old duplicate project copies that are verified to be subsets of the live data.

Usage:
    python scripts/cleanup.py                 # dry run
    python scripts/cleanup.py --interactive   # show plan, ask for YES
    python scripts/cleanup.py --apply         # apply without prompting
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT.parent
DUPLICATES = [
    PROJECTS / "DOTA Pipeline 08-21-2026",
    PROJECTS / "DOTA Pipelinie - backup 08-21-2026",
    PROJECTS / "DOTA Pipeline - backup 08-16-2026",
    PROJECTS / "DOTA Pipeline - backup 08-02-2026",
]


def dir_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            pass
    return total


def human(size: int) -> str:
    return f"{size / (1024 ** 3):.2f} GB"


def cache_targets() -> list[Path]:
    targets = []
    for name in (".pytest_cache", ".ruff_cache", "transform/target",
                 "transform/logs", "logs/dbt.log"):
        path = ROOT / name
        if path.exists():
            targets.append(path)
    for path in ROOT.rglob("__pycache__"):
        if ".venv" in path.parts or ".git" in path.parts:
            continue
        if path.exists():
            targets.append(path)
    return targets


def old_backups() -> list[Path]:
    backups = sorted((ROOT / "backups").glob("*.dump"), key=lambda p: p.stat().st_mtime, reverse=True)
    # Keep the newest dump and one older bronze snapshot if present.
    keep = set(backups[:1])
    for path in backups:
        if path.name.startswith("bronze_") and path not in keep:
            keep.add(path)
            break
    return [p for p in backups if p not in keep]


def duplicate_safe(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    if path.resolve() == ROOT.resolve():
        return False, "same as live project"
    dup_matches = path / "data" / "proMatches"
    live_matches = ROOT / "data" / "proMatches"
    if not dup_matches.exists():
        return True, "no match data"
    if not live_matches.exists():
        return False, "live data directory missing"
    live_ids = {p.stem for p in live_matches.glob("*.json")}
    dup_ids = {p.stem for p in dup_matches.glob("*.json")}
    unique = dup_ids - live_ids
    if unique:
        return False, f"{len(unique)} match files not in live data"
    return True, f"all {len(dup_ids)} match files are already live"


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe cleanup for the DOTA project.")
    parser.add_argument("--apply", action="store_true", help="delete without prompting")
    parser.add_argument("--interactive", action="store_true", help="show plan and ask for YES")
    args = parser.parse_args()

    actions: list[tuple[Path, int, str]] = []
    for path in cache_targets():
        actions.append((path, dir_size(path), "cache"))
    for path in old_backups():
        actions.append((path, dir_size(path), "old backup"))

    duplicates = []
    for path in DUPLICATES:
        safe, reason = duplicate_safe(path)
        if safe:
            duplicates.append(path)
            actions.append((path, dir_size(path), f"duplicate: {reason}"))
        elif path.exists():
            print(f"SKIP duplicate {path} ({reason})")

    if not actions:
        print("Nothing to clean.")
        return

    total = 0
    print("Planned cleanup:")
    for path, size, label in actions:
        total += size
        print(f"  {human(size):>9}  {label:28} {path}")
    print(f"\nTotal reclaimable: {human(total)}")

    if not args.apply:
        if not args.interactive:
            print("\nDry run only. Re-run with --interactive or --apply.")
            return
        try:
            answer = input("\nDelete everything listed above? Type YES: ").strip()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer != "YES":
            print("Cancelled.")
            return

    for path, _, _ in actions:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            try:
                path.unlink()
            except OSError as exc:
                print(f"could not remove {path}: {exc}")
    print(f"\nCleanup complete. Reclaimed approximately {human(total)}.")


if __name__ == "__main__":
    main()
