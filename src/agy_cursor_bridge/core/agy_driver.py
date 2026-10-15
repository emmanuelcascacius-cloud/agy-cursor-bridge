import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
from agy_cursor_bridge.config import settings
from agy_cursor_bridge.core.auth import AuthManager

logger = logging.getLogger("agy_driver")

class AgyDriver:
    @staticmethod
    def build_command(
        prompt: str,
        model: Optional[str] = None,
        conversation_id: Optional[str] = None,
        mode: Optional[str] = None,
        effort: Optional[str] = None,
        auto_approve: bool = True,
    ) -> List[str]:
        agy_bin = AuthManager.find_agy_binary()
        cmd = [agy_bin]

        # Conversation continuation
        if conversation_id:
            cmd.extend(["--conversation", conversation_id])

        # Model selection
        if model:
            cmd.extend(["--model", model])

        # Mode (auto, plan, accept-edits)
        chosen_mode = mode or settings.default_mode
        if chosen_mode and chosen_mode != "auto":
            cmd.extend(["--mode", chosen_mode])

        # Effort (reasoning)
        chosen_effort = effort or settings.default_effort
        if chosen_effort:
            cmd.extend(["--effort", chosen_effort])

        # Auto approve permissions for seamless agent execution
        if auto_approve and settings.auto_approve_permissions:
            cmd.append("--dangerously-skip-permissions")

        # Headless streaming format
        cmd.extend(["--output-format", "stream-json"])

        # Prompt
        cmd.extend(["-p", prompt])

        return cmd

    @classmethod
    async def stream_turn(
        cls,
        prompt: str,
        model: Optional[str] = None,
        conversation_id: Optional[str] = None,
        mode: Optional[str] = None,
        effort: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes agy CLI for a single turn and yields parsed NDJSON events as they arrive.
        """
        cmd = cls.build_command(
            prompt=prompt,
            model=model,
            conversation_id=conversation_id,
            mode=mode,
            effort=effort,
        )

        logger.debug(f"Spawning agy command: {' '.join(cmd[:6])}...")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        try:
            assert proc.stdout is not None
            while True:
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break

                line = line_bytes.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                    yield event
                except json.JSONDecodeError:
                    logger.warning(f"Non-JSON line from agy: {line}")
                    yield {"event": "raw_text", "text": line}

            await proc.wait()

            if proc.returncode != 0:
                stderr_bytes = await proc.stderr.read() if proc.stderr else b""
                err_text = stderr_bytes.decode("utf-8", errors="replace").strip()
                logger.error(f"agy process exited with code {proc.returncode}: {err_text}")
                yield {
                    "event": "error",
                    "code": proc.returncode,
                    "message": err_text or f"agy exited with code {proc.returncode}"
                }

        except asyncio.CancelledError:
            logger.info("Client disconnected or cancelled stream. Terminating agy process...")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in stream_turn: {e}")
            yield {"event": "error", "message": str(e)}
        finally:
            if proc and proc.returncode is None:
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=1.5)
                except Exception:
                    try:
                        proc.kill()
                        await asyncio.wait_for(proc.wait(), timeout=1.0)
                    except Exception:
                        pass

    @classmethod
    async def run_turn(
        cls,
        prompt: str,
        model: Optional[str] = None,
        conversation_id: Optional[str] = None,
        mode: Optional[str] = None,
        effort: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Non-streaming execution of a single turn. Collects all output and returns final text.
        """
        full_text_parts: List[str] = []
        captured_conv_id: Optional[str] = conversation_id
        final_usage: Dict[str, int] = {}
        error_msg: Optional[str] = None

        async for event in cls.stream_turn(
            prompt=prompt,
            model=model,
            conversation_id=conversation_id,
            mode=mode,
            effort=effort,
            cwd=cwd,
        ):
            event_type = event.get("event")
            if event_type == "init":
                captured_conv_id = event.get("conversation_id")
            elif event_type == "step_update":
                step_update = event.get("step_update", {})
                delta = step_update.get("text_delta")
                if delta:
                    full_text_parts.append(delta)
                if "usage" in step_update:
                    final_usage = step_update["usage"]
            elif event_type == "result":
                res = event.get("result", {})
                if "response" in res and not full_text_parts:
                    full_text_parts.append(res["response"])
                if "usage" in res:
                    final_usage = res["usage"]
            elif event_type == "error":
                error_msg = event.get("message")

        return {
            "conversation_id": captured_conv_id,
            "response": "".join(full_text_parts),
            "usage": final_usage,
            "error": error_msg,
        }
