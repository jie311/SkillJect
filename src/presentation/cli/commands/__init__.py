"""
CLI Commands Module
"""

import sys
from pathlib import Path
from importlib import import_module, util

# Import TwoPhaseCommand directly
from .two_phase_command import TwoPhaseCommand

# For TwoPhaseEvalCommand, we need to import from parent commands.py file
# Use importlib to avoid circular import issues
_commands_py_path = Path(__file__).parent.parent / "commands.py"
spec = util.spec_from_file_location("presentation.cli._commands_module", str(_commands_py_path))
_commands_module = util.module_from_spec(spec)

# Add to sys.modules to cache it
if "presentation.cli._commands_module" not in sys.modules:
    sys.modules["presentation.cli._commands_module"] = _commands_module
    spec.loader.exec_module(_commands_module)

TwoPhaseEvalCommand = _commands_module.TwoPhaseEvalCommand

__all__ = ["TwoPhaseCommand", "TwoPhaseEvalCommand"]
