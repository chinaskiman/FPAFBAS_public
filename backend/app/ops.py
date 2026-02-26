from __future__ import annotations

import os
from fastapi import HTTPException, Request


def get_admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "").strip()


def require_admin(request: Request) -> bool:
    token = get_admin_token()
    if not token:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN not set")
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    provided = auth_header.split(" ", 1)[1].strip()
    if provided != token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return True
