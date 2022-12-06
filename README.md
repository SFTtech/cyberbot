**Cyberbot**
----------------

A matrix chatbot written in python.

**Install**:

```sh
cd /srv
git clone https://gitlab.stusta.de/stustanet/bernd-lauert
cd bernd-lauert
virtualevn -p python3 venv
source venv/bin/activate
# install olm (have a look at https://gitlab.matrix.org/matrix-org/olm)
pip install python-olm --extra-index-url https://gitlab.matrix.org/api/v4/projects/27/packages/pypi/simple
# install python requirements
pip install -r requirements.txt
chown -R bernd:bernd /srv/bernd-lauert
```

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
python cyberbot -c <config_file>
```

To add the bot to a room, invite it via your matrix client. The bot will join
automatically.

Adapt the systemd service to match with your setup and enable the bot with `systemctl enable --now cyberbot.service`

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
