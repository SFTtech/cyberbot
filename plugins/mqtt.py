import io
import logging
import json
import time

import libconf
from paho.mqtt.client import Client as PahoMqttClient
from matrix_bot_api.mcommand_handler import MCommandHandler


HELP_DESC = ("!alarm\t\t\t-\tFlash the signal light in the Hackerspace\n"
             "!devices\t\t-\tShow # of connected ETH devices in space")

# This is defined outside. hopefully we do not kill it this way
TRUSTED_ROOMS = []

class MQTTBahnhofClient:
    """
    A simplified hauptbahnhof client
    """
    def __init__(self, config, subscriptions):
        logformat = '%(asctime)s | %(name)s | %(levelname)5s | %(message)s'
        logging.basicConfig(format=logformat)
        self.log = logging.getLogger(__name__)
        if config['hauptbahnhof']['debug']:
            self.log.setLevel(logging.DEBUG)
        else:
            self.log.setLevel(logging.INFO)

        self.host = config['hauptbahnhof']['host']
        self.subscriptions = subscriptions

        self.mqtt = PahoMqttClient()
        self.mqtt.enable_logger(self.log)
        self.mqtt.on_message = self.on_message
        self.mqtt.on_connect = self.on_connect

        ssl = {"ca_certs": config['hauptbahnhof']['ca_crt'],
               "certfile": config['hauptbahnhof']['certfile'],
               "keyfile":  config['hauptbahnhof']['keyfile']}
        self.mqtt.tls_set(**ssl)

        auth = {"username": config['hauptbahnhof']['username'],
                "password": config['hauptbahnhof']['password']}
        self.mqtt.username_pw_set(**auth)

    def on_message(self, client, userdata, msg):
        """
        A message was received. push it back towards the async context
        """
        self.log("Unhandled message has arrived: %s %s %s", client, userdata, msg)

    def on_connect(self, client, userdata, flags, returncode):
        """ After a successfull connection the topics are set and subscribed """
        del client, userdata
        if returncode == 0:
            print("Flags: ", flags)
            self.mqtt.subscribe([(topic, 0) for topic in self.subscriptions])

            if not 'session present' in flags or flags['session present'] == 0:
                # If we have a new session
                for topic, callback in self.subscriptions.items():
                    if callback:
                        self.mqtt.message_callback_add(topic, callback)

        else:
            try:
                msg = {
                    0: "Connection successful",
                    1: "Incorrect Protocol Version",
                    2: "Invalid client identifier",
                    3: "Server unavailable",
                    4: "Bad username or password",
                    5: "Not authorized",
                }[returncode]
            except KeyError:
                msg = "Unknown error occured: " + returncode
            print("Connection refused: ", msg)


    def publish(self, topic, data):
        """ Publish a message """
        self.mqtt.publish(topic, data)

    def start(self):
        """ Connect and start the mqtt machine """

        # *_srv is needed when we connect to a DNS instead of an IP
        self.mqtt.connect_srv(self.host, port=8883)
        self.log.info("Successfully connected to %s", self.host)

        # Spinning of a thread for the magic
        self.mqtt.loop_start()



class HackerspaceHandler:
    """
    Setup communication between tha mqtt-connection and the bot
    """
    def __init__(self, configfile, bot):
        with io.open(configfile) as cfgfile:
            self.config = libconf.load(cfgfile)

        self.ratelimit = {
            'alarm':   {'rate': self.config['ratelimit']['alarm'], 'last': 0},
            'party':   {'rate': self.config['ratelimit']['party'], 'last': 0},
            'devices': {'rate': self.config['ratelimit']['devices'], 'last': 0}
        }

        self.device_count_requested_time = 0
        self.device_count_room = None

        self.bot = bot
        self.bot.add_handler(MCommandHandler("alarm", self.bot_alarm))
        self.bot.add_handler(MCommandHandler("party", self.bot_party))
        self.bot.add_handler(MCommandHandler("devices", self.bot_devices))

        self.client = MQTTBahnhofClient(self.config, {
            '/haspa/status': self.bhf_haspastatus,
            '/haspa/nsa/result': self.bhf_count_devices,
        })
        self.client.start()

    def is_ratelimited(self, action):
        """
        Returns true, if the message is not allowed and record 'now' for this
        action
        """
        if not action in self.ratelimit:
            print("Unknown action: ", action)
            return True

        now = time.time()
        if (self.ratelimit[action]['last'] + self.ratelimit[action]['rate']) < now:
            self.ratelimit[action]['last'] = now
            return False
        return True

    def bot_alarm(self, room, event):
        """ !alarm - callback"""
        if event['room_id'] not in TRUSTED_ROOMS:
            room.send_text("This feature is not available in this room")
            return
        if self.is_ratelimited('alarm'):
            # We do not generate more spam too an already spamming dude
            return

        self.client.publish('/haspa/action', {'action':'alarm'})

    def bot_party(self, room, event):
        """ !party - callback"""
        if event['room_id'] not in TRUSTED_ROOMS:
            room.send_text("This feature is not available in this room")
            return
        if self.is_ratelimited('party'):
            # We do not generate more spam too an already spamming dude
            return
        self.client.publish('/haspa/action', {'action':'party'})

    def bot_devices(self, room, event):
        """ !devices - callback """
        if event['room_id'] not in TRUSTED_ROOMS:
            room.send_text("This feature is not available in this room")
            return
        if self.is_ratelimited('devices'):
            # We do not generate more spam too an already spamming dude
            return

        if (self.device_count_requested_time + self.ratelimit['devices']['rate']) \
            > time.time():
            print("already waiting for a message: the last message is not too long ago")
            return

        self.device_count_requested_time = time.time()
        self.device_count_room = room
        self.client.publish('/haspa/nsa/scan', {'blacklist':'unknown'})

    def bhf_haspastatus(self, client, userdata, mqttmsg):
        """ /haspa/status change detected """
        del client, userdata
        msg = json.loads(mqttmsg.payload.decode('utf-8'))
        new_state = msg['haspa']

        for roomid in TRUSTED_ROOMS:
            try:
                print("  [i] Updating room topic [", new_state, "] of room", roomid)
                room = self.bot.client.get_rooms()[roomid]
                room.set_room_topic(self.config['status_topic'].format(new_state))
            except KeyError:
                # Not connected to trusted room
                pass

    def bhf_count_devices(self, client, userdata, mqttmsg):
        """ /haspa/nsa/result message """
        del client, userdata
        if self.device_count_requested_time != 0:
            print("we are not waiting for a device count - will not display!")
            return

        if not self.device_count_room:
            print("Target room not set")
            return

        self.device_count_requested_time = 0
        msg = json.loads(mqttmsg.payload.decode('utf-8'))
        text = str("Currently, {} auxiliary devices are connected to the "
                   "Hackerspace network.".format(msg['count']))
        self.device_count_room.send_text(text)

def register_to(bot):
    """ The callback done by bernd plugin to set this one up """
    HackerspaceHandler("./bernd.hauptbahnhof.conf", bot)

if __name__ == "__main__":
    # a dummy does not need more methods than the ones that are used
    # pylint: disable=too-few-public-methods
    class BotDummy:
        """ Only lives as a non-bernd environment """

        def add_handler(self, *args):
            """ Do nothing """
            pass

    HackerspaceHandler("./bernd.hauptbahnhof.conf", BotDummy())

    while True:
        time.sleep(100)
