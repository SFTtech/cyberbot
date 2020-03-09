import asyncio
import nio
import pathlib

nio.RoomMember.get_friendly_name = lambda self: self.display_name

class MatrixRoom():

    def __init__(self, client, nio_room):
        self.client = client
        self.nio_room = nio_room


    async def send_html(self, formatted_txt, txt=""):
        #print(formatted_txt)
        #print(txt)
        response = await self.client.room_send(
                room_id=self.nio_room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "format": "org.matrix.custom.html",
                    "formatted_body" : formatted_txt,
                    "body": txt,
                },
                ignore_unverified_devices=True)
        print(response)

    async def send_text(self, txt):
        await self.client.room_send(
                room_id=self.nio_room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": txt,
                },
                ignore_unverified_devices=True)

    async def send_notice(self, txt):
        await self.client.room_send(
                room_id=self.nio_room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.notice",
                    "body": txt,
                },
                ignore_unverified_devices=True)

    async def get_joined_members(self):
        """
        TODO: return right strings
        """
        k = await self.client.joined_members(self.nio_room.room_id)
        return k.members


    async def send_image(self, filename, text):
        p = pathlib.Path(filename)
        extension = p.suffix.lower()[1:]
        if extension not in ["gif", "png", "jpg", "jpeg"]:
            raise Exception(f"Unsupported image format: {extension}")
        uresp,fdi = await self.client.upload(lambda x,y: filename,
                content_type="image/{}".format(extension.replace("jpeg", "jpg")),
                filename=p.name,
                encrypt=self.nio_room.encrypted)
        if not type(uresp) == nio.UploadResponse:
            print("Unable to upload image")
        else:
            uri = uresp.content_uri
            c = {
                    "msgtype": "m.image",
                    "url": uri,
                    "body": p.name,
                }
            if fdi:
                c["file"] = fdi
            print(fdi)
            await self.client.room_send(
                    room_id=self.nio_room.room_id,
                    message_type="m.room.message",
                    content=c,
                    ignore_unverified_devices=True)
