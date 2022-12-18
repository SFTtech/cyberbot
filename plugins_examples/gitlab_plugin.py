from gitlab.formatting import format_event
from git import LocalHookManager

HELP_DESC = "!gitlab\t\t\t-\tGitlab Webhook Manager/Notifier 🦊\n"


async def register_to(plugin):
    lhm = LocalHookManager(
        plugin,
        git="gitlab",
        format_event_func=format_event,
        url="https://docs.gitlab.com/ee/user/project/integrations/webhooks.html",
        emoji="🦊",
    )
    await lhm.start()
