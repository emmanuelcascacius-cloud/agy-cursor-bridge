import logging
import uuid
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from agy_cursor_bridge.config import settings
from agy_cursor_bridge.core.auth import AuthManager
from agy_cursor_bridge.core.normalizer import RequestNormalizer
from agy_cursor_bridge.core.session_store import session_store
from agy_cursor_bridge.core.agy_driver import AgyDriver
from agy_cursor_bridge.core.stream_parser import StreamParser
from agy_cursor_bridge.models.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    CompletionChoice,
    ChoiceMessage,
    UsageInfo,
)

logger = logging.getLogger("completions")
router = APIRouter(tags=["completions"])
security = HTTPBearer(auto_error=False)

def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if credentials and credentials.credentials:
        if not AuthManager.validate_api_key(credentials.credentials):
            raise HTTPException(status_code=401, detail="Invalid API Key")
    return True


@router.post("/v1/chat/completions")
@router.post("/cursor/chat/completions")
@router.post("/chat/completions")
async def create_chat_completion(
    raw_req: ChatCompletionRequest,
    http_request: Request,
    authorized: bool = Depends(verify_token),
):
    # Normalize input (handles standard messages & Cursor input Responses format)
    norm = RequestNormalizer.normalize(raw_req)

    # Check for existing conversation ID
    conversation_id = None
    if norm.conversation_fingerprint and not norm.is_first_turn:
        conversation_id = session_store.get_conversation_id(norm.conversation_fingerprint)
        if conversation_id:
            logger.info(f"Continuing Antigravity conversation {conversation_id} for fingerprint {norm.conversation_fingerprint}")

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_ts = int(time.time())

    # Mode 1: Streaming response (SSE)
    if norm.stream:
        event_gen = AgyDriver.stream_turn(
            prompt=norm.compiled_prompt,
            model=norm.model,
            conversation_id=conversation_id,
            effort=norm.reasoning_effort,
        )

        sse_stream = StreamParser.parse_agy_stream(
            event_generator=event_gen,
            model=norm.model,
            fingerprint=norm.conversation_fingerprint,
            custom_id=completion_id,
        )

        headers = {
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }

        return StreamingResponse(sse_stream, headers=headers, media_type="text/event-stream")

    # Mode 2: Non-streaming response
    res = await AgyDriver.run_turn(
        prompt=norm.compiled_prompt,
        model=norm.model,
        conversation_id=conversation_id,
        effort=norm.reasoning_effort,
    )

    if res.get("conversation_id") and norm.conversation_fingerprint:
        session_store.set_conversation_id(norm.conversation_fingerprint, res["conversation_id"])

    response_text = res.get("response", "")
    if res.get("error"):
        response_text = f"Error: {res['error']}"

    usage_dict = res.get("usage", {})
    usage = UsageInfo(
        prompt_tokens=usage_dict.get("input_tokens", 0),
        completion_tokens=usage_dict.get("output_tokens", 0),
        total_tokens=usage_dict.get("total_tokens", 0),
    )

    return ChatCompletionResponse(
        id=completion_id,
        created=created_ts,
        model=norm.model,
        choices=[
            CompletionChoice(
                index=0,
                message=ChoiceMessage(role="assistant", content=response_text),
                finish_reason="stop",
            )
        ],
        usage=usage,
    )
