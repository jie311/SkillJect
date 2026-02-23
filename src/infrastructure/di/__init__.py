"""
Dependency Injection Module

Provides simple dependency injection container, supporting singleton and factory patterns
"""

from src.infrastructure.di.service_container import ServiceContainer, container

__all__ = ["ServiceContainer", "container"]
