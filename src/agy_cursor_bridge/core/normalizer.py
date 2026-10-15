import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple, Union
from agy_cursor_bridge.models.schemas import ChatCompletionRequest, ChatMessage
from agy_cursor_bridge.config import settings

class NormalizedRequest:
    def __init__(
        self,
        model: str,
        compiled_prompt: str,
        system_instruction: Optional[str] = None,
        conversation_fingerprint: str = "",
        is_first_turn: bool = True,
        latest_user_message: str = "",
        reasoning_effort: Optional[str] = None,
        stream: bool = False,
    ):
        self.model = model
        self.compiled_prompt = compiled_prompt
        self.system_instruction = system_instruction
        self.conversation_fingerprint = conversation_fingerprint
        self.is_first_turn = is_first_turn
        self.latest_user_message = latest_user_message
        self.reasoning_effort = reasoning_effort
        self.stream = stream

class RequestNormalizer:
    @staticmethod
    def _extract_text(content: Any) -> str:
        """Extracts plain text from string or structured content parts."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append(item.get("text", ""))
                    elif "content" in item:
                        parts.append(RequestNormalizer._extract_text(item["content"]))
            return "\n".join(parts)
        if isinstance(content, dict):
            if content.get("type") == "text":
                return content.get("text", "")
            if "content" in content:
                return RequestNormalizer._extract_text(content["content"])
        return str(content)

    @staticmethod
    def extract_messages(req: ChatCompletionRequest) -> List[ChatMessage]:
        """Extracts standard ChatMessage list from either messages or input field."""
        result: List[ChatMessage] = []

        if req.messages:
            for m in req.messages:
                text = RequestNormalizer._extract_text(m.content)
                result.append(ChatMessage(role=m.role or "user", content=text))
            return result

        # Handle Cursor Agent / Responses API 'input' field
        if req.input:
            if isinstance(req.input, str):
                return [ChatMessage(role="user", content=req.input)]
            if isinstance(req.input, list):
                for item in req.input:
                    if isinstance(item, ChatMessage):
                        result.append(item)
                    elif isinstance(item, dict):
                        role = item.get("role", "user")
                        content = RequestNormalizer._extract_text(item.get("content") or item.get("text") or "")
                        result.append(ChatMessage(role=role, content=content))
                return result

        return [ChatMessage(role="user", content="")]

    @staticmethod
    def map_model_name(requested_model: str) -> str:
        """Maps Cursor model names/aliases to valid agy models."""
        if not requested_model:
            return settings.default_model

        clean = requested_model.strip().lower()

        # Direct known mappings
        alias_map = {
            # Default aliases
            "default": settings.default_model,
            "auto": "auto",
            "cursor-agent": settings.default_model,
            "cursor-small": "gemini-3.8-flash-lite",
            "cursor-fast": "gemini-3.8-flash",

            # Non-colliding custom prefixes (for adding to Cursor Settings -> Models)
            "agy-flash": "gemini-3.8-flash",
            "agy-gemini": "gemini-3.8-flash",
            "agy-gemini-3.8-flash": "gemini-3.8-flash",
            "agy-pro": "gemini-3.8-pro",
            "agy-gemini-3.8-pro": "gemini-3.8-pro",
            "agy-sonnet": "claude-3-7-sonnet",
            "agy-claude": "claude-3-7-sonnet",
            "agy-deepseek": "deepseek-r1",
            "agy-r1": "deepseek-r1",
            "antigravity-flash": "gemini-3.8-flash",
            "antigravity-pro": "gemini-3.8-pro",

            # Built-in Cursor dropdown models mapped directly to Antigravity
            "gpt-4o": "gemini-3.8-flash",
            "gpt-4o-mini": "gemini-3.8-flash-lite",
            "gpt-4": "gemini-3.8-pro",
            "gpt-3.5-turbo": "gemini-3.8-flash-lite",
            "claude-3-5-sonnet": "claude-3-7-sonnet",
            "claude-3-5-sonnet-20241022": "claude-3-7-sonnet",
            "o1": "gemini-3.8-pro",
            "o3-mini": "gemini-3.8-flash",

            # Raw names
            "gemini-flash": "gemini-3.8-flash",
            "gemini-pro": "gemini-3.8-pro",
            "sonnet": "claude-3-7-sonnet",
            "claude-sonnet": "claude-3-7-sonnet",
            "r1": "deepseek-r1",
            "deepseek": "deepseek-r1",
        }

        for alias, mapped in alias_map.items():
            if clean == alias or clean.endswith("/" + alias):
                return mapped

        return clean

    @staticmethod
    def normalize(req: ChatCompletionRequest) -> NormalizedRequest:
        messages = RequestNormalizer.extract_messages(req)
        model = RequestNormalizer.map_model_name(req.model)
        effort = req.reasoning_effort or settings.default_effort

        # Extract system messages
        system_texts: List[str] = []
        conversation_turns: List[Tuple[str, str]] = []

        for m in messages:
            role = (m.role or "user").lower()
            text = RequestNormalizer._extract_text(m.content).strip()
            if not text:
                continue

            if role in ("system", "developer"):
                system_texts.append(text)
            else:
                conversation_turns.append((role, text))

        combined_system = "\n\n".join(system_texts) if system_texts else None

        # Build fingerprint from initial turns to identify conversation session
        fingerprint_source = ""
        if combined_system:
            fingerprint_source += f"sys:{combined_system[:200]}"
        if conversation_turns:
            # Hash the first user turn as anchor
            first_user = next((t[1] for t in conversation_turns if t[0] == "user"), "")
            fingerprint_source += f"u1:{first_user[:200]}"

        fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()[:16] if fingerprint_source else ""

        # Determine latest user message and total turn count
        latest_user_text = ""
        for role, text in reversed(conversation_turns):
            if role == "user":
                latest_user_text = text
                break
        if not latest_user_text and conversation_turns:
            latest_user_text = conversation_turns[-1][1]

        # Is this the first turn?
        is_first_turn = (len(conversation_turns) <= 1)

        # Build the compiled prompt
        # If this is turn 1 or if we are not continuing an existing agy conversation,
        # compile system prompt + dialogue turns
        prompt_parts: List[str] = []
        if combined_system:
            prompt_parts.append(f"[System Instructions]\n{combined_system}\n")

        if is_first_turn or not fingerprint:
            prompt_parts.append(latest_user_text)
        else:
            # For stateful continuation, we pass the latest user message
            prompt_parts.append(latest_user_text)

        compiled_prompt = "\n\n".join(prompt_parts)

        return NormalizedRequest(
            model=model,
            compiled_prompt=compiled_prompt,
            system_instruction=combined_system,
            conversation_fingerprint=fingerprint,
            is_first_turn=is_first_turn,
            latest_user_message=latest_user_text,
            reasoning_effort=effort,
            stream=bool(req.stream),
        )
