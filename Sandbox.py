"""
sandbox.py - run a shell command in Docker with limits and a timeout.
"""

import os
import signal
import subprocess
import uuid

from Config import COMMAND_TIMEOUT, DOCKER_IMAGE, SANDBOX, WORKSPACE


def run_in_sandbox(command: str, timeout: int = COMMAND_TIMEOUT) -> dict:
    """Run `command` isolated. Returns {exit_code, stdout, stderr, timed_out}."""
    WORKSPACE.mkdir(exist_ok=True)
    container_name = f"agent-{uuid.uuid4().hex[:8]}"

    if SANDBOX == "docker":
        argv = [
            "docker", "run", "--rm", "--name", container_name,
            "--network", "none",                      # no internet
            "--memory", "256m", "--cpus", "1",        # resource limits
            "--pids-limit", "128",                    # stops fork bombs
            "--cap-drop", "ALL",                      # drop all Linux capabilities
            "--security-opt", "no-new-privileges",
            "--read-only", "--tmpfs", "/tmp",         # container filesystem is read-only
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-v", f"{WORKSPACE}:/workspace",          # the ONLY writable, persistent place
            "-w", "/workspace",
            DOCKER_IMAGE, "sh", "-c", command,
        ]
        popen_kwargs = {}
    else:  # local mode: NOT a sandbox. Only for quick tests without Docker.
        argv = command
        popen_kwargs = {"shell": True, "cwd": str(WORKSPACE)}
        if os.name == "posix":
            popen_kwargs["start_new_session"] = True  # so we can kill the whole process group

    try:
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", **popen_kwargs,
        )
    except FileNotFoundError:
        return {"exit_code": -1, "stdout": "", "timed_out": False,
                "stderr": "Docker is not installed or not on PATH."}

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return {"exit_code": proc.returncode, "stdout": stdout, "stderr": stderr, "timed_out": False}
    except subprocess.TimeoutExpired:
        # Killing the `docker` client is NOT enough - the container keeps running.
        if SANDBOX == "docker":
            subprocess.run(["docker", "kill", container_name], capture_output=True)
            proc.kill()
        elif os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
        stdout, stderr = proc.communicate()
        return {"exit_code": -1, "stdout": stdout, "stderr": stderr, "timed_out": True}