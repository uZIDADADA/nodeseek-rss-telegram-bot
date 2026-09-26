# NodeSeek 关键词监控 Bot

监控 NodeSeek 关键词，命中新帖后自动推送到 Telegram。支持单用户自部署、组合关键词、屏蔽词、版块多选、推送历史和去重推送。

## 功能介绍

- 关键词独立管理与开关
- 支持组合关键词，例如 `dmit + corona` 同时命中才提醒
- 支持屏蔽词，命中后不推送
- 支持版块多选
- 支持多目标推送配置，用户+社群最多10个；
- 支持推送历史
- 去重推送，重启后状态不丢失
- 仅允许配置的一个 Telegram 用户操作
- 默认 10 秒轮询一次 RSS，可在 `.env` 调整

常用命令：

- `/keywords`：查看我的关键词
- `/keywords <词1,词2>`：添加一个或多个关键词
- `/combo <词1,词2>`：添加组合关键词，所有词都命中才提醒
- `/on <关键词ID>`：开启关键词
- `/off <关键词ID>`：关闭关键词
- `/delkw <关键词ID>`：删除关键词
- `/block <词1,词2>`：添加屏蔽词，命中后不推送
- `/blocks`：查看屏蔽词
- `/delblock <屏蔽词ID>`：删除屏蔽词
- `/addtarget`：把当前聊天加入推送目标
- `/addtarget <chat_id>`：在私聊里绑定群组或频道
- `/targets`：查看推送目标
- `/deltarget <目标ID>`：删除推送目标
- `/history`：查看最近命中的帖子
- `/status`：查看当前配置
- `/pause`：暂停提醒
- `/resume`：恢复提醒

说明：

- 默认私聊可直接使用，不需要手动 `/addtarget`
- 群组里可直接发送 `/addtarget`
- 频道可在私聊里发送 `/addtarget <chat_id>` 进行绑定
- 群组或频道都要求操作者是管理员
- 必须在 `ALLOWED_USER_IDS` 填写一个 Telegram 数字用户 ID，只有这个用户可以操作 Bot；留空时 Bot 拒绝启动

## 原项目的公开体验 Bot

https://t.me/NodeSeekKey_bot


## 个人部署教程

### 1. 准备 VPS 环境

在 VPS 上安装 Docker 和 Git：

```bash
apt update
apt install -y docker.io docker-compose-plugin git
```

### 2. 创建 Telegram Bot

在 Telegram 里找到 `@BotFather`，创建一个新的 Bot，并保存它给你的 `BOT_TOKEN`。

### 3. 下载项目

在 VPS 上克隆自己的 Fork，指定 `dev` 分支，随后复制并编辑配置文件：

```bash
git clone -b dev --single-branch https://github.com/uZIDADADA/nodeseek-rss-telegram-bot.git
cd nodeseek-rss-telegram-bot
cp .env.example .env
nano .env
```

### 4. 配置环境变量

在 `.env` 中至少填写这两项：

```text
BOT_TOKEN=从BotFather获取的Token
ALLOWED_USER_IDS=你的Telegram数字用户ID
```

`BOT_TOKEN` 来自你自己在 Telegram 的 `@BotFather` 创建的 Bot。`ALLOWED_USER_IDS` 必须且只能填写**你个人的数字用户 ID**；可以向 `@userinfobot` 发消息查看。这里不要填 Bot ID，也不要填群组或频道的 chat ID；无需把 Token 或用户 ID 发给别人。

### 5. 启动并检查 Bot

```bash
docker compose up -d --build
docker compose logs -f
```

看到 `Application started` 表示 Bot 已启动。按 `Ctrl + C` 退出日志查看不会停止 Bot。然后私聊你自己创建的 Bot，发送 `/start`；私聊会自动成为推送目标，无需手动填写私聊 chat ID。

VPS 不需要开放入站端口。它通过长轮询主动连接 Telegram，同时主动获取 NodeSeek RSS；请确保出站网络能访问 `api.telegram.org`、`rss.nodeseek.com`，且构建镜像时能访问 Docker 镜像源和 PyPI。

### 6. 更新 dev 分支

在项目目录中执行：

```bash
git pull --ff-only origin dev
docker compose up -d --build
```

如果 Git 提示分支已分叉，请先处理 VPS 上的本地改动，不要强制重置分支。

## 隐私说明

- 本项目会保存 Telegram 用户 ID、chat_id、关键词、版块设置、推送目标和历史记录，仅用于提醒服务。
- 数据默认保存在部署者自己服务器上的 SQLite 数据库，不会上传到 GitHub。
- 请勿公开 `.env` 和 `data/` 目录；如果 `BOT_TOKEN` 泄露，请立即在 BotFather 重置。
