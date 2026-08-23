# 各平台数据获取指南

> 详细说明如何从 12+ 平台获取聊天数据，用于 immortal-skill 蒸馏。

## 一、API 实时拉取类

### 1. 飞书

**准备工作**：
1. 登录 [飞书开放平台](https://open.feishu.cn/app)
2. 创建企业自建应用，开启「机器人」能力
3. 申请权限：`im:message:readonly`、`im:chat:readonly`、`docx:document:readonly`
4. 将 bot 添加到目标群聊

**配置**：
```bash
python3 kit/immortal_cli.py setup feishu
# 输入 App ID 和 App Secret
```

**采集**：
```bash
python3 kit/immortal_cli.py collect --platform feishu --scan --keyword "项目组"
python3 kit/immortal_cli.py collect --platform feishu --channel oc_xxx --output corpus/feishu-msg.md
```

### 2. 钉钉

**准备工作**：
1. 登录 [钉钉开放平台](https://open.dingtalk.com/)
2. 创建企业内部应用
3. 申请消息/群聊相关权限

**配置**：
```bash
python3 kit/immortal_cli.py setup dingtalk
# 输入 AppKey 和 AppSecret
```

### 3. Slack

**准备工作**：
1. 在 [Slack API](https://api.slack.com/apps) 创建 App
2. 添加 Bot Token Scope：`channels:history`、`channels:read`、`groups:history`
3. Install to Workspace，获取 Bot Token（xoxb-）

**配置**：
```bash
export SLACK_TOKEN=xoxb-your-token
```

**采集**：
```bash
python3 kit/immortal_cli.py collect --platform slack --token xoxb-xxx --scan
python3 kit/immortal_cli.py collect --platform slack --token xoxb-xxx --channel C0xxxx --output corpus/slack.md
```

### 4. Discord

**准备工作**：
1. 在 [Discord Developer Portal](https://discord.com/developers/applications) 创建 Application
2. 创建 Bot，获取 Token
3. 添加到 Server，赋予 `Read Message History` 权限

**采集**：
```bash
python3 kit/immortal_cli.py collect --platform discord --token BOT_TOKEN --scan
python3 kit/immortal_cli.py collect --platform discord --channel 123456 --output corpus/discord.md
```

### 5. Telegram

**准备工作**：
1. 访问 [my.telegram.org](https://my.telegram.org/)
2. 进入 API development tools
3. 获取 `api_id` 和 `api_hash`

**配置**：
```bash
python3 kit/immortal_cli.py setup telegram
# 输入 API ID 和 API Hash
# 首次连接需要输入手机号和验证码
```

**注意**：Telegram 有 FloodWait 限制，大量采集时会自动减速。

### 6. Email (Gmail)

**方式一**（推荐）：Google Takeout
1. 访问 [takeout.google.com](https://takeout.google.com/)
2. 仅选择「邮件」
3. 下载 mbox 文件

```bash
python3 kit/immortal_cli.py collect --platform email --mbox ~/Downloads/All\ mail.mbox --channel user@example.com --output corpus/email.md
```

**方式二**：直接解析 mbox 文件（Thunderbird 等客户端导出）

## 二、本地数据库类

### 7. 微信

微信没有公开的聊天导出 API。推荐流程：

**Windows 用户**：
1. 使用 [WeChatMsg](https://github.com/LC044/WeChatMsg) 导出为 CSV/TXT
2. 导入到 immortal-skill：
```bash
python3 kit/immortal_cli.py import ~/wechat-export.csv --output corpus/wechat.md
```

**macOS/iOS 用户**：
1. 使用 [WechatExporter](https://github.com/BlueMatthew/WechatExporter) 从 iTunes 备份导出
2. 导入导出的文本文件

**如有解密后的 SQLite 数据库**：
```bash
python3 kit/immortal_cli.py collect --platform wechat --db ~/EnMicroMsg.db --channel "张三" --output corpus/wechat.md
```

### 8. iMessage

仅 macOS 可用。

**准备**：
- System Settings → Privacy & Security → Full Disk Access → 添加 Terminal/iTerm

**采集**：
```bash
python3 kit/immortal_cli.py collect --platform imessage --scan
python3 kit/immortal_cli.py collect --platform imessage --channel 42 --output corpus/imessage.md
```

## 三、归档文件类

### 9. WhatsApp

**导出方式**：
1. 打开对话 → 点击对话名称 → 导出聊天 → 不含媒体
2. 将 .txt 文件保存到本地

```bash
python3 kit/immortal_cli.py import ~/WhatsApp-Chat.txt --output corpus/whatsapp.md
```

### 10. Twitter/X

**获取归档**：
1. Settings → Your account → Download an archive of your data
2. 等待归档生成（通常 24-48h）
3. 下载并解压 ZIP

```bash
python3 kit/immortal_cli.py collect --platform twitter --archive ~/twitter-archive/ --channel tweets --output corpus/twitter.md
```

### 11. 社交媒体归档

**Google Takeout**：
```bash
python3 kit/immortal_cli.py collect --platform social --archive ~/Takeout/ --scan
```

**Facebook/Instagram 数据下载**：
Settings → Your information → Download your information → 选择 JSON 格式

```bash
python3 kit/immortal_cli.py import ~/facebook-data/messages/inbox/chat.json --output corpus/fb.md
```

### 12. 手动导入

任何格式的文本文件均可导入：

```bash
# 纯文本/Markdown
python3 kit/immortal_cli.py import ~/notes.md --output corpus/notes.md

# JSON（含 messages 数组）
python3 kit/immortal_cli.py import ~/export.json --output corpus/export.md

# CSV（含 sender, text, time 列）
python3 kit/immortal_cli.py import ~/chat.csv --output corpus/chat.md
```

或直接在 OpenClaw 对话中粘贴文本。

## 四、数据安全提示

1. **凭证保护**：API Token/密钥存储在 `~/.immortal-skill/` 下，确保权限为 600
2. **脱敏处理**：聊天记录中第三方的真名建议替换为代号
3. **本地优先**：所有采集数据默认保存在本地 `corpus/` 目录
4. **最小权限**：API 权限申请时仅开通必要的只读权限
5. **合规使用**：各平台 ToS 对数据用途有要求，请自行确认
