import json
import os
import re
import socket
import sys
import threading

import uvicorn

from easyai.api import create_app
from easyai.services.local_workspace import LocalWorkspace
from pathlib import Path


def main() -> None:
    raw = sys.stdin.buffer.readline(8193)
    workspace: LocalWorkspace | None = None
    try:
        handshake = json.loads(raw)
        token = handshake["token"]
        if set(handshake) not in ({"token"}, {"token", "storageRoot"}) or not isinstance(
            token, str
        ):
            raise ValueError("Invalid startup handshake")
        if re.fullmatch(r"[0-9a-f]{64}", token) is None:
            raise ValueError("Invalid startup handshake")
        if "storageRoot" in handshake:
            storage = handshake["storageRoot"]
            if not isinstance(storage, str) or not storage or not Path(storage).is_absolute():
                raise ValueError("Invalid startup handshake")
    except (ValueError, KeyError, TypeError):
        print("Invalid startup handshake", file=sys.stderr)
        raise SystemExit(2) from None
    if "storageRoot" in handshake:
        workspace = LocalWorkspace(Path(handshake["storageRoot"]))
    app = create_app(token, workspace=workspace)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]

    class ReadyServer(uvicorn.Server):
        async def startup(self, sockets: list[socket.socket] | None = None) -> None:
            await super().startup(sockets)
            if self.started:
                print(
                    json.dumps({"port": port, "protocolVersion": 1, "pid": os.getpid()}), flush=True
                )

    server = ReadyServer(uvicorn.Config(app, log_level="warning", access_log=False, workers=1))

    def parent_watch() -> None:
        # Main closes its anonymous pipe on exit/crash; never leave an orphan sidecar.
        sys.stdin.buffer.read()
        server.should_exit = True

    threading.Thread(target=parent_watch, daemon=True).start()
    try:
        server.run(sockets=[listener])
    finally:
        try:
            if workspace is not None:
                workspace.close()
        finally:
            listener.close()


if __name__ == "__main__":
    main()
