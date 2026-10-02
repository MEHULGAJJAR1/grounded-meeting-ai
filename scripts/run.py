#!/usr/bin/env python3
"""One-command local bootstrap: real dependencies, React build, migrations and API."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

from configure import ROOT, configure


def run(command: list[str], cwd: Path = ROOT):
    subprocess.run(command, cwd=cwd, check=True)


def main():
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Use the already provisioned project virtual environment and web build",
    )
    parser.add_argument("--port", type=int, default=None, help="Override APP_PORT")
    args = parser.parse_args()
    configure()
    directory = ROOT / ".venv"
    python = directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        print("Creating isolated Python environment…")
        venv.EnvBuilder(with_pip=True).create(directory)
    if not args.skip_install:
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        node = shutil.which("node")
        if not npm or not node:
            raise SystemExit("Install Node.js 20+ (including npm), then run this command again")
        version = subprocess.check_output([node, "--version"], text=True).strip().lstrip("v")
        if int(version.split(".")[0]) < 20:
            raise SystemExit("Node.js 20 or newer is required")
        print("Installing locked dependencies…")
        run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
        run([str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
        run([npm, "ci"], ROOT / "frontend")
        run([npm, "run", "build"], ROOT / "frontend")
    elif not (ROOT / "frontend" / "web" / "index.html").exists():
        raise SystemExit("No web build exists. Run without --skip-install first")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend")
    # Read values with python-dotenv in the provisioned environment, respecting
    # environment overrides and the same typed settings as the actual server.
    command = [
        str(python),
        "-c",
        "from app.config import get_settings; s=get_settings(); print(s.app_host); print(s.app_port)",
    ]
    host, configured_port = (
        subprocess.check_output(command, env=env, cwd=ROOT, text=True).strip().splitlines()[-2:]
    )
    port = args.port or int(configured_port)
    print(
        f"\nGrounded is starting at http://localhost:{port}\nAPI documentation: http://localhost:{port}/api/docs\nPress Ctrl+C to stop.\n"
    )
    try:
        result = subprocess.run(
            [
                str(python),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                host,
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=ROOT,
            env=env,
        )
        raise SystemExit(result.returncode)
    except KeyboardInterrupt:
        print("\nGrounded stopped.")


if __name__ == "__main__":
    main()
