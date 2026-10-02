#!/usr/bin/env python3
"""Build a reproducible-source ZIP without credentials, data or dependencies."""

import argparse
import hashlib
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".cache",
    ".npm",
    ".next",
    "coverage",
    "htmlcov",
    "data",
    "uploads",
    "dist",
    "build",
    "target",
    "out",
    ".arena",
}
TEXT_TYPES = {
    ".py",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".txt",
    ".yml",
    ".yaml",
    ".html",
    ".toml",
    ".css",
    ".xml",
    ".sh",
}
SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{32,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def release_files() -> list[Path]:
    files = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if (
            any(part in EXCLUDED for part in relative.parts)
            or path.is_symlink()
            or not path.is_file()
        ):
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue
        if path.name in {".coverage", "preview-session.json"} or path.suffix in {
            ".db",
            ".sqlite",
            ".sqlite3",
            ".pyc",
            ".zip",
        }:
            continue
        if "session" in path.name.casefold() and path.suffix == ".json":
            continue
        if path.suffix in TEXT_TYPES:
            content = path.read_text(encoding="utf-8")
            if any(pattern.search(content) for pattern in SECRET_PATTERNS):
                raise SystemExit(f"Potential credential found in {relative}; packaging aborted")
        files.append(path)
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT.parent / "Grounded-AI-Meeting-Notes-Summariser-Action-Tracker.zip",
    )
    args = parser.parse_args()
    destination = args.output.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = release_files()
    required = {
        "README.md",
        "requirements.txt",
        "requirements-dev.txt",
        ".env.example",
        "Dockerfile",
        "docker-compose.yml",
        "scripts/run.py",
        "frontend/package-lock.json",
        "frontend/web/index.html",
        "docs/VERIFICATION.md",
    }
    names = {p.relative_to(ROOT).as_posix() for p in files}
    if not required <= names:
        raise SystemExit("Missing required release files: " + ", ".join(sorted(required - names)))
    prefix = ROOT.name + "/"
    manifest = []
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for file in files:
            relative = file.relative_to(ROOT).as_posix()
            archive.write(file, prefix + relative)
            manifest.append(f"{hashlib.sha256(file.read_bytes()).hexdigest()}  {relative}")
        archive.writestr(prefix + "SHA256SUMS.txt", "\n".join(manifest) + "\n")
    with ZipFile(destination) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise SystemExit(f"Archive integrity failure: {corrupt}")
        for name in archive.namelist():
            parts = Path(name).parts
            assert not any(part in EXCLUDED for part in parts)
            assert Path(name).name != ".env"
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(".zip.sha256").write_text(digest + "  " + destination.name + "\n")
    print(
        f"Release: {destination.name}\nFiles: {len(files) + 1}\nSize: {destination.stat().st_size / 1024 / 1024:.2f} MiB\nSHA-256: {digest}\nPrivate/runtime/dependency files excluded; integrity and secret scan passed."
    )


if __name__ == "__main__":
    main()
