"""Safe first-run configuration; never overwrites existing credentials."""

from pathlib import Path
import os
import secrets

ROOT = Path(__file__).resolve().parents[1]


def configure() -> Path:
    destination = ROOT / ".env"
    if not destination.exists():
        content = (ROOT / ".env.example").read_text(encoding="utf-8")
    else:
        content = destination.read_text(encoding="utf-8")
    lines = []
    changed = not destination.exists()
    for line in content.splitlines():
        for key in ("JWT_SECRET_KEY", "POSTGRES_PASSWORD"):
            if line.startswith(key + "=") and not line.partition("=")[2].strip():
                line = key + "=" + secrets.token_urlsafe(48)
                changed = True
        lines.append(line)
    if changed:
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if os.name != "nt":
            destination.chmod(0o600)
        print("Created/updated .env with randomly generated secrets. No secrets are printed.")
    return destination


if __name__ == "__main__":
    configure()
