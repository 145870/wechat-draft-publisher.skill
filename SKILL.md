---
name: wechat-draft-skill
description: Create WeChat Official Account drafts from Markdown, HTML, plain text, or an article request by using the WeChat API. Use when the user asks to send, publish, save, upload, or draft an article for a WeChat Official Account, including Chinese-language requests about gongzhonghao, WeChat public account articles, WeChat drafts, saved drafts, or sending an article to an official account. The skill creates drafts by default and should not mass-send automatically unless the user explicitly asks for publish behavior.
---

# WeChat Draft Skill

Use this skill to create a WeChat Official Account draft through the WeChat API. Prefer direct execution: when required inputs are available from the user request, local files, or environment variables, run the script immediately instead of asking for confirmation. Ask the user only when a required value is missing and cannot be inferred, such as credentials, title, article body, or cover image / `thumb_media_id`.

## Execution Policy

- Default to `draft`, not `publish`; creating a draft is the safe action.
- Do not ask "should I execute?" after the user has asked to create or send a draft.
- If `WECHAT_APP_ID`, `WECHAT_APP_SECRET`, title, content, and cover information are present, run the command directly.
- If the user asks to publish but the account/API cannot publish, keep the draft and report the draft `media_id`.
- Never expose `WECHAT_APP_SECRET` in the final response or logs.

## Configuration

The script reads credentials in this order:

1. CLI arguments: `--appid`, `--secret`
2. Environment variables
3. `.env.local` or `.env` in the skill root or `scripts/` directory

Required values:

| Variable | Required | Description |
|---|---:|---|
| `WECHAT_APP_ID` | yes | WeChat Official Account AppID |
| `WECHAT_APP_SECRET` | yes | WeChat Official Account AppSecret |
| `WECHAT_THUMB_MEDIA_ID` | no | Existing cover image media id |
| `WECHAT_AUTHOR` | no | Default author name |

Copy `.env.example` to `.env` and fill in real values if environment variables are not already set.

## Commands

Run commands from the skill directory:

```bash
python scripts/wechat_draft.py upload cover.jpg
python scripts/wechat_draft.py draft --title "Title" --file article.md --cover cover.jpg
python scripts/wechat_draft.py draft --title "Title" --content "<p>Body</p>" --thumb-id "media_id"
python scripts/wechat_draft.py publish --title "Title" --file article.md --cover cover.jpg
```

Use `draft` for normal requests. Use `publish` only when the user explicitly asks for actual publishing.

## Content Handling

- `.md` files are converted to WeChat-compatible HTML by the script.
- `.html` and `.txt` files are used as provided.
- `--cover` uploads a local image and uses the returned `media_id`.
- `--thumb-id` uses an existing permanent material `media_id`.

## Result Reporting

After a successful draft creation, report:

- The draft `media_id`
- That the article is saved as a WeChat draft
- That final preview and mass-send should be handled in `mp.weixin.qq.com` when needed

For common API errors, include the practical fix:

| errcode | Meaning | Fix |
|---:|---|---|
| `40164` | IP is not whitelisted | Add the current public IP to the WeChat Official Account IP whitelist |
| `40007` | Invalid `media_id` | Upload the cover again or provide a valid `thumb_media_id` |
| `48001` | API permission unavailable | Keep the draft and finish manually in the WeChat backend |
