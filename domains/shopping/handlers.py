# domains/shopping/handlers.py
from telegram import Update
from telegram.ext import ContextTypes

from common.state import ensure_user_bucket, alloc_gid
from common.scheduling import jobname_shopping, run_once
from common.timeutil import next_digest_at_configured_time
from .jobs import shopping_digest_job


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /buy command — adds shopping items and ensures a weekly digest job."""

    # --- Make sure user_data exists and is properly initialized
    ensure_user_bucket(context.user_data)

    # --- Require per-user timezone (no default anymore)
    tz = context.user_data.get("tz")
    if not tz:
        return await update.message.reply_text(
            "⚠️ Please set your timezone first using /timezone <Region/City>\n"
            "Example: /timezone America/New_York"
        )

    # --- Basic argument validation
    if not context.args:
        return await update.message.reply_text("Usage: /buy item[, item2, ...]")

    # Join all args into a single string and split by commas or newlines
    raw = " ".join(context.args)
    names = [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]
    if not names:
        return await update.message.reply_text("No items recognized.")

    # --- Add new items into the unified item pool
    items = context.user_data["items"]
    added = []

    for name in names:
        # Skip duplicates (case-insensitive, not marked done)
        if any(
            it["kind"] == "shopping"
            and not it.get("done")
            and it["label"].lower() == name.lower()
            for it in items.values()
        ):
            continue

        # Allocate unique ID for each item (global counter)
        gid = alloc_gid(context.user_data)

        # Create and store the item entry
        items[gid] = {
            "id": gid,
            "kind": "shopping",
            "label": name,
            "done": False,
        }

        added.append(f"[{gid}] {name}")

    # --- Schedule the weekly digest if it’s not already active
    # Digest lists all unpurchased items every configured weekday/hour
    jn = jobname_shopping(update.effective_user.id)
    if not context.job_queue.get_jobs_by_name(jn):
        # Compute the next digest time based on config.json (e.g., Friday @ 15:00)
        when_local = next_digest_at_configured_time(tz)

        # Schedule one-off job; it will reschedule itself weekly
        run_once(
            context,
            shopping_digest_job,  # function to call
            when_local,           # first trigger time (in user’s tz)
            jn,                   # unique job name
            update.effective_chat.id,  # send digest to this chat
            {"user_id": update.effective_user.id},  # job data payload
        )

    # --- Confirm items added
    await update.message.reply_text(
        "Added:\n" + "\n".join(f"- {x}" for x in added) if added else "No new items."
    )



def render_shopping_summary(items: dict, show_done: bool = False) -> str:
    # Split into two lists
    pending = [x for x in items.values() if x["kind"] == "shopping" and not x.get("done")]
    done = [x for x in items.values() if x["kind"] == "shopping" and x.get("done")]

    # --- Format output
    lines = []
    if pending:
        lines.append("*To buy:*")
        lines += [f"[[#{x['id']}]] 🛒 {x['label']}" for x in pending]
        lines += [f"\n\nUse /done [[id number]] (i.e. '/done 5') to complete"]

    if show_done and done:
        if lines:
            lines.append("")  # blank line between sections
        lines.append("*Done:*")
        lines += [f"✅ [[#{x['id']}]] {x['label']}" for x in done]

    return "\n".join(lines)


async def shoppinglist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_bucket(context.user_data)
    items = context.user_data["items"]
    show_done = bool(context.args and context.args[0].lower() == "all")

    section = render_shopping_summary(items, show_done=show_done)
    if not section:
        return await update.message.reply_text("Your shopping list is empty.")
    await update.message.reply_text(section, parse_mode="Markdown")

