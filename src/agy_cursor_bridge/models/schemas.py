import time
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: str = Field(default="user", description="Role of the message author (system, user, assistant, developer, tool)")
    content: Optional[Union[str, List[Dict[str, Any]]]] = Field(default="", description="Content of the message")
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model: str = Field(default="gemini-3.8-flash")
    messages: Optional[List[ChatMessage]] = None
    # Cursor Agent / Responses API support
    input: Optional[Union[str, List[Dict[str, Any]], List[ChatMessage]]] = None
    stream: Optional[bool] = False
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    max_tokens: Optional[int] = None
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    reasoning_effort: Optional[Literal["low", "medium", "high", "xhigh", "max"]] = None
    stream_options: Optional[Dict[str, Any]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    user: Optional[str] = None

class ModelCard(BaseModel):
    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "antigravity"
    root: Optional[str] = None
    parent: Optional[str] = None
    permission: List[Dict[str, Any]] = Field(default_factory=list)

class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelCard]

# Non-streaming response schemas
class ChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str = ""

class CompletionChoice(BaseModel):
    index: int = 0
    message: ChoiceMessage
    finish_reason: Optional[str] = "stop"

class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[CompletionChoice]
    usage: Optional[UsageInfo] = None

# Streaming response schemas
class StreamDelta(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    reasoning_content: Optional[str] = None

class StreamChoice(BaseModel):
    index: int = 0
    delta: StreamDelta
    finish_reason: Optional[str] = None

class ChatCompletionChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[StreamChoice]
    usage: Optional[UsageInfo] = None
