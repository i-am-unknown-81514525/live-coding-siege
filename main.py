import os, logging, secrets, random
from threading import Event as tEvent, Timer
from datetime import datetime, timezone

from dotenv import load_dotenv
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.client import BaseSocketModeClient
from slack_sdk.web import WebClient
import re
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from schema.base import Event, Recv
from schema.message import MessageEvent
from schema.huddle import HuddleChange, HuddleState
from schema.interactive import BlockActionEvent
from reg import message_dispatch, msg_listen, action_dispatch, action_listen, huddle_dispatch, huddle_listen, smart_msg_listen, MessageContext
from crypto.core import DeterRnd, Handler, _sha3, randint
import db
import blockkit
from blockkit import Message, Section, Button

def int_handler(bits: int) -> Handler[int]:
    """A handler for DeterRnd that returns an integer of a specified bit length."""
    return (bits, lambda x: x)

AUTHORIZED_USERS = ["U092BGL0UUQ"]

@msg_listen("live.test1")
def test_interactive(event: MessageEvent, client: WebClient):
    message_payload = (
        blockkit.Message(text="This is a test message with a button.")
        .add_block(
            blockkit.Section("test")
            .accessory(
                blockkit.Button("Test Button")
                .action_id("test_button")
            )
        )
    ).build()
    client.chat_postMessage(
        channel=event.channel, **message_payload
    )

@msg_listen("live.init")
def init_game(event: MessageEvent, client: WebClient):
    user_id = event.message.user
    channel_id = event.channel
    thread_ts = event.message.thread_ts or event.message.ts

    if os.getenv("RIG"):
        AUTHORIZED_USERS.append(user_id)

    if user_id not in AUTHORIZED_USERS:
        client.chat_postMessage(channel=user_id, text="You cannot overrule the magician.")
        return

    if db.game_exists_in_thread(channel_id, thread_ts):
        client.chat_postMessage(channel=channel_id, text="A magic show already exist in this thread.", thread_ts=thread_ts)
        return

    user_huddles = db.get_user_huddles(user_id)
    if not user_huddles:
        client.chat_postEphemeral(user=user_id, channel=channel_id, text="You don't seem to be in an active show.", thread_ts=thread_ts)
        return
    huddle_id = user_huddles[0] # Assume the user is in one huddle at a time

    if db.get_active_game_in_huddle(huddle_id):
        client.chat_postEphemeral(user=user_id, channel=channel_id, text="A magic show is already active in this huddle.", thread_ts=thread_ts)
        return

    client_secret = secrets.token_hex(16)
    server_secret = secrets.token_hex(16)
    game_id = db.start_game(huddle_id, channel_id, thread_ts, datetime.now(timezone.utc), client_secret, server_secret)
    db.add_game_manager(game_id, user_id)

    client.chat_postMessage(channel=channel_id, text=f"✨ A new show has started! (ID: {game_id})", thread_ts=thread_ts)

def _handle_manager_action_timeout(game_id: int, user_id: str, channel_id: str, thread_ts: str, client: WebClient):
    pending_user = db.get_pending_turn_user(game_id)
    if pending_user == user_id:
        print(f"Manager action timeout for user {user_id} in game {game_id}.")
        message_payload = (
            Message(text=f"⏰ <@{user_id}>'s performance was not started in time.")
            .add_block(
                Section(f"⏰ <@{user_id}>'s performance setup time has expired. A manager must confirm to skip their performance.")
                .accessory(
                    Button("Confirm Skip")
                    .action_id("confirm_skip")
                    .value(user_id)
                    .style("danger")
                )
            )
        ).build()
        db.set_turn_timeout_notified(game_id, user_id)
        client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, **message_payload)

ACTIVE_TURN_TIMERS: dict[tuple[int, str], Timer] = {}

def _handle_user_turn_timeout(game_id: int, user_id: str, channel_id: str, thread_ts: str, client: WebClient):
    turn_details = db.get_turn_by_status(game_id, ['IN_PROGRESS', 'ACCEPTED'])
    if not turn_details or turn_details['user_id'] != user_id or turn_details['timeout_notified']:
        return

    ACTIVE_TURN_TIMERS.pop((game_id, user_id), None)
    
    print(f"⌛️ User turn for {user_id} in game {game_id} has expired. Sending manager notification.")
    message_payload = (
        Message(text=f"⌛️ Time's up for <@{user_id}>!")
        .add_block(
            Section(f"⌛️ Time's up for <@{user_id}>! A manager needs to confirm the outcome.")
        )
        .add_block(
            blockkit.Actions([
                Button("Mark Completed")
                .action_id("manager_mark_completed")
                .value(user_id)
                .style("primary"),
                Button("Mark Failed")
                .action_id("manager_mark_failed")
                .value(user_id)
                .style("danger")
            ])
        )
    ).build()
    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, **message_payload)
    db.set_turn_timeout_notified(game_id, user_id)


def _build_active_turn_message(game_id: int, is_public: bool = False) -> Message | None:
    active_turn = db.get_active_turn_details(game_id)
    if not active_turn:
        return None

    user_id = active_turn['user_id']
    status = active_turn['status']
    
    user_display_name = f"<@{user_id}>"
    if is_public:
        user_names_map = db.get_user_names([user_id])
        user_display_name = user_names_map.get(user_id, user_id)

    status_text = f"Status: `{status}`"
    time_text = ""

    if status in ('IN_PROGRESS', 'ACCEPTED') and active_turn['start_time']:
        start_time = datetime.fromisoformat(active_turn['start_time'])
        duration = active_turn['assigned_duration_seconds']
        end_time = start_time.timestamp() + duration
        remaining_seconds = max(0, int(end_time - datetime.now(timezone.utc).timestamp()))
        
        if remaining_seconds > 0:
            time_text = f" | Remaining: `{remaining_seconds // 60}m {remaining_seconds % 60}s`"
        else:
            time_text = " | Time's up!"

    message = Message(text=f"A turn for {user_display_name} is already active.")
    message.add_block(
        Section(f"A turn for *{user_display_name}* is already active.\n{status_text}{time_text}")
    )

    if status == 'PENDING':
        message.add_block(
            blockkit.Actions([
                Button("Start Turn").action_id("start_turn"),
                Button("Skip Turn").action_id("skip_turn").confirm(
                    blockkit.Confirm(
                        title="Are you sure you want to skip this turn?",
                        text="This will count as one of your two consecutive skips.",
                        confirm="Yes, skip",
                        deny="No"
                    )
                )
            ])
        )
    
    return message

@msg_listen("live.add_mgr")
def add_manager(event: MessageEvent, client: WebClient):
    user_id = event.message.user
    channel_id = event.channel
    thread_ts = event.message.thread_ts or event.message.ts

    game_id = db.get_active_game_by_thread(channel_id, thread_ts)
    if not game_id:
        client.chat_postEphemeral(user=user_id, channel=channel_id, text="No active show found in this thread.", thread_ts=thread_ts)
        return

    if not db.is_game_manager(game_id, user_id):
        client.chat_postEphemeral(user=user_id, channel=channel_id, text="You cannot overrule the magician.", thread_ts=thread_ts)

    user_id = event.message.text.removeprefix("live.add_mgr").strip()

    if not re.match(r"<@(U\w+)>", user_id):
        client.chat_postEphemeral(user=user_id, channel=channel_id, text="Invalid user ID.", thread_ts=thread_ts)
        return
    user_id = user_id.removeprefix("<@").removesuffix(">")

    if not db.has_user(user_id):
        client.chat_postEphemeral(user=user_id, channel=channel_id, text="The user have not been indexed... Ask them to join the huddle to do so!", thread_ts=thread_ts)
        return
    
    if not db.has_game_manager(user_id):
        db.add_game_manager(game_id, user_id)
        client.chat_postMessage(channel=channel_id, text="<@" + user_id + "> is now the new show manager!", thread_ts=thread_ts)
    else:
        client.chat_postMessage(channel=channel_id, text="<@" + user_id + "> is already a manager in some active game show!", thread_ts=thread_ts)
    return

@msg_listen("live.force_leave") # Deregister as game manager in any active game participated. Would also end the huddle if it is the last game manager
def force_leave(event: MessageEvent, client: WebClient):
    user_id = event.message.user
    channel_id = event.channel
    thread_ts = event.message.thread_ts # Reason of difference: don't thread the message if not already threaded

    if (managing_game_id := db.get_game_mgr_active_game(user_id)) is None: 
        return client.chat_postEphemeral(user=user_id, channel=channel_id, text="You are not a game manager in any active show instance.", thread_ts=thread_ts)

    db.remove_game_manager(managing_game_id, user_id)

    client.chat_postMessage(channel=channel_id, text="You are removed from the game manager in the active game", thread_ts=thread_ts)

    if not db.list_game_manager(managing_game_id):
        db.update_turn_status(managing_game_id, user_id, "COMPLETED")
        client.chat_postEphemeral(user=user_id, channel=channel_id, text="Additional from removing from game manager, the event is also ended", thread_ts=thread_ts)

@smart_msg_listen("live.leave")
def leave(ctx: MessageContext):
    user_id = ctx.event.message.user
    channel_id = ctx.event.channel
    thread_ts = ctx.event.message.thread_ts

    if (managing_game_id := db.get_game_mgr_active_game(user_id)) is None: 
        return ctx.private_send(text="You are not a game manager in any active show instance.")
    
    if db.list_game_manager(managing_game_id) == [user_id]:
        return ctx.private_send(text="You are the only manager left, therefore you cannot leave without ending the event. If you still want to do so, use `live.force_leave`")

    db.remove_game_manager(managing_game_id, user_id)

    ctx.public_send(channel=channel_id, text="You are removed from the game manager in the active game")


@smart_msg_listen("live.takeover")
def takeover(ctx: MessageContext):
    if ctx.event.message.user not in AUTHORIZED_USERS:
        return ctx.private_send(text="You cannot pretend to be authorised magician.")
    
    user_id = ctx.event.message.user
    channel_id = ctx.event.channel
    thread_ts = ctx.event.message.thread_ts
    if not thread_ts:
        return ctx.private_send(text="This command must be used within a game show's thread.")

    if not (game_id := db.get_active_game_by_thread(channel_id, thread_ts)):
        return ctx.private_send(text="No active game found in this thread.")
    
    db.add_game_manager(game_id, user_id)
    
    return ctx.public_send(text=f"You have been added as a game manager in game {game_id}")




@msg_listen("live.turn")
@msg_listen("live.info")
def show_game_info(event: MessageEvent, client: WebClient):
    user_id = event.message.user
    channel_id = event.channel
    thread_ts = event.message.thread_ts or event.message.ts

    game_id = db.get_active_game_by_thread(channel_id, thread_ts)
    if not game_id:
        client.chat_postEphemeral(user=user_id, channel=channel_id, text="No active show found in this thread.", thread_ts=thread_ts)
        return

    message = _build_active_turn_message(game_id, is_public=False)
    if message:
        client.chat_postEphemeral(user=user_id, channel=channel_id, thread_ts=thread_ts, **message.build())
    else:
        client.chat_postEphemeral(user=user_id, channel=channel_id, text="No performance is currently active.", thread_ts=thread_ts)

@msg_listen("live.pick")
def pick_user(event: MessageEvent, client: WebClient):
    manager_id = event.message.user
    channel_id = event.channel
    thread_ts = event.message.thread_ts or event.message.ts

    if not thread_ts:
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="This command must be used within a game's thread.", thread_ts=thread_ts)
        return

    game_id = db.get_active_game_by_thread(channel_id, thread_ts)
    if not game_id:
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="Cannot pick user: No active game found in this thread.", thread_ts=thread_ts)
        return

    if not db.is_game_manager(game_id, manager_id):
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="You cannot overrule the magician.", thread_ts=thread_ts)
        return

    active_turn_message = _build_active_turn_message(game_id, is_public=False)
    if active_turn_message:
        client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, **active_turn_message.build())
        return

    eligible_users = db.get_eligible_participants(game_id)
    if not eligible_users:
        client.chat_postMessage(channel=channel_id, text="Magician don't like any of you so he don't want to start a performance.", thread_ts=thread_ts)
        return
    
    secrets = db.get_latest_secrets(game_id)
    if not secrets:
        client.chat_postMessage(channel=channel_id, text="Cannot pick user: Game secrets could not be retrieved.", thread_ts=thread_ts)
        return
    client_secret, server_secret = secrets
    seed = f"{client_secret}{server_secret}"

    t = randint(300, 1200)
    if os.getenv("RIG"):
        t = randint(180, 180)

    selected_index, duration_seconds = (
        DeterRnd(randint(0, len(eligible_users) - 1), t)
        .with_seed(seed)
        .retrieve()
    )

    target_user_id = eligible_users[selected_index]
    
    duration_minutes = duration_seconds // 60
    remaining_seconds = duration_seconds % 60

    duration_text_parts = []
    if duration_minutes > 0:
        duration_text_parts.append(f"{duration_minutes} minute{'s' if duration_minutes > 1 else ''}")
    if remaining_seconds > 0:
        duration_text_parts.append(f"{remaining_seconds} second{'s' if remaining_seconds > 1 else ''}")
    duration_text = " and ".join(duration_text_parts)

    db.add_user_selection_transaction(game_id, target_user_id, duration_seconds)

    timeout_seconds = 120
    Timer(timeout_seconds, _handle_manager_action_timeout, args=(game_id, target_user_id, channel_id, thread_ts, client)).start()

    message_payload = (
        Message(text=f"👉 <@{target_user_id}> has been selected for the next performance by the magician!")
        .add_block(
            Section(f"👉 <@{target_user_id}> has been selected for the next performance for *{duration_text}* by the magician!")
        )
        .add_block(
            blockkit.Actions([
                Button("Start Turn").action_id("start_turn"),
                Button("Skip Turn").action_id("skip_turn").confirm(
                    blockkit.Confirm(
                        title="Are you sure you want to skip this performance?",
                        text="This will make the magician don't like you.",
                        confirm="Yes, skip",
                        deny="No"
                    )
                )
            ])
        )
    ).build()

    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, **message_payload)

@smart_msg_listen("live.summary")
def show_game_summary(ctx: MessageContext):
    if ctx.event.message.thread_ts is None:
        return ctx.private_send(text="This command must be used within a game's thread.")
    game_id = db.get_any_game_by_thread(ctx.event.channel, ctx.event.message.thread_ts)

@msg_listen("live.rnd")
def refresh_server_secret(event: MessageEvent, client: WebClient):
    manager_id = event.message.user
    channel_id = event.channel
    thread_ts = event.message.thread_ts or event.message.ts

    if not thread_ts:
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="You cannot be doing this outside the performance, get back here.", thread_ts=thread_ts)
        return

    game_id = db.get_active_game_by_thread(channel_id, thread_ts)
    if not game_id:
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="There are no active magic performance, do you want to start one with `live.init`?", thread_ts=thread_ts)
        return

    if not db.is_game_manager(game_id, manager_id):
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="You cannot overrule the magician.", thread_ts=thread_ts)
        return

    new_server_secret = secrets.token_hex(16)
    new_server_secret_hash = _sha3(new_server_secret)
    db.update_server_secret(game_id, new_server_secret)
    
    eligible_users = db.get_eligible_participants(game_id)
    if eligible_users:
        user_names_map = db.get_user_names(eligible_users)
        # Fallback to user_id if name not found, though this shouldn't happen in normal operation
        user_name_list = [user_names_map.get(uid, uid) for uid in eligible_users]
        eligible_section = Section(f"👥 *The participant the magician like:*\n{', '.join(user_name_list)}")
    else:
        eligible_section = Section("👥 *The participant the magician like:*\nLiterally no one he hate y'all (or maybe he like the one who just completed it and give him a break)")

    message = (
        Message(text=f"🎲 New server secret has been generated. Hash: `{new_server_secret_hash}`")
        .add_block(Section(f"🎲 New server secret has been generated.\n*Hash:* `{new_server_secret_hash}`"))
        .add_block(eligible_section)
    )

    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, **message.build())

@msg_listen("live.end")
def end_game(event: MessageEvent, client: WebClient):
    manager_id = event.message.user
    channel_id = event.channel
    thread_ts = event.message.thread_ts or event.message.ts

    if not thread_ts:
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="This command must be used within the magic show thread.", thread_ts=thread_ts)
        return

    game_id = db.get_active_game_by_thread(channel_id, thread_ts)
    if not game_id:
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="No active game found in this thread to end.", thread_ts=thread_ts)
        return

    if not db.is_game_manager(game_id, manager_id):
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="You cannot overrule the magician.", thread_ts=thread_ts)
        return

    db.update_game_status(game_id, "COMPLETED")

    summary_stats = db.get_game_summary_stats(game_id)
    
    summary_message = Message(text="The show has ended! Here is the summary:")
    summary_message.add_block(Section("*The show has ended! Here is the summary:*"))
    
    if not summary_stats:
        summary_message.add_block(Section("No participants had any recorded activity."))
    else:
        summary_text = ""
        for stat in summary_stats:
            summary_text += f"• *{stat['name']}*: {stat['successful_rounds']} successful performance(s) :), {stat['consecutive_skips']} skip(s) :(.\n"
        
        summary_message.add_block(Section(summary_text))

    summary_message.add_block(blockkit.Divider())
    summary_message.add_block(Section("Thanks for playing! 🎉"))

    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, **summary_message.build())

@action_listen("manager_mark_completed")
def handle_manager_mark_completed(event: BlockActionEvent, client: WebClient):
    """Handles a manager marking a timed-out turn as COMPLETED."""
    manager_id = event.user.id
    channel_id = event.container.channel_id
    thread_ts = (event.message and event.message.thread_ts) or event.container.message_ts
    message_ts = event.container.message_ts
    user_id = event.actions[0].value

    game_id = db.get_active_game_by_thread(channel_id, thread_ts)
    if not game_id or not user_id:
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="Could not find an active show or user for this action.", thread_ts=thread_ts)
        return

    if not db.is_game_manager(game_id, manager_id):
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="You cannot overrule the magician.", thread_ts=thread_ts)
        return

    db.update_turn_status(game_id, user_id, "COMPLETED")

    client.chat_update(
        channel=channel_id,
        ts=message_ts,
        text=f"Turn for <@{user_id}> marked as *completed* by <@{manager_id}>.",
        blocks=Message().add_block(Section(f"✅ Turn for <@{user_id}> marked as *COcompletedMPLETED* by <@{manager_id}>.")).build()['blocks']
    )

@action_listen("manager_mark_failed")
def handle_manager_mark_failed(event: BlockActionEvent, client: WebClient):
    """Handles a manager marking a timed-out turn as FAILED."""
    manager_id = event.user.id
    channel_id = event.container.channel_id
    thread_ts = (event.message and event.message.thread_ts) or event.container.message_ts
    message_ts = event.container.message_ts
    user_id = event.actions[0].value

    game_id = db.get_active_game_by_thread(channel_id, thread_ts)
    if not game_id or not user_id:
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="Could not find an active game or user for this action.", thread_ts=thread_ts)
        return

    if not db.is_game_manager(game_id, manager_id):
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="You cannot overrule the magician.", thread_ts=thread_ts)
        return

    db.update_turn_status(game_id, user_id, "FAILED")

    client.chat_update(
        channel=channel_id,
        ts=message_ts,
        text=f"❌ Turn for <@{user_id}> marked as FAILED by <@{manager_id}>.",
        blocks=Message().add_block(Section(f"❌ Turn for <@{user_id}> marked as *FAILED* by <@{manager_id}>.")).build()['blocks']
    )


@action_listen("test_button")
def handle_test_button(event: BlockActionEvent, client: WebClient):
    """Handles the click of the 'test_button'."""
    user_name = event.user.name
    client.chat_postMessage(
        channel=event.container.channel_id,
        text=f"👋 Hello {user_name}, you clicked the button!"
    )

@action_listen("start_turn")
def handle_start_turn(event: BlockActionEvent, client: WebClient):
    """Handles a manager starting the current turn."""
    manager_id = event.user.id
    channel_id = event.container.channel_id
    thread_ts = (event.message and event.message.thread_ts) or event.container.message_ts

    game_id = db.get_active_game_by_thread(channel_id, thread_ts)
    if not game_id:
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="Could not find an active show in this thread.", thread_ts=thread_ts)
        return

    if not db.is_game_manager(game_id, manager_id):
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="YYou cannot overrule the magician.", thread_ts=thread_ts)
        return

    pending_user_id = db.get_pending_turn_user(game_id)
    if not pending_user_id:
        client.chat_postMessage(channel=channel_id, text="There is no pending performance to start.", thread_ts=thread_ts)
        return

    try:
        turn_details = db.start_turn(game_id, pending_user_id)
        message_payload = (
            Message(text=f"<@{pending_user_id}>'s performance has officially started! Good luck!")
        ).build()

        client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, **message_payload)

        duration_seconds = turn_details['assigned_duration_seconds']
        user_turn_timer = Timer(
            duration_seconds, 
            _handle_user_turn_timeout, 
            args=(game_id, pending_user_id, channel_id, thread_ts, client)
        )
        ACTIVE_TURN_TIMERS[(game_id, pending_user_id)] = user_turn_timer
        user_turn_timer.start()
    except ValueError as e:
        client.chat_postMessage(channel=channel_id, text=f"Error starting turn: {e}", thread_ts=thread_ts)

@action_listen("accept_turn")
def handle_accept_turn(event: BlockActionEvent, client: WebClient):
    """Handles the selected user accepting their turn."""
    clicker_id = event.user.id
    channel_id = event.container.channel_id
    message_ts = event.container.message_ts
    thread_ts = (event.message and event.message.thread_ts) or event.container.message_ts

    game_id = db.get_active_game_by_thread(channel_id, thread_ts)
    if not game_id:
        client.chat_postEphemeral(user=clicker_id, channel=channel_id, text="Could not find an active game in this thread.", thread_ts=thread_ts)
        return

    in_progress_user_id = db.get_in_progress_turn_user(game_id)
    if not in_progress_user_id:
        client.chat_postEphemeral(user=clicker_id, channel=channel_id, text="There is no turn currently in progress to accept.", thread_ts=thread_ts)
        return

    if clicker_id != in_progress_user_id:
        client.chat_postEphemeral(user=clicker_id, channel=channel_id, text="It's not your turn to accept.", thread_ts=thread_ts)
        return

    db.update_turn_status(game_id, clicker_id, "ACCEPTED")

    client.chat_update(
        channel=channel_id,
        ts=message_ts,
        text=f"<@{clicker_id}> has *started* the turn.",
        blocks=Message().add_block(Section(f"<@{clicker_id}> has *started* their performance. The countdown is on!")).build()['blocks']
    )

@action_listen("reject_turn")
def handle_reject_turn(event: BlockActionEvent, client: WebClient):
    """Handles the selected user rejecting (skipping) their turn."""
    clicker_id = event.user.id
    channel_id = event.container.channel_id
    message_ts = event.container.message_ts
    thread_ts = (event.message and event.message.thread_ts) or event.container.message_ts

    game_id = db.get_active_game_by_thread(channel_id, thread_ts)
    if not game_id:
        client.chat_postEphemeral(user=clicker_id, channel=channel_id, text="Could not find an active show in this thread.", thread_ts=thread_ts)
        return

    in_progress_user_id = db.get_in_progress_turn_user(game_id)
    if not in_progress_user_id:
        client.chat_postEphemeral(user=clicker_id, channel=channel_id, text="There is no performance currently in progress to reject.", thread_ts=thread_ts)
        return

    if clicker_id != in_progress_user_id:
        client.chat_postEphemeral(user=clicker_id, channel=channel_id, text="You cannot skip performance that is not yours..", thread_ts=thread_ts)
        return
    
    db.update_turn_status(game_id, clicker_id, "REJECTED")

    client.chat_update(
        channel=channel_id,
        ts=message_ts,
        text=f"<@{clicker_id}> has rejected the performance.",
        blocks=Message().add_block(Section(f"<@{clicker_id}> has rejected (skipped) their performance.")).build()['blocks']
    )

@action_listen("confirm_skip")
def handle_confirm_skip(event: BlockActionEvent, client: WebClient):
    """Handles a manager confirming to skip a user after a timeout."""
    manager_id = event.user.id
    channel_id = event.container.channel_id
    thread_ts = (event.message and event.message.thread_ts) or event.container.message_ts
    message_ts = event.container.message_ts
    user_to_skip = event.actions[0].value

    game_id = db.get_active_game_by_thread(channel_id, thread_ts)
    if not game_id:
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="Could not find an active game in this thread.", thread_ts=thread_ts)
        return

    if not db.is_game_manager(game_id, manager_id):
        client.chat_postEphemeral(user=manager_id, channel=channel_id, text="You cannot overrule the magician.", thread_ts=thread_ts)
        return

    db.update_turn_status(game_id, str(user_to_skip), "SKIPPED")

    client.chat_update(
        channel=channel_id,
        ts=message_ts,
        text=f"🏃 Turn for <@{user_to_skip}> has been skipped by <@{manager_id}>.",
        blocks=Message().add_block(Section(f"🏃 Turn for <@{user_to_skip}> has been skipped by <@{manager_id}>.")).build()['blocks']
    )



@action_listen("skip_turn")
def handle_skip_turn(event: BlockActionEvent, client: WebClient):
    clicker_id = event.user.id
    channel_id = event.container.channel_id
    thread_ts = (event.message and event.message.thread_ts) or event.container.message_ts

    game_id = db.get_active_game_by_thread(channel_id, thread_ts)
    if not game_id:
        client.chat_postEphemeral(user=clicker_id, channel=channel_id, text="Could not find an active game in this thread.", thread_ts=thread_ts)
        return

    pending_user_id = db.get_pending_turn_user(game_id)
    if not pending_user_id:
        client.chat_postEphemeral(user=clicker_id, channel=channel_id, text="There is no pending performance to skip.", thread_ts=thread_ts)
        return

    is_manager = db.is_game_manager(game_id, clicker_id)
    is_selected_user = (clicker_id == pending_user_id)

    if not is_manager and not is_selected_user:
        client.chat_postEphemeral(user=clicker_id, channel=channel_id, text="You cannot overrule the magician.", thread_ts=thread_ts)
        return

    db.update_turn_status(game_id, pending_user_id, "SKIPPED")

    client.chat_postMessage(channel=channel_id, text=f"🏃 <@{pending_user_id}>'s turn has been skipped, now the magician like you less.", thread_ts=thread_ts)


@msg_listen("huddle_thread", is_subtype=True)
def handle_huddle_start_message(event: MessageEvent, client: WebClient):
    room = event.message.room
    if not room or not room.channels:
        print(f"⚠️ Received huddle_thread message without room or channel data. TS: {event.message.ts}")
        return

    huddle_id = room.id
    channel_id = room.channels[0]
    start_time = room.date_start.datetime

    db.upsert_huddle(huddle_id, channel_id, start_time)
    print(f"✅ Huddle {huddle_id} in channel {channel_id} has been recorded.")

@huddle_listen(HuddleState.IN_HUDDLE)
def handle_huddle_join(event: HuddleChange, client: WebClient):
    user_id = event.user.id
    user_name = event.user.name
    huddle_id = event.call_id
    db.upsert_huddle(huddle_id, "UNKNOWN", datetime.now(timezone.utc))
    db.upsert_user(user_id, user_name)
    db.add_huddle_participant(huddle_id, user_id)
    print(f"ℹ️ User {user_name} ({user_id}) joined huddle {huddle_id}.")
    game_id = db.get_active_game_in_huddle(huddle_id)
    if game_id is not None:
        db.add_game_participant(game_id, user_id)

@huddle_listen(HuddleState.NOT_IN_HUDDLE)
def handle_huddle_leave(event: HuddleChange, client: WebClient):
    user_id = event.user.id
    user_name = event.user.real_name or event.user.name
    # When a user leaves, the event doesn't specify which huddle.
    # We find all huddles the user was in and remove them.
    # In this app's logic, a user is likely in only one huddle at a time.
    huddle_ids = db.get_user_huddles(user_id)
    for huddle_id in huddle_ids:
        db.remove_huddle_participant(huddle_id, user_id)
        print(f"🚪 User {user_name} ({user_id}) left huddle {huddle_id}.")

load_dotenv()

def load_active_timers(client: WebClient):
    print("⏳ Loading active timers from the database...")
    pending_turns = db.get_all_turns_by_status(['PENDING'])
    manager_timeout_duration = 120  # 2 minutes

    for turn in pending_turns:
        selection_time = datetime.fromisoformat(turn['selection_time']).replace(tzinfo=timezone.utc)
        elapsed_time = (datetime.now(timezone.utc) - selection_time).total_seconds()
        remaining_time = manager_timeout_duration - elapsed_time

        print(f"  - Found pending turn for user {turn['user_id']} in game {turn['game_id']}. Remaining time: {remaining_time:.0f}s")

        if remaining_time > 0:
            # Start a timer for the remaining duration
            Timer(remaining_time, _handle_manager_action_timeout, args=(turn['game_id'], turn['user_id'], turn['channel_id'], turn['thread_ts'], client)).start()
        elif not turn['timeout_notified']:
            # If time has expired and we haven't notified yet, handle the timeout.
            _handle_manager_action_timeout(turn['game_id'], turn['user_id'], turn['channel_id'], turn['thread_ts'], client)

    print(f"✅ Finished loading {len(pending_turns)} PENDING turn timers.")

    # Load IN_PROGRESS and ACCEPTED turns
    in_progress_turns = db.get_all_turns_by_status(['IN_PROGRESS', 'ACCEPTED'])
    for turn in in_progress_turns:
        start_time = datetime.fromisoformat(turn['start_time']).replace(tzinfo=timezone.utc) if turn['start_time'] else None
        if not start_time:
            continue

        duration = turn['assigned_duration_seconds']
        elapsed_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        remaining_time = duration - elapsed_time

        print(f"  - Found IN_PROGRESS turn for user {turn['user_id']} in game {turn['game_id']}. Remaining time: {remaining_time:.0f}s")

        if remaining_time > 0:
            user_turn_timer = Timer(remaining_time, _handle_user_turn_timeout, args=(turn['game_id'], turn['user_id'], turn['channel_id'], turn['thread_ts'], client))
            ACTIVE_TURN_TIMERS[(turn['game_id'], turn['user_id'])] = user_turn_timer
            user_turn_timer.start()
        else:
            _handle_user_turn_timeout(turn['game_id'], turn['user_id'], turn['channel_id'], turn['thread_ts'], client)

    print(f"Finished loading {len(in_progress_turns)} IN_PROGRESS turn timers.")


def process_message(client: BaseSocketModeClient, req: SocketModeRequest):
    response = SocketModeResponse(envelope_id=req.envelope_id)
    client.send_socket_mode_response(response)
    with open("event.log", "a") as f:
        f.write(f"{req.type} {str(req.payload)}\n")
    event: Recv
    # Check if the event is a message and not from a bot
    if req.type == "events_api":
        event_payload = req.payload.get("event", {})
        event_type = event_payload.get("type")

        if event_type == "message" and "bot_id" not in event_payload:
            event = MessageEvent.parse(req.payload)
            message_dispatch(event, client.web_client)
        
        elif event_type == "user_huddle_changed":
            event = HuddleChange.parse(req.payload)
            huddle_dispatch(event, client.web_client)
    
    elif req.type == "interactive" and req.payload.get("type") == "block_actions":
        event = BlockActionEvent.parse(req.payload)
        action_dispatch(event, client.web_client)




if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db.init_db()
    client = SocketModeClient(
        app_token=os.environ["SLACK_APP_LEVEL_TOKEN"],
        web_client=WebClient(token=os.environ["SLACK_BOT_OAUTH_TOKEN"])
    )
    load_active_timers(client.web_client)
    client.socket_mode_request_listeners.append(process_message)
    print("Bot is listening for messages...")
    client.connect()
    while True:
        try:
            tEvent().wait()
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error(f"Uncaught exception:", exc_info=True)
            
