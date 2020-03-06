from matrix_bot_api.mcommand_handler import MCommandHandler
#requires this package
import MVGLive
import json

HELP_DESC = ("!{mvg,mvv} <minutes>\t\t-\tDisplay Forschungszentrum depatures")

def register_to(bot):


    async def mvg_callback(room, event):
        args = event['content']['body'].split()

        m = MVGLive.MVGLive()
        #offest wurde als argument übergeben
        if len(args)>1:
            depJson = str(m.getlivedata(station="Garching-Forschungszentrum", entries=5, timeoffset=int(args[1]))).replace("'", '"')
        else:
            depJson = str(m.getlivedata(station="Garching-Forschungszentrum", entries = 5)).replace("'", '"')
        depObj = json.loads(depJson)
        outText="Vom Garching-Forschungszentrum:<br>"

        #Create the depature list
        for i in depObj:
            outText+=i["product"] + " <strong>" + i["linename"] + "</strong>, Richtung <strong>" + i["destination"] + \
                     "</strong> in <strong>"+ str(int(i["time"])) + "</strong> "+ ("minute" if int(i["time"])<=1 else "minutes") +".<br>"
        await room.send_html(outText)

    mvg_handler = MCommandHandler("mvg", mvg_callback)
    bot.add_handler(mvg_handler)

    mvv_handler = MCommandHandler("mvv", mvg_callback)
    bot.add_handler(mvv_handler)
