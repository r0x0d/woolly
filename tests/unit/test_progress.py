"""
Unit tests for woolly.progress module.

Tests cover:
- Good path: progress tracker lifecycle
- Critical path: progress updates and completion
"""

import pytest
from rich.console import Console

from woolly.progress import ProgressTracker


class TestProgressTracker:
    """Tests for ProgressTracker class."""

    @pytest.fixture
    def console(self):
        """Create a console for testing."""
        return Console(force_terminal=True, no_color=True)

    @pytest.fixture
    def tracker(self, console):
        """Create a ProgressTracker instance."""
        return ProgressTracker(console)

    @pytest.mark.unit
    def test_initialization(self, tracker):
        """Good path: tracker initializes with correct defaults."""
        assert tracker.processed == 0
        assert tracker.total_discovered == 0
        assert tracker.progress is not None

    @pytest.mark.unit
    def test_start_adds_task(self, tracker):
        """Good path: start() adds a progress task."""
        tracker.start("Testing dependencies")
        # Task should be added (task ID is assigned)
        assert tracker.task is not None
        tracker.stop()

    @pytest.mark.unit
    def test_update_increments_processed(self, tracker):
        """Critical path: update() increments processed count."""
        tracker.start()
        initial = tracker.processed

        tracker.update("package-1")
        assert tracker.processed == initial + 1

        tracker.update("package-2")
        assert tracker.processed == initial + 2
        tracker.stop()

    @pytest.mark.unit
    def test_update_with_discovered(self, tracker):
        """Critical path: update() accumulates discovered packages."""
        tracker.start()

        tracker.update("root", discovered=5)
        assert tracker.total_discovered == 5

        tracker.update("child", discovered=3)
        assert tracker.total_discovered == 8
        tracker.stop()

    @pytest.mark.unit
    def test_finish_marks_complete(self, tracker):
        """Good path: finish() marks progress as complete."""
        tracker.start()
        tracker.update("package-1")
        tracker.update("package-2")
        tracker.finish()
        # After finish, processed should equal total
        tracker.stop()

    @pytest.mark.unit
    def test_stop_is_safe_to_call_multiple_times(self, tracker):
        """Good path: stop() can be called multiple times safely."""
        tracker.start()
        tracker.stop()
        tracker.stop()  # Should not raise

    @pytest.mark.unit
    def test_lifecycle(self, tracker):
        """Critical path: full lifecycle works correctly."""
        # Start
        tracker.start("Analyzing")

        # Process packages
        tracker.update("pkg-1", discovered=3)
        tracker.update("pkg-2")
        tracker.update("pkg-3")
        tracker.update("pkg-4")

        # Finish
        tracker.finish()
        tracker.stop()

        assert tracker.processed == 4
        assert tracker.total_discovered == 3
