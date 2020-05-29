import random

def format_event(event, content, verbose=True, use="markdown"):
    # the use parameter should toggle different styles in the future (greyed
    # out, verbose, emojis, ...)
    # and make the verbose flag obsolete
    # from https://docs.gitlab.com/ee/user/project/integrations/webhooks.html
    events = ["Push Hook",
            "Tag Push Hook",
            "Issue Hook",
            "Note Hook",
            "Merge Request Hook",
            "Wiki Page Hook",
            "Pipeline Hook",
            "Job Hook"]
    #animals = "🐶🐺🦊🦝🐱🐱🦁🐯"
    animals = "🦊"
    animal = random.choice(animals)


    # PUSH HOOK
    if event == "Push Hook":
        user_name = content['user_name']
        user_email = content['user_email']
        if "ref" in content:
            ref = content['ref']
        else:
            ref = ""
        branch = ref.split("/")[-1]
        if "project" in content:
            projectname = content['project']['name']
            projecturl = content['project']['web_url']
        else:
            projectname = ""
        if not "commits" in content:
            commits = []
        else:
            commits = content['commits']

        if commits:
            lastcommiturl = content['commits'][0]['url']
            lastcommittitle = commits[0]
        else:
            lastcommiturl = ""
            lastcommittitle = ""

        if not verbose:
            return f'{animal} {user_name}({user_email}) pushed to 🌿 {branch} of {projectname}: {lastcommittitle}, {lastcommiturl}'
        else:
            if use.lower() == "html":
                s =  f"{animal} {user_name} (<a href='mailto:{user_email}'>{user_email}</a>) pushed to 🌿 {branch} of <a href={projecturl}>{projectname}</a><ul>\n"
                s += "\n".join(f"<li>{commit['title']} (<a href={commit['url']}>{commit['id'][:7]}</a>)</li>" for commit in commits)
                s += "</ul>"
            else:
                s =  f"{animal} {user_name}({user_email}) pushed to 🌿 {branch} of {projectname} {projecturl}\n"
                s += "\n".join(f"* {commit['title']} ({commit['url']})" for commit in commits)
        return s


    # TAG PUSH HOOK
    if event == "Tag Push Hook":
        user_name = content['user_name']
        user_email = content['user_email']
        zeroes = "0000000000000000000000000000000000000000"
        if content['after'] == zeroes:
            action = "deleted"
        elif content['before'] == zeroes:
            action = "pushed new"
        else:
            action = "changed"
        if "ref" in content:
            ref = content['ref']
        else:
            ref = ""
        tagname = ref.split("/")[-1]
        project = content['project']['name']
        projecturl = content['project']['web_url']
        return f"{animal} {user_name} ({user_email}) {action} remote 🏷{tagname} n <a href={projecturl}>{project}</a>"


    # ISSUE HOOK
    if event == "Issue Hook":
        user_email = content['user']['email']
        user_name = content['user']['name']
        if "ref" in content:
            ref = content['ref']
        else:
            ref = ""
        oa = content['object_attributes']
        issuetitle = oa['title']
        issueurl = oa['url']
        issueid = oa['iid']
        action = oa['action']
        actionpassive = action + "ed" if "open" in action else action + "d" # opened and reopened
        new = "new issue" if action == "open" else "issue"
        #TODO: check confidential attribute
        #TODO: print exact changes (also labels, etc, description if new) when verbose is set
        project = content['project']['name']
        projecturl = content['project']['web_url']
        return f"{animal} {user_name} ({user_email}) {actionpassive} {new} <a href={issueurl}>#{issueid} {issuetitle}</a> in <a href={projecturl}>{project}</a>"
    
    if event == "Note Hook":
        user_email = content['user']['email']
        user_name = content['user']['name']
        oa = content['object_attributes']
        noteable_type

    # TODO: note hook
    # TODO: merge request hook
    # TODO: wiki hook
    # TODO: pipeline hook
    # TODO: job hook

    return f"Unknown event received: {event}. Please poke the maintainers."
