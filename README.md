# Sentiment PBN

Sentiment analysis and user labeling tool with Telegram bot interface. Classifies users into categories based on message sentiment patterns.

## Quick Start

```bash
pip install -r requirements.txt
python run_bot.py
```

## Features

- Sentiment analysis of text messages
- User labeling (adept/hater/traitor classification)
- Telegram bot interface
- Analytics dashboard
- SQLite storage for analysis results

## Configuration

Set the following environment variables:
- `BOT_TOKEN` — Telegram bot token from @BotFather

## Requirements

- Python 3.8+
- `telebot`, `sqlite3`
