"""
Presentation Layer CLI Module
"""

# Note: Use lazy imports via __getattr__ to avoid import cycles

__all__ = [
    "TwoPhaseCommand",
    "ArgumentParser",
]


def __getattr__(name: str):
    """Lazy import to avoid circular dependencies"""
    if name == "TwoPhaseCommand":
        from .commands.two_phase_command import TwoPhaseCommand

        return TwoPhaseCommand
    elif name == "ArgumentParser":
        from .parsers import ArgumentParser

        return ArgumentParser
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
