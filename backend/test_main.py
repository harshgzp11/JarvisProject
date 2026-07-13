import os
import sys
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
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


if __name__ == "__main__":
    unittest.main()
