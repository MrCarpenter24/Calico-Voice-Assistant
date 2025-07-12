#!/usr/bin/env python3
"""
calico_skill_service.py - Refactored Calico skill loader and dispatcher
======================================================================
This service loads all available skills from the 'skills' directory on
startup. It listens for MQTT messages from Rhasspy and dispatches them
to the appropriate skill object for handling.
"""

import json
import logging
import os
import sys
import time
import importlib.util
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("FATAL: paho-mqtt is required. Please run 'pip install paho-mqtt'.")
    sys.exit(1)

# --- Paths & Configuration ---
BASE_DIR = Path.home() / "Documents" / "Calico"
SKILLS_DIR = BASE_DIR / "skills"
LIBRARIES_DIR = BASE_DIR / "libraries"
LOG_DIR = BASE_DIR / "logs"

# Add the project root to the Python path to allow imports from `libraries`
sys.path.append(str(BASE_DIR))

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
LOG_FILE = LOG_DIR / "calico_skill_service.log"
LOG_MAX_LINES = 2500

# This global dictionary will store all loaded skill instances
LOADED_SKILLS = {}
# This set will store the unique skill instances to prevent duplicate processing
UNIQUE_SKILL_INSTANCES = set()


# --- Logging Setup ---
def setup_logging():
    """Configures the main service logger."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.touch(exist_ok=True)
    
    # Trim the log file to prevent it from growing indefinitely
    try:
        lines = LOG_FILE.read_text().splitlines()
        if len(lines) > LOG_MAX_LINES:
            LOG_FILE.write_text("\n".join(lines[-LOG_MAX_LINES:]) + "\n")
    except Exception as e:
        print(f"Warning: Could not rotate log file {LOG_FILE}: {e}")

    # Get the root logger.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear any existing handlers to prevent duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Create a formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Create a handler to write to the log file
    file_handler = logging.FileHandler(LOG_FILE, mode='a')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Create a handler to write to the console (stdout)
    #stream_handler = logging.StreamHandler(sys.stdout)
    #stream_handler.setFormatter(formatter)
    #root_logger.addHandler(stream_handler)
    
    logging.info("Logging configured.")


# --- Skill Loading ---
def load_skills(client):
    """
    Scans the SKILLS_DIR, imports each skill as a module, and instantiates
    its main skill class, passing the MQTT client to it.
    """
    logging.info("--- Starting Skill Loading Process ---")
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    for skill_file in SKILLS_DIR.glob("*.py"):
        if skill_file.name.startswith("_"):
            logging.info(f"Skipping file: {skill_file.name}")
            continue

        try:
            module_name = skill_file.stem
            # Standard naming convention: 'ask_me_colors.py' -> 'AskMeColorsSkill'
            class_name = "".join(word.capitalize() for word in module_name.split('_')) + "Skill"
            
            logging.info(f"Attempting to load skill '{class_name}' from {skill_file.name}...")

            # Import the module dynamically
            spec = importlib.util.spec_from_file_location(module_name, skill_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, class_name):
                SkillClass = getattr(module, class_name)
                # Create an instance of the skill class
                skill_instance = SkillClass(client)
                
                # Store the instance, keyed by its trigger and answer intents
                LOADED_SKILLS[skill_instance.intent_name] = skill_instance
                LOADED_SKILLS[skill_instance.answer_intent] = skill_instance
                UNIQUE_SKILL_INSTANCES.add(skill_instance)
                
                logging.info(f"Successfully loaded skill '{class_name}'. Listening for intents: "
                             f"'{skill_instance.intent_name}' and '{skill_instance.answer_intent}'.")
            else:
                logging.warning(f"Could not find class '{class_name}' in {skill_file.name}. "
                                "Please check the file and class naming convention.")

        except Exception:
            logging.exception(f"Failed to load skill from {skill_file.name}.")
    
    if not LOADED_SKILLS:
        logging.warning("No skills were loaded. The 'skills' directory might be empty or "
                        "there may be errors in the skill files.")
    logging.info("--- Skill Loading Complete ---")


# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the MQTT broker."""
    if rc == 0:
        logging.info("Successfully connected to MQTT broker.")
        # Subscribe to all intents and the 'not recognized' topic
        client.subscribe("hermes/intent/#")
        client.subscribe("hermes/nlu/intentNotRecognized")
        logging.info("Subscribed to 'hermes/intent/#' and 'hermes/nlu/intentNotRecognized'.")
    else:
        logging.error(f"Failed to connect to MQTT broker with code: {rc}")

def on_message(client, userdata, msg):
    """
    Primary MQTT message handler. This function dispatches messages
    to the appropriate skill object.
    """
    try:
        payload = json.loads(msg.payload)
        topic = msg.topic

        # --- Handle Intent Not Recognized ---
        if topic == "hermes/nlu/intentNotRecognized":
            session_id = payload.get("sessionId")
            if not session_id:
                return # Ignore if there's no session ID

            logging.warning(f"Intent not recognized for session: {session_id}. Searching for active skill.")
            
            # Iterate over the unique set of skills to find which one is active in this session.
            # This is more robust and prevents potential duplicate handling.
            active_skill_found = False
            for skill in UNIQUE_SKILL_INSTANCES:
                if hasattr(skill, 'session_id') and skill.session_id == session_id:
                    logging.info(f"Found active skill '{type(skill).__name__}' for session. Dispatching.")
                    skill.handle_intent_not_recognized(payload)
                    active_skill_found = True
                    break # Stop after finding the active skill
            
            if not active_skill_found:
                logging.info("No active skill conversation found for this session.")
            return

        # --- Handle Recognized Intents ---
        intent_name = payload.get("intent", {}).get("intentName", "")
        if not intent_name:
            logging.warning("Received message on intent topic without an intent name.")
            return
            
        logging.info(f"Received intent: '{intent_name}'")

        if intent_name in LOADED_SKILLS:
            skill_to_handle = LOADED_SKILLS[intent_name]
            logging.info(f"Dispatching intent '{intent_name}' to skill '{type(skill_to_handle).__name__}'.")
            skill_to_handle.handle_intent(payload)
        else:
            logging.warning(f"Received intent '{intent_name}' but no skill is loaded to handle it.")
            # Optional: send a TTS message for unhandled intents
            # client.publish("hermes/tts/say", json.dumps({"text": "I don't know how to handle that command.", "siteId": payload.get("siteId")}))

    except json.JSONDecodeError:
        logging.error(f"Could not decode JSON from MQTT message on topic: {msg.topic}")
    except Exception as e:
        logging.exception("An unexpected error occurred in on_message: %s", e)

def on_disconnect(client, userdata, rc):
    logging.warning(f"Disconnected from MQTT broker (code: {rc}). Will attempt to reconnect.")


# --- Main Execution ---
def main():
    """Initializes and runs the skill service."""
    setup_logging()
    logging.info("Calico Skill Service - Starting")

    client = mqtt.Client(client_id="calico_skill_service")
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    # Load all skill modules before starting the MQTT loop
    load_skills(client)

    # Main loop to connect and reconnect to MQTT
    while True:
        try:
            logging.info(f"Attempting to connect to MQTT at {MQTT_HOST}:{MQTT_PORT}...")
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_forever()
        except KeyboardInterrupt:
            logging.info("Skill service stopped by user.")
            sys.exit(0)
        except ConnectionRefusedError:
            logging.error("Connection refused. Is the MQTT broker running?")
        except Exception as e:
            logging.exception("An error occurred in the main MQTT loop: %s", e)
        
        logging.info("Reconnecting in 5 seconds...")
        time.sleep(5)

if __name__ == "__main__":
    main()
