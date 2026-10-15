import json
import time
import uuid
from typing import AsyncGenerator, Dict, Any, Optional
from agy_cursor_bridge.config import settings
from agy_cursor_bridge.core.session_store import session_store

class StreamParser:
    @staticmethod
    def format_sse(data: str) -> str:
        return f"data: {data}\n\n"

    @classmethod
    async def parse_agy_stream(
        cls,
        event_generator: AsyncGenerator[Dict[str, Any], None],
        model: str,
        fingerprint: Optional[str] = None,
        custom_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Consumes agy NDJSON events and produces standard OpenAI SSE formatted strings.
        """
        completion_id = custom_id or f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created_time = int(time.time())

        # Track usage
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        # State tracking
        role_sent = False
        captured_conv_id: Optional[str] = None
        has_content = False

        try:
            async for event in event_generator:
                event_type = event.get("event")

                # 1. Init event
                if event_type == "init":
                    captured_conv_id = event.get("conversation_id")
                    if captured_conv_id and fingerprint:
                        session_store.set_conversation_id(fingerprint, captured_conv_id)

                    if not role_sent:
                        # Send initial empty chunk with assistant role
                        init_chunk = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created_time,
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {"role": "assistant", "content": ""},
                                "finish_reason": None,
                            }]
                        }
                        yield cls.format_sse(json.dumps(init_chunk))
                        role_sent = True

                # 2. Step updates (text, tool, thinking)
                elif event_type == "step_update":
                    step = event.get("step_update", {})
                    step_type = step.get("step_type")
                    text_delta = step.get("text_delta")
                    thought_delta = step.get("thought_delta")

                    # Handle tokens usage if attached to step
                    usage = step.get("usage", {})
                    if usage:
                        prompt_tokens = usage.get("input_tokens", prompt_tokens)
                        completion_tokens = usage.get("output_tokens", completion_tokens)
                        total_tokens = usage.get("total_tokens", total_tokens)

                    # A. Thinking / Reasoning delta
                    if thought_delta:
                        delta_payload: Dict[str, Any] = {}
                        if settings.emit_reasoning_content:
                            delta_payload["reasoning_content"] = thought_delta
                        elif settings.emit_thought_tags:
                            delta_payload["content"] = f"<thought>{thought_delta}</thought>"

                        if delta_payload:
                            chunk = {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": created_time,
                                "model": model,
                                "choices": [{
                                    "index": 0,
                                    "delta": delta_payload,
                                    "finish_reason": None,
                                }]
                            }
                            yield cls.format_sse(json.dumps(chunk))

                    # B. Agent Tool Activity notification (when agy executes tools)
                    if step_type == "tool" and not text_delta:
                        tool_name = step.get("tool_name", "tool")
                        tool_state = step.get("state", "ACTIVE")
                        if tool_state == "ACTIVE":
                            msg = f"\n> 🛠️ *Antigravity running `{tool_name}`...*\n"
                            chunk = {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": created_time,
                                "model": model,
                                "choices": [{
                                    "index": 0,
                                    "delta": {"content": msg},
                                    "finish_reason": None,
                                }]
                            }
                            yield cls.format_sse(json.dumps(chunk))
                            has_content = True

                    # C. Standard text delta
                    if text_delta:
                        chunk = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created_time,
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": text_delta},
                                "finish_reason": None,
                            }]
                        }
                        yield cls.format_sse(json.dumps(chunk))
                        has_content = True

                # 3. Result event
                elif event_type == "result":
                    res = event.get("result", {})
                    res_usage = res.get("usage", {})
                    if res_usage:
                        prompt_tokens = res_usage.get("input_tokens", prompt_tokens)
                        completion_tokens = res_usage.get("output_tokens", completion_tokens)
                        total_tokens = res_usage.get("total_tokens", total_tokens)

                    # If no content was streamed, send the result response
                    if not has_content and res.get("response"):
                        chunk = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created_time,
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": res["response"]},
                                "finish_reason": None,
                            }]
                        }
                        yield cls.format_sse(json.dumps(chunk))
                        has_content = True

                # 4. Error event
                elif event_type == "error":
                    err_msg = event.get("message", "Unknown error from agy")
                    chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created_time,
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": f"\n\n[Antigravity Error: {err_msg}]\n"},
                            "finish_reason": None,
                        }]
                    }
                    yield cls.format_sse(json.dumps(chunk))
                    has_content = True

            # End of stream: Final stop chunk
            final_chunk: Dict[str, Any] = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created_time,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }]
            }
            if total_tokens > 0:
                final_chunk["usage"] = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                }
            yield cls.format_sse(json.dumps(final_chunk))

            # Terminal SSE marker
            yield cls.format_sse("[DONE]")

        except Exception as e:
            err_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created_time,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": f"\n\n[Bridge Stream Error: {str(e)}]\n"},
                    "finish_reason": "stop",
                }]
            }
            yield cls.format_sse(json.dumps(err_chunk))
            yield cls.format_sse("[DONE]")
