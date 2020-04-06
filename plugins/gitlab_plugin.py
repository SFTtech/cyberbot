from matrix_bot_api.mcommand_handler import MCommandHandler
import re
import feedparser
import dbm.ndbm
import json
import time
import logging

from matrixroom import MatrixRoom
from pprint import pprint


HELP_DESC = ("gitlab\t\t- Gitlab Feed Manager/Notifier")

class RSSGitlabFeed:

    def __init__(self, plugin, url, feed_token, last_update):
        self.plugin = plugin
        self.dbmfile = "feed_read.dbm"
        self.feed_token = feed_token
        self.last_update = last_update
        self.url = url
        self.task = None


    async def start(self):
        async def check_for_changes():
            try:
                logging.info(f"GITLAB: fetching {self.url}")
                feed_url = f'{self.url}?feed_token={self.feed_token}'
                feed = feedparser.parse(feed_url)
                await self.update_from_feed(feed)
            except Exception as e:
                print(e)
        self.task = await self.plugin.start_task(check_for_changes,5)


    async def stop(self):
        if self.task is not None:
            await self.plugin.stop_task(self.task)
            self.task = None

    async def restart(self):
        self.stop()
        self.start()


    async def update_from_feed(self, feed):
        for entry in reversed(feed['entries']):
            if self.last_update is None or entry.updated_parsed > self.last_update:
                await self.notify_update(entry)
        self.last_update = max(entry.updated_parsed for entry in feed['entries'])
        print(self.last_update)

    async def notify_update(self, entry):
        """
        Extract the relevant information from the entry
        If the room is not yet set, it will terminate but also not record any
        recorded change. with is nice.
        """
        # Censor the link that is going to be displayed, if it contains the
        # RSS token - this is a horrible workaround for gitlab
        re.sub(r'.atom?rss_token=.*', '', entry['link'])
        re.sub(r'.atom?feed_token=.*', '', entry['link'])
        re.sub(r'.atom?personal_token=.*', '', entry['link'])
        await self.plugin.send_notice(f"{entry['title']} ({entry['link']})")



feeds = []


async def register_to(plugin):
    global feeds

    subcommands = """gitlab [subcommand] [option1 option2 ...]
Available subcommands:
    addfeed feedurl token   - add a feed with rss_token token
    remfeed feednr          - remove a feed
    listfeeds               - show subscribed feeds and their numbers

    issue                   - show a random issue

    See <a href="https://docs.gitlab.com/ee/api/api_resources.html">here</a> for more information on gitlab feeds.
"""


    def format_help(text):
        html_text = "<pre><code>" + text + "</code></pre>\n"
        return html_text

    async def show_help():
        formatted_subcommands = format_help(subcommands)
        await plugin.send_html(formatted_subcommands, subcommands)



    async def load_feeds():
        pass

    async def store_feeds():
        pass


    async def handle_addfeed(args):
        if len(args) != 2:
            await show_help()
        else:
            url = args[0]
            token = args[1]
            feed = RSSGitlabFeed(plugin, url, token, None)
            feeds.append(feed)
            await feed.start()
            await store_feeds()

    async def handle_remfeed(args):
        pass

    async def handle_listfeeds(args):
        pass

    async def handle_issue(args):
        pass

    # Echo back the given command
    async def gitlab_callback(room, event):
        args = plugin.extract_args(event)
        args.pop(0)
        if len(args) == 0:
            await show_help()
        elif args[0] == "addfeed":
            args.pop(0)
            await handle_addfeed(args)
        elif args[0] == "remfeed":
            args.pop(0)
            await handle_remfeed(args)
        elif args[0] == "listfeeds":
            args.pop(0)
            await handle_listfeeds(args)
        elif args[0] == "issue":
            args.pop(0)
            await handle_issue(args)
        else:
            await show_help()


    # Add a command handler waiting for the echo command
    await load_feeds()
    gitlab_handler = MCommandHandler("gitlab", gitlab_callback)
    plugin.add_handler(gitlab_handler)

    #feedreader = RSSGitlabFeed(plugin)
    #await feedreader.check_for_changes()
