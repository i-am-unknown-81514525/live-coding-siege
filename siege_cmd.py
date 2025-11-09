from reg import (
    action_listen,
    action_prefix_listen,
    smart_msg_listen,
    description,
    Context,
    slash_listen,
)
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
from schema.siege import ProjectStatus, SiegeUserStatus, SiegeProject
from collections import Counter

ALLOWED = os.environ["ALLOWLIST"].split(",")
BANNED = []


def _time_to_slack(time: Arrow) -> str:
    t1 = "{date_num}"
    t2 = "{time_secs}"
    utc = Arrow.utcfromtimestamp(time.timestamp())
    return f"<!date^{int(utc.timestamp())}^{t1}|{utc.date().strftime('%Y-%m-%d')}> <!date^{int(utc.timestamp())}^{t2}|{utc.time().strftime('%H:%M:%S')} UTC>"


def _parse_repo(repo: str) -> str:
    match = re.search(
        r"https?://(?:(?:(?:www\.?)?(github\.com|gitlab\.com|codeberg\.org|bitbucket\.org))|(git\.hackclub\.app|dev\.azure\.com))/([^/\"\n ]+)/([^/\"\n ]+)",
        repo,
    )

    if match is None:
        raise ValueError(f"Invalid repo: {repo}")

    match match.group(1) or match.group(2):
        case "github.com":
            return f"github:{match.group(3)}/{match.group(4)}"
        case "gitlab.com":
            return f"gitlab:{match.group(3)}/{match.group(4)}"
        case "codeberg.org":
            return f"codeberg:{match.group(3)}/{match.group(4)}"
        case "bitbucket.org":
            return f"bitbucket:{match.group(3)}/{match.group(4)}"
        case "dev.azure.com":
            return f"azure_dev:{match.group(3)}/{match.group(4)}"
        case "git.hackclub.app":
            return f"hc_git:{match.group(3)}/{match.group(4)}"
        case _:
            raise ValueError(f"Unknown repo: {repo}")


def _parse_repo_user_from_shorthand(repo_shorthand: str) -> str:
    return repo_shorthand.split("/")[0]


def _parse_repo_user(repo: str) -> str:
    return _parse_repo_user_from_shorthand(_parse_repo(repo))


def construct_from_short(shorthand: str) -> str:
    mapping = {
        "github": "https://github.com/{user}/{repo}",
        "gitlab": "https://gitlab.com/{user}/{repo}",
        "codeberg": "https://codeberg.org/{user}/{repo}",
        "bitbucket": "https://bitbucket.org/{user}/{repo}",
        "azure_dev": "https://dev.azure.com/{user}/{repo}",
        "hc_git": "https://git.hackclub.app/{user}/{repo}",
    }

    (init, user, repo, *_) = (
        shorthand.split(":")[0],
        *shorthand.split(":")[1].split("/"),
        None,
    )
    return mapping[init].format(user=user, repo=repo or "")


def _calc_base(week: int, hours: float) -> float:
    if week <= 4:
        return hours * 2
    if hours < 10:
        return float("inf")  # discard
    week_base = 10
    if week == 5:
        week_base = 9
    return 5 + (hours - week_base) * 2


@slash_listen("/user")
@smart_msg_listen("siege.user")
@description("/user <user_id>?", "Shhhh... sneak peek on a siege user, surely no one would notice :)")
def get_siege_user_info(ctx: Context):
    if ctx.author_id in BANNED:
        return
    user_id = ctx.author_id
    left_over = ctx.no_prefix
    if left_over:
        if re.match(r"<@(U\w+)(\|[0-9a-zA-Z\-_\.]+)?>", left_over):
            user_id = (
                left_over.removeprefix("<@").removesuffix(">").split("|")[0]
            )  # https://stackoverflow.com/questions/29392407/how-to-get-a-slack-user-by-email-using-users-info-api/51469610#51469610
        else:
            user_id = left_over

    user = get_user(user_id)
    proj_list = [(proj.week, proj.id, proj.name) for proj in user.projects]
    known_repo = [get_project(proj.id).repo_url for proj in user.projects]
    known_identity = [_parse_repo_user(repo) for repo in known_repo if repo]
    id_count = Counter(known_identity)
    id_string = ", ".join(
        f"<{construct_from_short(id)}|{id}> `{count}/{len(known_identity)}`"
        for id, count in id_count.most_common()
    )

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
            f"*Status:* {user.status.readable}\n"
            + (f"*Common identity:* {id_string}" if id_string else "")
        )
    )

    if buttons:
        message.add_block(blockkit.Actions(buttons))

    if ctx.author_id in ALLOWED:
        ctx.public_send(**message.build())
    else:
        ctx.private_send(**message.build())


@slash_listen("/proj")
@slash_listen("/project")
@smart_msg_listen("siege.proj")
@description("/proj <proj_id>", "Let me check a project coin value... What??? Someone got 607 coins in a week?")
def get_siege_proj_info(ctx: Context):
    if ctx.author_id in BANNED:
        return
    left_over = ctx.no_prefix.strip()
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

    buttons: list = [blockkit.Button(k).url(v) for k, v in kv if v] + [
        blockkit.Button("View User")
        .action_id("siege_user_view")
        .value(str(proj.user.id))
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
                f"*Hours:* {proj.hours} hours\n"
                + (
                    f"*Repo user:* <{construct_from_short(_parse_repo_user(proj.repo_url))}|{_parse_repo_user(proj.repo_url)}>"
                    if proj.repo_url
                    else ""
                )
            )
        )
        .add_block(blockkit.Actions(buttons))
    )

    if ctx.author_id in ALLOWED:
        ctx.public_send(**message.build(), unfurl_links=False)
    else:
        ctx.private_send(**message.build(), unfurl_links=False)


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
    thread_ts = (
        event.message.thread_ts if event.message else None
    ) or event.container.thread_ts

    kv = [
        ("Project Page", proj.project_url),
        ("Repo", proj.repo_url),
        ("Demo", proj.demo_url),
        ("Stonemason Page", proj.stonemason_review_url),
        ("Reviewer Page", proj.reviewer_url),
    ]

    buttons: list = [blockkit.Button(k).url(v) for k, v in kv if v] + [
        blockkit.Button("View User")
        .action_id("siege_user_view")
        .value(str(proj.user.id))
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
                f"*Hours:* {proj.hours} hours\n"
                + (
                    f"*Repo user:* <{construct_from_short(_parse_repo_user(proj.repo_url))}|{_parse_repo_user(proj.repo_url)}>"
                    if proj.repo_url
                    else ""
                )
            )
        )
        .add_block(blockkit.Actions(buttons))
    )
    # if user_id in ALLOWED:
    #     client.chat_postMessage(channel=channel, thread_ts=thread_ts, **message.build())
    # else:
    #     client.chat_postEphemeral(
    #         channel=channel, thread_ts=thread_ts, user=user_id, **message.build()
    #     )
    client.chat_postEphemeral(
        channel=channel,
        thread_ts=thread_ts,
        user=user_id,
        **message.build(),
        unfurl_links=False,
    )


@action_listen("siege_user_view")
def handle_siege_user_view(event: BlockActionEvent, client: WebClient):
    v = event.actions[0].value
    ori_uid = event.user.id
    if ori_uid in BANNED:
        return
    if not v:
        logging.warning("siege_proj_view missing project id")
        return
    user_id = int(v)
    user = get_user(user_id)

    channel = event.container.channel_id
    thread_ts = (
        event.message.thread_ts if event.message else None
    ) or event.container.thread_ts

    proj_list = [(proj.week, proj.id, proj.name) for proj in user.projects]
    known_repo = [get_project(proj.id).repo_url for proj in user.projects]
    known_identity = [_parse_repo_user(repo) for repo in known_repo if repo]
    id_count = Counter(known_identity)
    id_string = ", ".join(
        f"<{construct_from_short(id)}|{id}> `{count}/{len(known_identity)}`"
        for id, count in id_count.most_common()
    )

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
            f"*Status:* {user.status.readable}\n"
            + (f"*Common identity:* {id_string}" if id_string else "")
        )
    )

    if buttons:
        message.add_block(blockkit.Actions(buttons))

    client.chat_postEphemeral(
        channel=channel, thread_ts=thread_ts, user=ori_uid, **message.build()
    )


@slash_listen("/global")
@smart_msg_listen("siege.global")
@description("/global", "Uhh am I gonna get my global bet payout this time :nervous:")
def get_total_proj_time(ctx: Context):
    if ctx.author_id in BANNED:
        return

    p1 = time.perf_counter()

    proj_list = get_all_projs()

    p2 = time.perf_counter()

    week = max(proj_list, key=lambda x: x.week).week
    curr_week_proj = [proj for proj in proj_list if proj.week == week]

    p3 = time.perf_counter()

    total_time = sum(map(lambda x: x.hours, curr_week_proj))
    logging.info(f"Request time: {p2 - p1}s, Sorting time: {p3 - p2}s")
    ctx.public_send(text=f"Total global tracked time this week: {total_time} hours.")


LEADERBOARD_AMOUNT = 20


@slash_listen("/lb")
@slash_listen("/leaderboard")
@smart_msg_listen("siege.leaderboard")
@smart_msg_listen("siege.lb")
@description("/lb <lb_option>?", "The hall of fame!")
def get_leaderboard(ctx: Context):
    opt = ctx.no_prefix or ""
    message: blockkit.Message | None = None
    force_ephemeral: bool = False
    match opt:
        case "coin":
            leaderboard = get_coin_leaderboard()
            user_id = ctx.author_id
            idx = [
                (i, user)
                for i, user in enumerate(leaderboard)
                if user.slack_id == user_id
            ]
            message = blockkit.Message().add_block(
                blockkit.Section(
                    "\n".join(
                        [
                            f"*{index}*: {user.slack_mention} - {user.coins} coins"
                            for index, user in enumerate(
                                leaderboard[:LEADERBOARD_AMOUNT], start=1
                            )
                        ]
                        + (
                            [
                                f"...\n*{idx[0][0] + 1}*: {idx[0][1].slack_mention} - {idx[0][1].coins} coins"
                                if len(idx) > 0
                                else "You are not even in top 50... Start coding!"
                            ]
                            if len(idx) > 0 and idx[0][0] >= LEADERBOARD_AMOUNT
                            else [""]
                        )
                    )
                )
            )
            force_ephemeral = True
        case "proj_hours":
            proj_list = get_all_projs()
            week_proj = [
                proj for proj in proj_list if proj.status == ProjectStatus.FINISHED
            ]
            sorted_order = sorted(week_proj, key=lambda x: x.hours, reverse=True)
            message = blockkit.Message().add_block(
                blockkit.Section(
                    "\n".join(
                        [
                            f"*{index}*: W{proj.week} {proj.name} - {proj.hours} hours by {proj.user.display_name} with {float(proj.coin_value)} coins payout"
                            for index, proj in enumerate(
                                sorted_order[:LEADERBOARD_AMOUNT], start=1
                            )
                        ]
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
                        [
                            f"*{index}*: W{proj.week} {proj.name} - {proj.hours} hours by {proj.user.display_name}"
                            for index, proj in enumerate(
                                sorted_order[:LEADERBOARD_AMOUNT], start=1
                            )
                        ]
                    )
                )
            )
        case "proj_coins":
            proj_list = get_all_projs()
            week_proj = [
                proj for proj in proj_list if proj.status == ProjectStatus.FINISHED
            ]
            sorted_order = sorted(
                week_proj, key=lambda x: float(x.coin_value), reverse=True
            )
            message = blockkit.Message().add_block(
                blockkit.Section(
                    "\n".join(
                        [
                            f"*{index}*: W{proj.week} {proj.name} - {proj.hours} hours by {proj.user.display_name} with {float(proj.coin_value)} coins payout"
                            for index, proj in enumerate(
                                sorted_order[:LEADERBOARD_AMOUNT], start=1
                            )
                        ]
                    )
                )
            )
        case "efficiency":
            proj_list = get_all_projs()
            week_proj = [
                proj
                for proj in proj_list
                if proj.status == ProjectStatus.FINISHED
                and proj.hours > 0
                and proj.coin_value > 0
            ]
            sorted_order = list(
                sorted(
                    week_proj,
                    key=lambda x: x.coin_value / _calc_base(x.week, x.hours),
                    reverse=True,
                )
            )
            selected: list[SiegeProject] = []
            for proj in sorted_order:
                if len(selected) >= LEADERBOARD_AMOUNT:
                    break
                if proj.hours < 10:
                    continue
                if proj.coin_value / _calc_base(proj.week, proj.hours) > 15:
                    continue
                user_id = proj.user.id
                status = get_user(user_id).status
                if status == SiegeUserStatus.WORKING:
                    selected.append(proj)
            message = (
                blockkit.Message()
                .add_block(
                    blockkit.Section(
                        "\n".join(
                            [
                                f"*{index}*: W{proj.week} {proj.name} (`{proj.id}`) - {proj.hours}h,{proj.coin_value}c, {proj.coin_value / _calc_base(proj.week, proj.hours):.2f}x"
                                for index, proj in enumerate(selected, start=1)
                            ]
                        )
                    )
                )
                .add_block(
                    blockkit.Section(
                        "Note for the underlying assumption/filter used for this leaderboard:\n- Any result with >15 multiplier is discarded as it is not possible\n- Only user who have status `working` is consider\n- Project with < 10 hours is discarded\n- Assumption is made that no project have used mercenary, as such information cannot be collected over API"
                    )
                )
            )
        case _:
            message = blockkit.Message(
                "Don't know how to use this? You can do the following options:\n`coin`, `proj_hours`, `week_hours`, `proj_coins`, `efficiency`"
            )

    if ctx.author_id in ALLOWED and not force_ephemeral:
        ctx.public_send(**message.build())
    else:
        ctx.private_send(**message.build())


@slash_listen("/stats")
@smart_msg_listen("siege.stats")
@description("/stats", "Stats for the Siege YSWS")
def get_stats(ctx: Context):
    all_projs = get_all_projs()
    week_proj: dict[int, list[SiegeProject]] = {}
    for proj in all_projs:
        week = proj.week
        week_proj[week] = week_proj.get(week, [])
        week_proj[week].append(proj)
    total_msg = []
    for week in sorted(week_proj):
        projs = week_proj[week]
        week_msg = [
            f"*W{week}* - {len(projs)} with {sum(map(lambda x: x.hours, projs)):.1f}h"
        ]
        status_dict: dict[str, tuple[int, float]] = {}
        for proj in projs:
            status = proj.status
            status_dict[status] = status_dict.get(status, (0, 0))
            status_dict[status] = (
                status_dict[status][0] + 1,
                status_dict[status][1] + proj.hours,
            )
        for status in sorted(status_dict):
            week_msg.append(
                f"- {status} - {status_dict[status][0]} project with {status_dict[status][1]:.1f}h"
            )
        total_msg.append("\n".join(week_msg))
    if ctx.author_id in ALLOWED:
        ctx.public_send(True, text="\n".join(total_msg))
    else:
        ctx.private_send(False, text="\n".join(total_msg))
