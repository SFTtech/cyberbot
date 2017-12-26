import requests
from threading import Thread
from time import sleep
from matrix_bot_api.mcommand_handler import MCommandHandler

import json
import ssl
import socket

HELP_DESC = ("(automatic)\t\tUpdates room topic according to haspa status")
TRUSTED_ROOMS = []
hauptbahnhof_port = 1337

class StatusWatch:
    current_state = None
    ROOM_TOPIC = "Hackerspace: {} | StuStaNet e. V. public chatroom"
    #ROOM_TOPIC = "Arkadenraum SSoC: {} | StuStaNet e. V. public chatroom"

    def __init__(self, bot):
        self.stream = None
        self.bot = bot

        if (not self.tls_connect()):
            return None

        # start polling
        self.thread = Thread(target=self.start_listening)
        self.thread.start()

    def __del__(self):
        jsn = {'op' : 'UNREGISTER', 'data': 'OPEN'}
        try:
            self.stream.send(json.dumps(jsn).encode())
            resp = self.stream.recv(2048)
        except ConnectionResetError as e:
            print("Failed to correctly unregister from server. Disconnecting")

        if self.stream:
            self.stream.close()

    def __exit__(self, exc_type, exc_value, traceback):
        jsn = {'op' : 'UNREGISTER', 'data': 'OPEN'}
        try:
            self.stream.send(json.dumps(jsn).encode())
            resp = self.stream.recv(2048)
        except ConnectionResetError as e:
            print("Failed to correctly unregister from server. Disconnecting")

        if self.stream:
            self.stream.close()

    def tls_connect(self):
        """
        Try to establish a TLS connection to the Hauptbahnhof Server.
        """

        # create tls connection to the hauptbahnhof
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.load_cert_chain('./cert.pem', './key.pem')
        context.load_verify_locations('./trusted.pem')

        s = socket.socket()

        try:
            s.connect(('knecht.stusta.de', hauptbahnhof_port))
        except ConnectionRefusedError as e:
            return False

        try:
            self.stream = context.wrap_socket(s, server_side = False,
                                              server_hostname='Hauptbahnhof')
        except ssl.SSLError as e:
            return False

        # Register for PUSH-messages at the server
        jsn = {'op': 'REGISTER', 'data': 'OPEN'}

        self.stream.send(json.dumps(jsn).encode())
        resp = self.stream.recv(2048)

        try:
            jsn = json.loads(resp)
        except json.decoder.JSONDecodeError as e:
            return False

        if (jsn['state'] == 'FAIL'):
            return False

        return True

    def start_listening(self):
        """
        Listen on the established stream for push messages and update the status
        accordingly
        """
        conn_fail = False

        # Infinitely listen for push messages and try to reconnect in case of
        # failure
        while (True):

            try:
                resp = self.stream.recv(2048)
            except Exception:
                conn_fail = true

            if (resp == b'' or conn_fail == True):
                print("  [-] TLS Connection to Hauptbahnhof reset. "
                      + "Trying to reconnect...")
                self.stream.close()
                while (not self.tls_connect()):
                    print("  [-] Reconnecting failed." +
                          " Retrying in 10 seconds...")
                    sleep(10)
                print("  [+] Reestablished Hauptbahnhof connection")
                conn_fail = False
                continue

            try:
                jsn = json.loads(resp)
            except json.decoder.JSONDecodeError as e:
                print("  [-] Received malformed JSON from Hauptbahnhof." +
                      "Reconnecting...")
                self.stream.close()
                conn_fail = True
                continue

            if (jsn['state'] == 'PUSH' and jsn['data'] == 'OPEN'):
                state = jsn['msg']
                if (self.current_state != state):
                    self.current_state = state
                    state_str = "offen" if state else "geschlossen"
                    self.set_status(state_str)
            else:
                print("  [-] Received Hauptbahnhof message," +
                      " differing from PUSH format:" +
                      " {}. Reconnecting...".format(jsn))
                self.stream.close()
                conn_fail = True
                continue

    def set_status(self, new_state):
        global TRUSTED_ROOMS
        for r in TRUSTED_ROOMS:
            try:
                print("  [i] Updating room topic [", new_state, "] of room", r)
                room = self.bot.client.get_rooms()[r]
                room.set_room_topic(self.ROOM_TOPIC.format(new_state))
            except KeyError:
                # Not connected to trusted room
                pass

def register_to(bot):
    watch = StatusWatch(bot)
