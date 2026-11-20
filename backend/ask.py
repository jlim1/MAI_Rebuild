"""Local-only Ask Mai API. Discovery reads configuration but never contacts vendors."""

import json
import os
import re
from ipaddress import ip_address
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from starlette.concurrency import run_in_threadpool

from .ask_vendors import VendorFailure, complete

DEFAULT_MODELS = {"openai": "gpt-4o-mini", "anthropic": "claude-haiku-4-5"}
LOCAL_HOST = re.compile(r"(?:localhost|127\.0\.0\.1|\[::1\])(?::([0-9]{1,5}))?")
MAX_BODY = 16 * 1024


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    provider: Literal["openai", "anthropic"]
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]
    order_id: str | None = Field(default=None, min_length=1, max_length=80)


def require_local(request):
    denied = HTTPException(403, "Ask Mai requires a same-origin loopback request.")
    try:
        if not request.client or not ip_address(request.client.host).is_loopback:
            raise denied
    except ValueError:
        raise denied from None
    headers = request.headers
    hosts = headers.getlist("host")
    host = hosts[0].lower() if len(hosts) == 1 else ""
    match = LOCAL_HOST.fullmatch(host)
    if not match or (match[1] and not 1 <= int(match[1]) <= 65535):
        raise denied
    if any(h == "forwarded" or h.startswith("x-forwarded-") for h in headers):
        raise denied
    origins = headers.getlist("origin")
    if origins and origins != [f"{request.scope['scheme']}://{host}"]:
        raise denied
    sites = headers.getlist("sec-fetch-site")
    if sites and sites != ["same-origin"] and not (request.method == "GET" and sites == ["none"]):
        raise denied


async def read_question(request):
    types = request.headers.getlist("content-type")
    if len(types) != 1 or types[0].partition(";")[0].strip().lower() != "application/json":
        raise HTTPException(415, "Use application/json.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY:
            raise HTTPException(413, "Ask Mai request is too large.")
        body.extend(chunk)
    try:
        return Question.model_validate_json(body)
    except ValidationError:
        raise HTTPException(422, "Invalid provider, question, or order ID.") from None


def answer(store, env, args):
    provider = args.provider
    prefix = provider.upper()
    key = env.get(prefix + "_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "Selected provider is not configured.")
    model = env.get(prefix + "_MODEL", "").strip() or DEFAULT_MODELS[provider]
    snapshot = store.ask_snapshot(args.order_id)
    context = json.dumps({**snapshot, "question": args.question}, ensure_ascii=False, separators=(",", ":"))
    if len(context.encode("utf-8")) > 8192:
        raise HTTPException(422, "Demo context is too large.")
    try:
        return {"answer": complete(provider, key, model, context), "provider": provider}
    except VendorFailure:
        raise HTTPException(502, "Selected provider could not complete the request.") from None


def ask_router(store, env=None):
    env = os.environ if env is None else env
    router = APIRouter(prefix="/api/ask")

    @router.get("/providers")
    def providers(request: Request, response: Response):
        require_local(request)
        response.headers["Cache-Control"] = "no-store"
        return {p: bool(env.get(p.upper() + "_API_KEY", "").strip()) for p in ("openai", "anthropic")}

    @router.post("")
    async def ask(request: Request, response: Response):
        require_local(request)
        args = await read_question(request)
        response.headers["Cache-Control"] = "no-store"
        return await run_in_threadpool(answer, store, env, args)

    return router
