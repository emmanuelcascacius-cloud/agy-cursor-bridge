# agy-cursor-bridge 🚀

> **OpenAI-Compatible Routing Layer Exposing Google Antigravity (`agy` CLI) to Cursor IDE**

`agy-cursor-bridge` enables you to use **Google Antigravity** models (Gemini 3.8 Flash, Gemini 3.8 Pro, Claude 3.7 Sonnet, DeepSeek R1) inside **Cursor IDE's native Agent, Composer, Chat, and Inline-Edit** windows.

---

## ✨ Features

- **Zero-Config Authentication:** Uses your active local `agy` credentials (`~/.gemini/antigravity-cli/antigravity-oauth-token`). No Google Cloud API keys or external credits required!
- **True Low-Latency Streaming:** Maps `agy` NDJSON output into standard OpenAI Server-Sent Events (`choices[0].delta.content`) with zero buffer lag.
- **Cursor Agent & Responses API Support:** Works with both standard OpenAI chat completion payloads and Cursor Agent's internal `input` format.
- **Stateful Multi-Turn Conversations:** Preserves dialogue history across turns using Antigravity's `--conversation <id>` context tracking.
- **Zero-Config Cloudflare Tunnel (`--tunnel`):** Automatically provisions a public HTTPS endpoint for seamless verification by Cursor's cloud verification servers (`api2.cursor.sh`).
- **Dynamic Model Discovery:** Queries `agy models` to dynamically populate `/v1/models` in Cursor's dropdown.

---

## 🚀 Quickstart

### 1. Installation

```bash
git clone https://github.com/emmanuelcascacius/agy-cursor-bridge.git
cd agy-cursor-bridge
pip install -e .
```

### 2. Verify Your Antigravity Setup

```bash
agy-cursor check
```

### 3. Start the Bridge Server

```bash
# Start local server on port 8000
agy-cursor serve --port 8000

# OR start with a free, instant Cloudflare Public Tunnel (recommended for Cursor Cloud verification):
agy-cursor serve --tunnel
```

---

## 💻 Cursor Configuration

1. In Cursor, open **Settings** (`Cmd+,` or `Ctrl+,`), then navigate to **Cursor Settings** -> **Models**.
2. Scroll to the **OpenAI API Key** section:
   - **OpenAI API Key:** `agy-live` *(or any dummy string)*
3. Enable **Override OpenAI Base URL**:
   - Local: `http://127.0.0.1:8000/v1`
   - Tunnel: `https://<your-tunnel-name>.trycloudflare.com/v1`
4. Under **Model Names**, add any model from your Antigravity tier:
   - `gemini-3.8-flash`
   - `gemini-3.8-pro`
   - `claude-3-7-sonnet`
   - `deepseek-r1`
5. Click **Verify** next to the API key. You will see a green checkmark!
6. Open **Cursor Agent** (`Cmd+I` or `Ctrl+I`) or Chat (`Cmd+L`), select `gemini-3.8-flash`, and start coding!

---

## 🛠️ CLI Reference

```bash
agy-cursor check       # Verify agy binary and active OAuth session
agy-cursor models      # List all available models from agy
agy-cursor serve       # Launch the OpenAI-compatible HTTP proxy
agy-cursor version     # Print package version
```

### Options for `serve`:
- `--port INTEGER`: Port to listen on (default: `8000`)
- `--host TEXT`: Host to bind (default: `0.0.0.0`)
- `--api-key TEXT`: Virtual API key required by Cursor (default: `agy-live`)
- `--model TEXT`: Default model name (default: `gemini-3.8-flash`)
- `--mode TEXT`: Execution mode: `auto`, `accept-edits`, or `plan` (default: `auto`)
- `--effort TEXT`: Reasoning effort: `low`, `medium`, `high`, `xhigh`, `max` (default: `high`)
- `--tunnel`, `-t`: Spin up a zero-config Cloudflare public tunnel

---

## 📄 Architecture

For in-depth architectural details, see [IMPLEMENTATION.md](IMPLEMENTATION.md).

## ⚖️ License

MIT License.
