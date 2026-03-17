# Naggy

<p align="center">
  <img src="assets/icon.png" alt="Naggy icon" width="150">
</p>

A Telegram bot that nags you until you get things done.

Naggy manages **reminders**, **to-dos**, and **shopping lists** with timezone-aware scheduling and motivational messages that actually work.

## Features

- **Text reminders** (`/text`) — "Text Mom @ 7pm" → pings you every minute until you do it
- **To-do reminders** (`/todo`) — "Finish report @ 3pm" → nudges you every 30 minutes with motivational quotes
- **Shopping lists** (`/buy`) — Add items anytime, get a weekly digest on Fridays
- **Natural language dates** — "tomorrow at 9", "next monday 3pm", "in 2 hours"
- **Timezone support** — All reminders respect your local time
- **125+ motivational messages** — Weighted by tone (gentle, medium, harsh, long-term) depending on task type

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Show help |
| `/timezone America/New_York` | Set your timezone (required first step) |
| `/text <name> @ <time>` | Remind you to text/call someone |
| `/todo <task> @ <time>` | Remind you to do something |
| `/buy <item>, <item>, ...` | Add to your shopping list |
| `/textlist` | View active text reminders |
| `/todolist` | View active to-dos |
| `/shoppinglist` | View shopping list (`/shoppinglist all` includes done items) |
| `/all` | View everything |
| `/done <id>` | Mark any item as done |

## Setup

### Prerequisites

- Python 3.12+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### Local (polling mode)

```bash
git clone https://github.com/ayhankonar/RecuerdaBot.git
cd RecuerdaBot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```
BOT_TOKEN=your-telegram-bot-token
```

Run:

```bash
python main.py
```

### AWS (serverless mode)

RecuerdaBot can also run on AWS Lambda with API Gateway, DynamoDB, and EventBridge using the included SAM template.

```bash
sam build
sam deploy --guided \
  --parameter-overrides BotToken=<your-token> WebhookSecret=<random-string>
```

Then register the webhook URL with Telegram:

```bash
curl "https://api.telegram.org/bot<your-token>/setWebhook?url=<WebhookUrl>&secret_token=<random-string>"
```


**Key design decisions:**
- Plugin-style domain modules — each feature is self-contained
- Configuration-driven reminders — intervals, emoji, and motivation tones defined in `config.json`
- Dual deployment — same bot logic runs locally (polling + pickle persistence) or on AWS (webhook + DynamoDB)

## How It Works

1. You set your timezone with `/timezone`
2. Create a reminder: `/todo Clean desk @ 5pm`
3. At 5pm, RecuerdaBot sends you a message with a motivational nudge
4. It keeps reminding you (every 30min for todos, every 1min for texts) until you `/done` it
5. Shopping items collect quietly and get sent as a digest every Friday at 3pm
