from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes
from common.config import TASK_CONFIG
from domains.reminders.render import render_reminder_section
from domains.reminders.handlers import make_reminder_handler
from common.state import ensure_user_bucket, alloc_gid

todo = make_reminder_handler("todo", "{task}")

async def todo_summary(update, context):
    ensure_user_bucket(context.user_data)
    tz = context.user_data.get("tz")
    if not tz:
        return await update.message.reply_text("Set tz: /timezone <Region/City>")
    section = render_reminder_section(context.user_data["items"], "todo", tz, "To-dos")
    return await update.message.reply_text(section or "No active to-dos.", parse_mode="Markdown")

