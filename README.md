# **Calico Voice Assistant**

Calico is a modular and extensible skill-based framework designed to work with the powerful open-source [Rhasspy 2.5](https://rhasspy.readthedocs.io/en/latest/) voice assistant. It provides a robust structure for creating complex, conversational skills that can manage their own state, handle multi-turn dialogues, and perform actions on your system.

This project was developed and tested in Ubuntu 24.04.2 LTS and is currently undergoing testing in Raspberry Pi OS (Bookworm).

## **About The Project**

While Rhasspy provides the core voice processing pipeline (Wake Word, Speech-to-Text, Intent Recognition, Text-to-Speech), Calico handles the "thinking." It acts as the brain, taking the recognized intents from Rhasspy and dispatching them to the appropriate skill to be handled.

The core of Calico is a central service that communicates with Rhasspy's MQTT broker. This service dynamically loads all available skills, allowing for easy expansion and management of your voice assistant's capabilities.

### **Key Features**

* **Modular, Class-Based Skills:** Each skill is a self-contained Python class, making them easy to develop, test, and maintain.  
* **Stateful Conversations:** Skills can manage their own state, allowing for complex, multi-turn conversations (e.g., asking a question, waiting for a reply, and acting on that reply).  
* **Robust Logging:** The main service and each individual skill have their own dedicated log files with automatic rotation, making debugging a breeze.  
* **Centralized Configuration:** A shared settings file allows skills to access common configuration values, like location information or preferred units of measurement.  
* **Extensible Foundation:** A BaseSkill class provides all the boilerplate for MQTT communication and session management, so you can focus on writing the logic for your skill.

### **Installation**  
**WARNING:** It is currently recommended that Calico be installed on a dedicated machine or in an isolated, virual environment.
* The voice assistant is still in early development and has not been vetted for bugs, security vulnerabilities or compatibility issues in an environment that runs other programs or scripts.

1. **Download the Install Script**  
   * Start by downloading *calico-install.sh*, located in the repository above.
2. **Make the Script Executable**  
   * In some operating systems, such as *Ubuntu*, you can simply right click the downloaded file and edit permissions to make the script executable.
   * However, other distros, such as *Raspberry Pi OS*, do not have this ability and require the use of the commands instead.
   * To do this, open your shell or terminal emulator and navigate to your downloads directory using something like this:
```bash
cd /home/[your-username-here]/Downloads
```
   * Next we'll use *chmod* to make the file executable, like so:
```bash
chmod +x calico-install.sh
```
3. **Run the Installer:**  
   * If you're already in the terminal, you can type the command below to execute.
```bash
./calico-install.sh
```
   * Otherwise, or if you simply prefer a graphical approach, you can right click and select an option similar to *execute*, *execute in terminal*, or *run as program*.
4. **Password Required**
   * Before the installer can get things set up for you, it will need your system password to enable *root*.
   * If you don't have one set, simply hit *enter* when the *sudo* prompt appears.
   * Next, the installer will get to work! This should only take a few minutes.
5. **Restart**
   * For all of the necessary changes to take effect, you will need to restart and log back in.
6. **The Launcher**
   * Here is where you'll command Calico. It should be located with the rest of your installed applications.
   * You can *start* and *stop* the application, edit locale and preferrence info in *settings*, or restart Calico's skill service (also located in *settings*).
7. **First Launch**
   * After hitting *start* for the first time, you'll need top open a browser and navigate to *http://localhost:12101/*.
   * This is Rhasspy's web interface and where, **with caution**, voice-related settings can be tweaked and edited. See the [docs](https://rhasspy.readthedocs.io/en/latest/).
   * For now, we need to download the required files for Rhasspy (and Calico) to work properly. By acknowledging the banner up top, this should be done for you.
   * Once finished, things should be good to go. You may need to hit *train* or switch the wake word module to *porcupine* (non-functioning on Raspberry Pi OS), or simply make your own wake word with *raven*. Again, see the [docs](https://rhasspy.readthedocs.io/en/latest/).
8. **We're Done!**
   * Everything *should* be good to go!
   * Remember, Calico is in very early stages of development, so there will be bugs...
   * But here's a lot more to come!

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

```python
# skills/Hello_World.py  
from pathlib import Path

# Add the project's root directory (Calico) to the Python path
# This allows us to import from the 'libraries' module
sys.path.append(str(Path(__file__).resolve().parents[1]))

from libraries.base_skill import BaseSkill

class HelloWorldSkill(BaseSkill):  
    def __init__(self, mqtt_client):  
        super().__init__(  
            intent_name="Hello_World",  
            # No follow-up question, otherwise "Answer_<name>"
            # is the amswer intent naming scheme.
            answer_intent="",  
            mqtt_client=mqtt_client  
        )

    def handle_intent(self, message: dict):  
        super().handle_intent(message) # Sets up session info  
        self.speak("Hello there! The world says hello back.")
```

## **Troubleshooting**

If a skill isn't working as expected, your first stop should be the log files in the /logs directory.

* calico\_skill\_service.log shows the overall health of the service, including which intents are being received and dispatched.  
* logs/skills/\<Your\_Skill\_Name\>.log contains the detailed, step-by-step execution log for that specific skill.

## **Acknowledgments**

* This project would not be possible without the amazing work of the [Rhasspy](https://rhasspy.readthedocs.io/en/latest/) community.  
* Weather data provided by [Open-Meteo](https://open-meteo.com/).  
* ZIP code lookup via [Zippopotam.us](http://www.zippopotam.us/).
