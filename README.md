**Cyberbot**
----------------

A matrix chatbot written in python.

**Requirements**:

All required python modules are listed in the requirements.txt
file. Furthermore the bot needs read and write permissions in the installation
folder for correct execution.
[Libolm v3](https://gitlab.matrix.org/matrix-org/olm) needs to be installed.

**Execution**:

Specify the login credentials and server for the bot and the plugin locations in
the provided *config.ini* file.
Quotes should be generally omitted in the file.

An example ini file can be found in the repository.

After the bot has been configured, issue:

```sh
python bernd -c <config_file>
```

To add the bot to a room, invite it via your matrix client. The bot will join
automatically.


**Commands**:

As the functionality of the bot depends heavily on the installed plugins, use
the `!help` command, in order to display the currently available features.
Use `!listplugins` to see all available plugins and use `!addplugin` to add one
of them into your room.


**Structure**:

The bot itself only uses the basic functionality of the `matrix-nio` module
to establish a matrix connection. All higher functionality is implemented in
*plugin files*. These plugins need to be located one of the folders specified in the `PLUGINPATH` in your config file.

Every plugin needs to define an async `register_to(plugin)` function, which is called upon
plugin loading, and a `HELP_DESC` variable, containing a string with a short
textual description of its features.


**Plugins**:
See [./PLUGINS.md](PLUGINS.md).
