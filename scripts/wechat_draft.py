#!/usr/bin/env python3
"""Create WeChat Official Account drafts from local content."""

import argparse
import html
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import requests


class WeChatDraftPublisher:
    TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
    UPLOAD_URL = "https://api.weixin.qq.com/cgi-bin/material/add_material"
    DRAFT_URL = "https://api.weixin.qq.com/cgi-bin/draft/add"
    PUBLISH_URL = "https://api.weixin.qq.com/cgi-bin/freepublish/submit"

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        author: str = "",
        thumb_media_id: str = "",
    ):
        self.app_id = app_id or os.getenv("WECHAT_APP_ID", "")
        self.app_secret = app_secret or os.getenv("WECHAT_APP_SECRET", "")
        self.author = author or os.getenv("WECHAT_AUTHOR", "")
        self.thumb_media_id = thumb_media_id or os.getenv("WECHAT_THUMB_MEDIA_ID", "")
        self._access_token: Optional[str] = None
        self._token_expires_at = 0.0

        self._load_env()

        if not self.app_id or not self.app_secret:
            raise ValueError(
                "Set WECHAT_APP_ID and WECHAT_APP_SECRET with CLI args, "
                "environment variables, or a .env file."
            )

    def _load_env(self) -> None:
        script_dir = Path(__file__).resolve().parent
        skill_dir = script_dir.parent
        env_files = [
            skill_dir / ".env.local",
            skill_dir / ".env",
            script_dir / ".env.local",
            script_dir / ".env",
        ]

        for env_file in env_files:
            if not env_file.exists():
                continue
            for raw_line in env_file.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key == "WECHAT_APP_ID" and not self.app_id:
                    self.app_id = value
                elif key == "WECHAT_APP_SECRET" and not self.app_secret:
                    self.app_secret = value
                elif key == "WECHAT_AUTHOR" and not self.author:
                    self.author = value
                elif key == "WECHAT_THUMB_MEDIA_ID" and not self.thumb_media_id:
                    self.thumb_media_id = value

    def get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 300:
            return self._access_token

        response = requests.get(
            self.TOKEN_URL,
            params={
                "grant_type": "client_credential",
                "appid": self.app_id,
                "secret": self.app_secret,
            },
            timeout=15,
        )
        data = response.json()

        if "access_token" not in data:
            raise RuntimeError(f"Failed to get access_token: {json.dumps(data, ensure_ascii=False)}")

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 7200)
        return self._access_token

    def upload_image(self, image_path: str) -> str:
        token = self.get_access_token()
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image does not exist: {image_path}")

        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
        }
        content_type = mime_map.get(path.suffix.lower(), "image/jpeg")

        with path.open("rb") as file:
            response = requests.post(
                self.UPLOAD_URL,
                params={"access_token": token, "type": "image"},
                files={"media": (path.name, file, content_type)},
                timeout=30,
            )

        data = response.json()
        if "media_id" not in data:
            raise RuntimeError(f"Failed to upload image: {json.dumps(data, ensure_ascii=False)}")
        return data["media_id"]

    def create_draft(
        self,
        title: str,
        content: str,
        thumb_media_id: str = "",
        author: str = "",
        digest: str = "",
        content_source_url: str = "",
        need_open_comment: int = 0,
        only_fans_can_comment: int = 0,
        cover_image_path: str = "",
    ) -> dict:
        token = self.get_access_token()

        if cover_image_path:
            thumb_media_id = self.upload_image(cover_image_path)
        if not thumb_media_id:
            thumb_media_id = self.thumb_media_id
        if not thumb_media_id:
            raise ValueError("Provide a cover image with --cover or an existing --thumb-id.")

        article = {
            "title": title,
            "thumb_media_id": thumb_media_id,
            "content": content,
            "need_open_comment": need_open_comment,
            "only_fans_can_comment": only_fans_can_comment,
        }

        author = author or self.author
        if author:
            article["author"] = author
        if digest:
            article["digest"] = digest
        if content_source_url:
            article["content_source_url"] = content_source_url

        response = requests.post(
            self.DRAFT_URL,
            params={"access_token": token},
            data=json.dumps({"articles": [article]}, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=15,
        )
        result = response.json()

        if "media_id" not in result:
            errcode = result.get("errcode")
            errmsg = result.get("errmsg", "unknown error")
            raise RuntimeError(f"Failed to create draft [{errcode}]: {errmsg}\n{self._error_tip(errcode)}")

        return result

    def publish(self, media_id: str) -> dict:
        token = self.get_access_token()
        response = requests.post(
            self.PUBLISH_URL,
            params={"access_token": token},
            json={"media_id": media_id},
            timeout=15,
        )
        data = response.json()
        if data.get("errcode", 0) == 0:
            return {"published": True, "publish_id": data.get("publish_id", "")}
        return {"published": False, "reason": data.get("errmsg", "")}

    def smart_publish(self, **kwargs) -> dict:
        draft_result = self.create_draft(**kwargs)
        media_id = draft_result["media_id"]

        try:
            publish_result = self.publish(media_id)
        except Exception as exc:
            return {
                "mode": "draft_only",
                "media_id": media_id,
                "message": f"Publish API failed: {exc}. Draft was saved.",
            }

        if publish_result["published"]:
            return {
                "mode": "published",
                "media_id": media_id,
                "publish_id": publish_result["publish_id"],
                "message": "Article published successfully.",
            }
        return {
            "mode": "draft_only",
            "media_id": media_id,
            "message": f"{publish_result['reason']}. Draft was saved; finish manually in WeChat backend.",
        }

    @staticmethod
    def _error_tip(errcode: Optional[int]) -> str:
        tips = {
            40164: "Add the current public IP to the WeChat Official Account IP whitelist.",
            40007: "Check thumb_media_id or upload the cover image again.",
            48001: "The account does not have this API permission; keep the draft and finish manually.",
            -1: "Check network connectivity and verify AppID/AppSecret.",
        }
        return tips.get(errcode, "")

    @classmethod
    def markdown_to_html(cls, markdown_text: str) -> str:
        text = html.escape(markdown_text)
        text = cls._convert_tables(text)

        text = re.sub(r"^#### (.+)$", r'<h4 style="font-weight:bold;">\1</h4>', text, flags=re.MULTILINE)
        text = re.sub(r"^### (.+)$", r'<h3 style="font-weight:bold;font-size:16px;">\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r"^## (.+)$", r'<h2 style="font-weight:bold;font-size:18px;">\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r"^# (.+)$", r'<h1 style="font-weight:bold;font-size:20px;text-align:center;">\1</h1>', text, flags=re.MULTILINE)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        text = re.sub(r"!\[(.*?)\]\((.*?)\)", r'<img src="\2" alt="\1">', text)
        text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
        text = re.sub(r"^- (.+)$", r"<li>\1</li>", text, flags=re.MULTILINE)
        text = re.sub(r"(<li>.*?</li>\n?)+", r"<ul>\g<0></ul>", text)

        wrapped = []
        for paragraph in text.split("\n\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if paragraph.startswith(("<h", "<ul", "<img", "<table", "<blockquote")):
                wrapped.append(paragraph)
            elif paragraph.startswith("<li>"):
                wrapped.append(f"<ul>{paragraph}</ul>")
            else:
                wrapped.append(f'<p style="font-size:15px;line-height:1.75;">{paragraph}</p>')
        return "\n".join(wrapped)

    @staticmethod
    def _convert_tables(text: str) -> str:
        lines = text.splitlines()
        output = []
        table_buffer = []

        def flush_table() -> None:
            if table_buffer:
                output.append(WeChatDraftPublisher._table_to_html(table_buffer))
                table_buffer.clear()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("|") and "|" in stripped[1:]:
                table_buffer.append(line)
            else:
                flush_table()
                output.append(line)
        flush_table()
        return "\n".join(output)

    @staticmethod
    def _table_to_html(lines: list[str]) -> str:
        if len(lines) < 2:
            return "\n".join(lines)

        headers = [cell.strip() for cell in lines[0].strip("|").split("|")]
        body_lines = lines[2:] if re.fullmatch(r"\s*\|?[\s:\-|]+\|?\s*", lines[1]) else lines[1:]
        rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in body_lines]

        table_style = "border-collapse:collapse;width:100%;margin:10px 0;font-size:13px;"
        th_style = "border:1px solid #ddd;padding:6px 8px;background-color:#f5f7fa;text-align:center;font-weight:bold;"
        td_style = "border:1px solid #ddd;padding:6px 8px;"

        parts = [f'<table style="{table_style}">', "<thead><tr>"]
        parts.extend(f'<th style="{th_style}">{cell}</th>' for cell in headers)
        parts.append("</tr></thead><tbody>")
        for row in rows:
            parts.append("<tr>")
            for index, cell in enumerate(row):
                align = "left" if index == 0 else "center"
                parts.append(f'<td style="{td_style}text-align:{align};">{cell}</td>')
            parts.append("</tr>")
        parts.append("</tbody></table>")
        return "\n".join(parts)


def load_content(args: argparse.Namespace, publisher: WeChatDraftPublisher) -> str:
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            raise FileNotFoundError(f"File does not exist: {args.file}")
        raw = file_path.read_text(encoding="utf-8")
        if file_path.suffix.lower() == ".md":
            return publisher.markdown_to_html(raw)
        return raw
    if args.content:
        return args.content
    raise ValueError("Provide --content or --file.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create WeChat Official Account drafts.")
    subparsers = parser.add_subparsers(dest="command", help="subcommands")

    upload_parser = subparsers.add_parser("upload", help="upload a cover image")
    upload_parser.add_argument("image", help="cover image path")
    upload_parser.add_argument("--appid", help="AppID")
    upload_parser.add_argument("--secret", help="AppSecret")

    for command, help_text in [
        ("draft", "create a draft only"),
        ("publish", "create a draft and try to publish it"),
    ]:
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument("--title", required=True, help="article title")
        command_parser.add_argument("--content", help="article HTML/plain text; use --file for files")
        command_parser.add_argument("--file", help="article file path (.md/.html/.txt)")
        command_parser.add_argument("--cover", help="cover image path")
        command_parser.add_argument("--thumb-id", help="existing cover media_id")
        command_parser.add_argument("--author", help="author name")
        command_parser.add_argument("--digest", help="article digest")
        command_parser.add_argument("--source-url", help="source URL")
        command_parser.add_argument("--appid", help="AppID")
        command_parser.add_argument("--secret", help="AppSecret")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    try:
        publisher = WeChatDraftPublisher(
            app_id=getattr(args, "appid", None),
            app_secret=getattr(args, "secret", None),
        )

        if args.command == "upload":
            media_id = publisher.upload_image(args.image)
            print(f"Upload succeeded\nmedia_id: {media_id}")
            return 0

        content = load_content(args, publisher)
        draft_kwargs = {
            "title": args.title,
            "content": content,
            "cover_image_path": args.cover or "",
            "thumb_media_id": args.thumb_id or "",
            "author": args.author or "",
            "digest": args.digest or "",
            "content_source_url": args.source_url or "",
        }

        if args.command == "draft":
            result = publisher.create_draft(**draft_kwargs)
            print(f"Draft created\nmedia_id: {result['media_id']}")
            print("Open mp.weixin.qq.com to preview and mass-send manually if needed.")
            return 0

        if args.command == "publish":
            result = publisher.smart_publish(**draft_kwargs)
            print(f"mode: {result['mode']}")
            print(f"media_id: {result['media_id']}")
            if result["mode"] == "published":
                print(f"publish_id: {result['publish_id']}")
            print(f"result: {result['message']}")
            return 0

        parser.print_help()
        return 1
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
