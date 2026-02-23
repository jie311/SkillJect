"""
Shared Exception Definitions Module

Provides common exception classes for cross-module use, including:
1. Domain exception classes
2. Test exception system with retry mechanism
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


# =============================================================================
# Domain Exception Classes (Original)
# =============================================================================


class EvaluationError(Exception):
    """Base class for evaluation errors"""

    pass


class ConfigurationError(EvaluationError):
    """Configuration error"""

    pass


class SkillNotFoundError(EvaluationError):
    """Skill not found error"""

    pass


class AgentNotFoundError(EvaluationError):
    """Agent not found error"""

    pass


class TestNotFoundError(EvaluationError):
    """Test not found error"""

    pass


class PayloadNotFoundError(EvaluationError):
    """Payload not found error"""

    pass


# ValidationError is defined below, merging two versions


# =============================================================================
# Error Classification System (Merged from src.exceptions.py)
# =============================================================================


class ErrorCategory(Enum):
    """Error category"""

    TRANSIENT = "transient"  # Temporary error, retryable
    PERMANENT = "permanent"  # Permanent error, should not retry
    TIMEOUT = "timeout"  # Timeout error, possibly retryable
    NETWORK = "network"  # Network error, possibly retryable
    VALIDATION = "validation"  # Validation error, should not retry


class SecurityTestError(EvaluationError):
    """Base exception for security testing framework

    Inherits from EvaluationError, supports error classification and retry determination.
    """

    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.PERMANENT):
        self.message = message
        self.category = category
        super().__init__(self.message)

    def is_retryable(self) -> bool:
        """Check if the error is retryable"""
        return self.category in [
            ErrorCategory.TRANSIENT,
            ErrorCategory.TIMEOUT,
            ErrorCategory.NETWORK,
        ]


class SandboxError(SecurityTestError):
    """Sandbox-related error"""

    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.TRANSIENT):
        super().__init__(f"Sandbox error: {message}", category)


class TestExecutionError(SecurityTestError):
    """Test execution error"""

    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.PERMANENT):
        super().__init__(f"Test execution error: {message}", category)


class ConsequenceDetectionError(SecurityTestError):
    """Consequence detection error"""

    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.PERMANENT):
        super().__init__(f"Consequence detection error: {message}", category)


class LogCollectionError(SecurityTestError):
    """Log collection error"""

    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.TRANSIENT):
        super().__init__(f"Log collection error: {message}", category)


# Merge two versions of TimeoutError
class TimeoutError(SecurityTestError):
    """Timeout error"""

    def __init__(self, message: str, timeout_seconds: int):
        super().__init__(f"Timeout after {timeout_seconds}s: {message}", ErrorCategory.TIMEOUT)
        self.timeout_seconds = timeout_seconds


# Use SecurityTestError as the base class for ValidationError
class ValidationError(SecurityTestError):
    """Validation error (with error classification)"""

    def __init__(self, message: str):
        super().__init__(f"Validation error: {message}", ErrorCategory.VALIDATION)


# =============================================================================
# Retry Configuration and Utilities
# =============================================================================


@dataclass
class RetryConfig:
    """Retry configuration"""

    max_attempts: int = 3  # Maximum number of attempts (including first)
    base_delay: float = 1.0  # Base delay (seconds)
    max_delay: float = 30.0  # Maximum delay (seconds)
    exponential_backoff: bool = True  # Whether to use exponential backoff
    jitter: bool = True  # Whether to add random jitter

    def get_delay(self, attempt: int) -> float:
        """
        Get the delay time for the Nth retry

        Args:
            attempt: Current retry count (starting from 1)

        Returns:
            Delay time in seconds
        """
        if self.exponential_backoff:
            delay = self.base_delay * (2 ** (attempt - 1))
        else:
            delay = self.base_delay

        delay = min(delay, self.max_delay)

        if self.jitter:
            import random

            delay = delay * (0.5 + random.random())

        return delay


async def retry_with_backoff(
    func: Callable,
    retry_config: RetryConfig | None = None,
    operation_name: str = "operation",
) -> Any:
    """
    Retry decorator/function with exponential backoff

    Args:
        func: Async function to execute
        retry_config: Retry configuration
        operation_name: Operation name (for logging)

    Returns:
        Function execution result

    Raises:
        SecurityTestError: Last error after all retries fail
    """
    if retry_config is None:
        retry_config = RetryConfig()

    last_error = None

    for attempt in range(1, retry_config.max_attempts + 1):
        try:
            return await func()
        except SecurityTestError as e:
            last_error = e

            # Check if retryable
            if not e.is_retryable():
                raise

            # Last attempt failed, no need to wait
            if attempt >= retry_config.max_attempts:
                break

            # Calculate delay time
            delay = retry_config.get_delay(attempt)

            print(
                f"  ⚠ {operation_name} failed (attempt {attempt}/{retry_config.max_attempts}): {e.message}"
            )
            print(f"  ⏳ Retrying in {delay:.1f}s...")

            await asyncio.sleep(delay)

        except Exception as e:
            # Unexpected exception type
            last_error = SecurityTestError(str(e), ErrorCategory.TRANSIENT)
            raise

    # All retries failed
    raise last_error or SecurityTestError(
        f"{operation_name} failed after {retry_config.max_attempts} attempts"
    )


def classify_error(error: Exception) -> ErrorCategory:
    """
    Classify an exception into an error category

    Args:
        error: Exception object

    Returns:
        Error category
    """
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()

    # Network-related errors
    network_keywords = [
        "connection",
        "network",
        "timeout",
        "remote",
        "protocol",
        "httpx",
        "http",
        "tcp",
        "socket",
    ]
    if any(keyword in error_str or keyword in error_type for keyword in network_keywords):
        return ErrorCategory.NETWORK

    # Timeout errors
    if "timeout" in error_str or "timeout" in error_type:
        return ErrorCategory.TIMEOUT

    # Validation errors
    validation_keywords = [
        "validation",
        "invalid",
        "not found",
        "does not exist",
        "permission",
        "unauthorized",
        "forbidden",
    ]
    if any(keyword in error_str for keyword in validation_keywords):
        return ErrorCategory.VALIDATION

    # Default to transient error
    return ErrorCategory.TRANSIENT


def wrap_error(error: Exception, context: str = "") -> SecurityTestError:
    """
    Wrap a generic exception as SecurityTestError

    Args:
        error: Original exception
        context: Context information

    Returns:
        SecurityTestError instance
    """
    if isinstance(error, SecurityTestError):
        return error

    category = classify_error(error)
    message = f"{context}: {error}" if context else str(error)

    return SecurityTestError(message, category)


__all__ = [
    # Domain exceptions
    "EvaluationError",
    "ConfigurationError",
    "SkillNotFoundError",
    "AgentNotFoundError",
    "TestNotFoundError",
    "PayloadNotFoundError",
    "ValidationError",
    # Error classification system
    "ErrorCategory",
    "SecurityTestError",
    "SandboxError",
    "TestExecutionError",
    "ConsequenceDetectionError",
    "LogCollectionError",
    "TimeoutError",
    # Retry mechanism
    "RetryConfig",
    "retry_with_backoff",
    "classify_error",
    "wrap_error",
]
