---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: c9f507441c6e1088e881e76cf4b2f90d_8bb3161a5ef811f18d42525400d9a7a1
    ReservedCode1: SctRR5QESwPVILH39Z9YRVR9oqdd1j+25Rl6y/QYnhvO7betQNE4wXD3nTxbvDJUUvxrusd5QwYajVGh/0nxj+BTK+SKvaqjT+UecnXaiAjb4a9MVkbSIRgwmb0FHAoEuRvsviEowoZt/e6/d/zCc0XkeKlJy+K73ajl7xmC2WkxqBoq8/mgeprE8h4=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: c9f507441c6e1088e881e76cf4b2f90d_8bb3161a5ef811f18d42525400d9a7a1
    ReservedCode2: SctRR5QESwPVILH39Z9YRVR9oqdd1j+25Rl6y/QYnhvO7betQNE4wXD3nTxbvDJUUvxrusd5QwYajVGh/0nxj+BTK+SKvaqjT+UecnXaiAjb4a9MVkbSIRgwmb0FHAoEuRvsviEowoZt/e6/d/zCc0XkeKlJy+K73ajl7xmC2WkxqBoq8/mgeprE8h4=
---

# WeChat Draft Publisher Skill

微信公众号草稿发布器，通过微信 API 创建草稿，支持 Markdown 自动转微信 HTML。

## 快速开始

### 1. 配置

```bash
cp .env.example .env
# 编辑 .env，填入你的 AppID 和 AppSecret
```

### 2. 安装依赖

```bash
pip install requests
```

### 3. 使用示例

**命令行：**

```bash
# 从 Markdown 文件创建草稿
python wechat_draft.py draft --title "我的文章" --file article.md --cover cover.jpg

# 直接传入 HTML 内容
python wechat_draft.py draft --title "测试" --content "<p>正文内容</p>" --thumb-id "已有的media_id"

# 上传封面图
python wechat_draft.py upload cover.jpg
```

**Python 代码：**

```python
from wechat_draft import WeChatDraftPublisher

publisher = WeChatDraftPublisher(
    app_id="wx7a44b1cd0c9b22f0",
    app_secret="your_secret",
    author="予书又搞砸啦"
)

# 上传封面
thumb_id = publisher.upload_image("cover.jpg")

# Markdown 转 HTML
html = publisher.markdown_to_html(open("article.md").read())

# 创建草稿
result = publisher.create_draft(
    title="文章标题",
    content=html,
    thumb_media_id=thumb_id,
)
print(f"草稿 ID: {result['media_id']}")
```

## 文件结构

```
wechat-draft-skill/
├── SKILL.md          # Skill 说明文档
├── wechat_draft.py   # 核心脚本
├── .env.example      # 配置模板
└── README.md         # 本文件
```

## 注意事项

- 个人订阅号只能创建草稿，需手动在公众号后台群发
- 需在公众号后台 IP 白名单中添加运行环境公网 IP
- access_token 每日调用上限 2000 次，脚本内置缓存
*（内容由AI生成，仅供参考）*
