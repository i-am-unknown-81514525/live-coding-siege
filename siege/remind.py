import os
import logging, time

from base import ExecutionContext
from siege.core import prox_get_user, retrieve_all_user_proj_record
from schema.user import UserProfile
from slack_sdk.socket_mode.client import BaseSocketModeClient
from siege.schema.siege import SiegeUser


def send_remind(
    client: BaseSocketModeClient,
    user: SiegeUser,
    channel: str,
    thread_ts: str,
    text: str,
    mention: bool = True,
):
    user_mention = f"<@{user.slack_id}>"
    no_mention = "/".join(user.display_name)
    message = f"{user_mention} {text}" if mention else f"{no_mention} {text}"
    client.web_client.chat_postMessage(
        channel=channel, thread_ts=thread_ts, text=message
    )


USER_LOOP_TIME = 900


def remind_loop(client: BaseSocketModeClient):
    return
    while True:
        start = time.perf_counter()
        try:
            slack_id = os.environ["REMIND_USER"]
            user = prox_get_user(slack_id)
            mention: bool = True
            try:
                profile = UserProfile.parse(
                    client.web_client.users_profile_get(user=slack_id).data["profile"]
                )  # type: ignore
                print(profile.status_emoji)
                if profile.status_emoji == ":sleeping_parrot:":
                    mention = False
            except Exception as e:
                logging.warning(f"Failed to fetch user profile", exc_info=True)
            heartbeats = retrieve_all_user_proj_record(user.id)
            if not heartbeats:
                send_remind(
                    client=client,
                    user=user,
                    channel=os.environ["REMIND_CHANNEL"],
                    thread_ts=os.environ["REMIND_THREAD"],
                    text="Bark! Where is your project???? Make one!",
                    mention=mention,
                )
            max_week = max(heartbeats, key=lambda x: x.week_num).week_num
            max_week_heartbeats = [hb for hb in heartbeats if hb.week_num == max_week]
            latest_heartbeat = max(
                max_week_heartbeats, key=lambda x: x.measurement_time.timestamp()
            )
            one_h_ago_heartbeat = max(
                filter(
                    lambda x: x.measurement_time.timestamp() <= time.time() - 3600,
                    max_week_heartbeats,
                ),
                default=None,
                key=lambda x: x.measurement_time.timestamp(),
            )
            if (
                latest_heartbeat.hours
                - (one_h_ago_heartbeat.hours if one_h_ago_heartbeat else 0)
                < 0.09
            ):
                send_remind(
                    client=client,
                    user=user,
                    channel=os.environ["REMIND_CHANNEL"],
                    thread_ts=os.environ["REMIND_THREAD"],
                    text="Bark! Code on your project. Bark!",
                    mention=mention,
                )
        except Exception as e:
            logging.warning(f"Faile to fetch users", exc_info=True)
        curr = time.perf_counter()
        logging.info(f"Check reminders")
        sleep_time = USER_LOOP_TIME - (curr - start)
        if sleep_time > 0:
            time.sleep(sleep_time)


import threading


def start(client: ExecutionContext):
    thread = threading.Thread(target=remind_loop, args=(client.slack_client.client,), daemon=True)
    thread.start()
