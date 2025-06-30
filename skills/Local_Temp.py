# Calico/skills/Local_Temp.py
"""
Simple skill to pull local temperature using ipinfo.io service
and Open-Meteo API.
"""

# We need to adjust the path to import from the parent directory's 'libraries' folder
import sys, requests, json, os
from pathlib import Path

# Add the project's root directory (Calico) to the Python path
# This allows us to import from the 'libraries' module
sys.path.append(str(Path(__file__).resolve().parents[1]))

from libraries.base_skill import BaseSkill

class LocalTempSkill(BaseSkill):
    """
    A skill that gives the user the local temperature based on
    the zip code entered in settings.
    """

    def __init__(self, mqtt_client):
        # This skill is triggered by the "Local_Temp" intent.
        # It has no follow-up question, so the answer_intent is empty.
        super().__init__(
            intent_name="Local_Temp",
            answer_intent="",  # No answer is expected
            mqtt_client=mqtt_client
        )

    def load_and_validate_config(self):
        """
        Loads settings from config.json, validates required fields, 
        and returns them.
        """
        # Construct the absolute path to config.json
        # Assumes this script is in a 'scripts' folder, and 'settings' is a sibling folder.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, '..', 'settings', 'config.json')

        if not os.path.exists(config_path):
            raise FileNotFoundError("Configuration file (config.json) not found.")

        with open(config_path, 'r') as f:
            config = json.load(f)

        # Validate that required settings exist and are not empty
        zip_code = config.get("zip_code")
        region = config.get("region")
        temp_unit = config.get("temp_unit")

        if not zip_code:
            raise ValueError("Zip code is not set in the configuration file.")
        if not region:
            raise ValueError("Region is not set in the configuration file.")
        if not temp_unit:
            raise ValueError("Temperature unit is not set in the configuration file.")
            
        return zip_code, region, temp_unit

    def zip_to_latlon(self, zip_code: str, country: str = "us"):
        """Return (lat, lon, city, state) for a postal code using Zippopotam.us."""
        url = f"http://api.zippopotam.us/{country}/{zip_code}"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            raise ValueError(f"ZIP lookup failed ({resp.status_code}).")
        data = resp.json()
        place = data["places"][0]          # always at least one place when 200 OK
        return (
            float(place["latitude"]),
            float(place["longitude"]),
            place["place name"],
            place["state"]
        )

    def get_temperature(self, lat: float, lon: float):
        """Return current temperature in °C from Open-Meteo."""
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&current_weather=true"
        )
        data = requests.get(url, timeout=5).json()
        return data["current_weather"]["temperature"]

    def handle_intent(self, message: dict):
        """
        Handles the logic for the Local_Temp intent.
        """
        # This call sets self.session_id and self.site_id from the message
        super().handle_intent(message)

        try:
            # Load settings from config file first
            ZIP_CODE, COUNTRY, TEMP_UNIT = self.load_and_validate_config()

            # Use loaded settings to get weather data
            lat, lon, city, state = self.zip_to_latlon(ZIP_CODE, COUNTRY)
            temp_c = self.get_temperature(lat, lon)
            
            place = f"{city}, {state}" if city and state else "your area"

            # Format the output based on the user's preferred unit
            if TEMP_UNIT == 'f':
                temp_f = temp_c * 9 / 5 + 32
                self.speak(f"It's currently {temp_f:.1f} degrees Fahrenheit in {place}.")
            else: # Default to Celsius
                self.speak(f"It's currently {temp_c:.1f} degrees Celsius in {place}.")
            self.log.info("Successfully provided local temperature to the user.")
        except Exception as e:
            # Alternative sentence if something goes wrong
            self.log.info("Faied to provide the user with local temperature. Error: %s", e)
            self.speak("Sorry, I can't get the temperature right now.")
