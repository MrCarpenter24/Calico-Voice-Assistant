# Calico/skills/Tell_Time.py
"""
Tells the user the current time as sourced from their operating system.
"""

# We need to adjust the path to import from the parent directory's 'libraries' folder
import sys, datetime, random
from pathlib import Path

# Add the project's root directory (Calico) to the Python path
# This allows us to import from the 'libraries' module
sys.path.append(str(Path(__file__).resolve().parents[1]))

from libraries.base_skill import BaseSkill

class TellTimeSkill(BaseSkill):
    """
    A skill that tells the user the current time in 12-hour format.
    Uses varied replies to create nuance.
    """

    def __init__(self, mqtt_client):
        # This skill is triggered by the "Tell_Time" intent.
        # It has no follow-up question, so the answer_intent is empty.
        super().__init__(
            intent_name="Tell_Time",
            answer_intent="",  # No answer is expected
            mqtt_client=mqtt_client
        )

    def handle_intent(self, message: dict):
        """
        Handles the logic for the Tell_Time intent.
        """
        # This call sets self.session_id and self.site_id from the message
        super().handle_intent(message)
    
        try:
            now = datetime.datetime.now()
            cycle = "ae em"

            if (now.strftime('%p')) == "PM":
                cycle = "pee em"

            replies = ["The time is",
                    "It is currently",
                    "The clock says it's"]
            say = random.choice(replies)

            self.speak(f"{say} {now.strftime('%I')} {now.minute}, {cycle}.")
            self.log.info("Successfully spoke the current time to the user.")
        except Exception as e:
            # Alternative sentence if something goes wrong
            self.speak("Sorry, I couldn't fetch the time.")
            self.log.error("Failed to tell the user the current time. Error: %s", e)
