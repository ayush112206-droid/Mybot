# 🤖 Master Extractor Bot

Telegram bot for extracting and uploading content from various educational apps. Supports TXT file uploads with encrypted video/PDF decryption.

## ✨ Features

- 📱 **Multi-App Support** — Extracts from 30+ educational apps (PW, Allen, Khan Sir, etc.)
- 📤 **TXT Upload** — Parse `.txt` files and bulk upload videos/PDFs to Telegram
- 🔐 **XOR Decryption** — Automatically decrypts Appx encrypted videos and PDFs
- 🎬 **Video Quality Selection** — Choose resolution (360p to 1080p)
- 📊 **Progress Tracking** — Real-time download/upload progress bars
- 👑 **Premium System** — Admin-managed premium subscriptions via UPI
- 🗄️ **MongoDB Backend** — User data, settings, and subscription management

## 🚀 One-Click Deploy to Heroku

Click the button below — **all environment variables will be auto-filled!**

[![Deploy To Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/nat-king-15/Master-Extractor-Bot)

> **Note:** After deploy, go to **Resources** tab → turn OFF `web` dyno → turn ON `worker` dyno.

## ⚙️ Environment Variables

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram Bot Token from [@BotFather](https://t.me/BotFather) |
| `API_ID` | Telegram API ID from [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | Telegram API Hash from [my.telegram.org](https://my.telegram.org) |
| `ADMIN_ID` | Admin user IDs (comma separated) |
| `OWNER_ID` | Bot owner's Telegram user ID |
| `DB_URL` | MongoDB connection string |
| `DB_NAME` | MongoDB database name |
| `CHANNEL` | Main Telegram channel ID |
| `TXT_LOG` | Text log channel ID |
| `AUTH_LOG` | Auth log channel ID |
| `HIT_LOG` | Hit log channel ID |
| `DRM_DUMP` | DRM dump channel ID |
| `CH_URL` | Channel invite link |
| `OWNER` | Owner Telegram profile link |
| `THUMB_URL` | Thumbnail image URL |

## 📋 Setup Notes

1. **Create channels** — Make sure all log channels and groups are created before deployment
2. **Add bot as admin** — Bot must be admin in all channels
3. **Worker dyno** — After deploying, switch to `worker` dyno (not `web`)
4. **Keep secrets safe** — Never share your API tokens publicly

## 🛠️ Local Development

```bash
# Clone the repo
git clone https://github.com/nat-king-15/Master-Extractor-Bot.git
cd Master-Extractor-Bot

# Set environment variables
export BOT_TOKEN="your_token"
export API_ID="your_api_id"
export API_HASH="your_api_hash"
# ... set all other vars

# Install dependencies
pip install -r requirements.txt

# Run
python3 main.py
```

## 📁 Project Structure

```
├── main.py              # Bot entry point
├── config.py            # Environment variable configuration
├── helper.py            # Core helper functions
├── plugins/
│   ├── __init__.py      # Command handlers
│   ├── txt_uploader.py  # TXT file upload handler
│   └── upload_utils.py  # Download/upload/decrypt utilities
├── module/              # App-specific extractors (30+ apps)
├── Database/            # MongoDB database helpers
├── Dockerfile           # Heroku container build
├── heroku.yml           # Heroku deployment config
└── app.json             # Heroku one-click deploy config
```

## 📝 License

This project is for educational purposes only.
