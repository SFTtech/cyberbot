import hmac
import logging

from git_manager import GitManager


async def parse_request(request, tokens):
    if "X-Hub-Signature-256" not in request.headers:
        return None, None
    sig = request.headers.get("X-Hub-Signature-256").split("=")[1]
    if "X-GitHub-Event" not in request.headers:
        return None, None
    event = request.headers.get("X-GitHub-Event")

    # how to check if not really is from github and simultaniously find out which token was used:
    # https://docs.github.com/en/developers/webhooks-and-events/securing-your-webhooks
    # we just check all tokens and if one has a matching hash, this is the one
    # linearly in number of tokens and slow as we compute a hash until we find the token
    # also probably vulnerable to timing attacks. But at the moment I don't have a better idea

    c = await request.content.read()
    for token in tokens:
        h = hmac.new(bytes(token, encoding="utf8"), c, "sha256")
        if hmac.compare_digest(h.hexdigest(), sig):
            return token, event

    return None, None


logging.info("Creating GitHubManager")
Object = GitManager("github", parse_request)
