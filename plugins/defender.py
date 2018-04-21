from matrix_bot_api.mcommand_handler import MCommandHandler
from matrix_bot_api.mregex_handler import MRegexHandler
import random
import threading
import time

HELP_DESC = ("(automatic)\t\tThe bot defends the room against spambots")

class RoomDefender:

    def __init__(self, bot, ban_time=20):
        self.bot = bot
        # Suspect DB. Format: [[name, expected code, ban state],...]
        self.spam_suspects = []
        self.ban_time = ban_time

        # Add a regex handler waiting for suspected spam
        def_handler = MRegexHandler("(([A-ZÄÖÜ]){3,}\s){3,}", self.def_callback)
        self.bot.add_handler(def_handler)

        # Add a command handler for the 'nope' command
        nope_handler = MCommandHandler("nope", self.nope_callback)
        self.bot.add_handler(nope_handler)

    def ban_wait(self, room, event, suspect):
        time.sleep(self.ban_time)

        for i in range(len(self.spam_suspects)):
            if (self.spam_suspects[i][0] == suspect):
                if (self.spam_suspects[i][2]):
                    room.send_text(suspect + ": Authorization failed. Goodbye.")
                    kicked = room.kick_user(suspect, 'We do not tolerate spam.')
                    banned = room.ban_user(suspect, 'Goodbye.')

                    if (not kicked or not banned):
                        print("[-] Failed to kickban {}.".format(suspect) +
                              " Not enough privileges.")

                else:
                    print("[i] {} completed spambot auth.".format(suspect))
                    room.send_text(suspect + ": Authorization succeeded.")

                self.spam_suspects.pop(i)


    def def_callback(self, room, event, data):
        suspect = event['sender']

        if (suspect not in [s[0] for s in self.spam_suspects]):
            s = [chr(a) for a in range(65, 91)]
            s.extend([chr(a) for a in range(97, 123)])
            s = ''.join(random.sample(s, 4))
            self.spam_suspects.append([suspect, s, True])

            print("[i] Possible spambot detected: ", suspect)
            warn = ('{} : We suspect that you are a spambot.'.format(suspect) +
                    ' Issue \'!nope {}\' to proove otherwise.'.format(s) +
                    ' If no correct response is received' +
                    ' within {}'.format(self.ban_time) +
                    ' seconds you will be banned.')

            room.send_text(warn)

            t = threading.Thread(target=self.ban_wait,
                                 args=(room, event, suspect), daemon=True)
            t.start()

    def nope_callback(self, room, event, data):
        suspect = event['sender']

        for s in self.spam_suspects:
            if (s[0] == suspect):
                try:
                    code = event['content']['body'].split()[1]
                except IndexError as e:
                    continue

                if (s[1] == code):
                    s[2] = False

def register_to(bot):
    defender = RoomDefender(bot)
