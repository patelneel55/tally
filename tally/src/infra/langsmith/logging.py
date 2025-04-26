"""LangSmith logging module.

This module provides utilities for logging to LangSmith.
"""
import json
from contextvars import ContextVar
from typing import Any, Dict, Optional

from langsmith import Client
from langsmith.run_helpers import traceable

from .config import get_langsmith_settings

# Context variable for storing run metadata
run_metadata: ContextVar[Dict[str, Any]] = ContextVar("run_metadata", default={})


class LangSmithLogger:
    """LangSmith logging utility.
    
    This class provides methods for logging to LangSmith with proper context
    and metadata management.
    """
    def __init__(self) -> None:
        """Initialize LangSmith logger."""
        settings = get_langsmith_settings()
        self.client = Client(
            api_key=settings.api_key,
            api_url=settings.endpoint,
        )
        self.project_name = settings.project_name
        self.tracing_enabled = settings.tracing_enabled

    def log_prompt(
        self,
        prompt: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ) -> None:
        """Log a prompt and its response to LangSmith.
        
        Args:
            prompt: The input prompt
            response: The model's response
            metadata: Additional metadata to log
            tags: Tags to associate with the run
        """
        if not self.tracing_enabled:
            return

        run_meta = run_metadata.get()
        if metadata:
            run_meta.update(metadata)

        self.client.create_run(
            project_name=self.project_name,
            inputs={"prompt": prompt},
            outputs={"response": response},
            metadata=run_meta,
            tags=tags or [],
        )

    def update_metadata(self, **kwargs: Any) -> None:
        """Update the current run's metadata.
        
        Args:
            **kwargs: Key-value pairs to add to metadata
        """
        current_meta = run_metadata.get()
        current_meta.update(kwargs)
        run_metadata.set(current_meta)


def get_langsmith_logger() -> LangSmithLogger:
    """Get a LangSmith logger instance.
    
    Returns:
        LangSmithLogger: Configured LangSmith logger
    """
    return LangSmithLogger()


def traceable_with_metadata(**metadata: Any) -> Any:
    """Decorator for tracing functions with metadata.
    
    Args:
        **metadata: Metadata to associate with the traced function
        
    Returns:
        Any: Decorated function
    """
    def decorator(func: Any) -> Any:
        @traceable
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_langsmith_logger()
            logger.update_metadata(**metadata)
            return func(*args, **kwargs)
        return wrapper
    return decorator 