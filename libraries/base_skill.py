# Calico/libraries/base_skill.py
"""
This module provides the BaseSkill abstract class, which is the foundation
for all Calico skills. It handles MQTT communication, session management,
state, logging, and a retry mechanism for conversations.
"""

import json
import logging
import random
from abc import ABC, abstractmethod
from pathlib import Path

# --- Constants ---
LOG_MAX_LINES = 500
MAX_RETRIES = 3
RETRY_MESSAGES = [
    "I'm sorry, I didn't catch that. Could you say it again?",
    "I didn't quite get that. Please repeat yourself.",
    "Could you say that one more time?",
    "I'm having a little trouble understanding. What was that?",
]

class BaseSkill(ABC):
    """
    Abstract base class for all Calico skills.

    Each skill that inherits from this class will have its own logger,
    state management, and methods for communicating with the Rhasspy
    dialogue manager via MQTT.
    """

    def __init__(self, intent_name: str, answer_intent: str, mqtt_client):
        """
        Initializes the skill.

        Args:
            intent_name (str): The primary intent name that triggers this skill.
            answer_intent (str): The intent name to listen for in follow-up turns.
            mqtt_client: The shared paho.mqtt.client instance.
        """
        self.intent_name = intent_name
        self.answer_intent = answer_intent
        self.mqtt_client = mqtt_client

        # Session-specific variables, reset for each interaction
        self.session_id = None
        self.site_id = None
        self.retries = 0

        # Define path to config file for use in helper function
        self.config_path = Path.home() / "Documents" / "Calico" / "settings" / "config.json"

        # --- Set up dedicated logger for the skill ---
        log_dir = Path.home() / "Documents" / "Calico" / "logs" / "skills"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{self.intent_name}.log"

        # Trim the log file to prevent it from growing indefinitely
        try:
            lines = log_file.read_text().splitlines()
            if len(lines) > LOG_MAX_LINES:
                log_file.write_text("\n".join(lines[-LOG_MAX_LINES:]) + "\n")
        except Exception as e:
            print(f"Warning: Could not rotate log file {log_file}: {e}")

        # The logger name is based on the skill's intent name
        logger_name = f"skill.{self.intent_name}"
        self.log = logging.getLogger(logger_name)

        # Prevents adding duplicate handlers if skill is reloaded
        if not self.log.handlers:
            self.log.setLevel(logging.INFO)
            # Create a file handler to write logs to a file
            fh = logging.FileHandler(log_file, mode='a')
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            fh.setFormatter(formatter)
            self.log.addHandler(fh)

    def get_config(self, key: str, default=None):
        """
        Loads a value from the central config.json file.

        Args:
            key (str): The specific key to retrieve from the config file.
            default: The value to return if the key is not found.

        Returns:
            The value from the config file, or the default value.
        """
        try:
            if not self.config_path.exists():
                self.log.warning("Configuration file (config.json) not found.")
                return default
            
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            return config.get(key, default)

        except json.JSONDecodeError:
            self.log.error("Could not decode config.json. Please check for syntax errors.")
            return default
        except Exception as e:
            self.log.error(f"An unexpected error occurred while reading config: {e}")
            return default

    def _publish(self, topic: str, payload: dict):
        """Private helper to publish a JSON payload to an MQTT topic."""
        try:
            self.log.info(f"Publishing to MQTT topic: {topic}")
            self.log.info(f"Payload: {json.dumps(payload)}")
            self.mqtt_client.publish(topic, json.dumps(payload))
        except Exception as e:
            self.log.error(f"Failed to publish to MQTT topic {topic}: {e}", exc_info=True)

    def speak(self, text: str, end_the_session: bool = True):
        """
        Speaks a sentence. By default, it also ends the conversation.
        """
        if not self.site_id:
            self.log.error("Cannot use speak() without a valid site_id.")
            return

        self.log.info(f"Speaking response: '{text}'")
        self._publish("hermes/tts/say",{"text": text, "siteId": self.site_id})

        if end_the_session and self.session_id:
            self.end_session()

    def end_session(self, text: str = ""):
        """Explicitly ends the current dialogue session."""
        if not self.session_id:
            self.log.warning("Attempted to end a session that was not active.")
            return

        self.log.info(f"Ending session {self.session_id}")
        self._publish("hermes/dialogueManager/endSession", {"sessionId": self.session_id, "text": text})
        # Clear session data after ending
        self._clear_session()

    def continue_session(self, text_to_speak: str):
        """
        Asks a follow-up question and keeps the session alive,
        listening for the skill's specific answer_intent.
        """
        if not self.session_id:
            self.log.error("Cannot continue a session that is not active.")
            return

        self.log.info(f"Continuing session {self.session_id}, asking: '{text_to_speak}'")

        self._publish("hermes/dialogueManager/continueSession", {
            "sessionId": self.session_id,
            "text": text_to_speak,
            "intentFilter": [self.answer_intent],
            #"customData": json.dumps({"origin": self.intent_name}), # Add customData to the payload
            "sendIntentNotRecognized": True, # Critical for retry logic
        })

    def _clear_session(self):
        """Resets all session-specific variables."""
        self.session_id = None
        self.site_id = None
        self.retries = 0
        # The skill's internal state should be reset within the skill's own logic
        self.log.info("Session data cleared.")

    def _prepare_for_intent(self, message: dict):
        """
        Prepares the skill for handling a new intent message by setting
        session variables. To be called at the start of handle_intent.
        """
        self.session_id = message.get("sessionId")
        self.site_id = message.get("siteId")
        self.log.info(f"Handling intent for session: {self.session_id}, site: {self.site_id}")

    @abstractmethod
    def handle_intent(self, message: dict):
        """
        Main entry point for the skill, called by the skill service.
        The implementation in the child class must handle the skill's logic.

        Args:
            message (dict): The full JSON payload from the hermes/intent message.
        """
        self._prepare_for_intent(message)
        # The rest of the logic is implemented in the child skill class
        pass

    def handle_intent_not_recognized(self, message: dict):
        """
        Handles the hermes/nlu/intentNotRecognized message.
        This is called by the service when Rhasspy fails to understand the user
        during a continued session with this skill.
        """
        if message.get("sessionId") != self.session_id:
            # This message is not for this skill's active session, ignore it.
            return

        self.retries += 1
        self.log.warning(f"Intent not recognized. Retry attempt {self.retries}/{MAX_RETRIES}.")

        if self.retries >= MAX_RETRIES:
            self.log.error("Maximum retry limit reached. Ending conversation.")
            self.speak("I'm still not understanding. Let's try again later.")
            # self.end_session() is called by self.speak()
        else:
            # Ask the user to repeat themselves with a random prompt
            retry_prompt = random.choice(RETRY_MESSAGES)
            self.continue_session(retry_prompt)
