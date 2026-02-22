# domains/shopping/jobs.py
from common.timeutil import next_digest_at_configured_time
from common.scheduling import run_once

async def shopping_digest_job(context):
    """Send a weekly digest of shopping items, then reschedule itself."""
    job = context.job
    uid = job.data["user_id"]
    ud = context.application.user_data.get(uid, {})
    items = ud.get("items", {})
    tz = ud.get("tz")

    # Get active shopping items
    shopping_items = [x for x in items.values() if x["kind"] == "shopping" and not x.get("done")]
    if not shopping_items:
        return  # skip message if list empty

    # Send digest message
    lines = "\n".join(f"- [{x['id']}] {x['label']}" for x in shopping_items)
    await context.bot.send_message(job.chat_id, f"🛒 Weekly Shopping List:\n\n{lines}")

    # Reschedule next digest
    if tz:
        when_next = next_digest_at_configured_time(tz)
        run_once(
            context,
            shopping_digest_job,
            when_next,
            job.name,
            job.chat_id,
            {"user_id": uid},
        )
