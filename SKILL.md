---
name: wechat-draft-publisher
description: 微信公众号草稿发布器。通过微信 API 将 Markdown/HTML/纯文本文章发布到公众号草稿箱，仅保存草稿不自动群发。当用户提到"发公众号"、"微信公众号"、"发布文章"、"保存草稿"、"写一篇公众号文章"、"把这篇文章发到公众号"、"微信草稿"时，必须使用此skill。
---

# WeChat Draft Publisher Skill

通过微信 API 将文章发布到微信公众号草稿箱。仅保存草稿，不自动群发，安全稳妥。

## 前置要求

- 微信公众号（订阅号或服务号均可）
- AppID 和 AppSecret（设置与开发 → 基本配置）
- IP 白名单已添加运行环境公网 IP

## 环境变量

首次使用时引导用户配置：

| 变量 | 必填 | 说明 |
|---|---|---|
| `WECHAT_APP_ID` | 是 | 公众号 AppID |
| `WECHAT_APP_SECRET` | 是 | 公众号 AppSecret |
| `WECHAT_AUTHOR` | 否 | 默认作者名 |
| `WECHAT_THUMB_MEDIA_ID` | 否 | 默认封面 media_id |

配置方式：在 skill 目录下创建 `.env` 文件（参考 `.env.example`），脚本自动读取。

## 工作流程

```
用户输入 → 读取/生成文章 → 上传封面 → 创建草稿 → 告知结果
```

### Step 1: 获取 access_token

```bash
python scripts/wechat_draft.py token
```

### Step 2: 上传封面图

```bash
python scripts/wechat_draft.py upload cover.jpg
```

### Step 3: 创建草稿

```bash
# 从 Markdown 文件
python scripts/wechat_draft.py draft --title "标题" --file article.md

# 从文本内容
python scripts/wechat_draft.py draft --title "标题" --content "<p>正文</p>" --thumb-id "media_id"
```

### Step 4: 告知结果

草稿创建后提示用户：
> 草稿已保存。请登录 mp.weixin.qq.com → 草稿箱 → 预览并手动群发。

## API 参考

| 端点 | 方法 | 说明 |
|---|---|---|
| `/cgi-bin/token` | GET | 获取 access_token |
| `/cgi-bin/material/add_material` | POST | 上传永久素材（封面图） |
| `/cgi-bin/draft/add` | POST | 创建草稿 |

## 草稿接口参数

```json
{
    "articles": [{
        "title": "标题",
        "thumb_media_id": "封面media_id",
        "author": "作者",
        "digest": "摘要",
        "content": "<p>HTML正文</p>",
        "content_source_url": "原文链接",
        "need_open_comment": 0,
        "only_fans_can_comment": 0
    }]
}
```

## Markdown 转微信 HTML 规则

| Markdown | 微信 HTML |
|---|---|
| `# 标题` | `<h1>` |
| `**加粗**` | `<strong>` |
| `*斜体*` | `<em>` |
| `[链接](url)` | `<a href="url">` |
| `![图片](url)` | `<img src="url">` |
| `- 列表` | `<ul><li>` |

## 常见错误

| errcode | 说明 | 解决 |
|---|---|---|
| 40164 | IP 不在白名单 | 添加 IP 到公众号后台 |
| 40007 | 无效 media_id | 重新上传封面 |
| 48001 | API 未授权 | 个人订阅号仅支持草稿 |

## 注意事项

- 个人订阅号只能创建草稿，无法通过 API 群发
- access_token 每日调用上限 2000 次
- JSON 序列化必须用 `ensure_ascii=False` + UTF-8 编码