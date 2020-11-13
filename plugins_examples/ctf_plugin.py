
HELP_DESC = ("""!doing <TASKNAME>\t\t\t-\tTell people that you are doing a specific task
!done <TASKNAME>\t\t\t-\tRemove yourself from task
!finished <TASKNAME>\t\t-\tMark task as solved/finished and remove from task list
!cleardoing\t\t-\tClear current task mapping
""")



async def register_to(plugin):
    mapping = {}

    def format_block(text):
        return f"<pre><code>{text}</pre></code>"

    async def get_displayname(user_id):
        return (await plugin.client.get_displayname(user_id)).displayname

    async def print_mapping():
        nonlocal mapping
        s = "CURRENT TASKS\n===========================\n"
        for (task, idlist) in mapping.items():
            s += f"{task:30}:\t["
            s += ", ".join([("<a href='https://matrix.to/#/{}'>{}</a>".format(user_id, await get_displayname(user_id))) for user_id in idlist])
            s += "]\n"

        await plugin.send_html(format_block(s))

    async def doing_callback(room, event):
        nonlocal mapping
        args = plugin.extract_args(event)
        args.pop(0)

        for arg in args:
            if arg not in mapping:
                mapping[arg] = [event.source['sender']]
            elif event.source['sender'] not in mapping[arg]:
                mapping[arg].append(event.source['sender'])
        await print_mapping()

    async def cleardoing_callback(room, event):
        nonlocal mapping
        mapping = {}
        await print_mapping()

    async def done_callback(room, event):
        nonlocal mapping
        args = plugin.extract_args(event)
        args.pop(0)

        if len(args) != 1:
            await plugin.send_text(HELP_DESC)
            return

        if (args[0] in mapping):
            sender_id = event.source['sender']
            if sender_id in mapping[args[0]]:
                mapping[args[0]].remove(sender_id)
                if len(mapping[args[0]]) == 0:
                    mapping.pop(args[0])

        await print_mapping()

    async def finished_callback(room, event):
        nonlocal mapping
        args = plugin.extract_args(event)
        args.pop(0)

        if len(args) != 1:
            await plugin.send_text(HELP_DESC)
            return

        if (args[0] in mapping):
            mapping.pop(args[0])

        await print_mapping()

    doing_handler = plugin.CommandHandler("doing", doing_callback)
    plugin.add_handler(doing_handler)

    cleardoing_handler = plugin.CommandHandler("cleardoing", cleardoing_callback)
    plugin.add_handler(cleardoing_handler)

    done_handler = plugin.CommandHandler("done", done_callback)
    plugin.add_handler(done_handler)

    finished_handler = plugin.CommandHandler("finished", finished_callback)
    plugin.add_handler(finished_handler)
