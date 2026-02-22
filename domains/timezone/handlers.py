from telegram import Update
from telegram.ext import ContextTypes
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from common.state import ensure_user_bucket

async def set_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_bucket(context.user_data)

    if not context.args:
        tz = context.user_data.get("tz")
        msg = f"Your timezone is currently set to: {tz}" if tz else "No timezone set."
        return await update.message.reply_text(
            msg + "\nUsage: /timezone America/New_York"
        )
    
    tz_input = context.args[0]
    try:
        ZoneInfo(tz_input)
    except ZoneInfoNotFoundError:
        return await update.message.reply_text(
            f"❌ Unknown timeone '{tz_input}'. Example: /timezone Europe/Berlin"
        )
    
    context.user_data["tz"] = tz_input
    await update.message.reply_text(f"✅ Timezone set to {tz_input}")


async def check_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tz = context.user_data.get("tz")
    if not tz:
        return await update.message.reply_text(
            "⚠️ Please set your timezone first using /timezone <Region/City>"
        )
    else:
        return tz