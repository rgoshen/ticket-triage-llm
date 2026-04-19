"""Tests for triage_tab helpers - provider resolution logic."""

import pytest

from ticket_triage_llm.ui.triage_tab import resolve_default_provider


class TestResolveDefaultProvider:
    """The Triage tab's dropdown-default resolution logic.

    The test for '9B is the default' is covered indirectly: when
    OLLAMA_MODEL=qwen3.5:9b (the post-OD-4 default from .env.example), app.py
    passes default_provider='ollama:qwen3.5:9b' to build_triage_tab_content,
    which calls this resolver. If the 9B is in the registry, this function
    returns it; the dropdown then selects it.
    """

    def test_returns_requested_when_registered(self):
        names = ["ollama:qwen3.5:2b", "ollama:qwen3.5:4b", "ollama:qwen3.5:9b"]
        assert (
            resolve_default_provider(names, "ollama:qwen3.5:9b") == "ollama:qwen3.5:9b"
        )

    def test_9b_is_selected_when_all_three_registered(self):
        """Regression guard: post-OD-4 default is the 9B.

        With OLLAMA_MODEL=qwen3.5:9b (per .env.example after OD-4 resolution),
        the dropdown default must resolve to the 9B provider name - not the 4B
        or the first-registered fallback.
        """
        names = ["ollama:qwen3.5:2b", "ollama:qwen3.5:4b", "ollama:qwen3.5:9b"]
        assert (
            resolve_default_provider(names, "ollama:qwen3.5:9b") == "ollama:qwen3.5:9b"
        )

    def test_falls_back_to_first_when_requested_absent(self):
        names = ["ollama:qwen3.5:2b", "ollama:qwen3.5:4b"]
        assert (
            resolve_default_provider(names, "ollama:qwen3.5:9b") == "ollama:qwen3.5:2b"
        )

    def test_falls_back_to_first_when_default_is_none(self):
        names = ["ollama:qwen3.5:2b", "ollama:qwen3.5:4b"]
        assert resolve_default_provider(names, None) == "ollama:qwen3.5:2b"

    def test_falls_back_to_first_when_default_is_empty_string(self):
        names = ["ollama:qwen3.5:4b"]
        assert resolve_default_provider(names, "") == "ollama:qwen3.5:4b"

    def test_empty_provider_list_raises(self):
        """App-startup invariant: registry always has at least one provider.

        If this invariant is violated, the dropdown has nothing to show and
        the error should surface immediately, not silently resolve to None.
        """
        with pytest.raises(IndexError):
            resolve_default_provider([], "ollama:qwen3.5:9b")
