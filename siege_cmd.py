from reg import action_listen, action_prefix_listen, smart_msg_listen, MessageContext
import blockkit
from api import get_project, get_user, get_all_projs, get_coin_leaderboard
import re
from schema.interactive import BlockActionEvent
from slack_sdk.web import WebClient
import logging
import os
from arrow import Arrow
import time
import logging
from schema.siege import ProjectStatus

ALLOWED = os.environ["ALLOWLIST"].split(",")
BANNED = []

def _time_to_slack(time: Arrow) -> str:
    t1 = "{date_num}"
    t2 = "{time_secs}"
    utc = Arrow.utcfromtimestamp(time.timestamp())
    return f"<!date^{int(utc.timestamp())}^{t1}|{utc.date().strftime('%Y-%m-%d')}> <!date^{int(utc.timestamp())}^{t2}|{utc.time().strftime('%H:%M:%S')} UTC>"


@smart_msg_listen("siege.user")
def get_siege_user_info(ctx: MessageContext):
    if ctx.event.message.user in BANNED:
        return
    user_id = ctx.event.message.user
    left_over = ctx.event.message.text.removeprefix("siege.user").strip()
    if left_over:
        if re.match(r"<@(U\w+)>", left_over):
            user_id = left_over.removeprefix("<@").removesuffix(">")
        else:
            user_id = left_over

    user = get_user(user_id)

    proj_list = [(proj.week, proj.id, proj.name) for proj in user.projects]

    buttons: list = [
        blockkit.Button(f"W{item[0]} - {item[2]}")
        .value(str(item[1]))
        .action_id(f"siege_proj_view_{item[0]}")
        for item in sorted(proj_list, key=lambda x: x[0])
    ]

    message = blockkit.Message().add_block(
        blockkit.Section(
            f"*User info:*\n"
            f"*Slack ID:* `{user.slack_id}`\n"
            f"*User ID:* `{user.id}`\n"
            f"*Name:* {user.name}\n"
            f"*Display Name:* {user.display_name}\n"
            f"*Coins:* {user.coins}\n"
            f"*Rank:* {user.rank.readable}\n"
            f"*Status:* {user.status.readable}"
        )
    )

    if buttons:
        message.add_block(blockkit.Actions(buttons))

    if ctx.event.message.user in ALLOWED:
        ctx.public_send(**message.build())
    else:
        ctx.private_send(**message.build())


@smart_msg_listen("siege.proj")
def get_siege_proj_info(ctx: MessageContext):
    if ctx.event.message.user in BANNED:
        return
    left_over = ctx.event.message.text.removeprefix("siege.user").strip()
    if left_over:
        try:
            proj_id = int(left_over)
        except ValueError:
            return ctx.private_send(text="Invalid project id.")
    else:
        return ctx.private_send(text="Missing project id.")

    proj = get_project(proj_id)
    
    kv = [
        ("Project Page", proj.project_url),
        ("Repo", proj.repo_url),
        ("Demo", proj.demo_url),
        ("Stonemason Page", proj.stonemason_review_url),
        ("Reviewer Page", proj.reviewer_url),
    ]

    message = (
        blockkit.Message()
        .add_block(
            blockkit.Section(
                f"*Week {proj.week} - {proj.name}*\n"
                f"*ID:* `{proj.id}`\n"
                f"*Status:* {proj.status.readable}\n"
                f"*Created At:* {_time_to_slack(proj.created_at)}\n"
                f"*Description:* {proj.description}\n"
                f"*Coin Value:* {proj.coin_value or 'N/A'}\n"
                f"*Is Updated:* {proj.is_update}\n"
                f"*Hours:* {proj.hours} hours"
            )
        )
        .add_block(blockkit.Actions([blockkit.Button(k).url(v) for k, v in kv if v]))
    )

    if ctx.event.message.user in ALLOWED:
        ctx.public_send(**message.build())
    else:
        ctx.private_send(**message.build())

@action_prefix_listen("siege_proj_view")
def handle_siege_proj_view(event: BlockActionEvent, client: WebClient):
    v = event.actions[0].value
    user_id = event.user.id
    if user_id in BANNED:
        return
    if not v:
        logging.warning("siege_proj_view missing project id")
        return
    proj_id = int(v)
    proj = get_project(proj_id)

    channel = event.container.channel_id
    thread_ts = event.message.thread_ts if event.message else None

    kv = [
        ("Project Page", proj.project_url),
        ("Repo", proj.repo_url),
        ("Demo", proj.demo_url),
        ("Stonemason Page", proj.stonemason_review_url),
        ("Reviewer Page", proj.reviewer_url),
    ]

    message = (
        blockkit.Message()
        .add_block(
            blockkit.Section(
                f"*Week {proj.week} - {proj.name}*\n"
                f"*ID:* `{proj.id}`\n"
                f"*Status:* {proj.status.readable}\n"
                f"*Created At:* {_time_to_slack(proj.created_at)}\n"
                f"*Description:* {proj.description}\n"
                f"*Coin Value:* {proj.coin_value or 'N/A'}\n"
                f"*Is Updated:* {proj.is_update}\n"
                f"*Hours:* {proj.hours} hours"
            )
        )
        .add_block(blockkit.Actions([blockkit.Button(k).url(v) for k, v in kv if v]))
    )
    # if user_id in ALLOWED:
    #     client.chat_postMessage(channel=channel, thread_ts=thread_ts, **message.build())
    # else:
    #     client.chat_postEphemeral(
    #         channel=channel, thread_ts=thread_ts, user=user_id, **message.build()
    #     )
    client.chat_postEphemeral(
        channel=channel, thread_ts=thread_ts, user=user_id, **message.build()
    )

@smart_msg_listen("siege.global")
def get_total_proj_time(ctx: MessageContext):
    if ctx.event.message.user in BANNED:
        return

    p1 = time.perf_counter()

    proj_list = get_all_projs()

    p2 = time.perf_counter()

    week = max(proj_list, key=lambda x: x.week).week

    curr_week_proj = [proj for proj in proj_list if proj.week == week]

    p3 = time.perf_counter()

    total_time = sum(map(lambda x:x.hours, curr_week_proj))

    logging.info(f"Request time: {p2-p1}s, Sorting time: {p3-p2}s")



    ctx.public_send(text=f"Total global tracked time this week: {total_time} hours.")


@smart_msg_listen("siege.leaderboard")
@smart_msg_listen("siege.lb")
def get_leaderboard(ctx: MessageContext):
    opt = ctx.no_prefix or ""
    message: blockkit.Message | None = None
    force_ephemeral: bool = False
    match opt:
        case "coin":
            leaderboard = get_coin_leaderboard()
            user_id = ctx.event.message.user
            idx = [(i, user) for i, user in enumerate(leaderboard) if user.slack_id == user_id]
            message = blockkit.Message().add_block(
                blockkit.Section(
                    "\n".join(
                        [f"*{index}*: {user.slack_mention} - {user.coins} coins" for index, user in enumerate(leaderboard[:10], start=1)] + ([
                            f"...\n*{idx[0][0]+1}*: {idx[0][1].slack_mention} - {idx[0][1].coins} coins" if len(idx) > 0 else "You are not even in top 50... Start coding!"
                        ] if len(idx) > 0 and idx[0][0] >= 10 else [""])
                    )
                )
            )
            force_ephemeral = True
        case "proj_hours":
            proj_list = get_all_projs()
            week_proj = [proj for proj in proj_list if proj.status == ProjectStatus.FINISHED]
            sorted_order = sorted(week_proj, key=lambda x: x.hours, reverse=True)
            message = blockkit.Message().add_block(
                blockkit.Section(
                    "\n".join(
                        [f"*{index}*: W{proj.week} {proj.name} - {proj.hours} hours by {proj.user.display_name} with {float(proj.coin_value)} coins payout" for index, proj in enumerate(sorted_order[:10], start=1)]
                    )
                )
            )
        case "week_hours":
            proj_list = get_all_projs()
            curr_week = max(proj_list, key=lambda x: x.week).week
            week_proj = [proj for proj in proj_list if proj.week == curr_week]
            sorted_order = sorted(week_proj, key=lambda x: x.hours, reverse=True)
            message = blockkit.Message().add_block(
                blockkit.Section(
                    "\n".join(
                        [f"*{index}*: W{proj.week} {proj.name} - {proj.hours} hours by {proj.user.display_name}" for index, proj in enumerate(sorted_order[:10], start=1)]
                    )
                )
            )
        case "proj_coins":
            proj_list = get_all_projs()
            week_proj = [proj for proj in proj_list if proj.status == ProjectStatus.FINISHED]
            sorted_order = sorted(week_proj, key=lambda x: float(x.coin_value), reverse=True)
            message = blockkit.Message().add_block(
                blockkit.Section(
                    "\n".join(
                        [f"*{index}*: W{proj.week} {proj.name} - {proj.hours} hours by {proj.user.display_name} with {float(proj.coin_value)} coins payout" for index, proj in enumerate(sorted_order[:10], start=1)]
                    )
                )
            )
        case _:
            message = blockkit.Message("Don't know how to use this? You can do the following options:\n`coin`, `proj_hours`, `week_hours`, `proj_coins`")
    
    if ctx.event.message.user in ALLOWED and not force_ephemeral:
        ctx.public_send(**message.build())
    else:
        ctx.private_send(**message.build())



