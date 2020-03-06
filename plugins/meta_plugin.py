from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = ("""
!kickbot\t\t-\tmake bot leave the room
"""[1:-1])

def register_to(bot):

    async def kickbot_callback(room, event):
        if event.get('sender') in CONFIG_ADMINUSERS:
            await room.send_text("Bye, bye. Invite me to this room to let me join again.")
            await room.client.room_leave(room.nio_room.room_id)
        else:
            await room.send_text("You are not privileged to do this.")

    kickbot_handler = MCommandHandler("kickbot", kickbot_callback)
    bot.add_handler(kickbot_handler)
