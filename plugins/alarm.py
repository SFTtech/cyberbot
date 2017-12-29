from matrix_bot_api.mcommand_handler import MCommandHandler

import json
import ssl
import socket

HELP_DESC = ("!alarm\t\t\t\t\t\t-\tFlash the signal light in the Hackerspace")

class AlarmManager:
    hauptbahnhof_port = 1337
    sstream = None

    def __init__(self, bot):
        alarm_handler = MCommandHandler("alarm", self.alarm_callback)
        bot.add_handler(alarm_handler)

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
            s.connect(('knecht.stusta.de', self.hauptbahnhof_port))
        except ConnectionRefusedError as e:
            return False

        try:
            self.sstream = context.wrap_socket(s, server_side = False,
                                              server_hostname='Hauptbahnhof')
        except ssl.SSLError as e:
            return False

        return True


    def alarm_callback(self, room, event):
        conn_fail = False

        if (not self.tls_connect()):
            print("  [-] Couldn't connect to Hauptbahnhof. Aborting alarm.")
            return

        # Try to trigger the alarm at the hauptbahnhof
        jsn = {'op': 'SET', 'data': 'BULB'}

        self.sstream.send(json.dumps(jsn).encode())
        try:
            resp = self.sstream.recv(2048)
        except Exception:
            conn_fail = True

        if (conn_fail or resp == b''):
            print("  [-] Connection to Hauptbahnhof reset. Aborting.")
            self.sstream.close()
            return

        try:
            jsn = json.loads(resp)
        except json.decoder.JSONDecodeError as e:
            print("  [-] Hauptbahnhof send malformed JSON. Aborting.")
            self.sstream.close()
            return

        if (jsn['state'] == 'FAIL'):
            print("  [-] Hauptbahnof failed to execute alarm command: "
                  + "{}".format(jsn['data']))
            self.sstream.close()
            return

def register_to(bot):
    alarm = AlarmManager(bot)

