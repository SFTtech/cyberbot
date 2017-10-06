import requests
import threading

from time import sleep
from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = ("!activate\t\t\t\t\t\t-\tActivate the hackerspace status watch")
ROOM_TOPIC = "Hackerspace: {} | StuStaNet e. V. public chatroom"
#ROOM_TOPIC = "Arkadenraum SSoC: {} | StuStaNet e. V. public chatroom"
current_state = False
statuswatch_running = False

def register_to(bot):

    def get_status():
        r=requests.get("http://hackerspace.stusta.de/current.json")
        if r.status_code != 200:
            return False
        return r.json()["state"]

    def start_poll(room, event):
        global current_state

        while True:
            # check if a status change happened
            new_state = get_status()

            if (current_state != new_state):
                current_state = new_state
                room.set_room_topic(ROOM_TOPIC.format(new_state))

            sleep(10)

    def activate_callback(room, event):
        global statuswatch_running

        # ignore, if this feature is requested in a private room
        if (event['room_id'] not in TRUSTED_ROOMS):
            room.send_text("This feature is not available in this room")
            return

        if (not statuswatch_running):
            t = threading.Thread(target=start_poll, args=(room,event))
            t.start()
            statuswatch_running = True
        else:
            room.send_text("Hackerspace status watch is already in effect.")

    activate_handler = MCommandHandler("activate", activate_callback)
    bot.add_handler(activate_handler)
    """
    def topic_callback(room, event):
        state = event['content']['body']
        state = state.split(' ')[1]
        room.set_room_topic(ROOM_TOPIC.format(state))
    """
