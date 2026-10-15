import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agy_cursor_bridge.core.agy_driver import AgyDriver

def test_build_command_default():
    cmd = AgyDriver.build_command(prompt="Hello Antigravity")
    assert "agy" in cmd[0]
    assert "-p" in cmd
    assert "Hello Antigravity" in cmd
    assert "--output-format" in cmd
    assert "stream-json" in cmd
    assert "--dangerously-skip-permissions" in cmd

def test_build_command_custom_options():
    cmd = AgyDriver.build_command(
        prompt="Refactor code",
        model="claude-3-7-sonnet",
        conversation_id="conv-abc-123",
        mode="plan",
        effort="xhigh",
        auto_approve=False,
    )
    assert "--model" in cmd
    assert "claude-3-7-sonnet" in cmd
    assert "--conversation" in cmd
    assert "conv-abc-123" in cmd
    assert "--mode" in cmd
    assert "plan" in cmd
    assert "--effort" in cmd
    assert "xhigh" in cmd
    assert "--dangerously-skip-permissions" not in cmd

@pytest.mark.asyncio
async def test_stream_turn_mocked():
    mock_lines = [
        b'{"event": "init", "conversation_id": "test-c-1"}\n',
        b'{"event": "step_update", "step_update": {"text_delta": "Hello "}}\n',
        b'{"event": "step_update", "step_update": {"text_delta": "world!"}}\n',
        b'{"event": "result", "result": {"response": "Hello world!"}}\n',
    ]

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.wait = AsyncMock(return_value=0)

    iterator = iter(mock_lines + [b""])
    mock_proc.stdout.readline = AsyncMock(side_effect=lambda: next(iterator))
    mock_proc.stderr.read = AsyncMock(return_value=b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        events = []
        async for event in AgyDriver.stream_turn("test prompt"):
            events.append(event)

        assert len(events) == 4
        assert events[0]["event"] == "init"
        assert events[1]["step_update"]["text_delta"] == "Hello "
        assert events[2]["step_update"]["text_delta"] == "world!"
        assert events[3]["event"] == "result"

@pytest.mark.asyncio
async def test_stream_turn_cancellation_cleans_proc():
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.terminate = MagicMock()
    mock_proc.kill = MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)

    async def hanging_readline():
        await asyncio.sleep(10)
        return b""

    mock_proc.stdout.readline = AsyncMock(side_effect=hanging_readline)

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        async def cancel_caller():
            async for _ in AgyDriver.stream_turn("test prompt"):
                pass

        task = asyncio.create_task(cancel_caller())
        await asyncio.sleep(0.05)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Ensure proc.terminate was called during cancellation cleanup
        assert mock_proc.terminate.called or mock_proc.kill.called
