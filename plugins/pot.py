from matrix_bot_api.mcommand_handler import MCommandHandler
import urllib.request
import urllib.parse
import json
from datetime import datetime
import requests

HELP_DESC = ("!pot\t\t\t\t\t\t\t-\tDisplays the current meal at Pot.")

link = "https://pot.stusta.de/plan.json"

imageSearch = "https://api.qwant.com/api/search/images?count=1&offset=1&q=%s"


def getDate(args, room):
    if args:
        dateStr = args[0]
        try:
            return int(dateStr)
        except:
            if args[0] == "morgen":
                return datetime.now().day
            elif dateStr == "übermorgen" or dateStr == "uebermorgen":
                return datetime.now().day + 1

            elif dateStr == "heute":
                return datetime.now().day - 1
            elif dateStr == "gestern":
                return datetime.now().day - 2
            else:
                try:
                    return datetime.strptime(dateStr, '%d.%m.').day - 1
                except:
                    room.send_text("Usage: !pot <date>, date as dd.mm. or heute/morgen/übermorgen")

    else:
        return datetime.now().day - 1


def register_to(bot):
    def pot_handler(room, event):
        potJson = urllib.request.urlopen(link).read()
        data = json.loads(potJson)

        args = event['content']['body'].split()
        args.pop(0)

        indexDay = getDate(args, room)

        currentDayInfo = data[indexDay]

        strToSend = "Hey " + event['sender'] + ", heute gibt es <strong>" + str(
            currentDayInfo["meal"]) + "</strong> im Pot. Komm doch im O-Haus vorbei :)<br>" + \
                    "Küche: " + currentDayInfo["kitchen"] + "; Bar: " + currentDayInfo["bar"]

        if indexDay != datetime.now().day - 1:
            strToSend = strToSend.replace("heute", str(indexDay + 1) + "." + str(datetime.now().month) + ".")
        if currentDayInfo["event"]:
            strToSend += "<br>Außerdem findet heute folgendes Event statt: <strong>" + currentDayInfo[
                "event"] + "</strong>"

        strToSend += "<br><br>Weiter Infos findest du auf https://pot.stusta.de"

        webimgstr = imageSearch.replace("%s", urllib.parse.quote_plus(currentDayInfo["meal"]))
        print(webimgstr)

        img = urllib.request.Request(
            webimgstr,
            headers={'User-Agent': 'Mozilla/5.0'})
        img = urllib.request.urlopen(img).read()
        img = json.loads(img)
        imgData = img["data"]["result"]["items"][0]["media"]
        print(imgData)

        r = requests.get(imgData)
        if r:
            img = r.content
            typ = r.headers['content-type']
            print('Downloaded', typ)
            up = room.client.api.media_upload(img, typ)
            print('Uploaded', up)
            uri = up['content_uri']
            room.send_image(uri, currentDayInfo["meal"])

        room.send_html(strToSend)

    pot_handler = MCommandHandler("pot", pot_handler)
    bot.add_handler(pot_handler)
