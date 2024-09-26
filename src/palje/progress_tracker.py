from __future__ import annotations
from dataclasses import dataclass
import time
from typing import Callable


# TODO: use a dict for the callback arguments


@dataclass
class ProgressTracker:
    """A class for tracking progress of a process."""

    passed: int = 0
    """The number of steps that have passed successfully."""

    failed: int = 0
    """The number of steps that have failed."""

    target_total: int = 0
    """The total number of steps to complete."""

    on_step_callback: Callable[[ProgressTracker], None] | None = None
    """An optional callback function that will be called after each step."""

    _message: str | None = None
    """Most recent message that came in via step function."""

    _start_time: float = 0.0

    @property
    def completed(self) -> int:
        """The number of completed steps (both successful and failed)."""
        return self.passed + self.failed

    @property
    def percents(self) -> float:
        """The percentage of completed steps from target_total."""
        if self.target_total == 0:
            return 0.0
        return round(100.0 * self.completed / float(self.target_total), 1)

    @property
    def message(self) -> str:
        """The most recent message that came in via step function."""
        if self._message:
            return self._message
        return ""

    @property
    def elapsed_time(self) -> float:
        """The time elapsed since the first step."""
        return time.time() - self._start_time

    def reset(self) -> None:
        """Clear the progress tracker's values. Callback is not affected."""
        self.passed = 0
        self.failed = 0
        self.target_total = 0
        self._message = None
        self._start_time = 0.0

    def step(self, passed: bool, message: str | None = None) -> None:
        """Forward the progress tracker by one step.

        Arguments
        ---------

        passed : bool
            Whether the step was successful or not.

        message : str, optional
            Optional message related to the step.

        """
        if self._start_time == 0.0:
            self._start_time = time.time()
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        self._message = message
        if self.on_step_callback:
            self.on_step_callback(self)
