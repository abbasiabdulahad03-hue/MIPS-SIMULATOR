"""
Custom exceptions for PyMIPS32 Studio.
Each exception carries context so errors can be shown in pop-ups and traced.
"""


class MIPSStudioError(Exception):
    """Base exception for all simulator errors."""

    def __init__(self, message: str, *, context: str = "", line: int = 0):
        self.message = message
        self.context = context
        self.line = line
        parts = [message]
        if line:
            parts.append(f"Line {line}")
        if context:
            parts.append(context)
        super().__init__(" — ".join(parts))


class AssemblyException(MIPSStudioError):
    """Raised when assembly / parsing fails."""


class RuntimeException(MIPSStudioError):
    """Raised when instruction execution fails at runtime."""


class AuthException(MIPSStudioError):
    """Raised when login or authentication fails."""


class FileOperationException(MIPSStudioError):
    """Raised when file open/save fails."""


class SimulatorStateException(MIPSStudioError):
    """Raised when an operation is invalid for current simulator state."""


class SyscallInputRequired(Exception):
    """Execution paused — simulator needs interactive user input."""

    def __init__(self, kind: str, prompt: str = "",
                 buffer_addr: int = 0, max_len: int = 256):
        self.kind = kind          # "int" | "string" | "float"
        self.prompt = prompt
        self.buffer_addr = buffer_addr
        self.max_len = max_len
        super().__init__(prompt or kind)
