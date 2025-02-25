# Cyberbot

Matrix chatbot in Python, with encryption support and easy to use API.

## Installation

Dependency installation in a `.venv` in the source directory:
```sh
pdm install
```

## Running

Running from the source directory:
```sh
pdm run cyberbot -c config
```

## Usage

Activate the bot in a room by inviting it.

Cyberbot will then invite you to a configuration room, in which you can configure the rooms where the bot is active in.


### Commands

As the functionality of the bot depends heavily on the active plugins.
Use `help` in a configuration room to see what is available in your current configuration.


## Development

Cyberbot is built by using `matrix-nio`.

Room interaction is implemented in `modules/`: see [./PLUGINS.md](PLUGINS.md) for information on how to create plugins.
