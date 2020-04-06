from matrix_bot_api.mcommand_handler import MCommandHandler
import feedparser
from threading import Thread
import dbm.ndbm
import time
import logging

from matrixroom import MatrixRoom


HELP_DESC = ("gitlab\t\t- (WIP)The bot will post changes in rbg gitlab Cybergruppe Group")

class RSSGitlabFeed:

    def __init__(self, plugin):
        self.plugin = plugin
        self.dbmfile = "feed_read.dbm"

    async def check_for_changes(self):
        rss_token = ENVIRONMENT.get('GITLABRSSTOKEN')
        async def k():
            try:
                feed_url = f'https://gitlab.rbg.tum.de/cyber.atom?feed_token={rss_token}'
                logging.info(f"GITLAB: fetching {feed_url}")
                feed = feedparser.parse(feed_url)
                await self.update_from_feed(feed)
            except:
                pass
        await self.plugin.start_task(k,5)


    async def update_from_feed(self, feed):
        """
        Generate a list of new entries, and mark the new entries as read
        """
        with dbm.open(self.dbmfile, 'c') as db:
            for entry in reversed(feed['entries']):
                if entry['id'] not in db:
                    await self.notify_update(entry)
                    db[entry['id']] = "1"

    async def notify_update(self, entry):
        """
        Extract the relevant information from the entry
        If the room is not yet set, it will terminate but also not record any
        recorded change. with is nice.
        """
        # Censor the link that is going to be displayed, if it contains the
        # RSS token - this is a horrible workaround for gitlab
        if ".atom?rss_token=" in entry['link']:
            entry['link'] = "https://gitlab.rbg.de/cyber"
        print(entry)
        plugin.send_notice(f"{entry['title']} ({entry['link']})")
#
#        for rid in self.plugin.bot.active_rooms:
#            await self.plugin.bot.client.room_send(
#                room_id=rid,
#                message_type="m.room.message",
#                content={
#                    "msgtype": "m.notice",
#                    "body": "{} ({})".format(entry['title'], entry['link']),
#                },
#                ignore_unverified_devices=True)
#

async def register_to(plugin):
    feedreader = RSSGitlabFeed(plugin)
    await feedreader.check_for_changes()
