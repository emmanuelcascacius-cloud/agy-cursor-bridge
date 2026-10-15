import asyncio
import sys
import typer
import uvicorn
from typing import Optional
from agy_cursor_bridge import __version__
from agy_cursor_bridge.config import settings
from agy_cursor_bridge.core.auth import AuthManager
from agy_cursor_bridge.core.tunnel import TunnelManager
from agy_cursor_bridge.routes.models import fetch_available_models

app = typer.Typer(
    name="agy-cursor",
    help="OpenAI-compatible routing layer connecting Cursor IDE to Google Antigravity (agy CLI)",
    add_completion=False,
)

@app.command()
def version():
    """Prints the current version of agy-cursor-bridge."""
    typer.echo(f"agy-cursor-bridge v{__version__}")

@app.command()
def check():
    """Verifies that agy CLI is installed, authenticated, and ready."""
    typer.echo("[*] Checking Antigravity (agy) configuration...")
    try:
        binary_path = AuthManager.find_agy_binary()
        typer.secho(f"  [+] Found agy binary: {binary_path}", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"  [-] Binary error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    token_path = AuthManager.get_token_path()
    if AuthManager.is_token_present():
        typer.secho(f"  [+] Active OAuth token: {token_path}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"  [-] No OAuth token found at: {token_path}", fg=typer.colors.YELLOW)
        typer.echo("      Run 'agy' once in your terminal to complete login.")

    typer.echo("  [*] Testing connection to Antigravity backend...")
    is_auth, status = asyncio.run(AuthManager.verify_auth())
    if is_auth:
        typer.secho(f"  [+] Backend status: {status}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"  [-] Backend verification failed: {status}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho("\nAll checks passed. agy-cursor-bridge is ready.", fg=typer.colors.GREEN, bold=True)

@app.command()
def models():
    """Lists available models from your Antigravity tier."""
    typer.echo("Fetching available models from agy...")
    models_list = asyncio.run(fetch_available_models())
    typer.secho(f"\nDiscovered {len(models_list)} models:\n", bold=True)
    for m in models_list:
        typer.echo(f"  • {m}")
    typer.echo("\nYou can enter any of these models into Cursor Settings -> Models.")

@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host address to bind to"),
    port: int = typer.Option(8000, help="Port to listen on"),
    api_key: str = typer.Option("sk-proj-antigravity-live-7f8e9d0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e", help="Virtual OpenAI API key expected by Cursor"),
    model: str = typer.Option("gemini-3.8-flash", help="Default model name"),
    mode: str = typer.Option("auto", help="Execution mode (auto, accept-edits, plan)"),
    effort: str = typer.Option("high", help="Reasoning effort (low, medium, high, xhigh, max)"),
    tunnel: bool = typer.Option(False, "--tunnel", "-t", help="Spin up a zero-config Cloudflare public tunnel"),
):
    """Starts the OpenAI-compatible HTTP routing server for Cursor."""
    # Update settings
    settings.host = host
    settings.port = port
    settings.api_key = api_key
    settings.default_model = model
    settings.default_mode = mode
    settings.default_effort = effort

    # Check auth quickly
    try:
        AuthManager.find_agy_binary()
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    tunnel_mgr: Optional[TunnelManager] = None
    public_url: Optional[str] = None

    if tunnel:
        tunnel_mgr = TunnelManager(local_port=port)
        typer.echo("[*] Initializing Cloudflare Quick Tunnel...")
        success, url_or_err = asyncio.run(tunnel_mgr.start())
        if success and url_or_err:
            public_url = url_or_err
            typer.secho(f"[+] Tunnel established: {public_url}", fg=typer.colors.GREEN)
        else:
            typer.secho(f"[-] Cloudflare tunnel could not be created ({url_or_err}). Using local binding.", fg=typer.colors.YELLOW)

    # Print clean Banner
    display_host = "127.0.0.1" if host in ("0.0.0.0", "127.0.0.1") else host
    base_url = f"http://{display_host}:{port}/v1"
    cursor_base = f"{public_url}/v1" if public_url else base_url

    typer.echo("\n" + "=" * 70)
    typer.secho("  agy-cursor-bridge: OpenAI-Compatible Gateway for Cursor IDE", bold=True)
    typer.echo("=" * 70)
    typer.echo(f"  Local Base URL:   {base_url}")
    if public_url:
        typer.secho(f"  Public Tunnel:    {cursor_base}", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  OpenAI API Key:   {api_key}")
    typer.echo(f"  Default Model:    {model}")
    typer.echo(f"  Reasoning Effort: {effort}")
    typer.echo("-" * 70)
    typer.secho("  Cursor Setup Guide:", bold=True)
    typer.echo("  1. Open Cursor Settings -> Models")
    typer.echo(f"  2. OpenAI API Key:           {api_key}")
    typer.echo(f"  3. Override OpenAI Base URL: {cursor_base}")
    typer.echo("  4. Model Selection:")
    typer.echo("     - Option A: Type 'agy-flash' in Add Model -> click +")
    typer.echo("     - Option B: Use default 'gpt-4o' in Chat (auto-routed to Gemini 3.8)")
    typer.echo("=" * 70 + "\n")

    try:
        uvicorn.run("agy_cursor_bridge.server:app", host=host, port=port, log_level="info")
    finally:
        if tunnel_mgr:
            asyncio.run(tunnel_mgr.stop())

if __name__ == "__main__":
    app()
