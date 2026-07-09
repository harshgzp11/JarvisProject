import os
import sys
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
