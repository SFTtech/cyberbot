from matrix_bot_api.mcommand_handler import MCommandHandler
import requests
import time
from threading import Thread
import random

HELP_DESC = ("!haspa\t\t\t\t\t\t-\tDo the * MAGIC *")

class haspa():
    def __init__(self):
        self.last_party = time.time()
    def callit(self):
        try:
            print("starting light")
            r = requests.get('http://10.150.9.132:5000/api/1337/2/1', timeout=0.1)
            if random.randint(0, 10) == 5:
                requests.get('http://bot.stusta.de/speak?phrase=alarm', timeout=0.1)
            else:
                requests.get('http://bot.stusta.de/set/109', timeout=0.1)

            time.sleep(5)
            print("stopping light")
            r = requests.get('http://10.150.9.132:5000/api/1337/2/0', timeout=0.1)
        except requests.exceptions.Timeout:
            print("connection timed out")

    def party_callback(self, a, b):
        #if self.last_party > time.time() - 60:
        #    self.last_party = time.time()
        #    print("rate limiting the party")
        #    return
        self.last_party = time.time()
        try:
            #if random.randint(0, 3) != 1:
            #    print("Skipping sound")
            #    return

            print("starting party")
            r = requests.get('http://10.150.9.132:5000/api/1337/1/0', timeout=0.1)
            time.sleep(1)
            r = requests.get('http://10.150.9.132:5000/api/1337/2/1', timeout=0.1)
            #requests.get('http://bot.stusta.de/set/56', timeout=0.1)
            requests.get('http://bot.stusta.de/set/110', timeout=0.1)
            time.sleep(4)
            r = requests.get('http://10.150.9.132:5000/api/1337/1/1', timeout=0.1)
            r = requests.get('http://10.150.9.132:5000/api/1337/2/0', timeout=0.1)
        except requests.exceptions.Timeout:
            print("connection timed out")


    # Echo back the given command
    def haspa_callback(self, room, event):
        t = Thread(target=self.callit)
        t.run()

def register_to(bot):
    h = haspa()
    bot.add_handler(MCommandHandler("haspa", h.haspa_callback))
    bot.add_handler(MCommandHandler("party", h.party_callback))
