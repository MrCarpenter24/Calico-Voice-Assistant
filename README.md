# **Calico Voice Assistant Skills**

Calico is a modular and extensible skill-based framework designed to work with the powerful open-source [Rhasspy 2.5](https://rhasspy.readthedocs.io/en/latest/) voice assistant. It provides a robust structure for creating complex, conversational skills that can manage their own state, handle multi-turn dialogues, and perform actions on your system.

This project was developed and tested on an Ubuntu 24.04.2 LTS environment using the Rhasspy 2.5.11 Docker container.

## **About The Project**

While Rhasspy provides the core voice processing pipeline (Wake Word, Speech-to-Text, Intent Recognition, Text-to-Speech), Calico handles the "thinking." It acts as the brain, taking the recognized intents from Rhasspy and dispatching them to the appropriate skill to be handled.

The core of Calico is a central service that communicates with Rhasspy's MQTT broker. This service dynamically loads all available skills, allowing for easy expansion and management of your voice assistant's capabilities.

### **Key Features**

* **Modular, Class-Based Skills:** Each skill is a self-contained Python class, making them easy to develop, test, and maintain.  
* **Stateful Conversations:** Skills can manage their own state, allowing for complex, multi-turn conversations (e.g., asking a question, waiting for a reply, and acting on that reply).  
* **Robust Logging:** The main service and each individual skill have their own dedicated log files with automatic rotation, making debugging a breeze.  
* **Centralized Configuration:** A shared settings file allows skills to access common configuration values, like API keys or user preferences.  
* **Extensible Foundation:** A BaseSkill class provides all the boilerplate for MQTT communication and session management, so you can focus on writing the logic for your skill.

## **Getting Started**

To get a local copy up and running, follow these simple steps.

### **Prerequisites**

* **Python 3.8+**  
* **Docker** and **Docker Compose**  
* **Git** for version control  
* An operational **Rhasspy 2.5.11** instance (the Docker installation is recommended).

### **Installation**

1. **Clone the repository:**  
   git clone \<YOUR\_REPOSITORY\_URL\>  
   cd Calico

2. **Set up the Python Environment:** It is highly recommended to use a virtual environment.  
   python3 \-m venv .venv  
   source .venv/bin/activate  
   pip install \-r requirements.txt

   *(You* will need to create a requirements.txt file containing paho-mqtt and *requests)*  
3. **Configure Rhasspy:** The sentences.ini and profile.json files included in this project are highly recommended for proper setup.  
   * Navigate to your Rhasspy profile directory (usually \~/.config/rhasspy/profiles/en/).
   * **Back up your existing sentences.ini and profile.json\!**  
   * Replace them with the versions from this project's /rhasspy\_config directory.  
   * Train your Rhasspy profile and restart it.  
4. **Configure Calico:**
   * Calico currently runs out of the Documents directoy (gross, I know).   
   * Configure it how you like. The variables that need changed are at the top of these files: Calico-Start.sh, Calico-Stop.sh, and calico_skill_service.py.   
   * Make sure these files are marked as executable - VERY IMPORTANT.
   * Navigate to the Calico/settings directory.   
   * Edit config.json to add your personal details, such as zip code and region for the weather skill.  
5. **Launch Calico:** Open a terminal, navigate to the project's root directory, and run the start script Calico-Start.sh. This will:  
   * Start up Docker CLI.  
   * Install and launch the latest version of the Docker Rhasspy container.  
   * Install and start up Mosquitto.  
   * Install the Tkinter Python library for the settings GUI.  
   * Starts up Calico's core service, calico_skill_service.py.  
   * The service will connect to the MQTT broker and begin listening for intents from Rhasspy.  
6. **Stopping Calico** Should anything go wrong, simply run the stop script, Calico-Stop.sh.  
   * This will shut everything down cleanly.  
7. **That's It!** Everything *should* be good to go! Just remeber, Calico is in very early stages of development. There's a lot more to come!

## **Project Structure**

Calico/  
├── libraries/  
│   └── calico\_common.py      \# The BaseSkill class for all skills  
├── logs/  
│   ├── calico\_skill\_service.log \# Main log file  
│   └── skills/                  \# Directory for individual skill logs  
├── services/  
│   └── calico\_skill\_service.py \# The main MQTT service  
├── settings/  
│   ├── config.json              \# User-specific settings  
│   └── settings.py              \# GUI for editing settings  
└── skills/  
    ├── Ask\_Me\_Colors.py         \# Example conversational skill  
    └── Open\_Gmail.py            \# Example one-shot skill

## **How It Works**

The architecture is designed to be simple and scalable.

1. **Service Initialization:** When calico\_skill\_service.py starts, it scans the /skills directory.  
2. **Skill Loading:** For each Python file found, it dynamically imports the module and creates an instance of the Skill class within it (e.g., AskMeColorsSkill). These skill objects are stored in memory.  
3. **MQTT Listening:** The service subscribes to hermes/intent/\# on Rhasspy's MQTT broker.  
4. **Intent Dispatching:** When an intent is recognized by Rhasspy (e.g., Ask\_Me\_Colors), the service receives the message. It looks up the corresponding skill object and calls its handle\_intent() method, passing along the message payload.  
5. **Skill Execution:** The skill object itself then takes over, managing its own logic, state, and any necessary follow-up conversation turns using methods provided by the BaseSkill class (speak(), continue\_session(), etc.).

## **Creating Your Own Skills**

Creating a new skill is straightforward.

1. Create a new Python file in the /skills directory (e.g., My\_New\_Skill.py).  
2. Inside the file, create a class that inherits from BaseSkill. The class name must be the CamelCase version of the file name (e.g., MyNewSkillSkill).  
3. In your \_\_init\_\_ method, call the parent super().\_\_init\_\_(), defining your skill's main intent\_name and an answer\_intent if it's a conversational skill.  
4. Implement the handle\_intent() method. This is the main entry point for your skill's logic.

### **Example: One-Shot Skill**

\# skills/Hello\_World.py  
from pathlib import Path

\# Add the project's root directory (Calico) to the Python path
\# This allows us to import from the 'libraries' module
sys.path.append(str(Path(\_\_file\_\_).resolve().parents[1]))

from libraries.base\_skill import BaseSkill

class HelloWorldSkill(BaseSkill):  
    def \_\_init\_\_(self, mqtt\_client):  
        super().\_\_init\_\_(  
            intent\_name="Hello\_World",  
            answer\_intent="",  \# No follow-up question  
            mqtt\_client=mqtt\_client  
        )

    def handle\_intent(self, message: dict):  
        super().handle\_intent(message) \# Sets up session info  
        self.speak("Hello there\! The world says hello back.")

## **Troubleshooting**

If a skill isn't working as expected, your first stop should be the log files in the /logs directory.

* calico\_skill\_service.log shows the overall health of the service, including which intents are being received and dispatched.  
* logs/skills/\<Your\_Skill\_Name\>.log contains the detailed, step-by-step execution log for that specific skill.

## **Acknowledgments**

* This project would not be possible without the amazing work of the [Rhasspy](https://rhasspy.readthedocs.io/en/latest/) community.  
* Weather data provided by [Open-Meteo](https://open-meteo.com/).  
* ZIP code lookup via [Zippopotam.us](http://www.zippopotam.us/).
