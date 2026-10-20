"""Authenticate before body parsing; bound each authenticated HTTP input."""

import asyncio
import secrets

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# A 5 MiB saved project may use six-byte JSON Unicode escapes on the wire.
# Keep room for its request envelope; this is a transport cap, not a new project limit.
BODY_LIMIT = 32 * 1024 * 1024
BODY_SECONDS = 10.0


class SessionRequestBoundary:
    def __init__(
        self,
        app: ASGIApp,
        token: str,
        *,
        body_limit: int = BODY_LIMIT,
        body_seconds: float = BODY_SECONDS,
    ):
        self.app = app
        self.authorization = f"Bearer {token}".encode("ascii")
        self.body_limit = body_limit
        self.body_seconds = body_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = scope.get("headers", [])
        authorization = [value for key, value in headers if key.lower() == b"authorization"]

        async def reject(status: int, code: str) -> None:
            response = JSONResponse(
                {"detail": "Session authorization required"}
                if status == 401
                else {"error": {"code": code}},
                status_code=status,
                headers={"Connection": "close"},
            )
            await response(scope, receive, send)

        if len(authorization) != 1 or not secrets.compare_digest(
            authorization[0], self.authorization
        ):
            await reject(401, "HTTP_SESSION_REQUIRED")
            return
        lengths = [value for key, value in headers if key.lower() == b"content-length"]
        transfer = any(key.lower() == b"transfer-encoding" for key, _ in headers)
        if (
            len(lengths) > 1
            or (lengths and transfer)
            or (lengths and (not 1 <= len(lengths[0]) <= 20 or not lengths[0].isdigit()))
        ):
            await reject(400, "HTTP_REQUEST_LENGTH_INVALID")
            return
        declared = int(lengths[0]) if lengths else None
        if declared is not None and declared > self.body_limit:
            await reject(413, "HTTP_REQUEST_BODY_TOO_LARGE")
            return
        # Pre-read even a declared empty body. The ASGI server immediately supplies
        # the initial empty http.request for GET/SSE, then later real disconnects.
        # No downstream response can start before the complete input is bounded.
        body = bytearray()
        failure: tuple[int, str] | None = None
        try:
            async with asyncio.timeout(self.body_seconds):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    if message["type"] != "http.request":
                        failure = (400, "HTTP_REQUEST_INVALID")
                        break
                    chunk = message.get("body", b"")
                    if len(chunk) > self.body_limit - len(body):
                        failure = (413, "HTTP_REQUEST_BODY_TOO_LARGE")
                        break
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            failure = (408, "HTTP_REQUEST_BODY_TIMEOUT")
        if failure:
            await reject(*failure)
            return
        if declared is not None and declared != len(body):
            await reject(400, "HTTP_REQUEST_LENGTH_INVALID")
            return
        payload = bytes(body)
        body.clear()
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": payload, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
