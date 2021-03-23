
HELP_DESC = ("""!doing <TASKNAME>\t\t\t-\tTell people that you are doing a specific task
!done <TASKNAME>\t\t\t-\tRemove yourself from task
!finished <TASKNAME>\t\t-\tMark task as solved/finished and remove from task list
!cleardoing\t\t-\tClear current task mapping
""")



async def register_to(plugin):
    mapping = {}

    def format_block(text):
        return f"<pre><code>{text}</pre></code>"

    def get_arg_as_single(event):
        args = plugin.extract_args(event)
        args.pop(0)
        return " ".join(args)

    async def get_displayname(user_id):
        try:
            # try and except as we can also get an error as answer which does not have the displayname attribute
            response = await plugin.client.get_displayname(user_id)
            return response.displayname
        except:
            return None

    async def get_name_link(user_id):
        dn = await get_displayname(user_id)
        if (dn == None):
            return "Name error"
        # link does not show up anymore
        return dn
        # return f"<a href='https://matrix.to/#/{user_id}'>{dn}</a>"
         

    async def print_mapping():
        nonlocal mapping
        s = "CURRENT TASKS\n===========================\n"
        for (task, idlist) in mapping.items():
            s += f"{task:30}:\t["
            s += ", ".join([await get_name_link(user_id) for user_id in idlist])
            s += "]\n"

        await plugin.send_html(format_block(s))

    async def doing_callback(room, event):
        nonlocal mapping
        arg = get_arg_as_single(event)

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
        arg = get_arg_as_single(event)

        if (arg in mapping):
            sender_id = event.source['sender']
            if sender_id in mapping[arg]:
                mapping[arg].remove(sender_id)
                if len(mapping[arg]) == 0:
                    mapping.pop(arg)

        await print_mapping()

    async def finished_callback(room, event):
        nonlocal mapping
        arg = get_arg_as_single(event)

        if (arg in mapping):
            mapping.pop(arg)

        await print_mapping()

    doing_handler = plugin.CommandHandler("doing", doing_callback)
    plugin.add_handler(doing_handler)

    cleardoing_handler = plugin.CommandHandler("cleardoing", cleardoing_callback)
    plugin.add_handler(cleardoing_handler)

    done_handler = plugin.CommandHandler("done", done_callback)
    plugin.add_handler(done_handler)

    finished_handler = plugin.CommandHandler("finished", finished_callback)
    plugin.add_handler(finished_handler)
