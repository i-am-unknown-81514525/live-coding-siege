import asyncio
from collections.abc import Awaitable, Callable
import os, logging, secrets, time
from threading import Lock
from datetime import datetime, timezone
from typing import Any, Concatenate

import arrow
from slack_sdk.web import WebClient
import re

import json
from base import Client, ExecutionContext, ExecutionContext
from config import get_config
from schema.message import MessageEvent
from schema.huddle import HuddleChange, HuddleState
from schema.interactive import BlockActionEvent
from slack.reg import (
    InteractionContext,
    huddle_listen,
    smart_action_listen,
    smart_msg_listen,
    MessageContext,
    Context,
)
from crypto.core import DeterRnd, Handler, _sha3, randint
import live.db as db
import blockkit
from blockkit import Message, Section, Button
from timer import Task
import utils
from ws_mgr import controller, signals
import jwt
from utils import get_group, require_allowed, require_authorised
from live.base import get_module
from live.utils import require_any_game_manager, require_game_thread, require_game_manager
from slack_sdk.socket_mode.client import BaseSocketModeClient
from base import description

def int_handler(bits: int) -> Handler[int]:
    """A handler for DeterRnd that returns an integer of a specified bit length."""
    return (bits, lambda x: x)


# AUTHORIZED_USERS = os.environ.get("AUTHORIZED_USERS", "").split(",")
# ALLOWLIST = os.environ.get("ALLOWLIST", "").split(",")
# SIEGE_MODE = os.environ.get("SIEGE_MODE", "1") == "1"
GLOBAL_LOC_RETRIVAL_LOCK = Lock()
GAME_LOCK: dict[int, Lock] = {}


def get_game_lock(game_id: int) -> Lock:
    with GLOBAL_LOC_RETRIVAL_LOCK:
        if game_id in GAME_LOCK:
            return GAME_LOCK[game_id]
        GAME_LOCK[game_id] = Lock()
        return GAME_LOCK[game_id]


def get_game_group[**P, T, C: Context](
    func: Callable[Concatenate[C, list[str], P], T],
) -> Callable[Concatenate[C, P], T]:
    # noinspection PyTypeChecker
    def inner(ctx: C, *args: P.args, **kwargs: P.kwargs) -> T:
        ret: list[str] = []
        if ctx.thread_ts:
            game_id = db.get_active_game_by_thread(ctx.channel_id, ctx.thread_ts)
            if game_id:
                instance = db.get_game_instance(game_id, ctx.client)
                ret = [instance.mode]
        return func(ctx, ret, *args, **kwargs)

    return inner


def filter_by_value[**P, T, C: Context](
    func: Callable[Concatenate[C, list[str], P], T],
) -> Callable[Concatenate[C, list[str], P], T]:
    # noinspection PyTypeChecker
    def inner(ctx: C, groups: list[str], *args: P.args, **kwargs: P.kwargs) -> T:
        ret: list[str] = []
        value: str = ctx.value
        if value.strip() in groups:
            ret = [value.strip()]
        return func(ctx, ret, *args, **kwargs)

    return inner


@smart_msg_listen("live.test1")
def test_interactive(ctx: MessageContext):
    try:
        user_info = ctx.client.client.web_client.users_profile_get(user=ctx.author_id).data
        logging.info(f"User profile: {json.dumps(user_info, indent=2)}")
    except:
        logging.info("Fail to get user profile", exc_info=True)
    message_payload = (
        blockkit.Message(text="This is a test message with a button.").add_block(
            blockkit.Section("test").accessory(
                blockkit.Button("Test Button").action_id("test_button")
            )
        )
    ).build()
    ctx.public_send(**message_payload)


def _technical_not_reveal(client_secret: str, server_secret: str) -> Message:
    return Message().add_block(
        Section(
            f"Technical data:\nClient secret: `{client_secret}`\nServer secret hash: `{_sha3(server_secret)}`"
        )
    )


def _technical_not_reveal_from_msg(
    message: Message, client_secret: str, server_secret: str
) -> Message:
    return message.add_block(
        Section(
            f"Technical data:\nClient secret: `{client_secret}`\nServer secret hash: `{_sha3(server_secret)}`"
        )
    )


@smart_msg_listen("live.init")
@description(
    "live.init",
    "Start the game (Stonemason only) or revive an existing game if it doesn't cause database state conflict (Game manager only)",
)
@get_group
@require_allowed
@utils.duplicate_second
@filter_by_value
@utils.filter_authorised
@utils.have_any_group()
def init_game(ctx: Context, is_authorized: bool, modes: list[str]) -> Any:
    picked_mode = ctx.value
    if picked_mode not in modes:
        text = f'"{picked_mode}" cannot be selected'
        if picked_mode:
            text += ", You can only select one of "
            text += ", ".join(f'"{mode}"' for mode in picked_mode)
        return ctx.private_send(text=text)
    user_id = ctx.author_id
    channel_id = ctx.channel_id
    thread_ts = ctx.thread_ts or ctx.message_ts

    if not thread_ts:
        ctx.public_send(text="Unable to locate the thread")
        return None

    existing_game_id = db.get_any_game_by_thread(channel_id, thread_ts)
    if existing_game_id:
        game_is_active = db.get_active_game_by_thread(channel_id, thread_ts) is not None
        if game_is_active:
            ctx.public_send(text="A magic show is already active in this thread.")
            return None

        previous_managers = db.list_game_manager(existing_game_id)
        if user_id in previous_managers:
            can_restart = False

            if is_authorized:
                if not db.get_game_mgr_active_game(user_id):
                    can_restart = True
            else:
                any_manager_busy = any(
                    db.get_game_mgr_active_game(mgr_id) for mgr_id in previous_managers
                )
                if not any_manager_busy:
                    can_restart = True

            if can_restart:
                ctx.private_send(
                    **Message(
                        "A previous show in this thread has ended. But currently you can restart the game."
                    )
                    .add_block(
                        Section("A previous show in this thread has ended.").accessory(
                            Button("Restart Show")
                            .action_id("restart_game")
                            .value(str(existing_game_id))
                            .style("primary")
                        )
                    )
                    .build(),
                )
                ctx.public_send(
                    text="It is currently valid to restart the existing game, awaiting manager action.",
                )
                return None
            else:
                ctx.public_send(
                    text="A magic show has already concluded in this thread and the condition required to restart the show is not sastified.",
                )
                return None

        ctx.public_send(
            text="A magic show has already concluded in this thread.",
        )
        return None

    user_huddles = db.get_user_huddles(user_id)
    if not user_huddles:
        ctx.private_send(
            text="You don't seem to be in an active show.",
        )
        return None
    huddle_id = user_huddles[0]  # Assume the user is in one huddle at a time

    if db.get_active_game_in_huddle(huddle_id):
        ctx.private_send(
            text="A magic show is already active in this huddle.",
        )
        return None

    client_secret = secrets.token_hex(16)
    server_secret = secrets.token_hex(16)
    server_secret_hash = _sha3(server_secret)
    game_id = db.start_game(
        huddle_id,
        channel_id,
        thread_ts,
        datetime.now(timezone.utc),
        client_secret,
        server_secret,
        picked_mode,
    )
    db.add_game_manager(game_id, user_id)
    instance = db.get_game_instance(game_id, ctx.client)
    module = get_module(instance)
    users: list[str] = db.get_huddle_participants(game_id)
    module.on_create()
    tickets = module.get_tickets(users)
    for user, ticket in tickets.items():
        db.add_game_participant(game_id, user, ticket)

    ctx.public_send(
        text=f"✨ A new show has started! (ID: {game_id})",
        **_technical_not_reveal_from_msg(
            Message().add_block(Section(f"✨ A new show has started! (ID: {game_id})")),
            client_secret,
            server_secret,
        ).build(),
    )
    return None


@smart_action_listen("restart_game")
@get_game_group
@utils.filter_authorised
@utils.have_any_group()
def handle_restart_game(ctx: InteractionContext, have_authorised: bool):
    """Handles a manager restarting a completed game."""
    user_id = ctx.author_id
    channel_id = ctx.channel_id
    thread_ts = ctx.thread_ts

    if ctx.value is None:
        logging.warning("Missing game_id in restart_game button")
        return

    try:
        game_id_to_restart = int(ctx.value)
    except (ValueError, TypeError):
        ctx.private_send(
            text="Invalid game ID for restart.",
        )
        return

    is_authorized = have_authorised
    if is_authorized:
        if db.get_game_mgr_active_game(user_id):
            ctx.private_send(
                text="You are already managing another active game.",
            )
            return
    else:
        previous_managers = db.list_game_manager(game_id_to_restart)
        if user_id not in previous_managers or any(
            db.get_game_mgr_active_game(mgr_id) for mgr_id in previous_managers
        ):
            ctx.private_send(
                text="Cannot restart: One of the previous managers is busy with another show.",
            )
            return

    with db.get_db_connection() as conn:
        if is_authorized:
            previous_managers = db.list_game_manager(game_id_to_restart)
            for mgr_id in previous_managers:
                if db.get_game_mgr_active_game(mgr_id):
                    conn.execute(
                        "DELETE FROM game_manager WHERE game_id = ? AND user_id = ?",
                        (game_id_to_restart, mgr_id),
                    )

            conn.execute(
                "INSERT OR IGNORE INTO game_manager (game_id, user_id) VALUES (?, ?)",
                (game_id_to_restart, user_id),
            )

        conn.execute(
            "UPDATE game SET status = 'ACTIVE', end_time = NULL WHERE id = ?",
            (game_id_to_restart,),
        )

        client_secret = secrets.token_hex(16)
        server_secret = secrets.token_hex(16)
        db._add_transaction(
            conn, game_id_to_restart, "GAME_RESTART", client_secret, server_secret
        )
        conn.commit()

    instance = db.get_game_instance(game_id_to_restart, ctx.client)
    module = get_module(instance)
    users: list[str] = db.get_huddle_participants(game_id_to_restart)
    module.on_restart()
    tickets = module.get_tickets(users)
    for user, ticket in tickets.items():
        db.add_game_participant(game_id_to_restart, user, ticket)
    ctx.public_send(
        text=f"✨ The show (ID: {game_id_to_restart}) has been restarted by <@{user_id}>!",
        **_technical_not_reveal(client_secret, server_secret).build(),
    )
    ctx.public_send(text="Show restarted.", blocks=[])


def _handle_manager_action_timeout(
    game_id: int, user_id: str, channel_id: str, thread_ts: str, client: WebClient
):
    pending_user = db.get_pending_turn_user(game_id)
    if pending_user == user_id:
        print(f"Manager action timeout for user {user_id} in game {game_id}.")
        message_payload = (
            Message(
                text=f"⏰ <@{user_id}>'s performance was not started in time."
            ).add_block(
                Section(
                    f"⏰ <@{user_id}>'s performance setup time has expired. A manager must confirm to skip their performance."
                ).accessory(
                    Button("Confirm Skip")
                    .action_id("confirm_skip")
                    .value(user_id)
                    .style("danger")
                )
            )
        ).build()
        db.set_turn_timeout_notified(game_id, user_id)
        client.chat_postMessage(
            channel=channel_id, thread_ts=thread_ts, **message_payload
        )




def _handle_user_turn_timeout(
    game_id: int, user_id: str, channel_id: str, thread_ts: str, client: WebClient
):
    turn_details = db.get_turn_by_status(game_id, ["IN_PROGRESS", "ACCEPTED"])
    logging.info(turn_details)
    if (
        not turn_details
        or turn_details["user_id"] != user_id
        or turn_details["timeout_notified"]
    ):
        return

    db.set_turn_timeout_notified(game_id, user_id)
    logging.info(
        f"⌛️ User turn for {user_id} in game {game_id} has expired. Sending manager notification."
    )
    message_payload = (
        Message(text=f"⌛️ Time's up for <@{user_id}>!")
        .add_block(
            Section(
                f"⌛️ Time's up for <@{user_id}>! A manager needs to confirm the outcome."
            )
        )
        .add_block(
            blockkit.Actions(
                [
                    Button("Mark Completed")
                    .action_id("manager_mark_completed")
                    .value(user_id)
                    .style("primary"),
                    Button("Mark Failed")
                    .action_id("manager_mark_failed")
                    .value(user_id)
                    .style("danger")
                    .confirm(
                        blockkit.Confirm(
                            title="Are you sure you want to fail this performance",
                            text="This would make the performer not gain any coin",
                            confirm="Yes, fail this",
                            deny="No",
                        )
                    ),
                ]
            )
        )
    ).build()
    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, **message_payload)


@smart_msg_listen("live.huddle_rst")
@description(
    "live.huddle_rst",
    "Remove bot knowledge of you being in any huddle (If you are currently in a game huddle, it will believe you are not)",
)
def huddle_rst(ctx: MessageContext):
    user_id = ctx.author_id
    huddles = db.get_user_huddles(user_id)
    if not huddles:
        ctx.private_send(text="You are not in any huddle currently.")
        return
    for huddle in set(huddles):
        db.remove_huddle_participant(user_id, huddle)
    ctx.private_send(
        text=f"Your {len(set(huddles))} huddle join state have been reset."
    )


@smart_msg_listen("live.reloc")
@description(
    "live.reloc", "Relocate the game into different thread, channel and huddle"
)
@get_group
@require_allowed
@utils.consume_second
@require_any_game_manager
def reloc(ctx: MessageContext, game_id: int):
    thread_ts = ctx.thread_ts
    channel_id = ctx.channel_id
    if not thread_ts:
        ctx.private_send(text="Cannot locate the thread.")
        return
    if db.get_any_game_by_thread(channel_id, thread_ts):
        ctx.private_send(
            text="Another game is already active or have existed in this thread."
        )
        return
    with get_game_lock(game_id):
        huddles = db.get_user_huddles(ctx.author_id)
        if len(huddles) == 0:
            ctx.private_send(
                text="You are not in any huddle currently. Therefore the game cannot be relocated."
            )
            return
        if len(set(huddles)) > 1:
            ctx.private_send(
                text=f"Potential ambigious relocation: {', '.join(f'"{huddle}"' for huddle in set(huddles))}. Only join with a single huddle, or leave the huddle, run `live.huddle_rst` and rejoin."
            )
            return
        huddle_id = huddles[0]
        db.edit_game(game_id, huddle_id, channel_id, thread_ts)
    ctx.public_send(
        text=f"Game relocated to this thread and huddle `{huddle_id}` successfully. (Location: https://hackclub.slack.com/archives/{channel_id}/p{thread_ts.replace('.', '')})"
    )


@smart_msg_listen("live.debug_turn")
@description(
    "live.debug_turn",
    "Debug turn status when necessary (Authorized user only, same as #siege-announcement channel manager currently)",
)
@get_game_group
@require_authorised
@utils.consume_second
@require_game_manager
def debug(ctx: MessageContext, game_id: int):
    user_id = ctx.value

    if not re.match(r"<@(U\w+)>", user_id):
        ctx.private_send(text="Invalid user ID.")
        return
    user_id = user_id.removeprefix("<@").removesuffix(">")

    if not db.has_user(user_id):
        ctx.private_send(
            text="The user have not been indexed... Ask them to join the huddle to do so!"
        )
        return

    message_payload = (
        Message(text=f"DEBUGGER").add_block(
            blockkit.Actions(
                [
                    Button("Mark Completed")
                    .action_id("manager_mark_completed")
                    .value(user_id)
                    .style("primary"),
                    Button("Mark Failed")
                    .action_id("manager_mark_failed")
                    .value(user_id)
                    .style("danger")
                    .confirm(
                        blockkit.Confirm(
                            title="Are you sure you want to fail this turn?",
                            text="The performer wouldn't get any coin for the turn",
                            confirm="Yes, fail the turn",
                            deny="No",
                        )
                    ),
                    Button("Skip Turn")
                    .action_id("skip_turn")
                    .confirm(
                        blockkit.Confirm(
                            title="Are you sure you want to skip this turn?",
                            text="This will count as one of your two consecutive skips.",
                            confirm="Yes, skip",
                            deny="No",
                        )
                    ),
                    Button("Start Turn").action_id("start_turn"),
                ]
            )
        )
    ).build()

    ctx.public_send(**message_payload)


def _build_active_turn_message(game_id: int, is_public: bool = False) -> Message | None:
    active_turn = db.get_active_turn_details(game_id)
    if not active_turn:
        return None

    user_id = active_turn["user_id"]
    status = active_turn["status"]

    user_display_name = f"<@{user_id}>"
    if is_public:
        user_names_map = db.get_user_names([user_id])
        user_display_name = user_names_map.get(user_id, user_id)

    status_text = f"Status: `{status}`"
    time_text = ""

    finish_button = False
    in_progress_button = False

    if status in ("IN_PROGRESS", "ACCEPTED") and active_turn["start_time"]:
        start_time = datetime.fromisoformat(active_turn["start_time"])
        duration = active_turn["assigned_duration_seconds"]
        end_time = start_time.timestamp() + duration
        remaining_seconds = max(
            0, int(end_time - datetime.now(timezone.utc).timestamp())
        )

        if remaining_seconds > 0:
            time_text = (
                f" | Remaining: `{remaining_seconds // 60}m {remaining_seconds % 60}s`"
            )
            in_progress_button = True
        else:
            time_text = " | Time's up!"
            finish_button = True

    message = Message(text=f"A turn for {user_display_name} is already active.")
    message.add_block(
        Section(
            f"A turn for *{user_display_name}* is already active.\n{status_text}{time_text}"
        )
    )

    if status == "PENDING":
        message.add_block(
            blockkit.Actions(
                [
                    Button("Start Turn").action_id("start_turn"),
                    Button("Skip Turn")
                    .action_id("skip_turn")
                    .confirm(
                        blockkit.Confirm(
                            title="Are you sure you want to skip this turn?",
                            text="This will count as one of your two consecutive skips.",
                            confirm="Yes, skip",
                            deny="No",
                        )
                    ),
                ]
            )
        )
    if in_progress_button:
        message.add_block(
            blockkit.Actions(
                [
                    Button("Mark Skipped")
                    .action_id("skip_turn")
                    .confirm(
                        blockkit.Confirm(
                            title="Are you sure you want to skip this performance?",
                            text="This will make the magician don't like you.",
                            confirm="Yes, skip",
                            deny="No",
                        ),
                    ),
                    Button("Safe skip (Mark Failed)")
                    .action_id("manager_mark_failed")
                    .value(user_id)
                    .style("danger")
                    .confirm(
                        blockkit.Confirm(
                            title="Are you sure you want to fail this performance",
                            text="This will not be mark as skipped (And not subject to consecutive skip limit)",
                            confirm="Yes, fail",
                            deny="No",
                        )
                    ),
                    Button("Force mark as completed")
                    .action_id("force_manager_mark_completed")
                    .value(user_id)
                    .style("primary")
                    .confirm(
                        blockkit.Confirm(
                            title="Are you sure you want to mark as completed?",
                            text="This is only to be used when you start the turn late/other error occur.",
                            confirm="Yes, mark as completed anyway",
                            deny="No",
                        )
                    ),
                ]
            )
        )

    if finish_button:
        message.add_block(
            blockkit.Actions(
                [
                    Button("Mark Completed")
                    .action_id("manager_mark_completed")
                    .value(user_id)
                    .style("primary"),
                    Button("Mark Failed")
                    .action_id("manager_mark_failed")
                    .value(user_id)
                    .style("danger")
                    .confirm(
                        blockkit.Confirm(
                            title="Are you sure you want to mark as failed?",
                            text="This will make the performer not get any coin",
                            confirm="Yes, mark as fail",
                            deny="No",
                        )
                    ),
                ]
            )
        )

    return message

@smart_msg_listen("live.optin")
@description("live.optin", "Optin, which may or may not work:) You _never_ knows")
@require_game_thread
def optin(ctx: MessageContext, game_id: int):
    instance = db.get_game_instance(game_id, ctx.client)
    module = get_module(instance)
    if not module.CAN_OPTIN:
        return ctx.private_send(text="Optin is not supported in this game mode.")
    db.update_participant_opt_out(game_id, ctx.author_id, is_opted_out=False)
    ctx.private_send(
        text="You have opted in to the current show. You may be selected for performances."
    )

@smart_msg_listen("live.optout")
@description("live.optout", "Optout from the game (Why... :heavysob:)")
@require_game_thread
def optout(ctx: MessageContext, game_id: int):
    ctx.private_send(
        **Message()
        .add_block(
            Section("Click below to optout").accessory(
                Button("Optout")
                .action_id("confirm_optout")
                .confirm(
                    blockkit.Confirm(
                        title="Are you sure you want to opt out?",
                        text="You will not be able to participate further in this show. Optin might not be always possible.",
                        confirm="Yes, opt out",
                        deny="No",
                    )
                )
            )
        )
        .build()
    )


@smart_action_listen("confirm_optout")
def confirm_optout(ctx: InteractionContext):
    user_id = ctx.author_id
    channel_id = ctx.channel_id
    thread_ts = ctx.thread_ts

    if thread_ts is None:
        logging.warning("Cannot find thread.")
        return

    if channel_id is None:
        logging.warning("Cannot find channel")
        return

    game_id = db.get_active_game_by_thread(channel_id, thread_ts)
    if game_id is None:
        ctx.private_send(
            text="Could not find an active show in this thread.",
        )
        return

    db.update_participant_opt_out(game_id, user_id, is_opted_out=True)

    ctx.private_send(
        text="You have opted out of the current show. You will no longer be selected for performances.",
    )
    if ctx.message_ts:
        try:
            ctx.client.client.web_client.chat_update(
                channel=channel_id,
                ts=ctx.message_ts,
                text="You have opted out.",
                blocks=[],
            )
        except:
            logging.warning("Fail to send message update", exc_info=True)
            ctx.private_send(text="You have opted out.")


@smart_msg_listen("live.reject")
@description("live.reject", "Reject a turn")
@require_game_manager
def reject_turn(ctx: MessageContext, game_id: int):
    turn_row = db.get_active_turn_details(game_id)

    if turn_row:
        db.update_turn_status(game_id, turn_row["user_id"], "FAILED")
        ctx.public_send(text=f"Rejected <@{turn_row['user_id']}>'s performance")
    else:
        ctx.public_send(text="There are no active turn rn!")


@smart_msg_listen("live.add_mgr")
@description("live.add_mgr", "Add a game manager (Current game manager only)")
@get_game_group
@utils.flatten_get_first_require_value
@require_game_manager
def add_manager(ctx: Context, game_id: int, group: str):
    user_id = ctx.value

    if ctx.value.strip() == "all":
        allowed = utils.get_all_allowed(group)
        added = []
        for user in allowed:
            if not db.has_game_manager(user):
                try:
                    db.upsert_user(user, "UNKNOWN", None, ctx.client)
                    db.add_game_manager(game_id, user)
                    added.append(user)
                except Exception as e:
                    logging.warning(f"Failed to add game manager {user} to game {game_id}:", exc_info=True)
        return ctx.public_send(
            text=f"Added new {len(added)} game managers: {', '.join(f'`{uid}`' for uid in added)}",
        )

    if not re.match(r"<@(U\w+)>", user_id):
        ctx.private_send(
            text="Invalid user ID.",
        )
        return
    user_id = user_id.removeprefix("<@").removesuffix(">")

    if not db.has_user(user_id):
        ctx.private_send(
            text="The user have not been indexed... Ask them to join the huddle to do so!",
        )
        return

    if not db.has_game_manager(user_id):
        db.add_game_manager(game_id, user_id)
        ctx.public_send(
            text=f"<@{user_id}> is now the new show manager!",
        )
    else:
        ctx.public_send(
            text=f"<@{user_id}> is already a manager in some active game show!",
        )
    return


@smart_msg_listen(
    "live.force_leave"
)  # Deregister as game manager in any active game participated. Would also end the huddle if it is the last game manager
@require_game_manager
def force_leave(ctx: MessageContext, game_id: int):
    user_id = ctx.author_id

    db.remove_game_manager(game_id, user_id)

    ctx.public_send(text="You are removed from the game manager in the active game")

    if not db.list_game_manager(game_id):
        db.update_turn_status(game_id, user_id, "COMPLETED")
        ctx.private_send(
            text="Additional from removing from game manager, the event is also ended",
        )


@smart_msg_listen("live.leave")
@require_game_manager
def leave(ctx: MessageContext, game_id: int):
    user_id = ctx.author_id

    if db.list_game_manager(game_id) == [user_id]:
        return ctx.private_send(
            text="You are the only manager left, therefore you cannot leave without ending the event. If you still want to do so, use `live.force_leave`"
        )

    db.remove_game_manager(game_id, user_id)

    return ctx.public_send(
        text="You are removed from the game manager in the active game",
    )


@smart_msg_listen("live.takeover")
@get_game_group
@require_authorised
@utils.consume_second
@require_game_thread
def takeover(ctx: MessageContext, game_id: int):
    user_id = ctx.author_id
    db.add_game_manager(game_id, user_id)

    return ctx.public_send(
        text=f"You have been added as a game manager in game {game_id}"
    )


@smart_msg_listen("live.rm_mgr")
@description(
    "live.rm_mgr",
    "Remove a game manager from the game ((Authorized user only, same as #siege-announcement channel manager currently))",
)
@get_game_group
@require_authorised
@utils.consume_second
@require_game_thread
def remove_manager(ctx: MessageContext, game_id: int):
    user_id = ctx.value

    if not re.match(r"<@(U\w+)>", user_id):
        ctx.private_send(text="Invalid user ID.")
        return
    user_id = user_id.removeprefix("<@").removesuffix(">")

    if not db.has_user(user_id):
        ctx.private_send(
            text="The user have not been indexed... (Probably currently isn't a game manager)!"
        )
        return

    if not db.has_game_manager(user_id):
        ctx.public_send(text="<@" + user_id + "> is not a manager anyway :)")
    else:
        db.remove_game_manager(game_id, user_id)
        ctx.public_send(text="<@" + user_id + "> is now no longer a show manager!")

    return


@smart_msg_listen("live.members")  # Show the user in the huddle, not just eligiable
@description("live.members", "List all the member in the huddle")
@require_game_thread
def show_members(ctx: MessageContext, game_id: int):
    user_ids = db.get_huddle_participants(game_id)
    user_names_map = db.get_user_names(user_ids)
    user_name_list = [user_names_map.get(uid, uid) for uid in user_ids]

    message = f"All member in the huddle: \n{'\n'.join(map(lambda x: f'- {x}', user_name_list))}\nIf you are in the huddle but not on this list, please re-join so the bot can register it. \nIf it still don't work, ping i-am-unknown-81514525 to investigate"

    if db.is_game_manager(game_id, ctx.event.message.user):
        ctx.public_send(True, text=message)
    else:
        ctx.private_send(text=message)


@smart_msg_listen("live.elligible")
@smart_msg_listen("live.eligiable")
@smart_msg_listen("live.eligible")
@description("live.eligible", "List all the member that elligible for the next round")
@require_game_thread
def show_eligiable(ctx: MessageContext, game_id: int):
    user_ids = db.get_eligible_participants(game_id)
    user_names_map = db.get_user_names(user_ids)
    user_name_list = [user_names_map.get(uid, uid) for uid in user_ids]

    message = f"All eligiable participants for this round: \n{'\n'.join(map(lambda x: f'- {x}', user_name_list))}\nIf you are in `live.members` and not here, you might have\n- You participate the last turn(including skip/failed)\n- You have consecutive skipped twice"

    if db.is_game_manager(game_id, ctx.event.message.user):
        ctx.public_send(True, text=message)
    else:
        ctx.private_send(text=message)


@smart_msg_listen("live.turn")
@description("live.turn", "View turn information")
@require_game_thread
def show_game_info(ctx: Context, game_id: int):
    message = _build_active_turn_message(game_id, is_public=False)
    if message:
        ctx.private_send(**message.build())
    else:
        ctx.private_send(text="No performance is currently active.")


@smart_msg_listen("live.ticket ")
@smart_msg_listen("live.tickets")
@description("live.tickets", "View your ticket count for the game")
@require_game_thread
def get_ticket_count(ctx: MessageContext, game_id: int):
    if ctx.value:
        return

    user = ctx.author_id
    instance = db.get_game_instance(game_id, ctx.client)
    users: list[str] = db.get_huddle_participants(game_id)
    tickets = get_module(instance).get_tickets(users)
    for user, ticket in tickets.items():
        db.add_game_participant(game_id, user, ticket)

    ticket_count = tickets.get(user, "N/A")

    push_ticket_update_ws(game_id)

    ctx.private_send(text=f"You have {ticket_count} tickets.")


# @smart_msg_listen("live.reset")
# @description("live.reset", "Reset your siege project record in the database for the game")
# @require_game_thread
# def reset_proj(ctx: MessageContext, game_id: int):
#     if not SIEGE_MODE:
#         return ctx.private_send(text="`SIEGE_MODE` is off, therefore ticket is insignificant here")
#     db.reset_game_participant(game_id, ctx.author_id)
#     ctx.private_send(text="Attempted to reset your project")


def push_ticket_update_ws(game_id: int):
    coro = controller.connection_manager.send(f"ticket/{game_id}", b"UPDATE")
    asyncio.run_coroutine_threadsafe(_dispatch_async(coro), signals.ROOT.loop)


@smart_msg_listen("live.ticket_list")
@description("live.ticket_list", "List everyone tickets")
@require_game_thread
def get_ticket_list(ctx: MessageContext, game_id: int):
    ticket_dt: dict[str, tuple[str, int | None]] = {}
    huddle_participant = db.get_huddle_participants(game_id)
    usernames = db.get_user_names(huddle_participant)
    instance = db.get_game_instance(game_id, ctx.client)
    users: list[str] = db.get_huddle_participants(game_id)
    tickets = get_module(instance).get_tickets(users)
    for user, ticket in tickets.items():
        db.add_game_participant(game_id, user, ticket)
    for user in huddle_participant:
        username = usernames.get(user, f"`{user}`")
        if username == "UNKNOWN":
            username = f"`{user}`"
        ticket_dt[user] = username, tickets.get(user)
    push_ticket_update_ws(game_id)

    structured = "Ticket List\n" + "\n".join(
        f"{username} {ticket_count or 'N/A'}"
        for username, ticket_count in ticket_dt.values()
    )

    if db.is_game_manager(game_id, ctx.event.message.user):
        ctx.public_send(True, text=structured)
    else:
        ctx.private_send(True, text=structured)


@smart_msg_listen("live.pick")
@description(
    "live.pick",
    "Pick a user to start a turn, or switch state for the corresponding state of the game (Game manager only)",
)
@require_game_manager
def pick_user(ctx: MessageContext, game_id: int):
    channel_id = ctx.channel_id

    with get_game_lock(game_id):
        active_turn_message = _build_active_turn_message(game_id, is_public=False)
        if active_turn_message:
            ctx.public_send(**active_turn_message.build())
            return

        eligible_users = db.get_eligible_participants(game_id)
        if not eligible_users:
            ctx.public_send(
                text="Magician don't like any of you so he don't want to start a performance.",
            )
            return

        eligible_users = list(sorted(eligible_users))

        game_secrets = db.get_latest_secrets(game_id)
        if not game_secrets:
            ctx.public_send(
                text="Cannot pick user: Game secrets could not be retrieved.",
            )
            return
        client_secret, server_secret = game_secrets

        seed = f"{client_secret}{server_secret}"

        instance = db.get_game_instance(game_id, ctx.client)
        module = get_module(instance)

        t = randint(module.BOUND[0], module.BOUND[1])

        users: list[str] = db.get_huddle_participants(game_id)
        user_tickets = module.get_tickets(users)
        for user, ticket in user_tickets.items():
            db.add_game_participant(game_id, user, ticket)

        push_ticket_update_ws(game_id)

        tickets = []
        for user in eligible_users:
            tickets += [user] * user_tickets.get(user, 0)

        selected_index, duration_seconds = (
            DeterRnd(randint(0, len(tickets) - 1), t).with_seed(seed).retrieve()
        )
        target_user_id = tickets[selected_index]

        duration_hours = (duration_seconds) // 3600
        duration_minutes = (duration_seconds // 60) % 60
        remaining_seconds = duration_seconds % 60

        duration_text_parts = []
        if duration_hours > 0:
            duration_text_parts.append(
                f"{duration_hours} hour{'s' if duration_hours > 1 else ''}"
            )
        if duration_minutes > 0:
            duration_text_parts.append(
                f"{duration_minutes} minute{'s' if duration_minutes > 1 else ''}"
            )
        if remaining_seconds > 0:
            duration_text_parts.append(
                f"{remaining_seconds} second{'s' if remaining_seconds > 1 else ''}"
            )
        duration_text = " and ".join(duration_text_parts)

        db.add_user_selection_transaction(game_id, target_user_id, duration_seconds)

        user_names_map = db.get_user_names([target_user_id])
        user_name = user_names_map.get(target_user_id, target_user_id)

        coro = controller.connection_manager.send(
            f"turn/{game_id}",
            json.dumps(
                {
                    "type": "turn_update",
                    "status": "PENDING",
                    "user_id": target_user_id,
                    "user_name": user_name,
                }
            ).encode(),
        )
        asyncio.run_coroutine_threadsafe(_dispatch_async(coro), signals.ROOT.loop)

        timeout_seconds = 120
        if not ctx.thread_ts:
            logging.warning("Cannot find thread.")
        else:
            Task(
                arrow.now().shift(seconds=timeout_seconds),
                _handle_manager_action_timeout,game_id, target_user_id, channel_id, ctx.thread_ts, ctx.client.client.web_client
            ).set_log_on_error()
        new_server_secret = secrets.token_hex(16)
        db.update_server_secret(game_id, new_server_secret)

        message_payload = (
            Message(
                text=f"👉 <@{target_user_id}> has been selected for the next performance by the magician!"
            )
            .add_block(
                Section(
                    f"👉 <@{target_user_id}> has been selected for the next performance for *{duration_text}* by the magician!"
                )
            )
            .add_block(
                blockkit.Actions(
                    [
                        Button("Start Turn").action_id("start_turn"),
                        Button("Skip Turn")
                        .action_id("skip_turn")
                        .confirm(
                            blockkit.Confirm(
                                title="Are you sure you want to skip this performance?",
                                text="This will make the magician don't like you.",
                                confirm="Yes, skip",
                                deny="No",
                            ),
                        ),
                        Button("Safe skip (Mark Failed)")
                        .action_id("manager_mark_failed")
                        .value(target_user_id)
                        .style("danger")
                        .confirm(
                            blockkit.Confirm(
                                title="Are you sure you want to fail this performance?",
                                text="This wouldn't be mark as skipping",
                                confirm="Yes",
                                deny="No",
                            )
                        ),
                    ]
                )
            )
            .add_block(blockkit.Divider())
            .add_block(
                blockkit.Section(
                    "Technical Data: \n"
                    f"Client secret: `{client_secret}`\n"
                    f"Previous Server secret: `{_sha3(new_server_secret)}` \n"
                    f"New Server secret hash: `{_sha3(server_secret)}` \n"
                    f"Eligiable list: {', '.join(f'`{user_id}` ({user_tickets.get(user_id, 0)} tickets)' for user_id in eligible_users)}\n"
                    f"Selected ticket: `{selected_index}` (0-index)"
                )
            )
        ).build()

        ctx.public_send(**message_payload)


@smart_msg_listen("live.summary")
@description("live.summary", "View a summary of the game")
@require_game_thread
def show_game_summary(ctx: MessageContext, game_id: int):
    summary_stats = db.get_game_summary_stats(game_id)

    summary_message = Message(text="Here is the current show summary:")
    summary_message.add_block(Section("*Here is the current show summary:*"))

    if not summary_stats:
        summary_message.add_block(Section("No participants have had a turn yet."))
    else:
        summary_text = ""
        for stat in summary_stats:
            summary_text += f"• *{stat['name']}*: {stat['successful_rounds']} successful performance(s), {stat['consecutive_skips']} consecutive skip(s).\n"

        summary_message.add_block(Section(summary_text))

    summary_message.add_block(blockkit.Divider())
    summary_message.add_block(Section("The show is still ongoing! 🎉"))

    if db.is_game_manager(game_id, ctx.event.message.user):
        ctx.public_send(**summary_message.build())
    else:
        ctx.private_send(**summary_message.build())


@smart_msg_listen("live.export")
@description("live.export", "Export the game state for coin distribution")
@require_game_thread
def export_game_history(ctx: MessageContext, game_id: int):
    turns = db.get_all_turns_for_game(game_id)
    if not turns:
        return ctx.public_send(text="No turns have been recorded for this game yet.")

    history_text = f"*Turn History for Game {game_id}*\n"
    for i, turn in enumerate(turns):
        user_id = turn["user_id"]
        status = turn["status"] == "COMPLETED"
        duration_seconds = turn["assigned_duration_seconds"]
        duration_minutes = duration_seconds // 60
        remaining_seconds = duration_seconds % 60
        min_string = f"{duration_minutes}m" if duration_minutes > 0 else ""
        sec_string = f"{remaining_seconds}s" if remaining_seconds > 0 else ""
        if min_string and sec_string:
            min_string += " "

        history_text += f"{i}. `{user_id}` - Status: `{status}` - Assigned Time: `{min_string}{sec_string}` `({turn['status']})`\n"

    return ctx.public_send(text=history_text)


@smart_msg_listen("live.rnd")
@description("live.rnd", "Change the server secret")
@require_game_manager
def refresh_server_secret(ctx: Context, game_id: int):
    new_server_secret = secrets.token_hex(16)
    new_server_secret_hash = _sha3(new_server_secret)
    db.update_server_secret(game_id, new_server_secret)

    (client_secret, _) = db.get_latest_secrets(game_id) or ("N/A", "N/A")

    eligible_users = db.get_eligible_participants(game_id)
    if eligible_users:
        user_names_map = db.get_user_names(eligible_users)
        # Fallback to user_id if name not found, though this shouldn't happen in normal operation
        user_name_list = [user_names_map.get(uid, uid) for uid in eligible_users]
        eligible_section = Section(
            f"👥 *The participant the magician like:*\n{', '.join(user_name_list)}"
        )
    else:
        eligible_section = Section(
            "👥 *The participant the magician like:*\nLiterally no one he hate y'all (or maybe he like the one who just completed it and give him a break)"
        )

    message = (
        Message(
            text=f"🎲 New server secret has been generated. Hash: `{new_server_secret_hash}`"
        )
        .add_block(
            Section(
                f"🎲 New server secret has been generated.\n*Hash:* `{new_server_secret_hash}`"
            )
        )
        .add_block(eligible_section)
        .add_block(
            Section(
                f"Current client secret: `{client_secret}`. \n"
                "The sent messsage content and message ID would influence this value!"
            )
        )
    )

    ctx.public_send(**message.build())


@smart_msg_listen("live.end")
@description("live.end", "End the game")
@require_game_manager
def end_game(ctx: Context, game_id: int):
    db.update_game_status(game_id, "COMPLETED")

    summary_stats = db.get_game_summary_stats(game_id)

    summary_message = Message(text="The show has ended! Here is the summary:")
    summary_message.add_block(Section("*The show has ended! Here is the summary:*"))

    if not summary_stats:
        summary_message.add_block(Section("No participants had any recorded activity."))
    else:
        summary_text = ""
        for stat in summary_stats:
            summary_text += f"• *{stat['name']}*: {stat['successful_rounds']} successful performance(s) :), {stat['consecutive_skips']} consecutive skip(s) :(.\n"

        summary_message.add_block(Section(summary_text))

    summary_message.add_block(blockkit.Divider())
    summary_message.add_block(Section("Thanks for playing! 🎉"))

    module = get_module(db.get_game_instance(game_id, ctx.client))
    module.on_end()

    ctx.public_send(**summary_message.build())


@smart_action_listen("force_manager_mark_completed")
@require_game_manager
def handle_manager_force_mark_completed(ctx: InteractionContext, game_id: int):
    """Handles a manager marking a timed-out turn as COMPLETED."""
    manager_id = ctx.author_id
    channel_id = ctx.channel_id
    thread_ts = ctx.thread_ts
    user_id = ctx.value

    if not game_id or not user_id:
        ctx.private_send(
            text="Could not find an active show or user for this action.",
        )
        return

    if not db.is_game_manager(game_id, manager_id):
        ctx.private_send(
            text="You cannot overrule the magician.",
        )
        return

    user_names_map = db.get_user_names([user_id])
    user_name = user_names_map.get(user_id, user_id)
    coro = controller.connection_manager.send(
        f"turn/{game_id}",
        json.dumps(
            {
                "type": "turn_update",
                "status": "COMPLETED",
                "user_id": user_id,
                "user_name": user_name,
            }
        ).encode(),
    )
    asyncio.run_coroutine_threadsafe(_dispatch_async(coro), signals.ROOT.loop)

    db.update_turn_status(game_id, user_id, "COMPLETED")

    ctx.public_send(
        text=f"Turn for <@{user_id}> marked as *completed* by <@{manager_id}>.",
        blocks=Message()
        .add_block(
            Section(
                f"✅ Turn for <@{user_id}> marked as *COMPLETED* by <@{manager_id}> before the time limit forcibly."
            )
        )
        .build()["blocks"],
    )


@smart_action_listen("manager_mark_completed")
@require_game_manager
def handle_manager_mark_completed(ctx: InteractionContext, game_id: int):
    """Handles a manager marking a timed-out turn as COMPLETED."""
    manager_id = ctx.author_id
    channel_id = ctx.channel_id
    thread_ts = ctx.thread_ts
    message_ts = ctx.message_ts
    user_id = ctx.value

    if not game_id or not user_id:
        ctx.private_send(
            text="Could not find an active show or user for this action.",
        )
        return

    if not db.is_game_manager(game_id, manager_id):
        ctx.private_send(
            text="You cannot overrule the magician.",
        )
        return

    user_names_map = db.get_user_names([user_id])
    user_name = user_names_map.get(user_id, user_id)
    coro = controller.connection_manager.send(
        f"turn/{game_id}",
        json.dumps(
            {
                "type": "turn_update",
                "status": "COMPLETED",
                "user_id": user_id,
                "user_name": user_name,
            }
        ).encode(),
    )
    asyncio.run_coroutine_threadsafe(_dispatch_async(coro), signals.ROOT.loop)

    db.update_turn_status(game_id, user_id, "COMPLETED")
    message = Message(f"Turn for <@{user_id}> marked as *completed* by <@{manager_id}>.").add_block(
                Section(
                    f"✅ Turn for <@{user_id}> marked as *COcompletedMPLETED* by <@{manager_id}>." # Intention because It it funny
                )
            ).build()
    send_normal = False
    if not message_ts: 
        send_normal = True
    if message_ts:
        try:
            ctx.client.client.web_client.chat_update(
                channel=channel_id,
                ts=message_ts,
                **message
            )
        except:
            logging.warning("Fail to update message", exc_info=True)
            send_normal = True
    if send_normal:
        ctx.public_send(**message)



@smart_msg_listen("live.client_secret")
@description(
    "live.client_secret", "The current client secret (Just look at the screen)"
)
@require_game_thread
def show_client_secret(ctx: MessageContext, game_id: int):
    (client_secret, _) = db.get_latest_secrets(game_id) or ("N/A", "N/A")
    ctx.public_send(text=f"Current client secret: `{client_secret}`.")


@smart_action_listen("manager_mark_failed")
@require_game_manager
def handle_manager_mark_failed(ctx: InteractionContext, game_id: int):
    """Handles a manager marking a timed-out turn as FAILED."""
    manager_id = ctx.author_id
    channel_id = ctx.channel_id
    thread_ts = ctx.thread_ts
    message_ts = ctx.message_ts
    user_id = ctx.value

    if not game_id or not user_id:
        ctx.private_send(
            text="Could not find an active game or user for this action.",
        )
        return

    if not db.is_game_manager(game_id, manager_id):
        ctx.private_send(
            text="You cannot overrule the magician.",
        )
        return

    user_names_map = db.get_user_names([user_id])
    user_name = user_names_map.get(user_id, user_id)
    coro = controller.connection_manager.send(
        f"turn/{game_id}",
        json.dumps(
            {
                "type": "turn_update",
                "status": "FAILED",
                "user_id": user_id,
                "user_name": user_name,
            }
        ).encode(),
    )
    asyncio.run_coroutine_threadsafe(_dispatch_async(coro), signals.ROOT.loop)

    db.update_turn_status(game_id, user_id, "FAILED")

    message = Message(f"❌ Turn for <@{user_id}> marked as FAILED by <@{manager_id}>.").add_block(
                    Section(f"❌ Turn for <@{user_id}> marked as *FAILED* by <@{manager_id}>.")
                ).build()

    send_normal = False
    if not message_ts:
        send_normal = True
    else:
        try:
            ctx.client.client.web_client.chat_update(
                channel=channel_id,
                ts=message_ts,
                **message
            )
        except:
            logging.warning("Fail to send message update", exc_info=True)
            send_normal = True
    if send_normal:
        ctx.public_send(**message)
    


@smart_action_listen("test_button")
def handle_test_button(ctx: InteractionContext):
    """Handles the click of the 'test_button'."""
    user_name = ctx.author_id
    ctx.public_send(
        text=f"👋 Hello {user_name}, you clicked the button!",
    )


@smart_action_listen("start_turn")
@require_game_thread
def handle_start_turn(ctx: InteractionContext, game_id: int):
    """Handles a manager starting the current turn."""
    manager_id = ctx.author_id
    channel_id = ctx.channel_id
    thread_ts = ctx.thread_ts

    try:

        if not db.is_game_manager(game_id, manager_id):
            ctx.private_send(text="You cannot overrule the magician.")
            return

        pending_user_id = db.get_pending_turn_user(game_id)
        if not pending_user_id:
            ctx.public_send(text="There is no pending performance to start.")
            return
        turn_details = db.start_turn(game_id, pending_user_id)
        message_payload = (
            Message(
                text=f"<@{pending_user_id}>'s performance has officially started! Good luck!"
            )
        ).build()
        ctx.public_send(**message_payload)

        duration_seconds = turn_details["assigned_duration_seconds"]
        if not thread_ts:
            logging.warning("Missing thread ts when start turn task creation")
        else:
            Task(
                arrow.now().shift(seconds=duration_seconds),
                _handle_user_turn_timeout,
                game_id, pending_user_id, channel_id, thread_ts, ctx.client.client.web_client,
            ).set_log_on_error()
        user_names_map = db.get_user_names([pending_user_id])
        user_name = user_names_map.get(pending_user_id, pending_user_id)
        end_time = datetime.now(timezone.utc).timestamp() + duration_seconds
        coro = controller.connection_manager.send(
            f"turn/{game_id}",
            json.dumps(
                {
                    "type": "turn_update",
                    "status": "IN_PROGRESS",
                    "user_id": pending_user_id,
                    "user_name": user_name,
                    "endTime": end_time,
                }
            ).encode(),
        )
        asyncio.run_coroutine_threadsafe(_dispatch_async(coro), signals.ROOT.loop)
    except ValueError as e:
        logging.error(f"Error starting turn:", exc_info=True)
        ctx.public_send(text="Could not start turn.")


@smart_action_listen("accept_turn")
@require_game_manager
def handle_accept_turn(ctx: InteractionContext, game_id: int):
    """Handles the selected user accepting their turn."""
    clicker_id = ctx.author_id
    channel_id = ctx.channel_id
    message_ts = ctx.message_ts

    in_progress_user_id = db.get_in_progress_turn_user(game_id)
    if not in_progress_user_id:
        ctx.private_send(text="There is no turn currently in progress to accept.")
        return

    if clicker_id != in_progress_user_id:
        ctx.private_send(text="It's not your turn to accept.")
        return

    db.update_turn_status(game_id, clicker_id, "ACCEPTED")

    message = Message(f"<@{clicker_id}> has *started* the turn.").add_block(
            Section(
                f"<@{clicker_id}> has *started* their performance. The countdown is on!"
            )
        ).build()
    send_normal = False
    if not message_ts:
        send_normal = True
    else:
        try:
            ctx.client.client.web_client.chat_update(
                channel=channel_id,
                ts=message_ts,
                **message
            )
        except:
            send_normal = True
            logging.warning("Fail to send message update", exc_info=True)
    if send_normal:
        ctx.public_send(**message)


@smart_action_listen("confirm_skip")
@require_game_manager
def handle_confirm_skip(ctx: InteractionContext, game_id: int):
    """Handles a manager confirming to skip a user after a timeout."""
    manager_id = ctx.author_id
    channel_id = ctx.channel_id
    thread_ts = ctx.thread_ts
    user_to_skip = ctx.value
    message_ts = ctx.message_ts

    if not db.is_game_manager(game_id, manager_id):
        ctx.client.client.web_client.chat_postEphemeral(
            user=manager_id,
            channel=channel_id,
            text="You cannot overrule the magician.",
            thread_ts=thread_ts,
        )
        return

    user_names_map = db.get_user_names([str(user_to_skip)])
    user_name = user_names_map.get(str(user_to_skip), str(user_to_skip))
    coro = controller.connection_manager.send(
        f"turn/{game_id}",
        json.dumps(
            {
                "type": "turn_update",
                "status": "SKIPPED",
                "user_id": str(user_to_skip),
                "user_name": user_name,
            }
        ).encode(),
    )
    asyncio.run_coroutine_threadsafe(_dispatch_async(coro), signals.ROOT.loop)

    db.update_turn_status(game_id, str(user_to_skip), "SKIPPED")

    message = (Message(f"🏃 Turn for <@{user_to_skip}> has been skipped by <@{manager_id}>.")
        .add_block(
            Section(
                f"🏃 Turn for <@{user_to_skip}> has been skipped by <@{manager_id}>."
            )
        )
        .build())
    send_normal = False
    if not message_ts:
        send_normal = True
    else:
        try:
            ctx.client.client.web_client.chat_update(
                channel=channel_id,
                ts=message_ts,
                **message
            )
        except:
            send_normal = True
            logging.warning("Fail to send chat update", exc_info=True)
    if send_normal:
        ctx.public_send(**message)



@smart_action_listen("skip_turn")
@require_game_thread
def handle_skip_turn(ctx: InteractionContext, game_id: int):
    clicker_id = ctx.author_id
    channel_id = ctx.channel_id
    thread_ts = ctx.thread_ts

    if not game_id:
        ctx.private_send(
            text="Could not find an active game in this thread.",
        )
        return

    pending_user_id = db.get_pending_turn_user(game_id)
    if not pending_user_id:
        ctx.private_send(
            text="There is no pending performance to skip.",
        )
        return

    is_manager = db.is_game_manager(game_id, clicker_id)
    is_selected_user = clicker_id == pending_user_id

    if not is_manager and not is_selected_user:
        ctx.private_send(
            text="You cannot overrule the magician.",
        )
        return

    user_names_map = db.get_user_names([pending_user_id])
    user_name = user_names_map.get(pending_user_id, pending_user_id)
    coro = controller.connection_manager.send(
        f"turn/{game_id}",
        json.dumps(
            {
                "type": "turn_update",
                "status": "SKIPPED",
                "user_id": pending_user_id,
                "user_name": user_name,
            }
        ).encode(),
    )
    asyncio.run_coroutine_threadsafe(_dispatch_async(coro), signals.ROOT.loop)

    db.update_turn_status(game_id, pending_user_id, "SKIPPED")

    ctx.public_send(
        text=f"🏃 <@{pending_user_id}>'s turn has been skipped, now the magician like you less.",
    )


async def _dispatch_async(coro: Awaitable[Any]):
    try:
        await coro
    except Exception:
        logging.error("Exception in a dispatched task:", exc_info=True)


@smart_msg_listen("live.mgr_secret")
@description(
    "live.mgr_secret",
    "Show manager secret for authentication on https://livecode.relay7f98.us.to for web dashboard",
)
@require_game_manager
def show_mgr_secret(ctx: MessageContext, game_id: int):
    user_id = ctx.event.message.user

    jwt_token = jwt.encode(
        {
            "user_id": user_id,
            "exp": time.time() + 648000, # 43200
            "iss": "bot",
            "aud": "web",
            "sub": user_id,
            "iat": time.time(),
            "nbf": time.time() - 1,
        },
        algorithm="HS256",
        key=os.environ["JWT_SECRET"],
    )

    msg = Message("DO NOT SHARE THIS with anyone.").add_block(
        Section(
            "This token is is not revokable and can be used for the next 12 hours, for web dashboard access"
        ).accessory(
            Button("Show secret")
            .action_id("mgr_secret_display")
            .style("danger")
            .value(
                f"{ctx.event.channel};{jwt_token};{ctx.event.message.thread_ts or ''}"
            )
        )
    )

    ctx.private_send(**msg.build())


@smart_action_listen("mgr_secret_display")
@require_game_manager
def handle_mgr_secret_display(ctx: InteractionContext, _: int):
    data = ctx.event.actions[0].value
    if data is None:
        return
    channel_id, jwt_token, thread_ts = data.split(";")
    thread_ts = thread_ts or None
    ctx.private_send(
        text=f"The secret is:",
        **Message().add_block(Section(f"`{jwt_token}`")).build(),
    )


@smart_msg_listen("")
def listen_all(ctx: MessageContext):
    if (
        ctx.event.message.text.startswith("live.")
        or ctx.event.message.user == os.environ["SLACK_APP_ID"]
    ):
        return

    thread_ts = ctx.event.message.thread_ts
    if not thread_ts:
        return

    if game_id := db.get_active_game_by_thread(ctx.event.channel, thread_ts):
        db.upsert_user(ctx.event.message.user, "UNKNOWN", None, ctx.client)
        db.add_message_transaction(
            game_id,
            ctx.event.message.user,
            ctx.event.message.text,
            ctx.event.message.ts,
        )
        client_secret, _ = db.get_latest_secrets(game_id) or ("N/A", "N/A")
        coro = controller.connection_manager.send(
            f"client/{game_id}",
            json.dumps({"type": "secret", "value": client_secret}).encode(),
        )
        asyncio.run_coroutine_threadsafe(_dispatch_async(coro), signals.ROOT.loop)


@smart_msg_listen("huddle_thread", is_subtype=True)
def handle_huddle_start_message(ctx: MessageContext):
    room = ctx.event.message.room
    if not room or not room.channels:
        logging.info(
            f"⚠️ Received huddle_thread message without room or channel data. TS: {ctx.event.message.ts}"
        )
        return

    huddle_id = room.id
    channel_id = room.channels[0]
    start_time = room.date_start.datetime

    db.upsert_huddle(huddle_id, channel_id, start_time)
    print(f"✅ Huddle {huddle_id} in channel {channel_id} has been recorded.")


@huddle_listen(HuddleState.IN_HUDDLE)
def handle_huddle_join(event: HuddleChange, client: Client[BaseSocketModeClient]):
    user_id = event.user.id
    user_name = (
        event.user.profile.display_name or event.user.real_name or event.user.name
    )
    huddle_id = event.call_id
    db.upsert_huddle(huddle_id, "UNKNOWN", datetime.now(timezone.utc))
    db.upsert_user(user_id, user_name, event.user.profile.avatars.image_512, client)
    db.add_huddle_participant(huddle_id, user_id)
    print(f"ℹ️ User {user_name} ({user_id}) joined huddle {huddle_id}.")
    game_id = db.get_active_game_in_huddle(huddle_id)
    if game_id is not None:
        instance = db.get_game_instance(game_id, client)
        module = get_module(instance)
        is_in = False
        if user_id in db.get_huddle_participants(game_id):
            is_in = True
        db.add_game_participant(game_id, user_id, module.get_ticket(user_id))
        push_ticket_update_ws(game_id)
        if not is_in:
            module.on_join(user_id)


@huddle_listen(HuddleState.NOT_IN_HUDDLE)
def handle_huddle_leave(event: HuddleChange, client: Client[BaseSocketModeClient]):
    user_id = event.user.id
    user_name = event.user.real_name or event.user.name
    # When a user leaves, the event doesn't specify which huddle.
    # We find all huddles the user was in and remove them.
    # In this app's logic, a user is likely in only one huddle at a time.
    huddle_ids = db.get_user_huddles(user_id)
    for huddle_id in huddle_ids:
        db.remove_huddle_participant(huddle_id, user_id)
        print(f"🚪 User {user_name} ({user_id}) left huddle {huddle_id}.")
        game_id = db.get_active_game_in_huddle(huddle_id)
        if game_id is not None:
            instance = db.get_game_instance(game_id, client)
            module = get_module(instance)
            module.on_leave(user_id)


def load_active_timers(client: WebClient):
    logging.info("⏳ Loading active timers from the database...")
    pending_turns = db.get_all_turns_by_status(["PENDING"])
    manager_timeout_duration = 120  # 2 minutes

    for turn in pending_turns:
        try:
            selection_time = datetime.fromisoformat(turn["selection_time"]).replace(
                tzinfo=timezone.utc
            )
            elapsed_time = (datetime.now(timezone.utc) - selection_time).total_seconds()
            remaining_time = manager_timeout_duration - elapsed_time

            logging.info(
                f"  - Found pending turn for user {turn['user_id']} in game {turn['game_id']}. Remaining time: {remaining_time:.0f}s"
            )

            if remaining_time > 0:
                # Start a timer for the remaining duration
                Task(
                    arrow.now().shift(seconds=remaining_time),
                    _handle_manager_action_timeout,
                    turn["game_id"],
                    turn["user_id"],
                    turn["channel_id"],
                    turn["thread_ts"],
                    client,
                ).set_log_on_error()
            elif not turn["timeout_notified"]:
                # If time has expired and we haven't notified yet, handle the timeout.
                _handle_manager_action_timeout(
                    turn["game_id"],
                    turn["user_id"],
                    turn["channel_id"],
                    turn["thread_ts"],
                    client,
                )
        except Exception:
            logging.info("Fail to run handler", exc_info=True)

    logging.info(f"✅ Finished loading {len(pending_turns)} PENDING turn timers.")

    # Load IN_PROGRESS and ACCEPTED turns
    in_progress_turns = db.get_all_turns_by_status(["IN_PROGRESS", "ACCEPTED"])
    for turn in in_progress_turns:
        try:
            start_time = (
                datetime.fromisoformat(turn["start_time"]).replace(tzinfo=timezone.utc)
                if turn["start_time"]
                else None
            )
            if not start_time:
                continue

            duration = turn["assigned_duration_seconds"]
            elapsed_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            remaining_time = duration - elapsed_time

            logging.info(
                f"  - Found IN_PROGRESS turn for user {turn['user_id']} in game {turn['game_id']}. Remaining time: {remaining_time:.0f}s"
            )

            if remaining_time > 0:
                user_turn_timer = Task(
                    arrow.now().shift(seconds=remaining_time),
                    _handle_user_turn_timeout,
                    turn["game_id"],
                    turn["user_id"],
                    turn["channel_id"],
                    turn["thread_ts"],
                    client,
                ).set_log_on_error()
            else:
                _handle_user_turn_timeout(
                    turn["game_id"],
                    turn["user_id"],
                    turn["channel_id"],
                    turn["thread_ts"],
                    client,
                )
        except:
            logging.info("Fail to run handler", exc_info=True)

    logging.info(f"Finished loading {len(in_progress_turns)} IN_PROGRESS turn timers.")


def start(client: ExecutionContext):
    db.init_db()
    load_active_timers(client.slack_client.client.web_client)