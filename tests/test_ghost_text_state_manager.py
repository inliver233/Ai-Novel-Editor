# tests/test_ghost_text_state_manager.py

import unittest
import sys
import os
from unittest.mock import Mock

# Add the project root to the Python path to allow for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.gui.editor.ghost_text_state_manager import GhostTextStateManager, GhostTextState
from PyQt6.QtCore import QObject, pyqtSignal

class TestGhostTextStateManager(unittest.TestCase):

    def setUp(self):
        """Set up the test environment."""
        self.manager = GhostTextStateManager()
        self.mock_state_changed = Mock()
        self.mock_completion_updated = Mock()
        self.mock_text_accepted = Mock()
        self.mock_text_to_clear = Mock()

        self.manager.state_changed.connect(self.mock_state_changed)
        self.manager.completion_updated.connect(self.mock_completion_updated)
        self.manager.text_accepted.connect(self.mock_text_accepted)
        self.manager.text_to_clear.connect(self.mock_text_to_clear)


    def test_initial_state(self):
        """Test that the initial state is IDLE."""
        self.assertEqual(self.manager.state, GhostTextState.IDLE)
        self.assertFalse(self.manager.is_active())
        self.assertEqual(self.manager.completion, "")

    def test_request_completion_from_idle(self):
        """Test requesting completion from IDLE state."""
        result = self.manager.request_completion()
        self.assertTrue(result)
        self.assertEqual(self.manager.state, GhostTextState.GENERATING)
        self.assertTrue(self.manager.is_active())
        self.mock_state_changed.assert_called_once_with(GhostTextState.GENERATING)

    def test_request_completion_when_active_fails(self):
        """Test that requesting completion fails when not in IDLE state."""
        # From GENERATING
        self.manager.set_state(GhostTextState.GENERATING)
        self.mock_state_changed.reset_mock()
        result = self.manager.request_completion()
        self.assertFalse(result)
        self.assertEqual(self.manager.state, GhostTextState.GENERATING)
        self.mock_state_changed.assert_not_called()

        # From VISIBLE
        self.manager.set_state(GhostTextState.VISIBLE)
        self.mock_state_changed.reset_mock()
        result = self.manager.request_completion()
        self.assertFalse(result)
        self.assertEqual(self.manager.state, GhostTextState.VISIBLE)
        self.mock_state_changed.assert_not_called()

    def test_show_completion_from_generating(self):
        """Test showing a completion from GENERATING state."""
        self.manager.set_state(GhostTextState.GENERATING)
        test_text = "This is a test completion."
        result = self.manager.show(test_text)
        self.assertTrue(result)
        self.assertEqual(self.manager.state, GhostTextState.VISIBLE)
        self.assertEqual(self.manager.completion, test_text)
        self.mock_state_changed.assert_called_with(GhostTextState.VISIBLE)
        self.mock_completion_updated.assert_called_once_with(test_text)

    def test_show_completion_from_wrong_state_fails(self):
        """Test that showing a completion fails if not in GENERATING state."""
        test_text = "This is a test completion."
        # From IDLE
        result = self.manager.show(test_text)
        self.assertFalse(result)
        self.assertEqual(self.manager.state, GhostTextState.IDLE)

        # From VISIBLE
        self.manager.set_state(GhostTextState.VISIBLE)
        result = self.manager.show(test_text)
        self.assertFalse(result)
        self.assertEqual(self.manager.state, GhostTextState.VISIBLE)

    def test_accept_completion_from_visible(self):
        """Test accepting a completion from VISIBLE state."""
        test_text = "Accepted text."
        self.manager.set_state(GhostTextState.GENERATING)
        self.manager.show(test_text)
        self.mock_state_changed.reset_mock()
        self.mock_completion_updated.reset_mock()

        result = self.manager.accept()
        self.assertTrue(result)
        self.assertEqual(self.manager.state, GhostTextState.IDLE)
        self.assertEqual(self.manager.completion, "") # Completion should be cleared
        self.mock_state_changed.assert_called_with(GhostTextState.IDLE)
        self.mock_text_accepted.assert_called_once_with(test_text)
        self.mock_completion_updated.assert_called_once_with("")

    def test_accept_completion_from_wrong_state_fails(self):
        """Test that accepting fails if not in VISIBLE state."""
        # From IDLE
        result = self.manager.accept()
        self.assertFalse(result)
        self.assertEqual(self.manager.state, GhostTextState.IDLE)

        # From GENERATING
        self.manager.set_state(GhostTextState.GENERATING)
        result = self.manager.accept()
        self.assertFalse(result)
        self.assertEqual(self.manager.state, GhostTextState.GENERATING)

    def test_reject_completion_from_visible(self):
        """Test rejecting a completion from VISIBLE state."""
        self.manager.set_state(GhostTextState.GENERATING)
        self.manager.show("some text")
        self.mock_state_changed.reset_mock()

        result = self.manager.reject()
        self.assertTrue(result)
        self.assertEqual(self.manager.state, GhostTextState.IDLE)
        self.assertFalse(self.manager.is_active())
        self.mock_state_changed.assert_called_with(GhostTextState.IDLE)
        self.mock_text_to_clear.assert_called_once()

    def test_reject_completion_from_generating(self):
        """Test rejecting a completion from GENERATING state."""
        self.manager.set_state(GhostTextState.GENERATING)
        self.mock_state_changed.reset_mock()

        result = self.manager.reject()
        self.assertTrue(result)
        self.assertEqual(self.manager.state, GhostTextState.IDLE)
        self.mock_state_changed.assert_called_with(GhostTextState.IDLE)
        self.mock_text_to_clear.assert_called_once()

    def test_reject_completion_from_idle_does_nothing(self):
        """Test that rejecting from IDLE state does nothing."""
        result = self.manager.reject()
        self.assertFalse(result)
        self.assertEqual(self.manager.state, GhostTextState.IDLE)
        self.mock_text_to_clear.assert_not_called()

class TestGhostTextIntegration(unittest.TestCase):
    """
    These tests simulate the interaction between a higher-level controller
    (like SmartCompletionManager) and the GhostTextStateManager.
    """
    def setUp(self):
        self.manager = GhostTextStateManager()
        # Mock external components
        self.mock_text_editor = Mock()
        self.mock_smart_completion_manager = Mock()

        # Connect signals for verification
        self.mock_text_accepted_handler = Mock()
        self.mock_text_to_clear_handler = Mock()
        self.manager.text_accepted.connect(self.mock_text_accepted_handler)
        self.manager.text_to_clear.connect(self.mock_text_to_clear_handler)

    def test_happy_path_accept(self):
        """Simulate the full flow: request -> show -> accept."""
        # 1. Request completion
        self.assertTrue(self.manager.request_completion())
        self.assertEqual(self.manager.state, GhostTextState.GENERATING)

        # 2. AI provides text, manager shows it
        completion_text = "This is the happy path."
        self.assertTrue(self.manager.show(completion_text))
        self.assertEqual(self.manager.state, GhostTextState.VISIBLE)
        self.assertEqual(self.manager.completion, completion_text)

        # 3. User accepts (e.g., presses Tab)
        self.assertTrue(self.manager.accept())
        self.assertEqual(self.manager.state, GhostTextState.IDLE)
        self.mock_text_accepted_handler.assert_called_once_with(completion_text)
        self.mock_text_to_clear_handler.assert_not_called()

    def test_happy_path_reject(self):
        """Simulate the full flow: request -> show -> reject."""
        # 1. Request completion
        self.assertTrue(self.manager.request_completion())
        self.assertEqual(self.manager.state, GhostTextState.GENERATING)

        # 2. AI provides text, manager shows it
        completion_text = "This is the rejection path."
        self.assertTrue(self.manager.show(completion_text))
        self.assertEqual(self.manager.state, GhostTextState.VISIBLE)

        # 3. User rejects (e.g., presses Esc)
        self.assertTrue(self.manager.reject())
        self.assertEqual(self.manager.state, GhostTextState.IDLE)
        self.mock_text_to_clear_handler.assert_called_once()
        self.mock_text_accepted_handler.assert_not_called()

    def test_typing_rejection(self):
        """Simulate user typing another character while ghost text is visible."""
        # 1. Ghost text is visible
        self.manager.set_state(GhostTextState.GENERATING)
        self.manager.show("Some ghost text.")
        self.assertEqual(self.manager.state, GhostTextState.VISIBLE)

        # 2. Higher-level manager detects a key press that is not Tab/Esc
        #    and decides to reject the current completion.
        self.assertTrue(self.manager.reject())
        self.assertEqual(self.manager.state, GhostTextState.IDLE)
        self.mock_text_to_clear_handler.assert_called_once()
        self.mock_text_accepted_handler.assert_not_called()

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)