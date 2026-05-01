# 📦 ekart-tracking-bot
A Telegram bot for tracking Ekart packages with automated updates.

## 📋 Overview
- 🤖 A Python-based Telegram bot that tracks Ekart shipments and pushes status updates to your chat.
- ⏱️ Updates are checked periodically (default every 1 hour).
- 💾 State is persisted locally in tracking_state.json.

## ✨ Features
- ➕ Add multiple tracking IDs per user
- 📝 List active trackings
- 🗑️ Remove a tracking
- 🔄 Manual update check via /check_now
- 📨 Richly formatted status messages with links to Ekart's shipment page

## 📋 Prerequisites
- 🐍 Python 3.8+ (or compatible)
- 🌐 Internet access
- 🤖 A Telegram bot token (see Configuration)
- 🔐 Optional: Ekart cookies and CSRF token for the Ekart API (see Configuration)

## 🚀 Installation
- 🔧 Create a Python virtual environment
- 📦 Install dependencies:
	- `pip install python-telegram-bot requests`
- 📄 Copy ekart_bot.py to your project root (already present in this repo)
- ✅ Ensure a writable directory for tracking_state.json is available

## 🎯 Usage
- ▶️ Run the bot:
	`python ekart_bot.py`
- 💬 Interact with the bot in Telegram:
	- `/start`: Welcome and help
	- `/add_tracking` or `/add`: Begin tracking a new ID
	- `/list_tracking` or `/list`: View all active trackings
	- `/remove_tracking` or `/remove`: Remove a tracking
	- `/check_now`: Trigger an immediate check
- 💾 The bot stores state in tracking_state.json by default.
- 📊 Logging is configured to INFO level; adjust as needed.

## ⚠️ Notes
- 🔐 The Ekart API URL and headers are provided in the code. Do not expose tokens or cookies publicly.
- 🔄 If you upgrade or change API keys, rotate credentials accordingly.
- 🛡️ You may want to add a .env file and update the code to load from environment variables for security.

## 📄 License
- 📋 See LICENSE for details.
