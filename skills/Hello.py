# Calico/skills/Hello.py
"""
This skill returns a simple greeting when prompted by the user.
"""

# Imports
import sys, random
from pathlib import Path

# Adding project's root directory to Python Path to import Calico's libraries.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from libraries.base_skill import BaseSkill

class HelloSkill(BaseSkill):
    
    def __init__(self, mqtt_client):
        # Triggered by "Hello" intent.
        # No follow-up, answer intent left blank.
        super().__init__(
            intent_name="Hello",
            answer_intent="",
            mqtt_client=mqtt_client
        )

    def handle_intent(self, message: dict):
        # Main logic - returns random phrase from available list.

        # This call sets self.session_id and self.site_id from the message
        super().handle_intent(message)

        try:

            replies=["Hi!",    # Added missing comma. Adding comment becuase github struggles when only one char is changed.
                    "Hello!",
                    "Hey!",
                    "Hello there!",
                    "Hi there!",
                    "Hey there!",
                    "Hello, human!"
                    ]
            
            say = random.choice(replies)
            self.speak(say)
            self.log.info("successfully spoke a greeting back to the user.")
        except Exception as e:
            self.log.error("Failed to return greeting to the user: %s", e)
            self.speak("Sorry, something went wrong.")
