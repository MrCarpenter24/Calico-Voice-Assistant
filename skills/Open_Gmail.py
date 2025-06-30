# Calico/skills/Open_Gmail.py
"""
This skill opens Gmail in the user's default web browser.
It demonstrates a simple, non-conversational "one-shot" skill.
"""

# We need to adjust the path to import from the parent directory's 'libraries' folder
import sys
import webbrowser
from pathlib import Path

# Add the project's root directory (Calico) to the Python path
# This allows us to import from the 'libraries' module
sys.path.append(str(Path(__file__).resolve().parents[1]))

from libraries.base_skill import BaseSkill

class OpenGmailSkill(BaseSkill):
    """A skill that opens Gmail in the browser."""

    def __init__(self, mqtt_client):
        # This skill is triggered by the "Open_Gmail" intent.
        # It has no follow-up question, so the answer_intent is empty.
        super().__init__(
            intent_name="Open_Gmail",
            answer_intent="",  # No answer is expected
            mqtt_client=mqtt_client
        )

    def handle_intent(self, message: dict):
        """
        Handles the logic for the Open_Gmail intent.
        """
        # This call sets self.session_id and self.site_id from the message
        super().handle_intent(message)

        url = "https://mail.google.com"
        self.log.info("Attempting to open Gmail.")

        try:
            webbrowser.open(url, new=0, autoraise=True)
            self.log.info(f"Successfully opened {url} in browser.")
            # The speak() method gives a verbal confirmation and ends the session.
            self.speak("Here is your inbox.")
        except Exception as e:
            self.log.error(f"Failed to open web browser: {e}", exc_info=True)
            self.speak("Sorry, I could not open your inbox right now.")
