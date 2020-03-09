from matrix_bot_api.mcommand_handler import MCommandHandler
import os
import random

HELP_DESC = ("!imagetest\t\t-\tSend back test image\n")

def register_to(bot):

    # Echo back the given command
    async def imagetest_callback(room, event):
        exts = ["gif", "jpg", "png", "jpeg"]
        images = filter(lambda x:any(x.lower().endswith(ext) for ext in exts), os.listdir())
        await room.send_image(random.choice(list(images)))

    # Add a command handler waiting for the echo command
    imagetest_handler = MCommandHandler("imagetest", imagetest_callback)
    bot.add_handler(imagetest_handler)
