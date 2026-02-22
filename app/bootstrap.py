# app/bootstrap.py
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram.ext import Application, CommandHandler, PicklePersistence

from common.config import BOT_TOKEN, log, TASK_CONFIG
from common.state import ensure_user_bucket
from common.scheduling import jobname_text, jobname_shopping, run_once
from common.timeutil import next_digest_at_configured_time

# reminder-like kinds (have snooze settings in config.json)
def _kinds_with_reminders():
    ks = set()
    for k, v in TASK_CONFIG.items():
        if v.get("reminder_value") is not None and v.get("reminder_unit") is not None:
            ks.add(k)
    return ks

# Handlers & jobs
from domains.timezone.handlers import set_timezone
from domains.reminders.jobs import reminder_job
from domains.shopping.jobs import shopping_digest_job

from domains.shopping.handlers import buy, shoppinglist, render_shopping_summary
from domains.text.handlers import text, text_summary
from domains.todo.handlers import todo, todo_summary

async def _post_init(app: Application):
    """Reschedule all reminder-like items and the shopping digest on startup."""
    reminder_kinds = _kinds_with_reminders()

    for uid, ud in app.user_data.items():
        ensure_user_bucket(ud)

        # ---- Reschedule timed items for ALL reminder kinds (text, todo, …) ----
        for gid, it in ud["items"].items():
            if it.get("kind") not in reminder_kinds or not it.get("active"):
                continue
            chat_id = it.get("chat_id")
            tz = it.get("tz")
            if not chat_id or not tz:
                log.warning("Skip reschedule: gid=%s user=%s missing chat_id/tz", gid, uid)
                continue

            try:
                due_dt = datetime.fromisoformat(it["due"])
                if due_dt.tzinfo is None:
                    due_dt = due_dt.replace(tzinfo=ZoneInfo(tz))
            except Exception as e:
                log.warning("Bad due for gid=%s user=%s: %s", gid, uid, e)
                continue

            now_local = datetime.now(ZoneInfo(tz))
            when_local = due_dt if due_dt > now_local else now_local  # fire ASAP if overdue
            run_once(
                app,
                reminder_job,                 # unified job for all reminder kinds
                when_local,
                jobname_text(uid, gid),       # job name still user+gid
                chat_id,
                {"user_id": uid, "gid": gid},
            )
            log.info("Rescheduled %s gid=%s user=%s at %s",
                     it.get("kind"), gid, uid, when_local.isoformat())

        # ---- Ensure weekly shopping digest (one job per user) ----
        tz = ud.get("tz")
        if not tz:
            continue

        name = jobname_shopping(uid)
        if app.job_queue.get_jobs_by_name(name):
            continue

        # choose a chat_id: prefer any reminder item’s chat_id
        chat_id = next(
            (x.get("chat_id") for x in ud["items"].values()
             if x.get("kind") in reminder_kinds and x.get("chat_id")), None
        )
        if not chat_id:
            # No known chat yet; skip. It’ll be scheduled after first /buy or reminder command.
            continue

        when_local = next_digest_at_configured_time(tz)
        run_once(app, shopping_digest_job, when_local, name, chat_id, {"user_id": uid})
        log.info("Scheduled shopping digest user=%s at %s", uid, when_local.isoformat())

async def start(update, context):
    await update.message.reply_text(
        "Bot ready.\n\n"
        "/timezone <Region/City> — set your timezone (required)\n"
        "/text Name @ time — text-style reminder\n"
        "/todo Task @ time — to-do reminder\n"
        "/shoppinglist [all] — view shopping items\n"
        "/textlist — view text reminders\n"
        "/todolist — view to-dos\n"
        "/all [all] — combined lists\n"
        "/done <id> — delete any item"
    )

# /all combines sections; reuse renderers from each domain
from domains.shopping.handlers import render_shopping_summary
from domains.reminders.render import render_reminder_section

async def show_all(update, context):
    ensure_user_bucket(context.user_data)
    items = context.user_data["items"]
    show_done = bool(context.args and context.args[0].lower() == "all")

    tz = context.user_data.get("tz")
    text_section = render_reminder_section(items, "text", tz, "Text reminders:") if tz else ""
    todo_section = render_reminder_section(items, "todo", tz, "To-dos:") if tz else ""
    shopping_section = render_shopping_summary(items, show_done=show_done)

    sections = [s for s in (todo_section, text_section, shopping_section) if s]
    if not sections and not tz:
        return await update.message.reply_text(
            "No items yet.\nTip: set your timezone to see dated reminders: /timezone <Region/City>"
        )
    if not sections:
        return await update.message.reply_text("No items yet.")
    await update.message.reply_text("\n\n".join(sections), parse_mode="Markdown")

async def done(update, context):
    """Universal delete/stop by ID."""
    ensure_user_bucket(context.user_data)
    if not context.args:
        return await update.message.reply_text("Usage: /done <id>")

    gid = " ".join(context.args).strip()
    items = context.user_data["items"]
    it = items.get(gid)
    if not it:
        return await update.message.reply_text("No item with that id.")

    reminder_kinds = _kinds_with_reminders()

    if it["kind"] in reminder_kinds:
        it["active"] = False
        name = jobname_text(update.effective_user.id, gid)
        for j in context.job_queue.get_jobs_by_name(name):
            j.schedule_removal()
        del items[gid]
        return await update.message.reply_text(f"✅ CONGRATS! '{it['label']}' IS DONE! ")

    if it["kind"] == "shopping":
        del items[gid]
        return await update.message.reply_text(f"✅ Done {it['label']}")

    await update.message.reply_text("Unknown item kind.")

def build_app() -> Application:
    persistence = PicklePersistence(filepath="data/state.pkl")
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .persistence(persistence)
        .post_init(_post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("timezone", set_timezone))

    # reminder-like kinds
    app.add_handler(CommandHandler("text", text))
    app.add_handler(CommandHandler("todo", todo))

    # lists

    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("textlist", text_summary))
    app.add_handler(CommandHandler("todolist", todo_summary))
    app.add_handler(CommandHandler("shoppinglist", shoppinglist))
    app.add_handler(CommandHandler("all", show_all))

    # stop/delete
    app.add_handler(CommandHandler("done", done))

    return app


# import os
# from datetime import datetime
# from zoneinfo import ZoneInfo

# from telegram.ext import Application, CommandHandler, PicklePersistence

# from common.config import BOT_TOKEN, log
# from common.state import ensure_user_bucket
# from common.scheduling import jobname_text, jobname_shopping, run_once
# from common.timeutil import next_digest_at_configured_time

# from domains.todo.handlers import todo, render_todo_summary, todo_summary

# from domains.text.handlers import text, render_text_summary, text_summary
# from domains.text.jobs import reminder_job

# from domains.shopping.handlers import buy, shoppinglist, render_shopping_summary
# from domains.shopping.jobs import shopping_digest_job

# from domains.timezone.handlers import set_timezone


# async def _post_init(app: Application):
#     """Reschedule text reminders and the shopping digest on startup."""
#     for uid, ud in app.user_data.items():
#         ensure_user_bucket(ud)

#         # ---- Reschedule timed /text items ----
#         for gid, it in ud["items"].items():
#             if it.get("kind") != "text" or not it.get("active"):
#                 continue
#             chat_id = it.get("chat_id")
#             tz = it.get("tz")
#             if not chat_id or not tz:
#                 log.warning("Skip reschedule: gid=%s user=%s missing chat_id/tz", gid, uid)
#                 continue

#             try:
#                 due_dt = datetime.fromisoformat(it["due"])
#                 if due_dt.tzinfo is None:
#                     due_dt = due_dt.replace(tzinfo=ZoneInfo(tz))
#             except Exception as e:
#                 log.warning("Bad due for gid=%s user=%s: %s", gid, uid, e)
#                 continue

#             now_local = datetime.now(ZoneInfo(tz))
#             when_local = due_dt if due_dt > now_local else now_local  # fire ASAP if overdue
#             run_once(
#                 app,
#                 reminder_job,
#                 when_local,
#                 jobname_text(uid, gid),
#                 chat_id,
#                 {"user_id": uid, "gid": gid},
#             )
#             log.info("Rescheduled text gid=%s user=%s at %s", gid, uid, when_local.isoformat())

#         # ---- Ensure weekly shopping digest (one job per user) ----
#         tz = ud.get("tz")
#         if not tz:
#             continue

#         name = jobname_shopping(uid)
#         if app.job_queue.get_jobs_by_name(name):
#             continue

#         # pick a chat_id to deliver the digest; prefer any known chat_id from text tasks
#         chat_id = next(
#             (x.get("chat_id") for x in ud["items"].values()
#              if x.get("kind") == "text" and x.get("chat_id")), None
#         )
#         if not chat_id:
#             # No known chat yet; skip scheduling. It will be scheduled after first /buy or /text.
#             continue

#         when_local = next_digest_at_configured_time(tz)
#         run_once(
#             app,
#             shopping_digest_job,
#             when_local,
#             name,
#             chat_id,
#             {"user_id": uid},
#         )
#         log.info("Scheduled shopping digest user=%s at %s", uid, when_local.isoformat())


# async def start(update, context):
#     await update.message.reply_text(
#         "Bot ready.\n\n"
#         "/text Name @ time — timed reminder\n"
#         "/todo Task @ time - timed reminder\n"
#         "/buy item[, ...] — add to shopping list\n"
#         "/shoppinglist [all] — view list\n"        
#         "/all - get all reminders\n"
#         "/done <id> — delete any item\n"
#         "/timezone <Region/City> — set your timezone (required)"
#     )


# async def show_all(update, context):
#     """Show combined lists (shopping + text). Extendable to more types later."""
#     ensure_user_bucket(context.user_data)
#     items = context.user_data["items"]

#     # shopping section (include done if user passes 'all')
#     show_done = bool(context.args and context.args[0].lower() == "all")
#     shopping_section = render_shopping_summary(items, show_done=show_done)

#     # text section (requires tz)
#     tz = context.user_data.get("tz")
#     text_section = render_text_summary(items, tz) if tz else ""
#     todo_section = render_todo_summary(items, tz) if tz else ""

#     # Compose non-empty sections
#     sections = [s for s in (todo_section, text_section, shopping_section) if s]
#     if not sections and not tz:
#         return await update.message.reply_text(
#             "No items yet.\n"
#             "Tip: set your timezone to see text reminders: /timezone <Region/City>"
#         )
#     if not sections:
#         return await update.message.reply_text("No items yet.")

#     await update.message.reply_text("\n\n".join(sections), parse_mode="Markdown")



# async def done(update, context):
#     ensure_user_bucket(context.user_data)
#     if not context.args:
#         return await update.message.reply_text("Usage: /done <id>")

#     gid = " ".join(context.args).strip()
#     items = context.user_data["items"]
#     it = items.get(gid)
#     if not it:
#         return await update.message.reply_text("No item with that id.")

#     if it["kind"] == "text":
#         it["active"] = False
#         name = jobname_text(update.effective_user.id, gid)
#         for j in context.job_queue.get_jobs_by_name(name):
#             j.schedule_removal()
#         del items[gid]
#         return await update.message.reply_text(f"Stopped [{gid}] {it['label']}")

#     if it["kind"] == "shopping":
#         del items[gid]
#         return await update.message.reply_text(f"Removed [{gid}] {it['label']}")

#     await update.message.reply_text("Unknown item kind.")


# def build_app() -> Application:
#     persistence = PicklePersistence(filepath="data/state.pkl")
#     app = (
#         Application.builder()
#         .token(BOT_TOKEN)
#         .persistence(persistence)
#         .post_init(_post_init)
#         .build()
#     )

#     app.add_handler(CommandHandler("start", start))
#     app.add_handler(CommandHandler("timezone", set_timezone))
#     app.add_handler(CommandHandler("text", text))
#     app.add_handler(CommandHandler("buy", buy))
#     app.add_handler(CommandHandler("shoppinglist", shoppinglist))
#     app.add_handler(CommandHandler("done", done))
#     app.add_handler(CommandHandler("all", show_all))
#     app.add_handler(CommandHandler("textlist", text_summary))  
#     app.add_handler(CommandHandler("todo", todo))    
#     app.add_handler(CommandHandler("todolist", todo_summary))  

#     return app
