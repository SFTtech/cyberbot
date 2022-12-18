from github.formatting import format_event
from git import LocalHookManager

HELP_DESC = "!github\t\t\t-\tGithub Webhook Manager/Notifier 🐱\n"


async def register_to(plugin):
    lhm = LocalHookManager(
        plugin,
        git="github",
        format_event_func=format_event,
        url="https://docs.github.com/webhooks/",
        emoji="🐱",
        important="IMPORTANT: Select content type: application/json\n",
    )
    await lhm.start()
