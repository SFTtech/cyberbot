[![Bernd Lauert](bernd.jpg)](http://krautchan.net)
==================================================

**Bernd Lauert**
----------------
A matrix chatbot, designed for the [*StuStaNet
e.V.*](http://vereinsanzeiger.stustanet.de/) administrator chatroom
(#admins:stusta.de), written in python.

**Requirements**:

All required python modules are listed in the requirements.txt
file. Furthermore the bot needs read and write permissions in the installation
folder for correct execution.

**Execution**:

Specify the login credentials for the bot, as well as target rooms to join, in
the provided *config.ini* file. When specifying target rooms, both room aliases
(`#alias:server.org`) and internal IDs (`!suchalongidwehavehere:server.org`) are
possible. If specifying multiple rooms, the IDs need to be separated by a
semicolon (';'). Quotes should be generally omitted in the file.

After the bot has been configured, issue:

```sh
python bernd -c <config_file>
```

**Structure**:

The bot itself only uses the basic functionality of the `matrix_bot_api` module
to establish a matrix connection. All higher functionality is implemented in
*plugin files*. These plugins need to be located in the *plugins* folder.

Every plugin needs to define a `register_to(bot)` function, which is called upon
plugin loading, and a `HELP_DESC` variable, containing a string with a short
textual description of its features.

For interaction with matrix services, respective modules need to be imported.
Consider this short example of an echo plugin for demonstration purposes:

```python
from matrix_bot_api.mcommand_handler import MCommandHandler

# Define a HELP_DESC, which describes the new functionality
HELP_DESC = ("!echo\t\t-\tEcho back the given string\n")

# plugin loading function, executed upon startup
def register_to(bot):

    # Callback functions, registered with MCommandHandler/MRegexHandler are
    # provided with a matrix room object, in which the event has been received,
    # and the event data itself. Events in matrix are JSON objects and can be
    # easily accessed as follows:   json_value = event['json_key']
    def echo_callback(room, event):
        args = event['content']['body'].split()
        args.pop(0)

        # Interaction with matrix is conducted through the room object. Consider
        # the documentation of matrix_client.client/api for further information
        room.send_text(event['sender'] + ': ' + ' '.join(args))

    # Add a command handler waiting for the echo command
    # This command handler reacts upon the command "!echo" and then invokes
    # the echo_callback function defined above
    echo_handler = MCommandHandler("echo", echo_callback)

    # register the handler with the running bot
    bot.add_handler(echo_handler)
```

Newly written plugins are loaded automatically once they are placed in the
plugins folder and fulfill all specified requirements.

**Commands**:

As the functionality of the bot depends heavily on the installed plugins, use
the `!help` command, in order to display the currently available features. The
displayed configuration is automatically generated at bot startup from the
plugin description texts.
