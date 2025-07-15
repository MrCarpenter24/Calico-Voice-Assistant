# Calico/skills/Local_Forecast.py
"""
A skill to provide a daily weather forecast with multiple levels of detail.
"""

import sys
import requests
from pathlib import Path

# Add the project's root directory to the Python path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from libraries.base_skill import BaseSkill

# WMO Weather interpretation codes from Open-Meteo documentation
WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "A thunderstorm", 96: "A thunderstorm with slight hail", 99: "A thunderstorm with heavy hail",
}

class LocalForecastSkill(BaseSkill):
    """
    A skill that gives the user a local weather forecast for today or tomorrow.
    """

    def __init__(self, mqtt_client):
        super().__init__(
            intent_name="Local_Forecast",
            answer_intent="",
            mqtt_client=mqtt_client
        )
        self.forecast_day = "today"

    def _get_forecast_data(self, lat, lon, temp_unit):
        """Fetches daily forecast data from Open-Meteo."""
        self.log.info(f"Fetching forecast for lat: {lat}, lon: {lon}")
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "current_weather": "true",
            "temperature_unit": "fahrenheit" if temp_unit.lower() == 'f' else "celsius",
            "timezone": "auto"
        }
        url = "https://api.open-meteo.com/v1/forecast"
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _format_forecast(self, weather_data):
        """Formats the main forecast summary."""
        day_index = 0 if self.forecast_day == "today" else 1
        daily_data = weather_data['daily']
        
        high_temp = round(daily_data['temperature_2m_max'][day_index])
        low_temp = round(daily_data['temperature_2m_min'][day_index])
        precip_chance = daily_data['precipitation_probability_max'][day_index]
        weather_code = daily_data['weathercode'][day_index]
        weather_desc = WMO_CODES.get(weather_code, "an unknown weather pattern")

        forecast = f"For {self.forecast_day}, expect {weather_desc}. "
        
        if self.forecast_day == "today":
            current_temp = round(weather_data['current_weather']['temperature'])
            forecast += f"It's currently {current_temp} degrees. "

        forecast += f"The high will be {high_temp} and the low {low_temp}. "
        
        if precip_chance > 10:
            forecast += f"There is a maximum {precip_chance} percent chance of precipitation for the day."
        else:
            forecast += "There is a low chance of precipitation."
            
        return forecast

    def _get_slot_value(self, message: dict, slot_name: str, default=None):
        """Helper function to safely extract a slot value from the slots list."""
        slots = message.get("slots", [])
        for slot in slots:
            if slot.get("slotName") == slot_name:
                return slot.get("value", {}).get("value", default)
        return default

    def handle_intent(self, message: dict):
        """Handles the logic for the Local_Forecast intent."""
        super().handle_intent(message)
        
        self.forecast_day = self._get_slot_value(message, "today_or_tomorrow", "today")
        
        try:
            zip_code = self.get_config("zip_code")
            if not zip_code:
                self.speak("I can't get the forecast because your zip code isn't set.")
                return

            temp_unit = self.get_config("temp_unit", "f")
            
            lat, lon, _, _ = self._zip_to_latlon(zip_code, self.get_config("region", "us"))
            weather_data = self._get_forecast_data(lat, lon, temp_unit)
            
            forecast_text = self._format_forecast(weather_data)
            
            # Speak the forecast and end the session.
            self.speak(forecast_text)
            self.log.info(f"Successfully spoke forecast request for {self.forecast_day}.")
        except Exception as e:
            self.log.error(f"Error getting forecast: {e}", exc_info=True)
            self.speak("Sorry, I'm having trouble getting the forecast right now.")

    def _zip_to_latlon(self, zip_code: str, country: str = "us"):
        """Return (lat, lon, city, state) for a postal code using Zippopotam.us."""
        url = f"http://api.zippopotam.us/{country}/{zip_code}"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        place = data["places"][0]
        return (
            float(place["latitude"]),
            float(place["longitude"]),
            place["place name"],
            place["state"]
        )
