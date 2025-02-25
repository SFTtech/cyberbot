from typing import Awaitable, Callable

from nio.events.room_events import RoomMessageText

# one text message in a room
# alias the type in case we need to switch from nio
type MessageText = RoomMessageText

# a handler that processes one text message in a room
type MessageHandler = Callable[[MessageText], Awaitable[None]]
