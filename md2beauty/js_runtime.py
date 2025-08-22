from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any, Mapping


class JSExecutionError(RuntimeError):
    pass


class JSBackend:
    def is_available(self) -> bool:
        raise NotImplementedError

    def run(self, script_path: str, payload: Mapping[str, Any], timeout: int = 60) -> dict:
        raise NotImplementedError


class NodeBackend(JSBackend):
    def __init__(self, node_cmd: str | None = None) -> None:
        self.node_cmd = node_cmd or shutil.which("node") or shutil.which("nodejs")

    def is_available(self) -> bool:
        return bool(self.node_cmd)

    def run(self, script_path: str, payload: Mapping[str, Any], timeout: int = 60) -> dict:
        if not self.is_available():
            raise JSExecutionError("Node.js runtime not found in PATH")
        try:
            proc = subprocess.run(
                [self.node_cmd, script_path],  # type: ignore[list-item]
                input=json.dumps(payload).encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except Exception as e:
            raise JSExecutionError(str(e)) from e
        if proc.returncode != 0:
            raise JSExecutionError(proc.stderr.decode("utf-8") or "JS renderer failed")
        out = proc.stdout.decode("utf-8") or "{}"
        try:
            return json.loads(out)
        except Exception as e:
            raise JSExecutionError(f"Invalid JSON from JS renderer: {out[:200]}") from e
