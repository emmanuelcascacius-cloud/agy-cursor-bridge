import json
import pytest
from agy_cursor_bridge.core.stream_parser import StreamParser

@pytest.mark.asyncio
async def test_stream_parser_events():
    async def mock_events():
        yield {"event": "init", "conversation_id": "test-conv-123"}
        yield {"event": "step_update", "step_update": {"step_type": "agent_response", "text_delta": "Hello"}}
        yield {"event": "step_update", "step_update": {"step_type": "agent_response", "text_delta": " world"}}
        yield {"event": "result", "result": {"status": "SUCCESS", "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}}}

    chunks = []
    async for sse in StreamParser.parse_agy_stream(mock_events(), model="gemini-3.8-flash", fingerprint="fp1"):
        chunks.append(sse)

    # Verify SSE format
    assert len(chunks) >= 4
    assert chunks[0].startswith("data: ")
    assert chunks[-1] == "data: [DONE]\n\n"

    # Verify content chunks
    data_lines = [json.loads(c[6:].strip()) for c in chunks if c[6:].strip() != "[DONE]"]
    content_deltas = [d["choices"][0]["delta"].get("content") for d in data_lines if "content" in d["choices"][0]["delta"]]
    assert "Hello" in content_deltas
    assert " world" in content_deltas
