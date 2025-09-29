"""Configuration helpers for the Granola MCP Server.

Exposes a single public function `load_config` that reads environment
variables and returns a typed `AppConfig` instance with sensible
defaults. Values are validated and normalized where appropriate.
"""

from .env import AppConfig, load_config

__all__ = ["AppConfig", "load_config"]
