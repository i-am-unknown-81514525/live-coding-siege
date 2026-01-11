import typing
from typing import Literal

from arrow import Arrow
from slack.reg import (
    smart_action_listen,
    smart_action_prefix_listen,
    smart_msg_listen,
    Context,
    InteractionContext,
)
import blockkit
from homelab.core import prox_get_all_projs as get_all_projs, get_project, get_user
import re
import utils

def _time_to_slack(time: Arrow) -> str:
    t1 = "{date_num}"
    t2 = "{time_secs}"
    utc = Arrow.utcfromtimestamp(time.timestamp())
    return f"<!date^{int(utc.timestamp())}^{t1}|{utc.date().strftime('%Y-%m-%d')}> <!date^{int(utc.timestamp())}^{t2}|{utc.time().strftime('%H:%M:%S')} UTC>"

@smart_msg_listen("homelab.user ")
@smart_action_listen("homelab_user_view")
@utils.get_group
@utils.filter_allowed
@utils.has_group("homelab")
def get_homelab_user_info(ctx: Context, public: bool):
    user_id = ctx.author_id
    left_over = ctx.value
    if left_over:
        if re.match(r"<@(U\w+)(\|[0-9a-zA-Z\-_\.]+)?>", left_over):
            user_id = (
                left_over.strip().removeprefix("<@").removesuffix(">").split("|")[0]
            )
        else:
            user_id = left_over

    user = get_user(user_id)
    if not user:
        ctx.private_send(text="User not found (A project is required for the command to work)")
        return
    proj_list = [(proj.proj_id, proj.title) for proj in user.projects]
    buttons: list = [
        blockkit.Button(f"{item[1]}").value(str(item[0])).action_id(f"homelab_proj_view_{item[0]}")
        for item in proj_list
    ]
    text = (f"*User info:*\n"
            f"*Slack ID:* `{user.slack_id}`\n"
            f"*User ID:* `{user.id}`\n"
            f"*Total Time:* {user.total_time_s / 3600:.2f} hours")

    message = blockkit.Message(text).add_block(
        blockkit.Section(text)
    )

    if buttons:
        message.add_block(blockkit.Actions(buttons))

    if public and not isinstance(ctx, InteractionContext):
        ctx.public_send(**message.build())
    else:
        ctx.private_send(**message.build())


@smart_msg_listen("homelab.proj ")
@smart_action_prefix_listen("homelab_proj_view")
@utils.get_group
@utils.filter_allowed
@utils.has_group("homelab")
def get_homelab_proj_info(ctx: Context, public: bool):
    left_over = ctx.value.strip()
    if left_over:
        try:
            proj_id = int(left_over)
        except ValueError:
            return ctx.private_send(text="Invalid project id.")
    else:
        return ctx.private_send(text="Missing project id.")

    try:
        proj = get_project(proj_id)
    except ValueError:
        return ctx.private_send(text="Project not found.")
    
    kv = [
        ("Repo", proj.github_link),
        ("Demo", proj.demo_link)
    ]

    buttons: list = [blockkit.Button(k).url(v) for k, v in kv if v] + [
        blockkit.Button("View User").action_id("homelab_user_view").value(str(proj.user.id))
    ]
    text = (f"*ID:* `{proj.proj_id}`\n"
            f"*Title:* {proj.title}\n"
            f"*Description:* {proj.description}\n"
            f"*Total Time:* {proj.time_s / 3600:.2f} hours\n"
            f"*Status:* {proj.status}\n"
            f"*Created At:* {_time_to_slack(proj.created_at)}\n"
            f"*Created by:* `{proj.user.slack_id}`"
    )
    message = (
        blockkit.Message(text)
        .add_block(
            blockkit.Section(text)
        )
        .add_block(blockkit.Actions(buttons))
    )
    if public:
        ctx.public_send(
            **message.build()
        )
    else:
        ctx.private_send(
            **message.build()
        )
    return None

@smart_msg_listen("homelab.stats ")
@utils.get_group
@utils.filter_allowed
@utils.has_group("homelab")
def get_homelab_stats(ctx: Context, public: bool):
    proj_list = get_all_projs()
    
    status_dict: dict[str, tuple[int, float]] = {}
    for proj in proj_list:
        status = proj.status
        status_dict[status] = status_dict.get(status, (0, 0))
        status_dict[status] = (
            status_dict[status][0] + 1,
            status_dict[status][1] + proj.time_s / 3600,
        )
    
    msg = [f"Total: {len(proj_list)} projects with {sum(map(lambda x: x.time_s, proj_list)) / 3600:.2f}h"]
    for status in sorted(status_dict):
        msg.append(
            f"- {status} - {status_dict[status][0]} project with {status_dict[status][1]:.2f}h"
        )
    
    text = "\n".join(msg)
    if public:
        ctx.public_send(True, text=text)
    else:
        ctx.private_send(False, text=text)
    