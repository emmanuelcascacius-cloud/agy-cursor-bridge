# agy-cursor-bridge

OpenAI-compatible routing layer bridging Google Antigravity (`agy` CLI) into Cursor IDE.

## Overview

`agy-cursor-bridge` exposes a local or tunneled HTTP server implementing the OpenAI `/v1/chat/completions` and `/v1/models` specifications. It translates incoming Chat Completions and Cursor Responses API requests into headless `agy` CLI executions (`--output-format stream-json`), streaming real-time tokens back to Cursor via Server-Sent Events (SSE).

It relies on existing local Antigravity credentials (`~/.gemini/antigravity-cli/antigravity-oauth-token`) without requiring external API keys.

## Features

- Local Credential Reuse: Uses your active `agy` CLI authentication session.
- Real-Time Streaming: Translates newline-delimited JSON chunks from `agy` directly into OpenAI SSE deltas.
- Cursor Protocol Support: Handles standard OpenAI chat format and Cursor Agent's internal `input` array format.
- Stateful Multi-Turn Tracking: Maps conversation history hashes to `agy --conversation <id>` threads to preserve context.
- Collision-Free Model Mapping: Aliases avoid Cursor's built-in catalog collisions and subscription checks.
- Optional Tunneling: Built-in Cloudflare quick tunnel support (`--tunnel`) for remote or cloud-verified environments.

## Installation

Prerequisites:
- Python 3.10+
- Installed and authenticated Antigravity CLI (`agy`)

```bash
git clone https://github.com/emmanuelcascacius-cloud/agy-cursor-bridge.git
cd agy-cursor-bridge
pip install -e .
```

Verify your setup:

```bash
agy-cursor check
```

## Usage

### Starting the Server

Local binding (port 8000):

```bash
agy-cursor serve --port 8000
```

With public Cloudflare tunnel (recommended when Cursor verifies URLs through cloud endpoints):

```bash
agy-cursor serve --tunnel
```

### CLI Reference

```bash
agy-cursor check       # Verify agy binary and token presence
agy-cursor models      # List available models from the local agy runtime
agy-cursor serve       # Run the OpenAI-compatible HTTP proxy
agy-cursor version     # Print package version
```

Flags for `serve`:
- `--host TEXT`: Bind address (default: `0.0.0.0`)
- `--port INTEGER`: Bind port (default: `8000`)
- `--api-key TEXT`: Virtual OpenAI key expected by client (default: `sk-proj-antigravity-live-...`)
- `--model TEXT`: Default target model (default: `gemini-3.8-flash`)
- `--mode TEXT`: Agent execution mode: `auto`, `accept-edits`, or `plan` (default: `auto`)
- `--effort TEXT`: Reasoning effort level: `low`, `medium`, `high`, `xhigh`, `max` (default: `high`)
- `--tunnel`, `-t`: Launch temporary public HTTPS tunnel via Cloudflare

## Cursor Configuration

1. Open Cursor and navigate to Settings > Cursor Settings > Models.
2. In the OpenAI API Key field, enter:
   `sk-proj-antigravity-live-7f8e9d0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e`
3. Toggle Override OpenAI Base URL ON and enter:
   - For local connections: `http://127.0.0.1:8000/v1`
   - For tunneled connections: `https://<tunnel-id>.trycloudflare.com/v1`
4. Configure models (choose one):
   - Option A: Under Add Model, type `agy-flash` and toggle it ON.
   - Option B: Use default `gpt-4o` in chat; the proxy automatically maps it to `gemini-3.8-flash`.
5. Open Chat (`Cmd+L` or `Ctrl+L`) or Composer (`Cmd+I` or `Ctrl+I`), select the model, and submit your prompt.

## Model Aliases

The proxy maps incoming client model strings to Antigravity backends:

| Client Model Name | Mapped Antigravity Model |
| :--- | :--- |
| `agy-flash`, `agy-gemini` | `gemini-3.8-flash` |
| `agy-pro` | `gemini-3.8-pro` |
| `agy-sonnet`, `agy-claude` | `claude-3-7-sonnet` |
| `agy-deepseek`, `agy-r1` | `deepseek-r1` |
| `gpt-4o` | `gemini-3.8-flash` |
| `gpt-4` | `gemini-3.8-pro` |
| `gpt-4o-mini` | `gemini-3.8-flash-lite` |
| `auto`, `cursor-agent` | Active default model |

## Important Notes on Cursor Tiers

Cursor restricts custom OpenAI API keys (BYOK) on Free accounts in recent releases. If your Cursor account is on the Free tier, selecting built-in frontier names or using custom endpoints in certain views may prompt an upgrade dialog. Using dedicated non-colliding aliases (`agy-flash`) or pairing this gateway with extensions like Continue, Cline, or Aider provides unrestricted access.

## Architecture

The server runs on FastAPI and Uvicorn. Incoming requests are normalized in `core/normalizer.py` to extract system instructions, context, and message turns. The driver (`core/agy_driver.py`) spawns `agy` in headless NDJSON mode (`--output-format stream-json`) with `--dangerously-skip-permissions` to allow tool execution. Output events are parsed by `core/stream_parser.py` and yielded as chunked OpenAI Server-Sent Events.

Session continuity is preserved across turns by computing conversation fingerprint hashes (`core/session_store.py`) and passing `--conversation <id>` on subsequent turns.

## Testing

```bash
pytest tests/ -v
```

## Author

Emmanuel Arhin

## License

MIT License. See LICENSE for details.
