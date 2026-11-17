"""Restart DDLC Mod Manager when a source file changes."""
import os
import subprocess
import sys
import time

from ddlc_mod_manager.config import MODS_ROOT
from ddlc_mod_manager.devtools import (DEV_ENV, ENTRY, ROOT,
                                       SUPERVISED_ENV, build_staging,
                                       snapshot)

POLL_SECONDS = 0.5
DEBOUNCE_SECONDS = 0.3


def start_app():
    print("[dev] starting DDLC Mod Manager", flush=True)
    env = os.environ.copy()
    env[DEV_ENV] = "1"
    env[SUPERVISED_ENV] = "1"
    return subprocess.Popen(
        [sys.executable, str(ENTRY)], cwd=str(ROOT), env=env)


def stop_app(process):
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main():
    previous = snapshot()
    pending = False
    waiting = False
    process = start_app()
    try:
        while True:
            time.sleep(POLL_SECONDS)
            current = snapshot()
            if current != previous:
                previous = current
                time.sleep(DEBOUNCE_SECONDS)
                previous = snapshot()
                pending = True
            if pending:
                alive = process is not None and process.poll() is None
                if alive and build_staging(MODS_ROOT):
                    if not waiting:
                        print("[dev] build in progress, waiting", flush=True)
                        waiting = True
                    continue
                waiting = False
                print("[dev] change detected, restarting", flush=True)
                stop_app(process)
                process = start_app()
                pending = False
                continue
            if process is not None and process.poll() is not None:
                code = process.returncode
                process = None
                if code == 0:
                    print("[dev] app closed", flush=True)
                    return 0
                print("[dev] app stopped with code %s; save a file to restart"
                      % code, flush=True)
    except KeyboardInterrupt:
        print("\n[dev] stopping", flush=True)
        stop_app(process)
        return 130


if __name__ == "__main__":
    sys.exit(main())
