# Calico/skills/Ask_Me_Colors.py
"""
This skill asks the user for their favorite color and then responds.
It demonstrates a simple two-turn conversation using a state machine.
"""

# We need to adjust the path to import from the parent directory's 'libraries' folder
import sys
from pathlib import Path

# Add the project's root directory (Calico) to the Python path
# This allows us to import from the 'libraries' module
sys.path.append(str(Path(__file__).resolve().parents[1]))

from libraries.base_skill import BaseSkill

class AskMeColorsSkill(BaseSkill):
    """A skill that asks for a favorite color and responds."""

    def __init__(self, mqtt_client):
        # The main intent that starts this skill is "Ask_Me_Colors"
        # The intent we listen for as an answer is "Answer_Colors"
        super().__init__(
            intent_name="Ask_Me_Colors",
            answer_intent="Answer_Colors",
            mqtt_client=mqtt_client
        )
        # This skill has a simple state machine: 'initial' or 'waiting_for_color'
        self.conversation_state = "initial"

    def handle_intent(self, message: dict):
        """
        Handles the logic for the Ask_Me_Colors and Answer_Colors intents.
        """
        # This call sets self.session_id and self.site_id from the message
        super().handle_intent(message)

        intent_name = message.get("intent", {}).get("intentName", "")

        # --- Logic for the first turn (triggered by "Ask_Me_Colors") ---
        if intent_name == self.intent_name and self.conversation_state == "initial":
            self.log.info("Starting 'Ask Me Colors' conversation.")
            # Change state to indicate we are now waiting for an answer
            self.conversation_state = "waiting_for_color"
            # Ask the question and keep the session open
            self.continue_session("What is your favorite color?")

        # --- Logic for the second turn (triggered by "Answer_Colors") ---
        elif intent_name == self.answer_intent and self.conversation_state == "waiting_for_color":
            user_color = message.get("input", "that color")
            self.log.info(f"User responded with color: {user_color}")

            # You could add more complex logic here, like checking slots
            # or having different responses for different colors.

            self.speak(f"Wow! {user_color} is a great color. Mine is orange.")

            # Reset state for the next time the skill is triggered
            self.log.info("Conversation finished. Resetting state.")
            self.conversation_state = "initial"
            # The self.speak() method calls self.end_session() by default
