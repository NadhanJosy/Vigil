# Vigil configuration module
"""
Centralized configuration management for Vigil.
All thresholds, secrets, and operational parameters are loaded from
environment variables or YAML config files.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def get_secret(env_var: str, default: str | None = None) -> str:
    """
    Resolve a secret from environment variables.
    Future: integrate with HashiCorp Vault or AWS Secrets Manager.
    """
    value = os.environ.get(env_var, default)
    if value is None:
        raise EnvironmentError(f"Required secret {env_var} is not set")
    return value
