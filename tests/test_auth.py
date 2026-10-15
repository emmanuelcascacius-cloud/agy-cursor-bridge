import os
from pathlib import Path
from unittest.mock import patch
import pytest
from agy_cursor_bridge.core.auth import AuthManager
from agy_cursor_bridge.config import settings

def test_validate_api_key():
    # Valid default configured key
    assert AuthManager.validate_api_key(settings.api_key) is True
    # With Bearer prefix
    assert AuthManager.validate_api_key(f"Bearer {settings.api_key}") is True
    # Any sk- prefix
    assert AuthManager.validate_api_key("sk-test123456789") is True
    assert AuthManager.validate_api_key("Bearer sk-proj-123456789") is True
    # Legacy alias
    assert AuthManager.validate_api_key("agy-live") is True

    # Invalid keys
    assert AuthManager.validate_api_key("") is False
    assert AuthManager.validate_api_key(None) is False
    assert AuthManager.validate_api_key("Bearer ") is False
    assert AuthManager.validate_api_key("invalid-token-xyz") is False

def test_find_agy_binary_override():
    with patch.object(settings, "agy_binary", "/usr/bin/python3"):
        found = AuthManager.find_agy_binary()
        assert found == "/usr/bin/python3"

def test_is_token_present(tmp_path):
    token_file = tmp_path / "antigravity-oauth-token"
    with patch.object(AuthManager, "get_token_path", return_value=token_file):
        assert AuthManager.is_token_present() is False
        token_file.write_text("dummy-token-contents")
        assert AuthManager.is_token_present() is True
