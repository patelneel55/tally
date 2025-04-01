"""
Handles loading and validation of application configuration from various sources
like environment variables, .env files, and YAML configuration files.
"""

import yaml
import os
import logging
from dotenv import load_dotenv
from typing import Dict, Any, Optional, Union
from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "config.yaml"
DOTENV_PATH = ".env" # Standard location for dotenv file

def _deep_update(source: Dict, overrides: Dict) -> Dict:
    """Recursively update a dictionary."""
    for key, value in overrides.items():
        if isinstance(value, dict) and key in source and isinstance(source[key], dict):
            source[key] = _deep_update(source[key], value)
        else:
            source[key] = value
    return source

def load_config(
    config_path: str = DEFAULT_CONFIG_PATH,
    dotenv_path: Optional[str] = DOTENV_PATH
    ) -> Dict[str, Any]:
    """
    Loads configuration hierarchically:
    1. Base configuration from YAML file (if exists).
    2. Overrides from environment variables (potentially loaded from .env file).

    Args:
        config_path: Path to the YAML configuration file.
        dotenv_path: Path to the .env file (set to None to disable).

    Returns:
        A dictionary containing the final configuration.

    Raises:
        ConfigurationError: If YAML parsing fails or required settings are missing.
    """
    config: Dict[str, Any] = {}

    # 1. Load base configuration from YAML
    yaml_path_abs = os.path.abspath(config_path)
    if os.path.exists(yaml_path_abs):
        try:
            with open(yaml_path_abs, 'r') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config: # Handle empty file returning None
                    config = yaml_config
            logger.info(f"Loaded base configuration from {yaml_path_abs}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error parsing YAML file {yaml_path_abs}: {e}")
        except IOError as e:
            raise ConfigurationError(f"Error reading config file {yaml_path_abs}: {e}")
    else:
        logger.warning(f"Configuration file {yaml_path_abs} not found. Relying on defaults and environment variables.")

    # 2. Load .env file into environment variables
    dotenv_loaded = False
    if dotenv_path:
        dotenv_path_abs = os.path.abspath(dotenv_path)
        if os.path.exists(dotenv_path_abs):
            # `override=True` ensures .env vars take precedence over existing env vars
            dotenv_loaded = load_dotenv(dotenv_path=dotenv_path_abs, override=True)
            if dotenv_loaded:
                logger.info(f"Loaded and overriding environment variables from {dotenv_path_abs}")
        # else: Optional .env file not found is not usually an error

    # 3. Prepare overrides from environment variables (structured approach)
    env_overrides: Dict[str, Any] = {}

    # Example: Mapping env vars to nested config structure
    env_map = {
        "OPENAI_API_KEY": ("llm_providers", "openai", "api_key"),
        "ANTHROPIC_API_KEY": ("llm_providers", "anthropic", "api_key"),
        "OPENAI_EMBEDDING_MODEL": ("embedding_providers", "openai", "model"),
        "VECTOR_STORE_PATH": ("vector_stores", "chroma", "persist_directory"), # Example for Chroma
        "VECTOR_STORE_COLLECTION": ("vector_stores", "chroma", "collection_name"), # Example for Chroma
        # Add mappings for other sensitive or environment-specific settings
    }

    for env_var, config_path_tuple in env_map.items():
        value = os.getenv(env_var)
        if value:
            logger.info(f"Found environment variable {env_var}")
            temp_dict = env_overrides
            for i, key in enumerate(config_path_tuple):
                if i == len(config_path_tuple) - 1:
                    temp_dict[key] = value
                else:
                    temp_dict = temp_dict.setdefault(key, {}) # Create nested dict if needed

    # 4. Deep merge environment overrides into the base config
    if env_overrides:
        config = _deep_update(config, env_overrides)
        logger.info("Applied environment variable overrides to configuration.")

    # 5. Basic Validation (Add more specific checks as needed)
    if not config:
         logger.warning("Configuration is empty after loading all sources.")
    # Example check: Ensure some LLM provider is configured
    # if not config.get('llm_providers'):
    #     raise ConfigurationError("Missing 'llm_providers' configuration section.")


    logger.debug(f"Final configuration loaded: {config}")
    return config

# Example of how to use it (typically called once at application startup)
# if __name__ == '__main__':
#     logging.basicConfig(level=logging.INFO)
#     try:
#         app_config = load_config()
#         print("\n--- Final Configuration ---")
#         import json
#         print(json.dumps(app_config, indent=2))
#         # Example access
#         # print(f"\nOpenAI API Key Present: {'api_key' in app_config.get('llm_providers', {}).get('openai', {})}")
#     except ConfigurationError as e:
#         logger.error(f"Configuration Error: {e}")