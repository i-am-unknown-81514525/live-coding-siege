import typing
from typing import Literal
from slack.reg import (
    smart_action_listen,
    smart_action_prefix_listen,
    smart_msg_listen,
    Context,
    slash_listen,
    InteractionContext,
    file_upload,
)
import blockkit
from siege.api import get_coin_leaderboard, get_shop_item
import re
from schema.interactive import BlockActionEvent
from slack_sdk.web import WebClient
import logging
import os
from arrow import Arrow
import time
import logging
from siege.schema.siege import ProjectStatus, SiegeUserStatus, SiegeProject
from collections import Counter
from rapidfuzz import fuzz
import utils
from siege.schema import dictionary
import requests
import siege.core as core
from collections import defaultdict
from siege.core import (
    prox_get_all_projs as get_all_projs,
    prox_get_user as get_user,
    prox_get_project as get_project,
)
from siege.utils import guess_week
import seaborn as sns
import pandas
from schema.file import PendingFile
from io import BytesIO
import matplotlib.pyplot as plt
from base import description
from irc.reg import irc_msg_listen

# ALLOWED = os.environ["ALLOWLIST"].split(",")
# BANNED = []


def _time_to_slack(time: Arrow) -> str:
    t1 = "{date_num}"
    t2 = "{time_secs}"
    utc = Arrow.utcfromtimestamp(time.timestamp())
    return f"<!date^{int(utc.timestamp())}^{t1}|{utc.date().strftime('%Y-%m-%d')}> <!date^{int(utc.timestamp())}^{t2}|{utc.time().strftime('%H:%M:%S')} UTC>"


def _parse_repo(repo: str) -> str:
    match = re.search(
        r"https?://(?:(?:(?:www\.?)?(github\.com|gitlab\.com|codeberg\.org|bitbucket\.org))|(git\.hackclub\.app|dev\.azure\.com))/([^/\"\n ]+)/([^/\"\n ]*)",
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
@smart_msg_listen("siege.user ")
@smart_action_listen("siege_user_view")
@irc_msg_listen("siege.user ")
@description(
    "/user <user_id>?",
    "Shhhh... sneak peek on a siege user, surely no one would notice :)",
)
@utils.get_group
@utils.filter_allowed
@utils.has_group("siege")
def get_siege_user_info(ctx: Context, public: bool):
    user_id = ctx.author_id
    left_over = ctx.value
    if left_over:
        if re.match(r"<@(U\w+)(\|[0-9a-zA-Z\-_\.]+)?>", left_over):
            user_id = (
                left_over.strip().removeprefix("<@").removesuffix(">").split("|")[0]
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

    text = (f"*User info:*\n"
            f"*Slack ID:* `{user.slack_id}`\n"
            f"*User ID:* `{user.id}`\n"
            f"*Name:* {user.name}\n"
            f"*Display Name:* {user.display_name}\n"
            f"*Coins:* {user.coins}\n"
            f"*Rank:* {user.rank.readable}\n"
            f"*Status:* {user.status.readable}\n"
            + (f"*Common identity:* {id_string}" if id_string else ""))

    message = blockkit.Message(text).add_block(
        blockkit.Section(text)
    )

    if buttons:
        message.add_block(blockkit.Actions(buttons))

    if public and not isinstance(ctx, InteractionContext):
        ctx.public_send(**message.build())
    else:
        ctx.private_send(**message.build())


@smart_msg_listen("internal.test ")
@utils.get_group
@utils.filter_authorised
@utils.require_group("siege", False)
def test(ctx: Context) -> typing.Any:
    return ctx.private_send(
        False, files=[PendingFile("test.txt", b"Hello world!", "A test file")]
    )


@slash_listen("/proj")
@slash_listen("/project")
@smart_msg_listen("siege.proj ")
@irc_msg_listen("siege.proj ")
@smart_action_prefix_listen("siege_proj_view")
@description(
    "/proj <proj_id>",
    "Let me check a project coin value... What??? Someone got 607 coins in a week?",
)
@utils.get_group
@utils.filter_allowed
@utils.has_group("siege")
def get_siege_proj_info(ctx: Context, public: bool):
    left_over = ctx.value.strip()
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

    text = (
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

    message = (
        blockkit.Message(text)
        .add_block(
            blockkit.Section(text)
        )
        .add_block(blockkit.Actions(buttons))
    )

    heartbeats = core.retrieve_all_proj_record(proj.id)
    result = core.analyse_hour_by_time_in_week(heartbeats)
    # logging.info(result)
    df = pandas.DataFrame(
        {"time": [t.datetime for t in result.keys()], "hours": list(result.values())}
    )
    fig, ax = plt.subplots(figsize=(6, 8))
    plot = sns.lineplot(df, x="time", y="hours", ax=ax)
    ax.locator_params(axis="x", nbins=7)
    ax.locator_params(axis="y", nbins=15)
    ax.set_title(f"Tracked hours over time for project {proj.name} (W{proj.week})")
    ax.set_xlabel("Time")
    ax.set_ylabel("Total tracked hours")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha="right")
    ax.set_xlim(min(df["time"]), max(df["time"]))
    ax.set_ylim(0, max(df["hours"]) * 1.1)
    fig.tight_layout()  # type: ignore

    iodt = BytesIO()
    img = b""
    if fig:
        try:
            fig.savefig(iodt, format="png")  # type: ignore
            img = iodt.getvalue()
        except Exception as e:
            logging.error(f"Failed to save figure: {e}")

    if public and not isinstance(ctx, InteractionContext):
        ctx.public_send(
            **message.build(),
            unfurl_links=False,
            files=[
                PendingFile(f"proj_{proj.id}.png", img, "Tracked hour by time in week")
            ]
            if img
            else [],
        )
    else:
        ctx.private_send(
            **message.build(),
            unfurl_links=False,
            files=[
                PendingFile(f"proj_{proj.id}.png", img, "Tracked hour by time in week")
            ]
            if img
            else [],
        )
    return None


@slash_listen("/global")
@smart_msg_listen("siege.global")
@irc_msg_listen("siege.global")
@description("/global", "Uhh am I gonna get my global bet payout this time :nervous:")
def get_total_proj_time(ctx: Context):
    p1 = time.perf_counter()

    proj_list = get_all_projs()

    p2 = time.perf_counter()

    week = max(proj_list, key=lambda x: x.week).week
    curr_week_proj = [proj for proj in proj_list if proj.week == week]
    

    p3 = time.perf_counter()

    total_time = sum(map(lambda x: x.hours, curr_week_proj))
    logging.info(f"Request time: {p2 - p1}s, Sorting time: {p3 - p2}s")
    ctx.public_send(
        text=f"Total global tracked time this week: {total_time:.1f} hours."
    )


LEADERBOARD_AMOUNT = 20


@slash_listen("/lb")
@slash_listen("/leaderboard")
@smart_msg_listen("siege.leaderboard")
@smart_msg_listen("siege.lb")
@irc_msg_listen("siege.leaderboard")
@irc_msg_listen("siege.lb")
@description("/lb <lb_option>?", "The hall of fame!")
@utils.get_group
@utils.filter_allowed
@utils.has_group("siege")
def get_leaderboard(ctx: Context, public: bool):
    opt = ctx.value or ""
    message: blockkit.Message | None = None
    force_ephemeral: bool = not public
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
                            f"*{index}*: W{proj.week} {proj.name} - {proj.hours:.1f} hours by {proj.user.display_name} with {float(proj.coin_value)} coins payout"
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
                            f"*{index}*: W{proj.week} {proj.name} - {proj.hours:.1f} hours by {proj.user.display_name}"
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
                            f"*{index}*: W{proj.week} {proj.name} - {proj.hours} hours by {proj.user.display_name} with {float(proj.coin_value):.0f} coins payout"
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
                blockkit.Message(
                    "\n".join(
                    [
                        f"*{index}*: W{proj.week} {proj.name} (`{proj.id}`) - {proj.hours:.1f}h,{proj.coin_value}c, {proj.coin_value / _calc_base(proj.week, proj.hours):.3f}x"
                        for index, proj in enumerate(selected, start=1)
                    ]
                )
                )
                .add_block(
                    blockkit.Section(
                        "\n".join(
                            [
                                f"*{index}*: W{proj.week} {proj.name} (`{proj.id}`) - {proj.hours:.1f}h,{proj.coin_value}c, {proj.coin_value / _calc_base(proj.week, proj.hours):.3f}x"
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

    if not force_ephemeral:
        ctx.public_send(**message.build())
    else:
        ctx.private_send(**message.build())


@slash_listen("/graph")
@smart_msg_listen("siege.graph")
@description("/graph <graph_opt>?", "We need to remember the history")
@utils.get_group
@utils.filter_allowed
@utils.has_group("siege")
def generate_graph(ctx: Context, public: bool):
    opt = ctx.value or ""
    force_ephemeral: bool = not public
    media: PendingFile | None = None
    match opt:
        case "coin":
            heartbeats: list[core.UserHeartbeatRecord] = core.retrieve_every_user_record()
            result: dict[Arrow, int] = core.analyse_coin_count(heartbeats)
            df = pandas.DataFrame(
                {
                    "time": [t.datetime for t in result.keys()],
                    "coins": list(result.values()),
                }
            )
            fig, ax = plt.subplots(figsize=(6, 8))
            plot = sns.lineplot(df, x="time", y="coins", ax=ax)
            ax.locator_params(axis="x", nbins=7)
            ax.locator_params(axis="y", nbins=15)
            ax.set_title("Tracked coin count over time")
            ax.set_xlabel("Time")
            ax.set_ylabel("Total tracked coins")
            ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha="right")
            ax.set_xlim(min(df["time"]), max(df["time"]))
            ax.set_ylim(0, max(df["coins"]) * 1.1)
            fig.tight_layout()
            iodt = BytesIO()
            img = b""
            if fig:
                try:
                    fig.savefig(iodt, format="png")  # type: ignore
                    img = iodt.getvalue()
                except Exception as e:
                    logging.error(f"Failed to save figure: {e}")
            media = PendingFile("coin.png", img, "Tracked coin count over time")
        case "coin_hours":
            user_result = core.analyse_per_person_coin_count_status(core.retrieve_every_user_record(Arrow.now().shift(minutes=-15)))
            proj_result = core.analyse_per_person_proj_hours(core.retrieve_every_proj_record(Arrow.now().shift(minutes=-15)))
            all_user_id = set(user_result.keys()).union(set(proj_result.keys()))
            data = []
            for user_id in all_user_id:
                coin_data = user_result.get(user_id, (0, "new"))
                proj_data = proj_result.get(user_id, 0)
                data.append(
                    {
                        "user_id": user_id,
                        "status": coin_data[0],
                        "coins": coin_data[1],
                        "hours": proj_data,
                    }
                )
            df = pandas.DataFrame(data)
            fig, ax = plt.subplots(figsize=(6, 8))
            plot = sns.scatterplot(
                df,
                x="hours",
                y="coins",
                hue="status",
                palette={"new": "blue", "working": "green", "out": "orange", "banned": "red"},
                ax=ax,
            )
            ax.set_title("Total coins vs total project hours by user")
            ax.set_xlabel("Total project hours")
            ax.set_ylabel("Total coins")
            ax.set_xlim(0, max(df["hours"]) * 1.1)
            fig.tight_layout()
            iodt = BytesIO()
            img = b""
            if fig:
                try:
                    fig.savefig(iodt, format="png")  # type: ignore
                    img = iodt.getvalue()
                except Exception as e:
                    logging.error(f"Failed to save figure: {e}")
            media = PendingFile("coin_hours.png", img, "Total coins vs total project hours by user")
        case "global":
            week = guess_week()
            proj_heartbeats: list[core.ProjHeartbeatRecord] = core.retrieve_all_week_record(week)
            proj_hour_result: dict[Arrow, float] = core.analyse_hour_by_time_in_week(proj_heartbeats)
            df = pandas.DataFrame(
                {"time": [t.datetime for t in proj_hour_result.keys()], "hours": list(proj_hour_result.values())}
            )
            fig, ax = plt.subplots(figsize=(6, 8))
            plot = sns.lineplot(df, x="time", y="hours", ax=ax)
            ax.locator_params(axis="x", nbins=7)
            ax.locator_params(axis="y", nbins=15)
            ax.set_title(f"Tracked hours over time in W{week}")
            ax.set_xlabel("Time")
            ax.set_ylabel("Total tracked hours")
            ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha="right")
            ax.set_xlim(min(df["time"]), max(df["time"]))
            ax.set_ylim(0, max(df["hours"]) * 1.1)
            fig.tight_layout()  # type: ignore

            iodt = BytesIO()
            img = b""
            if fig:
                try:
                    fig.savefig(iodt, format="png")  # type: ignore
                    img = iodt.getvalue()
                except Exception as e:
                    logging.error(f"Failed to save figure: {e}")
            media = PendingFile(f"global_w{week}.png", img, f"Tracked hour by time in week W{week}")
        case "user_status":
            dt = core.analyse_overall_user_status(core.retrieve_every_user_record())
            df = pandas.DataFrame(
                {
                    "time": [t[0].datetime for t in dt],
                    "status": [t[1] for t in dt],
                    "count": [t[2] for t in dt]
                }
            )
            fig, ax = plt.subplots(figsize=(6, 8))
            plot = sns.lineplot(df, x="time", y="count", ax=ax, hue="status",
                palette={"new": "blue", "working": "green", "out": "orange", "banned": "red"},)
            ax.locator_params(axis="x", nbins=7)
            ax.locator_params(axis="y", nbins=15)
            ax.set_title(f"User status over time")
            ax.set_xlabel("Time")
            ax.set_ylabel("User Count")
            ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha="right")
            ax.set_xlim(min(df["time"]), max(df["time"]))
            ax.set_ylim(0, max(df["count"]) * 1.1)
            fig.tight_layout()  # type: ignore
            iodt = BytesIO()
            img = b""
            if fig:
                try:
                    fig.savefig(iodt, format="png")  # type: ignore
                    img = iodt.getvalue()
                except Exception as e:
                    logging.error(f"Failed to save figure: {e}")
            media = PendingFile(f"user_status.png", img, f"User status over time")
        case _:
            ...

    if not force_ephemeral:
        if media:
            ctx.public_send(files=[media])
        else:
            ctx.public_send(text="No graph generated... Expected argument: `coin`, `coin_hours`, `global`")
    else:
        if media:
            ctx.private_send(files=[media])
        else:
            ctx.private_send(text="No graph generated... Expected argument: `coin`, `coin_hours`, `global`")


@slash_listen("/stats")
@slash_listen("/siege_stats")
@smart_msg_listen("siege.stats")
@irc_msg_listen("siege.stats")
@description("/stats", "Stats for the Siege YSWS")
@utils.get_group
@utils.filter_allowed
@utils.has_group("siege")
def get_stats(ctx: Context, public: bool):
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
    if public:
        ctx.public_send(True, text="\n".join(total_msg))
    else:
        ctx.private_send(False, text="\n".join(total_msg))


def _cmp(search: str, term: str) -> float:
    if len(search) < 3 or len(term) < 3:
        return 0
    return fuzz.partial_ratio(search, term) / 100


SIMILARITY_THRESHOLD = 0.9


@slash_listen("/searchs")
@smart_msg_listen("siege.search ")
@smart_msg_listen("siege.searchs ")
@irc_msg_listen("siege.searchs ")
@irc_msg_listen("siege.search ")
@description("/searchs <keyword>?", "Search for project by keyword")
@utils.get_group
@utils.filter_allowed
@utils.has_group("siege")
def search_project(ctx: Context, public: bool):
    req = ctx.value.lower()
    all_projs = get_all_projs()

    def full_info(
        proj: SiegeProject,
    ) -> Literal[
        "project name",
        "description",
        "repo user",
        "repo",
        None,
        "user id",
        "project id",
        "display name",
        "user name",
    ]:
        if (
            req in proj.name.lower()
            or _cmp(req, proj.name.lower()) > SIMILARITY_THRESHOLD
        ):
            return "project name"
        if (
            req in proj.description.lower()
            or _cmp(req, proj.description.lower()) > SIMILARITY_THRESHOLD
        ):
            return "description"
        if proj.repo_url:
            parsed = _parse_repo(proj.repo_url)
            if (
                req in _parse_repo_user_from_shorthand(parsed).lower()
                or _cmp(req, _parse_repo_user_from_shorthand(parsed).lower())
                > SIMILARITY_THRESHOLD
            ):
                return "repo user"
            if (
                req in parsed.split("/")[1].lower()
                or _cmp(req, parsed.split("/")[1].lower()) > SIMILARITY_THRESHOLD
            ):
                return "repo"
        try:
            if int(req) == proj.user.id or int(req) == proj.id:
                if int(req) == proj.user.id:
                    return "user id"
                else:
                    return "project id"
        except:
            ...
        if (
            req in proj.user.display_name.lower()
            or _cmp(req, proj.user.display_name.lower()) > SIMILARITY_THRESHOLD
        ):
            return "display name"
        if (
            req in proj.user.name.lower()
            or _cmp(req, proj.user.name.lower()) > SIMILARITY_THRESHOLD
        ):
            return "user name"
        return None

    def retrieve(
        proj: SiegeProject,
        key: Literal[
            "project name",
            "description",
            "repo user",
            "repo",
            "user id",
            "project id",
            "display name",
            "user name",
        ],
    ):
        match key:
            case "project name":
                return proj.name
            case "description":
                return proj.description
            case "display name":
                return proj.user.display_name
            case "repo user":
                return _parse_repo_user(proj.repo_url)
            case "repo":
                return proj.repo_url
            case "user id":
                return proj.user.id
            case "project id":
                return proj.id
            case "user name":
                return proj.user.name

    filtered = list(filter(lambda proj: full_info(proj) is not None, all_projs))

    base = f"Founded {len(filtered)} matched project"
    if req:
        base += f' with keyword "{req}"'
    if len(filtered) > 50:
        base += " (Only showing 50 results)"
    base += "\n"
    # noinspection PyTypeChecker
    base += "\n".join(
        f"`{p.id}`-`W{p.week}-{p.user.id}` - {p.name}: {p.status} with {p.hours:.1f}h"
        + (
            f" matched by {full_info(p)} - {
                str(retrieve(p, full_info(p) or 'project name'))[:150]
            }"
            if req
            else ""
        )
        for p in filtered[:50]
    )

    if public:
        ctx.public_send(text=base)
    else:
        ctx.private_send(text=base)


def fetch_dictionary(word: str) -> dictionary.DictError | dictionary.DictResult:
    req = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")
    if not req.ok:
        return dictionary.DictError.parse(req.json())
    return dictionary.DictResult.parse(req.json()[0])


@slash_listen("/define")
@smart_msg_listen("siege.define ")
@irc_msg_listen("siege.define ")
@description("/define <word>", "Get a dictionary definition of a word")
@utils.get_group
@utils.filter_allowed
@utils.has_group("siege")
def get_define(ctx: Context, public: bool):
    if public:
        return ctx.public_send(text=fetch_dictionary(ctx.value).readable)
    return ctx.private_send(text=fetch_dictionary(ctx.value).readable)


@slash_listen("/proj_details")
@smart_msg_listen("siege.proj_details ")
@irc_msg_listen("siege.proj_details ")
@description("/proj_details <proj_id>", "Peeking at every change you made :)")
@utils.get_group
@utils.filter_allowed
@utils.has_group("siege")
def get_user_details(ctx: Context, public: bool):
    if isinstance(ctx, InteractionContext):
        public = False
    try:
        proj_id = int(ctx.value)
    except ValueError:
        return ctx.private_send(text="Invalid project id.")
    message_lines = []
    try:
        proj = get_project(proj_id)
        core.push_proj([proj])
    except Exception:
        message_lines.append(
            "Project can no longer be discovered from the API, the project might be hidden or deleted."
        )
    heartbeats = list(reversed(core.retrieve_all_proj_record(proj_id)))
    if not heartbeats:
        return ctx.private_send(text="No heartbeat data found for this project.")
    message_lines.append(
        f"""*{_time_to_slack(heartbeats[0].measurement_time)}*: Project first discovered\n> Repo URL: {"None" if not heartbeats[0].repo_url else f"<{heartbeats[0].repo_url}|{_parse_repo(heartbeats[0].repo_url)}>"}\n> Demo URL: {heartbeats[0].demo_url or "None"}\n> Status: {heartbeats[0].proj_status}\n> Hours: {heartbeats[0].hours}\n> Project Name: \"{heartbeats[0].title}\"\n> Description: \"{heartbeats[0].description}\""""
    )
    for curr, next in zip(heartbeats, heartbeats[1:]):
        diff = curr.compare_to_new(next)
        if not diff:
            continue
        line = f"*{_time_to_slack(next.measurement_time)}*:"
        for key, (old, new) in diff.items():
            if key == "Repo URL":
                old_part = "None"
                if old:
                    old_part = f"<{old}|{_parse_repo(old)}>"
                new_part = "None"
                if new:
                    new_part = f"<{new}|{_parse_repo(new)}>"
                line += f"\n> {key}: {old_part} -> {new_part}"
            # elif key == "Demo URL":
            #     line += f"\n> {key}: {old} -> {new}"
            elif key in ["Project Name", "Description"]:
                line += f'\n> {key}: "{old}" -> "{new}"'
            elif key == "Hours":
                line += f"\n> {key}: {old}h -> {new}h"
            else:
                line += f"\n> {key}: {old} -> {new}"
        message_lines.append(line)
    if public:
        ctx.public_send(True, text="\n".join(message_lines))
    else:
        ctx.private_send(True, text="\n".join(message_lines))
    return None


@slash_listen("/siege_shop")
@smart_msg_listen("siege.shop")
@irc_msg_listen("siege.shop")
@description(
    "/siege_shop",
    "Time to go shopping!!! This is what you have working toward the whole time! (Or maybe not...)",
)
@utils.get_group
@utils.filter_allowed
@utils.has_group("siege")
def get_shop(ctx: Context, public: bool):
    if isinstance(ctx, InteractionContext):
        public = False
    shop_item = get_shop_item()
    message_lines = [f"*Items*", f"*Cosmetic*"]
    for item in sorted(shop_item.cosmetics, key=lambda x: x.id):
        message_lines.append(
            f"> *{item.name}* (`{item.id}`) - {item.description} for {item.cost} coins with type {item.type.capitalize()}"
        )
    message_lines.append(f"*Physical*")
    for item in sorted(shop_item.physical_items, key=lambda x: x.id):
        message_lines.append(
            f"> *{item.name}* (`{item.id}`) - {item.description} for {item.cost} coins, digital: {item.digital}"
        )
    if public:
        ctx.public_send(True, text="\n".join(message_lines))
    else:
        ctx.private_send(False, text="\n".join(message_lines))


@slash_listen("/user_details")
@smart_msg_listen("siege.user_details ")
@irc_msg_listen("siege.user_details ")
@description("/user_details <user_id>?", "Staring...")
@utils.get_group
@utils.filter_allowed
@utils.has_group("siege")
def get_proj_details(ctx: Context, public: bool):
    if isinstance(ctx, InteractionContext):
        public = False

    slack_user_id = ctx.author_id
    left_over = ctx.value
    if left_over:
        if re.match(r"<@(U\w+)(\|[0-9a-zA-Z\-_\.]+)?>", left_over):
            slack_user_id = (
                left_over.strip().removeprefix("<@").removesuffix(">").split("|")[0]
            )  # https://stackoverflow.com/questions/29392407/how-to-get-a-slack-user-by-email-using-users-info-api/51469610#51469610
        else:
            slack_user_id = left_over
    message_lines: list[str] = []
    user_id: int | None = None
    try:
        user = get_user(slack_user_id)
        user_id = user.id
        core.push_user([user])
    except Exception:
        message_lines.append(
            "User can no longer be discovered from the API; may be hidden or deleted."
        )
    if user_id is None:
        user_id = core.get_user_id_from_slack(slack_user_id)
    if user_id is None:
        message_lines.append("Cannot find user id from slack id.")
        return ctx.private_send(text="\n".join(message_lines))

    user_hbs = list(reversed(core.retrieve_all_user_record(user_id)))
    if not user_hbs:
        return ctx.private_send(text="No heartbeat data found for this user.")

    user_first = user_hbs[0].measurement_time

    timeline: list[tuple[Arrow, str]] = []

    timeline.append(
        (
            user_first,
            f"*{_time_to_slack(user_first)}*: User first discovered\n"
            f"> Username: {user_hbs[0].username}\n"
            f"> Coins: {user_hbs[0].coin_count}\n"
            f"> Status: {user_hbs[0].user_status}",
        )
    )

    for prev, curr in zip(user_hbs, user_hbs[1:]):
        diff = prev.compare_to_new(curr)
        if not diff:
            continue
        line = f"*{_time_to_slack(curr.measurement_time)}*:"
        for key, (old, new) in diff.items():
            if key == "Username":
                line += f'\n> {key}: "{old}" -> "{new}"'
            else:
                line += f"\n> {key}: {old} -> {new}"
        timeline.append((curr.measurement_time, line))

    proj_hbs = list(reversed(core.retrieve_all_user_proj_record(user_id)))

    grouped: dict[int, list[core.ProjHeartbeatRecord]] = defaultdict(list)
    for hb in proj_hbs:
        proj_id = hb.proj_id
        if proj_id is None:
            continue
        grouped[proj_id].append(hb)

    now = Arrow.utcnow()
    DISAPPEAR_SECS = 15 * 60

    for proj_id, records in grouped.items():
        records.sort(key=lambda r: r.measurement_time.timestamp())
        first = records[0]
        last = records[-1]

        if first.measurement_time > user_first:
            timeline.append(
                (
                    first.measurement_time,
                    f"*{_time_to_slack(first.measurement_time)}*: Project `{proj_id}` first discovered"
                    + (f'\n> Project Name: "{first.title}"'),
                )
            )

        if (now.timestamp() - last.measurement_time.timestamp()) >= DISAPPEAR_SECS:
            timeline.append(
                (
                    last.measurement_time,
                    f"*{_time_to_slack(last.measurement_time)}*: Project `{proj_id}` have been removed"
                    + (f'\n> Project Name: "{last.title}"'),
                )
            )

    timeline.sort(key=lambda t: t[0].timestamp())

    output = "\n".join(evt for _, evt in timeline)
    if public:
        ctx.public_send(True, text=output)
    else:
        ctx.private_send(True, text=output)
    return None
