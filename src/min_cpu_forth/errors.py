"""Exception hierarchy for the virtual machine and its toolchain."""


class MachineError(Exception):
    """Base class for every error raised by ``min_cpu_forth``."""


class StackError(MachineError):
    """Raised on data- or return-stack underflow or overflow."""


class EmulatorError(MachineError):
    """Raised when the emulator cannot continue (a runaway program, or a malformed instruction)."""


class InputExhaustedError(EmulatorError):
    """Raised when an ``IN`` instruction reads from an exhausted input device."""


class AssemblerError(MachineError):
    """Raised when source text cannot be assembled (bad syntax, unknown mnemonic, bad label)."""


class UnknownWordError(MachineError):
    """Raised when a colon definition references a word absent from the dictionary."""


class KernelError(MachineError):
    """Raised when the ITC kernel cannot be assembled or laid out (bad routine ordering, ...)."""
