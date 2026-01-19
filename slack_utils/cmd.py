import re
from slack.reg import smart_msg_listen, Context
from slack_utils.core import get_user_info
from base import description
import utils
import time
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from slack.schema.file import PendingFile
import logging


@smart_msg_listen("slack.inspect ")
@utils.get_group
@utils.filter_allowed
@utils.require_group("owner", False)
# @description("slack.inspect <user_id>?", "Inspect a Slack user profile")
def inspect_user(ctx: Context):
    client = ctx.client.client.web_client
    user_id = ctx.author_id
    text = ctx.value.strip()

    if text:
        if re.match(r"<@(U\w+)(\|[0-9a-zA-Z\-_\.]+)?>", text):
            user_id = (
                text.strip().removeprefix("<@").removesuffix(">").split("|")[0]
            )
        else:
            user_id = text

    try:
        user = get_user_info(client, user_id)
    except ValueError as e:
        ctx.private_send(text=f"Error fetching user: {e}")
        return

    profile = user.profile

    status_part = "None"
    if profile.status_emoji or profile.status_text:
        status_part = f"{profile.status_emoji or ''} {profile.status_text or ''}".strip()

    msg = (
        f"*User Inspection for <@{user.id}>*\n"
        f"*ID:* `{user.id}`\n"
        f"*Username:* {user.name}\n"
        f"*Real Name:* {user.real_name}\n"
        f"*Display Name:* {profile.display_name}\n"
        f"*Status:* {status_part}\n"
        f"*Timezone:* {user.tz} ({user.tz_label})\n"
        f"*Is Bot:* {user.flags.is_bot}\n"
        f"*Is Admin:* {user.flags.is_admin}"
    )

    ctx.public_send(text=msg)


@smart_msg_listen("slack.export ")
@utils.get_group
@utils.filter_allowed
@utils.require_group("owner", False)
def export_status(ctx: Context):
    try:
        users = json.loads((Path("data") / "dt2.json").read_text())
    except Exception as e:
        logging.warning("Failed to fetch user list", exc_info=True)
        return ctx.private_send(text=f"Failed to fetch user list: {e}")

    if not isinstance(users, list):
        return ctx.private_send(text="Invalid data format: Expected a list.")

    total_users = len(users)
    try:
        ctx.public_send(text=f"Starting export for {total_users} users...")
    except Exception:
        logging.warning("Failed to send start message", exc_info=True)

    client = ctx.client.client.web_client

    frequencies_pairing = Counter()
    frequencies_emoji = Counter()
    frequencies_text = Counter()
    errors = []
    last_req = 0.0

    for i, user_data in enumerate(users):
        slack_id = user_data.get("slack_id")

        if not slack_id:
            errors.append(f"INDEX_{i}_NO_SLACK_ID")
            continue

        try:
            # Rate limit: 100 req/min => 0.6s per req
            now = time.time()
            diff = now - last_req
            if diff < 0.6:
                time.sleep(0.6 - diff)
            last_req = time.time()

            user_info = get_user_info(client, slack_id)
            profile = user_info.profile

            emoji = profile.status_emoji or None
            text = profile.status_text or None

            if emoji is not None or text is not None:
                frequencies_pairing[(emoji, text)] += 1

            if emoji:
                frequencies_emoji[emoji] += 1

            if text:
                frequencies_text[text] += 1

        except Exception:
            logging.warning(f"Failed to process user {slack_id}", exc_info=True)
            errors.append(slack_id)

        if (i + 1) % 100 == 0:
            try:
                ctx.public_send(text=f"Exporting... {i + 1}/{total_users} ({(i + 1) / total_users * 100:.1f}%)")
            except Exception:
                logging.warning("Failed to send progress update", exc_info=True)

    output_data = {
        "frequencies_pairing": [{"emoji": k[0], "text": k[1], "count": v} for k, v in frequencies_pairing.most_common()],
        "frequencies_emoji": {k: v for k, v in frequencies_emoji.most_common()},
        "frequency_text": {k: v for k, v in frequencies_text.most_common()},
        "errors": errors
    }
    json_str = json.dumps(output_data, indent=2)

    filename = f"status_export_{datetime.now().isoformat()}.json"
    try:
        filepath = Path("data") / filename
        filepath.parent.mkdir(exist_ok=True)
        filepath.write_text(json_str)
    except Exception:
        logging.warning("Failed to save export file locally", exc_info=True)

    try:
        ctx.public_send(text=f"Export completed. Processed {total_users} users.", files=[PendingFile(filename, json_str, "Status Export")])
    except Exception:
        logging.warning("Failed to send final export message", exc_info=True)
