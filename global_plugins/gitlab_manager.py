import logging

from git_manager import GitManager


async def parse_request(request, tokens):
    token = request.headers.get("X-Gitlab-Token")
    event = request.headers.get("X-Gitlab-Event")
    return token, event


logging.info("Creating GitLabManager")
Object = GitManager("gitlab", parse_request)
