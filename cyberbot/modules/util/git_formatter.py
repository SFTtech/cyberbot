from __future__ import annotations

import html
import textwrap
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class User(BaseModel):
    login: str
    name: str | None
    url: str | None


class Repo(BaseModel):
    name: str
    url: str | None


class WorkItem(BaseModel):  # Issue, Task, Incident, ...
    number: int
    title: str | None
    url: str | None


class PR(WorkItem):
    state: str


class Ref(BaseModel):
    ref: str
    ref_type: str


class Commit(BaseModel):
    id: str
    title: str
    author: User
    url: str | None


class GitFormatter(ABC):
    @abstractmethod
    def format(str, event: str, content: Any, config: dict[str, bool]) -> str | None:
        """
        given an event, payload content and configuration, return a html text from a Git event.
        """
        pass

    @abstractmethod
    def get_config(self) -> dict[str, bool]:
        """
        return the default config dict which can be customized and persisted in storage.
        """
        pass


class GitEventFormatter(ABC):
    def __init__(self, emojis: bool, main_emoji: str | None) -> None:
        self.emojis = emojis
        self._main_emoji = main_emoji

    def format(self) -> str | None:
        """
        return html representation of event with formatting options
        """
        content = self._get_content()
        if not content:
            return None

        content = content.replace("\n", "<br/>")
        content = content.replace("\\n", "\n")

        if self.emojis:
            return f"{self._main_emoji} {content}"

        return content

    @abstractmethod
    def _get_content(self) -> str | None:
        pass

    def _format_link(self, url: str, linktext: str):
        return f"<a href='{url}'>{linktext}</a>"

    def _format_text_block(self, text: str, cut: int = 2, line_cut: int = 130) -> str:
        if cut and text.count("\n") > cut:
            lines = text.split('\n')[:cut]
            cut_lines = [textwrap.shorten(line, width=line_cut) for line in lines]
            res = f"{'\n'.join(cut_lines)}\n..."
        else:
            res = text
        res = html.escape(res)
        return f"<pre><code>{res}</code></pre>"

    def _format_repo(self, repo: Repo) -> str:
        if repo.url:
            return self._format_link(repo.url, repo.name)
        else:
            return repo.name

    def _format_user(self, user: User) -> str:
        name = user.name or user.login
        if user.url:
            return self._format_link(user.url, name)
        return name

    def _format_branch(self, branchname: str) -> str:
        if self.emojis:
            return f"🌿 {branchname}"
        else:
            return f"branch {branchname}"

    def _format_tag(self, tagname: str) -> str:
        if self.emojis:
            return f"🏷 {tagname}"
        else:
            return f"tag {tagname}"

    def _format_ref(self, ref: Ref) -> str:
        match ref.ref_type:
            case "branch":
                return self._format_branch(ref.ref.lstrip("refs/heads/"))
            case "tag":
                return self._format_tag(ref.ref.lstrip("refs/tags/"))
            case _:
                return ref.ref

    def _format_workitem_nr(self, work_item: WorkItem, href=True) -> str:
        res = f"#{work_item.number}"
        if href and (url := work_item.url):
            return self._format_link(url, res)
        return res

    def _format_workitem_title(self, work_item: WorkItem, href=True) -> str:
        res = f"#{work_item.number} {work_item.title}"
        if href and (url := work_item.url):
            return self._format_link(url, res)
        return res

    def _format_pr_title(self, pr: PR, href=True) -> str:
        res = f"#{pr.number} {pr.title}"
        if href and (url := pr.url):
            return self._format_link(url, res)
        return res

    def _format_commit(self, commit: Commit, href=True, branch=False, max_width: int = 75, hashlen: int = 7) -> str:
        message = textwrap.shorten(commit.title, width=max_width)
        commithash = commit.id[:hashlen]
        if href and commit.url:
            fmt = f"{message} ({self._format_link(commit.url, commithash)})"
        else:
            fmt = f"{message} ({commithash})"

        if branch:
            fmt = f"⇨ {fmt}"
        return fmt

    def _format_commits(self, commits: list[Commit], max_commits: int) -> str:
        """
        format commits as bullet list and place newest on top.
        expects commits where HEAD is last in list.
        """
        cut_fmt = ""
        if max_commits:
            commits = commits[-max_commits:]
            if len(commits) > max_commits:
                cut_fmt = "<li>... and more</li>"

        if commits:
            # HEAD first
            commits.reverse()

            commits_fmt = "\\n".join(
                f"<li>{self._format_commit(commit, branch=(i==0))}</li>"
                for (i, commit) in enumerate(commits)
            )
            return f"<ul>{commits_fmt}{cut_fmt}</ul>"
        else:
            return "no commits"

    def _format_repo_event(self, repo: Repo, event: str) -> str:
        return f"{self._format_repo(repo)}: {event}"

    def _format_repo_action(self, repo: Repo, user: User, action: str) -> str:
        return f"{self._format_repo(repo)}: {self._format_user(user)} {action}"

    def _format_state(self, text: str, state: str="success", prefix: bool = False) -> str:
        if self.emojis:
            emoji = {
                "success": "✅",
                "fail": "❌",
                #"pending": "...",
                #"running": "...",
                "skipped": "➡️",
                "created": "✨️",
                "confirmed": "☑️",
            }.get(state)

            if emoji:
                if prefix:
                    return f"{emoji} {text}"
                else:
                    return f"{text} {emoji}"

        return text
