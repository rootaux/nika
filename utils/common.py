from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, Union, Optional, Mapping
import subprocess
import time
import shlex
import os

@dataclass
class CommandResult:
    command: Union[str, Sequence[str]]
    returncode: int
    stdout: str
    stderr: str
    duration_sec: float
    cwd: Optional[str]

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def execute_command(
    command: Union[str, Sequence[str]],
    *,
    shell: bool = False,
    timeout: Optional[float] = None,
    cwd: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    check: bool = False,
    capture_output: bool = True,
    text: bool = True,
) -> CommandResult:
    if isinstance(command, str) and not shell:
        command_tokens = shlex.split(command)
    else:
        command_tokens = command

    popen_kwargs = {
        "shell": shell,
        "cwd": cwd,
        "timeout": timeout,
        "env": (dict(os.environ, **env) if env else None),
        "text": text,
    }
    if capture_output:
        popen_kwargs.update({"capture_output": True})

    start = time.perf_counter()
    try:
        completed = subprocess.run(command_tokens, **popen_kwargs)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Command timed out after {timeout}s: {command}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to execute command: {command}. Error: {e}") from e
    duration = time.perf_counter() - start

    stdout = completed.stdout if capture_output and completed.stdout is not None else ""
    stderr = completed.stderr if capture_output and completed.stderr is not None else ""
    result = CommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        duration_sec=duration,
        cwd=cwd,
    )

    if check and not result.ok:
        raise RuntimeError(
            f"Command failed (exit {result.returncode}): {command}\nSTDERR:\n{stderr}".rstrip()
        )

    return result


def count_lines_of_code(path: str, extensions: Sequence[str]) -> dict:
    normalized = tuple(
        ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions
    )
    total_files = 0
    total_lines = 0
    if not path or not os.path.isdir(path):
        return {"totalSourceFiles": 0, "totalLinesOfCode": 0}

    for root, _dirs, files in os.walk(path):
        for name in files:
            if not name.lower().endswith(normalized):
                continue
            total_files += 1
            file_path = os.path.join(root, name)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                    total_lines += sum(1 for _ in handle)
            except OSError:
                continue

    return {"totalSourceFiles": total_files, "totalLinesOfCode": total_lines}

