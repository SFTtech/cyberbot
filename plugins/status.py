import requests
from threading import Thread
from time import sleep
from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = ("\t\t\t\t\t\t\t-\tUpdates room topic according to haspa status")
TRUSTED_ROOMS = []

class StatusWatch:
    current_state = None
    ROOM_TOPIC = "Hackerspace: {} | StuStaNet e. V. public chatroom"
    #ROOM_TOPIC = "Arkadenraum SSoC: {} | StuStaNet e. V. public chatroom"

    def __init__(self, bot):
        self.bot = bot
        self.thread = Thread(target=self.start_poll)
        self.thread.start()

    def start_poll(self):
        """
        Polling thread requesting the status every 10 seconds
        """
        # The good version
        #current_state = self.get_status()
        # the debug version
        current_state = None
        while True:
            new_state = self.get_status()
            if (current_state != new_state):
                current_state = new_state
                self.set_status(new_state)
            sleep(10)

    def get_status(self):
        r=requests.get("http://hackerspace.stusta.de/current.json")
        if r.status_code != 200:
            return False
        return r.json()["state"]

    def set_status(self, new_state):
        global TRUSTED_ROOMS
        for r in TRUSTED_ROOMS:
            try:
                print("Updating room topic", new_state, "of room", r)
                room = self.bot.client.get_rooms()[r]
                room.set_room_topic(self.ROOM_TOPIC.format(new_state))
            except KeyError:
                # Not connected to trusted room
                pass

def register_to(bot):
    watch = StatusWatch(bot)
