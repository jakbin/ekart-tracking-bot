import requests
import json
import logging
from datetime import datetime
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = ""  # Replace with your bot token
TRACKING_ID_FILE = "tracking_state.json"
CHECK_INTERVAL = 1 * 60 * 60

# Ekart API Configuration
EKART_URL = "https://www.ekartlogistics.com:443/ekartlogistics-web-routes-api/ekartlogistics-web-proxy/trackings/v2"
EKART_COOKIES = {
    "session": "eyJjc3JmU2VjcmV0IjoiNnlqdjZyMGpPRFE2bjl3dlVMN19jTFZJIn0=",
    "session.sig": "5yqkJxWl_PrDw3KsMBvXOGwkmB0",
    "ab": "prodcluster",
    "epoctime": "1769845617.981"
}

EKART_HEADERS = {
    "Sec-Ch-Ua-Full-Version-List": "",
    "Sec-Ch-Ua-Platform": "\"Linux\"",
    "X-User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 EKCL/website/1",
    "Sec-Ch-Ua": "\"Not(A:Brand\";v=\"8\", \"Chromium\";v=\"144\"",
    "Csrf-Token": "EAuBfLf9-ZU_QhX5cEdFdVBXY-HzWCXrsuNY",
    "Sec-Ch-Ua-Mobile": "?0",
    "Content-Type": "application/json",
    "Accept-Language": "en-GB,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Origin": "https://www.ekartlogistics.com",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Accept-Encoding": "gzip, deflate, br",
}

# User conversation states
WAITING_FOR_TRACKING_ID = 1
TRACKING_ACTIVE = 2


class TrackingManager:
    """Manages tracking state and updates"""
    
    def __init__(self, state_file=TRACKING_ID_FILE):
        self.state_file = state_file
        self.data = self.load_state()
    
    def load_state(self):
        """Load tracking state from file"""
        if Path(self.state_file).exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading state: {e}")
                return {}
        return {}
    
    def save_state(self):
        """Save tracking state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def add_tracking(self, user_id, tracking_id):
        """Add tracking ID for user"""
        if str(user_id) not in self.data:
            self.data[str(user_id)] = {}
        
        self.data[str(user_id)][tracking_id] = {
            'last_details': [],
            'added_date': datetime.now().isoformat()
        }
        self.save_state()
    
    def remove_tracking(self, user_id, tracking_id):
        """Remove tracking ID for user"""
        if str(user_id) in self.data and tracking_id in self.data[str(user_id)]:
            del self.data[str(user_id)][tracking_id]
            self.save_state()
            return True
        return False
    
    def update_tracking_details(self, user_id, tracking_id, details):
        """Update tracking details for user"""
        if str(user_id) in self.data and tracking_id in self.data[str(user_id)]:
            self.data[str(user_id)][tracking_id]['last_details'] = details
            self.save_state()
    
    def get_user_trackings(self, user_id):
        """Get all trackings for user"""
        return self.data.get(str(user_id), {})


def fetch_tracking_info(tracking_id):
    """Fetch tracking info from Ekart API (real or fake)"""
    try:
        payload = {"tracking_ids": tracking_id}
        
        response = requests.post(
            EKART_URL,
            headers=EKART_HEADERS,
            cookies=EKART_COOKIES,
            json=payload,
            
            timeout=10
        )
        
        response.raise_for_status()
        
        result = response.json().get(tracking_id)
        return result
    except Exception as e:
        logger.error(f"Error fetching tracking info for {tracking_id}: {e}")
        return None


def format_tracking_message(tracking_id, tracking_info):
    """Format tracking info into a readable message"""
    if not tracking_info:
        return f"❌ Could not fetch tracking info for {tracking_id}"
    
    receiver_name = tracking_info.get('receiverName', 'N/A')
    merchant_name = tracking_info.get('merchantName', 'N/A')
    source_city = tracking_info.get('sourceCity', 'N/A')
    destination_city = tracking_info.get('destinationCity', 'N/A')
    reached_hub = tracking_info.get('reachedNearestHub', False)
    
    expected_ms = tracking_info.get('expectedDeliveryDate')
    if expected_ms:
        expected_date = datetime.fromtimestamp(expected_ms / 1000).strftime('%Y-%m-%d')
    else:
        expected_date = 'N/A'
    
    message = f"""📦 <b>Tracking Update: <code>{tracking_id}</code></b>

👤 <b>Receiver:</b> {receiver_name}
🏪 <b>Merchant:</b> {merchant_name}
📍 <b>Source:</b> {source_city}
📍 <b>Destination:</b> {destination_city}
📅 <b>Expected Delivery:</b> {expected_date}
✅ <b>Reached Nearest Hub:</b> {'🎉 Yes' if reached_hub else 'No'}
   
<b>Check On Ekart:</b> <a href="https://www.ekartlogistics.com/ekartlogistics-web/shipmenttrack/{tracking_id}">Track on Ekart</a>

<b>Recent Updates:</b>
"""
    
    tracking_details = tracking_info.get('shipmentTrackingDetails', [])
    for detail in tracking_details[-5:]:  # Show last 5 updates
        date_ms = detail.get('date')
        date = datetime.fromtimestamp(date_ms / 1000).strftime('%Y-%m-%d %I:%M %p') if date_ms else 'N/A'
        city = detail.get('city', 'N/A')
        status = detail.get('statusDetails', 'N/A')
        message += f"\n🔹 {date}\n   📌 {city} - {status}"
    
    return message


# Bot Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    welcome_message = """👋 Welcome to <b>Ekart Tracking Bot</b>!

This bot helps you track your Ekart packages with automatic updates every 2 hours.

<b>Available Commands:</b>
/add_tracking, /add - Add a tracking ID to monitor
/list_tracking, /list - View all your active trackings
/remove_tracking, /remove - Stop tracking a package
/check_now - Check all trackings immediately
/help - Show help information
/stop - Stop the bot"""
    
    await update.message.reply_text(welcome_message, parse_mode=ParseMode.HTML)


async def add_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding new tracking ID"""
    await update.message.reply_text(
        "📌 Please send me the <b>Tracking ID</b> you want to monitor:\n\n"
        "Example: <code>FMPP01234567</code>",
        parse_mode=ParseMode.HTML
    )
    return WAITING_FOR_TRACKING_ID


async def handle_tracking_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle tracking ID input"""
    tracking_id = update.message.text.strip().upper()
    user_id = update.effective_user.id
    
    # Validate tracking ID format
    if not tracking_id or len(tracking_id) < 5:
        await update.message.reply_text(
            "❌ Invalid tracking ID. Please send a valid tracking ID.",
            parse_mode=ParseMode.HTML
        )
        return WAITING_FOR_TRACKING_ID
    
    # Fetch info to verify tracking ID
    await update.message.reply_text("🔍 Verifying tracking ID...")
    tracking_info = fetch_tracking_info(tracking_id)
    
    if not tracking_info:
        await update.message.reply_text(
            f"❌ Could not find tracking information for <code>{tracking_id}</code>\n\n"
            "Please verify the tracking ID and try again.",
            parse_mode=ParseMode.HTML
        )
        return WAITING_FOR_TRACKING_ID
    
    # Add tracking and seed last_details to avoid notifying all history as new
    tracking_manager = context.bot_data.get('tracking_manager')
    tracking_manager.add_tracking(user_id, tracking_id)
    tracking_manager.update_tracking_details(
        user_id,
        tracking_id,
        tracking_info.get('shipmentTrackingDetails', [])
    )
    
    # Send confirmation
    message = format_tracking_message(tracking_id, tracking_info)
    await update.message.reply_text(
        f"✅ <b>Added to tracking!</b>\n\n{message}\n\n"
        f"📢 You will receive updates every {CHECK_INTERVAL // 3600} hours.",
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END


async def list_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all active trackings"""
    user_id = update.effective_user.id
    tracking_manager = context.bot_data.get('tracking_manager')
    trackings = tracking_manager.get_user_trackings(user_id)
    
    if not trackings:
        await update.message.reply_text(
            "📭 You don't have any active trackings.\n\n"
            "Use /add_tracking to add a package to monitor.",
            parse_mode=ParseMode.HTML
        )
        return
    
    message = "📋 <b>Your Active Trackings:</b>\n\n"
    for i, tracking_id in enumerate(trackings.keys(), 1):
        added_date = trackings[tracking_id].get('added_date', 'N/A')
        message += f"{i}. <code>{tracking_id}</code> (Added: {added_date[:10]})\n"
    
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def remove_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a tracking ID"""
    user_id = update.effective_user.id
    tracking_manager = context.bot_data.get('tracking_manager')
    trackings = tracking_manager.get_user_trackings(user_id)
    
    if not trackings:
        await update.message.reply_text(
            "📭 You don't have any active trackings to remove.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Check if tracking ID is provided as argument
    if context.args and len(context.args) > 0:
        tracking_id = context.args[0].upper()
        
        if tracking_id not in trackings:
            await update.message.reply_text(
                f"❌ Tracking ID <code>{tracking_id}</code> not found in your list.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Remove the tracking
        if tracking_manager.remove_tracking(user_id, tracking_id):
            await update.message.reply_text(
                f"✅ <b>Removed from tracking!</b>\n\n"
                f"Tracking ID: <code>{tracking_id}</code>\n"
                f"You will no longer receive updates for this package.",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                "❌ Error removing tracking. Please try again.",
                parse_mode=ParseMode.HTML
            )
        return
    
    # Show list of trackings to remove
    message = "🗑️ <b>Your Active Trackings:</b>\n\n"
    for i, tracking_id in enumerate(trackings.keys(), 1):
        message += f"{i}. <code>{tracking_id}</code>\n"
    
    message += "\n<b>To remove a tracking, use:</b>\n"
    for i, tracking_id in enumerate(trackings.keys(), 1):
        message += f"<code>/remove_tracking {tracking_id}</code>\n"
    
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def check_tracking_updates(context: ContextTypes.DEFAULT_TYPE, check_now=False):
    """Check for tracking updates and send notifications"""
    tracking_manager = context.bot_data.get('tracking_manager')

    for user_id_str, trackings in tracking_manager.data.items():
        for tracking_id, tracking_data in trackings.items():
            try:
                # Fetch current tracking info
                tracking_info = fetch_tracking_info(tracking_id)
                if not tracking_info:
                    continue
                
                current_details = tracking_info.get('shipmentTrackingDetails', [])
                last_details = tracking_data.get('last_details', [])
                
                if check_now:
                    # On manual check, just send current status
                    message = format_tracking_message(tracking_id, tracking_info)
                    try:
                        await context.bot.send_message(
                            chat_id=int(user_id_str),
                            text=message,
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True
                        )
                    except Exception as e:
                        logger.error(f"Error sending message to {user_id_str}: {e}")
                    continue

                # Check for new details
                if len(current_details) > len(last_details):

                    # New update found
                    new_details = current_details[len(last_details):]
                    message = format_tracking_message(tracking_id, tracking_info)
                    
                    # Add new updates highlight
                    message += "\n\n🆕 <b>New Updates:</b>\n"
                    for detail in new_details:
                        date_ms = detail.get('date')
                        date = datetime.fromtimestamp(date_ms / 1000).strftime('%Y-%m-%d %I:%M %p') if date_ms else 'N/A'
                        status = detail.get('statusDetails', 'N/A')
                        city = detail.get('city', 'N/A')
                        message += f"\n🔸 {date}\n   📌 {city} - {status}"
                    
                    # Send notification
                    try:
                        await context.bot.send_message(
                            chat_id=int(user_id_str),
                            text=message,
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True
                        )
                    except Exception as e:
                        logger.error(f"Error sending message to {user_id_str}: {e}")

                # Update last known details
                tracking_manager.update_tracking_details(int(user_id_str), tracking_id, current_details)
                
            except Exception as e:
                logger.error(f"Error checking tracking {tracking_id}: {e}")


async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check all trackings immediately"""
    await update.message.reply_text("🔄 Checking all your trackings now...")
    await check_tracking_updates(context, check_now=True)
    await update.message.reply_text("✅ Check complete!")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help"""
    hours = CHECK_INTERVAL // 3600
    help_text = f"""<b>📖 Help Guide</b>

<b>Commands:</b>
/start - Show welcome message
/add_tracking, /add - Add a new tracking ID
/list_tracking, /list - Show all active trackings
/remove_tracking, /remove - Remove a tracking
/check_now - Check updates immediately
/help - Show this help message
/stop - Stop the bot

<b>How it works:</b>
1️⃣ Use /add_tracking to add a package tracking ID
2️⃣ The bot will automatically check for updates every {hours} hours
3️⃣ You'll receive notifications when new tracking details are available
4️⃣ Use /check_now to manually check for updates

<b>Tips:</b>
• Keep your chat open for notifications
• You can track multiple packages simultaneously
• Updates are checked automatically in the background"""
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop the bot"""
    await update.message.reply_text(
        "👋 Bot stopped. Use /start to begin again.",
        parse_mode=ParseMode.HTML
    )


def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Initialize tracking manager
    tracking_manager = TrackingManager()
    application.bot_data['tracking_manager'] = tracking_manager
    
    # Add conversation handler for adding tracking
    add_tracking_handler = ConversationHandler(
        entry_points=[CommandHandler(['add_tracking', 'add'], add_tracking)],
        states={
            WAITING_FOR_TRACKING_ID: [
                CommandHandler('cancel', lambda u, c: ConversationHandler.END),
            ],
        },
        fallbacks=[],
    )
    
    # Regular handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(add_tracking_handler)
    application.add_handler(CommandHandler(['list_tracking', 'list'], list_tracking))
    application.add_handler(CommandHandler(['remove_tracking', 'remove'], remove_tracking))
    application.add_handler(CommandHandler('check_now', check_now))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('stop', stop))
    
    # Handle text messages (for tracking ID input)
    from telegram.ext import MessageHandler, filters
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tracking_id))
    
    # Setup job queue for periodic tracking checks
    application.job_queue.run_repeating(
        check_tracking_updates,
        interval= CHECK_INTERVAL,  # Convert hours to seconds
        first=0,  # Run immediately on start
        name='tracking_check'
    )
    
    logger.info("🤖 Ekart Tracking Bot started!")
    logger.info(f"Checking for updates every {CHECK_INTERVAL // 3600} hours")
    
    # Start bot
    application.run_polling()


if __name__ == '__main__':
    main()
