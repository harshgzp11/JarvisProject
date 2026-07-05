import subprocess
import pyautogui
import os
import datetime

def launch_application(system_path: str) -> dict:
    """Safely launches an application using its absolute path."""
    try:
        if not os.path.exists(system_path) and not system_path.lower().endswith(".exe"):
            # Simple check if it's a known system executable that might be in PATH
            pass 

        # Using argument list, shell=False to prevent injection
        # Popen to not block the server
        subprocess.Popen([system_path])
        return {"status": "success", "message": f"Launched {os.path.basename(system_path)} successfully."}
    except FileNotFoundError:
        return {"status": "error", "message": "Executable not found. Please verify the system path."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to launch application: {str(e)}"}

def take_screenshot() -> dict:
    """Takes a full-screen screenshot and saves it to a local 'screenshots' directory."""
    try:
        screenshots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = os.path.join(screenshots_dir, filename)
        
        # Pyautogui screenshot
        screenshot = pyautogui.screenshot()
        screenshot.save(filepath)
        
        return {"status": "success", "message": f"Screenshot saved to {filepath}"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to take screenshot: {str(e)}"}

def adjust_media_controls(action: str) -> dict:
    """Simulates media key presses."""
    try:
        if action == "volume_up":
            pyautogui.press("volumeup")
            return {"status": "success", "message": "Volume increased."}
        elif action == "volume_down":
            pyautogui.press("volumedown")
            return {"status": "success", "message": "Volume decreased."}
        elif action == "volume_mute":
            pyautogui.press("volumemute")
            return {"status": "success", "message": "Volume muted/unmuted."}
        elif action == "play_pause":
            pyautogui.press("playpause")
            return {"status": "success", "message": "Media play/pause toggled."}
        else:
            return {"status": "error", "message": "Unknown media action."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to adjust media controls: {str(e)}"}
