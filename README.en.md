# NodeSeek Keyword Monitor Bot

Monitor NodeSeek keywords and push matched new posts to Telegram. Supports single-user self-hosting, keyword combinations, block keywords, multi-category filtering, delivery history, and deduplicated notifications.

## Features

- Add and delete keywords without a count limit
- Keyword combinations, for example `dmit + corona` only matches when all terms appear
- Block keywords, so matched blocked terms suppress notifications
- Multi-select category filtering
- Notifications go only to your private chat with the bot; no target setup is needed
- Delivery history
- Notifications include the post author
- Deduplicated notifications with persisted state
- Only the configured Telegram user can control the bot
- Polls RSS every 10 seconds by default, configurable in `.env`

Common commands:

- `/keywords`: show your keywords
- `/keywords <kw1,kw2>`: add one or more keywords
- `/combo <kw1,kw2>`: add a keyword combination that requires all terms
- `/del <keyword_id>`: delete a keyword
- `/block <kw1,kw2>`: add block keywords
- `/blocks`: show block keywords
- `/delblock <block_keyword_id>`: delete a block keyword
- `/history`: show recent matched posts
- `/status`: show current settings
- `/pause`: pause notifications
- `/resume`: resume notifications

Notes:

- Your first private message enables private notifications automatically; old group and channel targets stop receiving notifications after upgrading
- Set `ALLOWED_USER_IDS` to one numeric Telegram user ID; only that user can control the bot, and the bot refuses to start if it is unset
- Keywords previously disabled with `/off` become monitored after upgrading; remove any unwanted rule with `/del <keyword_id>`

## Original Project's Public Demo Bot

[https://t.me/NodeSeekKey_bot](https://t.me/NodeSeekKey_bot)

## Personal Deployment Guide

### 1. Prepare Your VPS

Install Docker and Git on your VPS:

```bash
apt update
apt install -y docker.io docker-compose-plugin git
```

### 2. Create a Telegram Bot

Open Telegram, talk to `@BotFather`, create a new bot, and keep the `BOT_TOKEN` it gives you.

### 3. Clone the Project

Run this on your VPS:

```bash
git clone -b dev --single-branch https://github.com/uZIDADADA/nodeseek-rss-telegram-bot.git
cd nodeseek-rss-telegram-bot
```

### 4. Configure Environment Variables

Copy the config template:

```bash
cp .env.example .env
nano .env
```

Replace `BOT_TOKEN` in `.env` with your own token and set your numeric Telegram user ID. You can get your user ID by messaging `@userinfobot` on Telegram. Do not use a group or channel chat ID here.

`ALLOWED_USER_IDS` is required and must contain exactly one user ID:

```text
ALLOWED_USER_IDS=<your_numeric_telegram_user_id>
```

### 5. Start the Bot

```bash
docker compose up -d --build
```

### 6. Check Logs

```bash
docker compose logs -f
```

If you see `Application started`, the bot is running.

Press `Ctrl + C` to exit log viewing. This will not stop the bot.

### 7. Update the Project

For normal updates, run:

```bash
git pull --ff-only origin dev
docker compose up -d --build
```

If Git reports divergent branches, resolve local changes before pulling. Do not force-reset the branch.

## Privacy

- This project stores Telegram user IDs, chat IDs, keywords, category settings, and delivery history only for notifications.
- Data is stored in the deployer's own SQLite database and is not uploaded to GitHub.
- Do not expose `.env` or the `data/` directory. If your `BOT_TOKEN` leaks, reset it in BotFather immediately.
