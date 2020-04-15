#requires this package
import MVGLive
import json

HELP_DESC = ("!{mvg,mvv} <minutes>\t\t-\tDisplay Forschungszentrum depatures\n")

async def register_to(plugin):

    async def mvg_callback(room, event):
        args = plugin.extract_args(event)

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
        await plugin.send_html(outText)

    mvg_handler = plugin.CommandHandler("mvg", mvg_callback)
    plugin.add_handler(mvg_handler)

    mvv_handler = plugin.CommandHandler("mvv", mvg_callback)
    plugin.add_handler(mvv_handler)
