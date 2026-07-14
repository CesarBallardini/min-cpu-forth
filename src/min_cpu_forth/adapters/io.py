"""In-memory character I/O adapters for the emulator's ``IN``/``OUT`` opcodes."""

from collections import deque
from typing import TYPE_CHECKING

from min_cpu_forth.errors import InputExhaustedError
from min_cpu_forth.ports import CharacterInputPort, CharacterOutputPort

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


class QueueCharacterInputAdapter(CharacterInputPort):
    """A FIFO queue of character codes feeding ``IN``."""

    def __init__(self, initial: Iterable[int] | None = None) -> None:
        """Seed the queue with ``initial`` character codes, if any."""
        self._queue: deque[int] = deque(initial if initial is not None else ())

    def feed(self, values: Iterable[int]) -> None:
        """Append ``values`` to the back of the input queue."""
        self._queue.extend(values)

    def read(self) -> int:
        """Pop and return the next character code, or raise if the queue is empty."""
        if not self._queue:
            raise InputExhaustedError('IN: input queue is empty')
        return self._queue.popleft()


class BufferCharacterOutputAdapter(CharacterOutputPort):
    """Collects ``OUT`` character codes into an in-memory buffer."""

    def __init__(self) -> None:
        """Start with an empty output buffer."""
        self._buffer: list[int] = []

    def write(self, value: int) -> None:
        """Append the character code ``value`` to the buffer."""
        self._buffer.append(value)

    @property
    def buffer(self) -> Sequence[int]:
        """The character codes written so far, in order."""
        return tuple(self._buffer)
