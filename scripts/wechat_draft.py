#!/usr/bin/env python3
"""
微信公众号草稿发布器
功能：获取 access_token、上传封面图、创建草稿、智能发布
"""

import requests
import json
import os
import sys
import time
import re
from pathlib import Path
from typing import Optional


class WeChatDraftPublisher:
    """微信公众号草稿发布器"""

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
        # 优先使用传入参数，其次环境变量，最后 .env 文件
        self.app_id = app_id or os.getenv("WECHAT_APP_ID", "")
        self.app_secret = app_secret or os.getenv("WECHAT_APP_SECRET", "")
        self.author = author or os.getenv("WECHAT_AUTHOR", "")
        self.thumb_media_id = thumb_media_id or os.getenv("WECHAT_THUMB_MEDIA_ID", "")
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

        # 尝试从 .env / .env.local 加载
        self._load_env()

        if not self.app_id or not self.app_secret:
            raise ValueError(
                "请设置 WECHAT_APP_ID 和 WECHAT_APP_SECRET\n"
                "方式1: 设置环境变量\n"
                "方式2: 在同目录创建 .env 文件\n"
                "方式3: 初始化时传入 app_id/app_secret"
            )

    def _load_env(self):
        """加载 .env / .env.local 文件"""
        script_dir = Path(__file__).parent
        for env_file in [script_dir / ".env.local", script_dir / ".env"]:
            if env_file.exists():
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
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
        """获取或刷新 access_token（带缓存）"""
        if self._access_token and time.time() < self._token_expires_at - 300:
            return self._access_token

        resp = requests.get(
            self.TOKEN_URL,
            params={
                "grant_type": "client_credential",
                "appid": self.app_id,
                "secret": self.app_secret,
            },
            timeout=15,
        )
        data = resp.json()

        if "access_token" not in data:
            raise Exception(f"获取 access_token 失败: {json.dumps(data, ensure_ascii=False)}")

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 7200)
        return self._access_token

    def upload_image(self, image_path: str) -> str:
        """上传图片到微信永久素材库，返回 media_id"""
        token = self.get_access_token()

        # 自动处理图片路径
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"图片不存在: {image_path}")

        # 判断 MIME 类型
        ext = path.suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif"}
        content_type = mime_map.get(ext, "image/jpeg")

        with open(path, "rb") as f:
            resp = requests.post(
                self.UPLOAD_URL,
                params={"access_token": token, "type": "image"},
                files={"media": (path.name, f, content_type)},
                timeout=30,
            )

        data = resp.json()
        if "media_id" not in data:
            raise Exception(f"上传图片失败: {json.dumps(data, ensure_ascii=False)}")

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
        """
        创建草稿

        参数:
            title: 文章标题（必填）
            content: 文章正文 HTML（必填）
            thumb_media_id: 封面图 media_id，为空则使用默认配置
            author: 作者名，为空则使用配置默认值
            digest: 摘要
            content_source_url: 原文链接
            need_open_comment: 是否打开评论（0/1）
            only_fans_can_comment: 是否仅粉丝可评论（0/1）
            cover_image_path: 封面图本地路径，提供后自动上传

        返回:
            {"media_id": "xxx", "errcode": 0, ...}
        """
        token = self.get_access_token()

        # 处理封面图：传入路径则上传，否则用已有 media_id
        if cover_image_path:
            thumb_media_id = self.upload_image(cover_image_path)
        if not thumb_media_id:
            thumb_media_id = self.thumb_media_id
        if not thumb_media_id:
            raise ValueError("请提供封面图：传入 thumb_media_id 或 cover_image_path")

        # 处理作者名
        if not author:
            author = self.author

        article = {
            "title": title,
            "thumb_media_id": thumb_media_id,
            "content": content,
            "need_open_comment": need_open_comment,
            "only_fans_can_comment": only_fans_can_comment,
        }

        if author:
            article["author"] = author
        if digest:
            article["digest"] = digest
        if content_source_url:
            article["content_source_url"] = content_source_url

        payload = json.dumps({"articles": [article]}, ensure_ascii=False)
        resp = requests.post(
            self.DRAFT_URL,
            params={"access_token": token},
            data=payload.encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=15,
        )

        result = resp.json()
        if "media_id" not in result:
            errcode = result.get("errcode")
            errmsg = result.get("errmsg", "未知错误")

            # 友好提示常见错误
            tips = self._error_tips(errcode)
            raise Exception(f"创建草稿失败 [{errcode}]: {errmsg}\n{tips}")

        return result

    def publish(self, media_id: str) -> dict:
        """
        发布草稿

        参数:
            media_id: 草稿 media_id

        返回:
            {"published": True, "publish_id": "xxx"} 或 {"published": False, "reason": "..."}
        """
        token = self.get_access_token()
        resp = requests.post(
            self.PUBLISH_URL,
            params={"access_token": token},
            json={"media_id": media_id},
            timeout=15,
        )
        data = resp.json()
        errcode = data.get("errcode", 0)

        if errcode == 0:
            return {
                "published": True,
                "publish_id": data.get("publish_id", ""),
            }
        else:
            return {
                "published": False,
                "reason": data.get("errmsg", ""),
            }

    def smart_publish(
        self,
        title: str,
        content: str,
        thumb_media_id: str = "",
        author: str = "",
        digest: str = "",
        content_source_url: str = "",
        cover_image_path: str = "",
    ) -> dict:
        """
        智能发布：先创建草稿，再尝试发布。不支持发布时保留草稿。

        返回:
            {"mode": "published"|"draft_only", "media_id": "xxx", "message": "..."}
        """
        # Step 1: 创建草稿
        draft_result = self.create_draft(
            title=title,
            content=content,
            thumb_media_id=thumb_media_id,
            author=author,
            digest=digest,
            content_source_url=content_source_url,
            cover_image_path=cover_image_path,
        )
        media_id = draft_result["media_id"]

        # Step 2: 尝试发布
        try:
            publish_result = self.publish(media_id)
        except Exception as e:
            # 发布接口报错不可预期，保留草稿
            return {
                "mode": "draft_only",
                "media_id": media_id,
                "message": f"发布接口异常: {e}，草稿已保存",
            }

        if publish_result["published"]:
            return {
                "mode": "published",
                "media_id": media_id,
                "publish_id": publish_result["publish_id"],
                "message": "文章已发布成功！",
            }
        else:
            return {
                "mode": "draft_only",
                "media_id": media_id,
                "message": publish_result["reason"] + "，草稿已保存，请手动群发",
            }

    @staticmethod
    def _error_tips(errcode: int) -> str:
        tips = {
            40164: "将运行环境公网 IP 添加到公众号后台 → 设置与开发 → 基本配置 → IP白名单",
            40007: "检查 thumb_media_id 是否有效，或重新上传封面图",
            48001: "个人订阅号不支持此操作",
            -1: "检查网络连接，确认 AppID/AppSecret 是否正确",
        }
        return tips.get(errcode, "")

    @classmethod
    def _convert_markdown_table(cls, lines: list) -> str:
        """将 Markdown 表格行转为微信兼容 HTML 表格"""
        if len(lines) < 2:
            return "\n".join(lines)

        # 解析表头
        header_cells = [c.strip() for c in lines[0].strip("|").split("|")]

        # 跳过分隔行（|----|----|）
        body_start = 1
        if lines[1].strip().replace(" ", "").replace("-", "").replace("|", "") == "":
            body_start = 2

        # 解析数据行
        data_rows = []
        for line in lines[body_start:]:
            if line.strip().startswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                data_rows.append(cells)

        # 构建 HTML 表格
        table_style = 'border-collapse:collapse;width:100%;margin:10px 0;font-size:13px;'
        th_style = 'border:1px solid #ddd;padding:6px 8px;background-color:#f5f7fa;text-align:center;font-weight:bold;'
        td_base = 'border:1px solid #ddd;padding:6px 8px;'

        html = f'<table style="{table_style}">\n<thead>\n<tr>'
        for cell in header_cells:
            html += f'<th style="{th_style}">{cell}</th>'
        html += '</tr>\n</thead>\n<tbody>\n'

        for row in data_rows:
            html += '<tr>'
            for i, cell in enumerate(row):
                align = 'left' if i == 0 else 'center'
                html += f'<td style="{td_base}text-align:{align};">{cell}</td>'
            html += '</tr>\n'

        html += '</tbody>\n</table>'
        return html

    @classmethod
    def markdown_to_html(cls, markdown_text: str) -> str:
        """将 Markdown 转为微信兼容 HTML（含表格）"""
        html = markdown_text

        # 先处理表格——识别连续的 | 开头的行
        lines = html.split("\n")
        output_lines = []
        table_buffer = []
        in_table = False

        for line in lines:
            if line.strip().startswith("|") and "|" in line.strip()[1:]:
                if not in_table:
                    in_table = True
                    table_buffer = []
                table_buffer.append(line)
            else:
                if in_table and table_buffer:
                    output_lines.append(cls._convert_markdown_table(table_buffer))
                    table_buffer = []
                    in_table = False
                output_lines.append(line)

        if in_table and table_buffer:
            output_lines.append(cls._convert_markdown_table(table_buffer))

        html = "\n".join(output_lines)

        # 标题
        html = re.sub(r"^#### (.+)$", r'<h4 style="font-weight:bold;">\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r"^### (.+)$", r'<h3 style="font-weight:bold;font-size:16px;">\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r'<h2 style="font-weight:bold;font-size:18px;">\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)$", r'<h1 style="font-weight:bold;font-size:20px;text-align:center;">\1</h1>', html, flags=re.MULTILINE)

        # 加粗、斜体
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

        # 图片
        html = re.sub(r"!\[(.*?)\]\((.*?)\)", r'<img src="\2" alt="\1">', html)

        # 链接
        html = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', html)

        # 列表
        html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
        html = re.sub(r"(<li>.*?</li>\n?)+", r"<ul>\g<0></ul>", html)

        # 段落包裹（跳过已有 HTML 块）
        paragraphs = html.split("\n\n")
        wrapped = []
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            if p.startswith("<h") or p.startswith("<ul") or p.startswith("<img") or p.startswith("<table") or p.startswith("<blockquote"):
                wrapped.append(p)
            elif p.startswith("<li>"):
                wrapped.append(f"<ul>{p}</ul>")
            else:
                wrapped.append(f'<p style="font-size:15px;line-height:1.75;">{p}</p>')
        return "\n".join(wrapped)


# ==================== 命令行入口 ====================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="微信公众号发布器（优先发布，不支持则保留草稿）")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 上传封面图
    upload_parser = subparsers.add_parser("upload", help="上传封面图")
    upload_parser.add_argument("image", help="封面图路径")
    upload_parser.add_argument("--appid", help="AppID")
    upload_parser.add_argument("--secret", help="AppSecret")

    # 仅创建草稿
    draft_parser = subparsers.add_parser("draft", help="仅创建草稿（不尝试发布）")
    draft_parser.add_argument("--title", required=True, help="文章标题")
    draft_parser.add_argument("--content", help="文章正文 HTML，或提供 --file")
    draft_parser.add_argument("--file", help="从文件读取正文（.md/.html/.txt）")
    draft_parser.add_argument("--cover", help="封面图路径")
    draft_parser.add_argument("--thumb-id", help="封面图 media_id")
    draft_parser.add_argument("--author", help="作者名")
    draft_parser.add_argument("--digest", help="摘要")
    draft_parser.add_argument("--source-url", help="原文链接")
    draft_parser.add_argument("--appid", help="AppID")
    draft_parser.add_argument("--secret", help="AppSecret")

    # 智能发布：尝试发布，不支持则保留草稿
    publish_parser = subparsers.add_parser("publish", help="智能发布（优先发布，不支持则保存草稿）")
    publish_parser.add_argument("--title", required=True, help="文章标题")
    publish_parser.add_argument("--content", help="文章正文 HTML，或提供 --file")
    publish_parser.add_argument("--file", help="从文件读取正文（.md/.html/.txt）")
    publish_parser.add_argument("--cover", help="封面图路径")
    publish_parser.add_argument("--thumb-id", help="封面图 media_id")
    publish_parser.add_argument("--author", help="作者名")
    publish_parser.add_argument("--digest", help="摘要")
    publish_parser.add_argument("--source-url", help="原文链接")
    publish_parser.add_argument("--appid", help="AppID")
    publish_parser.add_argument("--secret", help="AppSecret")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    publisher = WeChatDraftPublisher(
        app_id=getattr(args, "appid", None),
        app_secret=getattr(args, "secret", None),
    )

    if args.command == "upload":
        media_id = publisher.upload_image(args.image)
        print(f"上传成功\nmedia_id: {media_id}")

    elif args.command == "draft":
        content = _load_content(args, publisher)
        try:
            result = publisher.create_draft(
                title=args.title,
                content=content,
                cover_image_path=args.cover or "",
                thumb_media_id=args.thumb_id or "",
                author=args.author or "",
                digest=args.digest or "",
                content_source_url=args.source_url or "",
            )
            print(f"草稿创建成功！media_id: {result['media_id']}")
            print("请登录 mp.weixin.qq.com → 草稿箱 → 手动群发")
        except Exception as e:
            print(f"失败: {e}")
            sys.exit(1)

    elif args.command == "publish":
        content = _load_content(args, publisher)
        try:
            result = publisher.smart_publish(
                title=args.title,
                content=content,
                cover_image_path=args.cover or "",
                thumb_media_id=args.thumb_id or "",
                author=args.author or "",
                digest=args.digest or "",
                content_source_url=args.source_url or "",
            )
            print(f"模式: {result['mode']}")
            print(f"media_id: {result['media_id']}")
            if result["mode"] == "published":
                print(f"publish_id: {result['publish_id']}")
            print(f"结果: {result['message']}")
        except Exception as e:
            print(f"失败: {e}")
            sys.exit(1)

    else:
        parser.print_help()


def _load_content(args, publisher):
    """辅助：从 --file 或 --content 加载正文"""
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"文件不存在: {args.file}")
            sys.exit(1)
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()
        if file_path.suffix.lower() == ".md":
            return publisher.markdown_to_html(raw)
        return raw
    if args.content:
        return args.content
    print("请提供 --content 或 --file")
    sys.exit(1)
