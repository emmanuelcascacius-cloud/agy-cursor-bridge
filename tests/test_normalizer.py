import pytest
from agy_cursor_bridge.models.schemas import ChatCompletionRequest, ChatMessage
from agy_cursor_bridge.core.normalizer import RequestNormalizer

def test_extract_messages_standard():
    req = ChatCompletionRequest(
        model="gemini-3.8-flash",
        messages=[
            ChatMessage(role="system", content="You are a helper."),
            ChatMessage(role="user", content="Hello world!"),
        ],
    )
    messages = RequestNormalizer.extract_messages(req)
    assert len(messages) == 2
    assert messages[0].role == "system"
    assert messages[0].content == "You are a helper."
    assert messages[1].role == "user"
    assert messages[1].content == "Hello world!"

def test_extract_messages_cursor_responses_input():
    # Cursor agent input shape
    req = ChatCompletionRequest(
        model="gemini-3.8-flash",
        input=[
            {"role": "user", "content": [{"type": "text", "text": "Fix this bug"}]}
        ],
    )
    messages = RequestNormalizer.extract_messages(req)
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "Fix this bug"

def test_normalize_turns_and_fingerprint():
    req = ChatCompletionRequest(
        model="cursor-fast",
        messages=[
            ChatMessage(role="system", content="System instruction"),
            ChatMessage(role="user", content="First question"),
            ChatMessage(role="assistant", content="First answer"),
            ChatMessage(role="user", content="Follow-up question"),
        ],
    )
    norm = RequestNormalizer.normalize(req)
    assert norm.model == "gemini-3.8-flash"
    assert norm.is_first_turn is False
    assert norm.latest_user_message == "Follow-up question"
    assert norm.conversation_fingerprint != ""

def test_map_model_aliases():
    assert RequestNormalizer.map_model_name("cursor-agent") == "gemini-3.8-flash"
    assert RequestNormalizer.map_model_name("sonnet") == "claude-3-7-sonnet"
    assert RequestNormalizer.map_model_name("deepseek") == "deepseek-r1"
    assert RequestNormalizer.map_model_name("gemini-3.8-pro") == "gemini-3.8-pro"
