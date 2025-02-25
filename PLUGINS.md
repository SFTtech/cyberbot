# Creating Plugins

Plugins are python files which are located either in this repository or as separate file somewhere externally.

Each plugin must define a class named `Module` that implements the abstract class `cyberbot.api.Plugin`.

Plugins are created for each room, meaning that each room that adds your plugin will load an own instance of your plugin's `Init` class.
When a plugin is activated in a room, code in `cyberbot/room_plugin.py` creates it once per room.

The API available to the room plugins is defined in `cyberbot/api/room_plugin.py`.
It allows plugins to have their own key-value store, send messages, react to room events etc.

Built-in modules are in `cyberbot/modules/`, a very simple example is `echo.py`.
