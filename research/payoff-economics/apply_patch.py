#!/usr/bin/env python3
"""Apply this source patch to a matching checkout. Default is read-only preflight.

No network, git writes, credentials, dependency installation, or trading calls.
Every touched original must match its pinned Git blob and every anchor must be
unique. All files are preflighted before writes; per-file replacement is atomic,
with best-effort rollback on an I/O exception (not a crash-atomic transaction).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

BUNDLE = Path(__file__).resolve().parent


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise ValueError(f"Unsafe path: {relative}")
    target = root / rel
    for p in [target, *target.parents]:
        if p == root:
            break
        if p.is_symlink():
            raise ValueError(f"Symlink not allowed: {relative}")
    if root != target.resolve() and root not in target.resolve().parents:
        raise ValueError(f"Path escapes checkout: {relative}")
    return target


def prepare(root: Path, manifest: dict, overlay: Path) -> dict[Path, tuple[bytes | None, bytes]]:
    changes: dict[Path, tuple[bytes | None, bytes]] = {}
    for item in manifest["edits"]:
        target = safe_path(root, item["path"])
        if target in changes:
            raise ValueError(f"Repeated target: {item['path']}")
        original = target.read_bytes()
        if git_blob(original) != item["expected_blob"]:
            raise ValueError(f"Base blob mismatch: {item['path']}; refusing to overwrite current work")
        content = original.decode("utf-8")
        for replacement in item["replacements"]:
            old, new = replacement["old"], replacement["new"]
            if not old or content.count(old) != 1:
                raise ValueError(f"Anchor missing or non-unique: {item['path']}")
            content = content.replace(old, new, 1)
        changes[target] = (original, content.encode("utf-8"))
    for source in sorted(overlay.rglob("*")):
        if source.is_symlink():
            raise ValueError(f"Symlink in overlay: {source}")
        if not source.is_file():
            continue
        target = safe_path(root, source.relative_to(overlay).as_posix())
        if target in changes or target.exists():
            raise ValueError(f"New file would overwrite existing work: {target.relative_to(root)}")
        changes[target] = (None, source.read_bytes())
    return changes


def atomic_write(target: Path, data: bytes, mode: int = 0o644) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".payoff-patch-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(name, mode)
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def apply(changes: dict[Path, tuple[bytes | None, bytes]]) -> None:
    written: list[tuple[Path, int]] = []
    try:
        for target, (old, new) in changes.items():
            # Recheck between preflight and replace; no blind overwrites.
            if (old is None and target.exists()) or (old is not None and target.read_bytes() != old):
                raise ValueError(f"File changed after preflight: {target}")
            mode = target.stat().st_mode & 0o777 if old is not None else 0o644
            atomic_write(target, new, mode)
            written.append((target, mode))
    except Exception:
        for target, mode in reversed(written):
            old, _new = changes[target]
            if old is None:
                target.unlink(missing_ok=True)
            else:
                atomic_write(target, old, mode)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path, help="Auto-Prediction checkout")
    parser.add_argument("--apply", action="store_true", help="Write after successful preflight; default checks only")
    args = parser.parse_args()
    root = args.repo.resolve(strict=True)
    manifest = json.loads((BUNDLE / "source-edits.json").read_text())
    changes = prepare(root, manifest, BUNDLE / "overlay")
    for target, (old, new) in changes.items():
        print(f"{'ADD' if old is None else 'EDIT'} {target.relative_to(root)} ({len(new)} bytes)")
    if args.apply:
        apply(changes)
        print("APPLIED_LOCALLY. No GitHub commit, full-suite pass, or live authority is implied.")
    else:
        print("CHECK_OK. No files written; pass --apply to write these changes.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        raise SystemExit(f"REFUSED: {exc}") from exc
