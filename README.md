# HelzerX Container Builder

A polished Discord Components V2 builder bot for HelzerX Studio.

## Goals

- Build Components V2 layouts entirely inside Discord
- Live preview while editing
- Component add/edit/remove/reorder workflows
- JSON import/export
- Reusable templates
- Centralized HelzerX emoji management in `emoji.py`
- Clean modular architecture ready for production

## Stack

- Python 3.12+
- discord.py 2.7.1+
- SQLite for local persistence
- Components V2 (`LayoutView`, `Container`, `TextDisplay`, `Section`, `Separator`, `MediaGallery`, `File`, `ActionRow`)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bot
```

Set `DISCORD_TOKEN` in `.env` before starting the bot.

> Components V2 is built around `LayoutView` and the newer Discord UI components; classic embeds/content should not be mixed into a Components V2 message.
