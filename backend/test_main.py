import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Bootstrap: ensure .env is loaded before importing config/main so all
# constants resolve correctly during tests.
# config.py handles load_dotenv internally — we just need to make sure
# JWT_SECRET is set so the startup guard doesn't raise.
# ---------------------------------------------------------------------------
_this_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_this_dir)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_root_dir, ".env"))
    load_dotenv(os.path.join(_this_dir, ".env"), override=True)
except ImportError:
    pass

# Fallback: ensure JWT_SECRET is always set so the startup guard never raises.
if not os.getenv("JWT_SECRET"):
    os.environ["JWT_SECRET"] = "test-secret-for-unit-tests-only"

# Ensure mock auth is disabled by default during tests unless overridden.
if not os.getenv("ENABLE_MOCK_AUTH"):
    os.environ["ENABLE_MOCK_AUTH"] = "false"

from PIL import Image

sys.path.insert(0, _this_dir)
import config as cfg
import main



class ExecuteSystemActionTests(unittest.TestCase):
    def test_executor_uses_top_level_desktop_primitives(self):
        with patch("main.subprocess.Popen") as popen_mock, \
             patch("main.pyautogui.hotkey") as hotkey_mock, \
             patch("main.pyperclip.copy") as copy_mock, \
             patch("main.time.sleep") as sleep_mock:
            result = main.execute_system_action([
                {"type": "LAUNCH", "payload": "notepad.exe"},
                {"type": "WAIT", "payload": "1.5"},
                {"type": "PASTE", "payload": "hello"},
                {"type": "SHORTCUT", "payload": "ctrl+s"},
            ])

        self.assertEqual(result["status"], "success")
        popen_mock.assert_called_once_with("notepad.exe", shell=True)
        sleep_mock.assert_any_call(1.5)
        copy_mock.assert_called_once_with("hello")
        hotkey_mock.assert_any_call("ctrl", "v")
        hotkey_mock.assert_any_call("ctrl", "s")

    def test_capture_desktop_state_returns_frame_dimensions(self):
        with patch("main.ImageGrab.grab", return_value=Image.new("RGB", (120, 80))):
            state = main.capture_desktop_state()

        self.assertEqual(state["width"], 120)
        self.assertEqual(state["height"], 80)
        self.assertIn("rgb_array", state)

    def test_execute_agent_action_handles_native_tool_calls(self):
        with patch("main.subprocess.Popen") as popen_mock, \
             patch("main.pyautogui.click") as click_mock, \
             patch("main.pyautogui.write") as write_mock, \
             patch("main.pyautogui.hotkey") as hotkey_mock:
            click_result = main.execute_agent_action({"action": "MOUSE_CLICK", "x": 10, "y": 20})
            type_result = main.execute_agent_action({"action": "TYPE_TEXT", "text": "hello"})
            shortcut_result = main.execute_agent_action({"action": "KEYBOARD_SHORTCUT", "keys": ["ctrl", "s"]})
            shell_result = main.execute_agent_action({"action": "SHELL_EXECUTE", "command": "notepad.exe"})

        self.assertEqual(click_result["status"], "success")
        self.assertEqual(type_result["status"], "success")
        self.assertEqual(shortcut_result["status"], "success")
        self.assertEqual(shell_result["status"], "success")
        click_mock.assert_called_once_with(10, 20)
        write_mock.assert_called_once_with("hello", interval=0.01)
        hotkey_mock.assert_any_call("ctrl", "s")
        popen_mock.assert_called_once_with("notepad.exe", shell=True)

    def test_handle_command_uses_smart_launch_for_open_requests(self):
        """
        Verifies that handle_command routes 'open X' through smart_launch()
        instead of any hardcoded alias map.  smart_launch is mocked here so
        the test does not depend on what is installed on the CI machine.
        """
        with patch("main.smart_launch", return_value="Dynamically discovered and opened calculator") as launch_mock:
            result = main.handle_command("open calculator")

        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["message"], "Success")
        launch_mock.assert_called_once_with("calculator")

    def test_handle_command_routes_search_to_web(self):
        """'search X' must open a browser search URL, never a local launcher."""
        with patch("main.webbrowser.open") as wb_mock:
            result = main.handle_command("search python tutorials")

        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "success")
        self.assertIn("python tutorials", result["message"].lower())
        wb_mock.assert_called_once()

    def test_handle_command_returns_ambiguity_on_low_confidence(self):
        """Inputs that are neither 'open X' nor 'search X' get the disambiguation prompt."""
        result = main.handle_command("python tutorials")
        self.assertIsNotNone(result)
        self.assertIn("Did you mean", result["message"])

    def test_verify_required_config_detects_missing_keys(self):
        """Startup guard must report every key that is absent from the environment."""
        # Temporarily clear a required key and verify it appears in the missing list.
        original = os.environ.pop("OLLAMA_ENDPOINT", None)
        try:
            missing = main.verify_required_config()
            self.assertIn("OLLAMA_ENDPOINT", missing)
        finally:
            if original is not None:
                os.environ["OLLAMA_ENDPOINT"] = original


if __name__ == "__main__":
    unittest.main()
