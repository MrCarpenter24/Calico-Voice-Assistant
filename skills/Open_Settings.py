# Calico/skills/Open_Settings.py
"""
Opens settings GUI, an application specific to user
prefrences - does not interfere with Rhasspy core.
"""

# We need to adjust the path to import from the parent directory's 'libraries' folder
import sys, os, subprocess
from pathlib import Path

# Add the project's root directory (Calico) to the Python path
# This allows us to import from the 'libraries' module
sys.path.append(str(Path(__file__).resolve().parents[1]))

from libraries.base_skill import BaseSkill

class OpenSettingsSkill(BaseSkill):
    """A skill that opens a simple settings GUI for the user."""

    def __init__(self, mqtt_client):
        # This skill is triggered by the "Open_Settings" intent.
        # It has no follow-up question, so the answer_intent is empty.
        super().__init__(
            intent_name="Open_Settings",
            answer_intent="",  # No answer is expected
            mqtt_client=mqtt_client
        )

    def handle_intent(self, message: dict):
        """
        Handles the logic for the Open_Settings intent.
        """

        # This call sets self.session_id and self.site_id from the message
        super().handle_intent(message)

        self.log.info("Attempting to open settings GUI.")

        try:
            # Logic to run settings.py, located in the adjacent /settings folder.

            # Get the absolute path to the directory containing this script.
            current_dir = os.path.dirname(os.path.abspath(__file__))

            # Construct the path to settings.py.
            settings_script_path = os.path.join(current_dir, '..', 'settings', 'settings.py')

            # Launch the settings GUI in a new, non-blocking process.
            # output streams. This prevents the parent script from hanging.
            subprocess.Popen(
                [sys.executable, settings_script_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # ── Sentence Rhasspy will say on success
            self.log.info("Successfully opened settings.")
            self.speak("Opening settings.")
        except Exception as e:
            # Alternative sentence if something goes wrong
            self.log.error("Failed to open settings. Error: %s", e)
            self.speak("Sorry, I couldn't open settings.")