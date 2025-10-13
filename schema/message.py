from dataclasses import dataclass
from .base import Event
from .base import SlackID
from .huddle import Room
from arrow import Arrow
from typing import Self

sample = {'api_app_id': 'A09KW3ZJLLQ',
 'authorizations': [{'enterprise_id': None,
                     'is_bot': True,
                     'is_enterprise_install': False,
                     'team_id': 'T0266FRGM',
                     'user_id': 'U09K5HC2FRS'}],
 'context_enterprise_id': None,
 'context_team_id': 'T0266FRGM',
 'event': {'channel': 'C08SKC6P85V',
           'channel_type': 'channel',
           'event_ts': '1759867394.232700',
           'hidden': True,
           'message': {'blocks': [{'block_id': 'UoEcF',
                                   'elements': [{'elements': [{'text': 'A '
                                                                       'huddle '
                                                                       'started',
                                                               'type': 'text'}],
                                                 'type': 'rich_text_section'}],
                                   'type': 'rich_text'}],
                       'channel': 'C08SKC6P85V',
                       'edited': {'ts': '1759867394.000000',
                                  'user': 'USLACKBOT'},
                       'no_notifications': True,
                       'permalink': 'https://hackclub.slack.com/call/R09K73DJVUN',
                       'room': {'app_id': 'A00',
                                'attached_file_ids': [],
                                'background_id': 'BIRDSONG',
                                'call_family': 'huddle',
                                'canvas_background': 'BIRDSONG',
                                'canvas_thread_ts': '1759867369.537409',
                                'channels': ['C08SKC6P85V'],
                                'created_by': 'U092BGL0UUQ',
                                'date_end': 1759867394,
                                'date_start': 1759867369,
                                'display_id': '',
                                'external_unique_id': '94ee0cce-24e9-44e3-acb9-7e0f051a2713',
                                'has_ended': True,
                                'huddle_link': 'https://app.slack.com/huddle/T0266FRGM/C08SKC6P85V',
                                'id': 'R09K73DJVUN',
                                'is_dm_call': False,
                                'is_prewarmed': False,
                                'is_scheduled': False,
                                'knocks': {},
                                'last_invite_status_by_user': {},
                                'locale': 'en-US',
                                'media_backend_type': 'free_willy',
                                'media_server': '',
                                'name': '',
                                'participant_history': ['U092BGL0UUQ'],
                                'participants': [],
                                'participants_camera_off': [],
                                'participants_camera_on': [],
                                'participants_events': {'U092BGL0UUQ': {'camera_off': False,
                                                                        'camera_on': False,
                                                                        'joined': True,
                                                                        'screenshare_off': True,
                                                                        'screenshare_on': True,
                                                                        'user_team': {}}},
                                'participants_screenshare_off': [],
                                'participants_screenshare_on': [],
                                'pending_invitees': {},
                                'recording': {'can_record_summary': 'unavailable'},
                                'thread_root_ts': '1759867369.537409',
                                'was_accepted': False,
                                'was_missed': False,
                                'was_rejected': False},
                       'subtype': 'huddle_thread',
                       'team': 'T0266FRGM',
                       'text': '',
                       'ts': '1759867369.537409',
                       'type': 'message',
                       'user': 'USLACKBOT'},
           'previous_message': {'blocks': [{'block_id': 'UoEcF',
                                            'elements': [{'elements': [{'text': 'A '
                                                                                'huddle '
                                                                                'started',
                                                                        'type': 'text'}],
                                                          'type': 'rich_text_section'}],
                                            'type': 'rich_text'}],
                                'channel': 'C08SKC6P85V',
                                'no_notifications': True,
                                'permalink': 'https://hackclub.slack.com/call/R09K73DJVUN',
                                'room': {'app_id': 'A00',
                                         'attached_file_ids': [],
                                         'background_id': 'BIRDSONG',
                                         'call_family': 'huddle',
                                         'canvas_background': 'BIRDSONG',
                                         'canvas_thread_ts': '1759867369.537409',
                                         'channels': ['C08SKC6P85V'],
                                         'created_by': 'U092BGL0UUQ',
                                         'date_end': 1759867394,
                                         'date_start': 1759867369,
                                         'display_id': '',
                                         'external_unique_id': '94ee0cce-24e9-44e3-acb9-7e0f051a2713',
                                         'has_ended': True,
                                         'huddle_link': 'https://app.slack.com/huddle/T0266FRGM/C08SKC6P85V',
                                         'id': 'R09K73DJVUN',
                                         'is_dm_call': False,
                                         'is_prewarmed': False,
                                         'is_scheduled': False,
                                         'knocks': {},
                                         'last_invite_status_by_user': {},
                                         'locale': 'en-US',
                                         'media_backend_type': 'free_willy',
                                         'media_server': '',
                                         'name': '',
                                         'participant_history': ['U092BGL0UUQ'],
                                         'participants': [],
                                         'participants_camera_off': [],
                                         'participants_camera_on': [],
                                         'participants_events': {'U092BGL0UUQ': {'camera_off': False,
                                                                                 'camera_on': False,
                                                                                 'joined': True,
                                                                                 'screenshare_off': True,
                                                                                 'screenshare_on': True,
                                                                                 'user_team': {}}},
                                         'participants_screenshare_off': [],
                                         'participants_screenshare_on': [],
                                         'pending_invitees': {},
                                         'recording': {'can_record_summary': 'unavailable'},
                                         'thread_root_ts': '1759867369.537409',
                                         'was_accepted': False,
                                         'was_missed': False,
                                         'was_rejected': False},
                                'subtype': 'huddle_thread',
                                'team': 'T0266FRGM',
                                'text': '',
                                'ts': '1759867369.537409',
                                'type': 'message',
                                'user': 'USLACKBOT'},
           'subtype': 'message_changed',
           'ts': '1759867394.232700',
           'type': 'message'},
 'event_context': '4-eyJldCI6Im1lc3NhZ2UiLCJ0aWQiOiJUMDI2NkZSR00iLCJhaWQiOiJBMDlLVzNaSkxMUSIsImNpZCI6IkMwOFNLQzZQODVWIn0',
 'event_id': 'Ev09K5MTNHD3',
 'event_time': 1759867394,
 'is_ext_shared_channel': False,
 'team_id': 'T0266FRGM',
 'token': 'Ip7vQhaJfENkuSOYZOCAvY3R',
 'type': 'event_callback'}

sample2 = {'api_app_id': 'A09KW3ZJLLQ',
 'authorizations': [{'enterprise_id': None,
                     'is_bot': True,
                     'is_enterprise_install': False,
                     'team_id': 'T0266FRGM',
                     'user_id': 'U09K5HC2FRS'}],
 'context_enterprise_id': None,
 'context_team_id': 'T0266FRGM',
 'event': {'blocks': [{'block_id': '16axG',
                       'elements': [{'elements': [{'text': 'Btw you have '
                                                           'precisely this '
                                                           'amount of time '
                                                           'left\n'
                                                           "Don't need to thx "
                                                           'me :)\n',
                                                   'type': 'text'},
                                                  {'text': 'https://www.tickcounter.com/countdown/8327761/my-countdown',
                                                   'type': 'link',
                                                   'url': 'https://www.tickcounter.com/countdown/8327761/my-countdown'}],
                                     'type': 'rich_text_section'}],
                       'type': 'rich_text'}],
           'channel': 'C08SKC6P85V',
           'channel_type': 'channel',
           'client_msg_id': 'cb3a9c91-3e7d-4f2c-84d2-983a373b6109',
           'event_ts': '1759878316.810789',
           'parent_user_id': 'U0828FYS2UC',
           'team': 'T0266FRGM',
           'text': 'Btw you have precisely this amount of time left\n'
                   "Don't need to thx me :)\n"
                   '<https://www.tickcounter.com/countdown/8327761/my-countdown|https://www.tickcounter.com/countdown/8327761/my-countdown>',
           'thread_ts': '1759876916.410249',
           'ts': '1759878316.810789',
           'type': 'message',
           'user': 'U092BGL0UUQ'},
 'event_context': '4-eyJldCI6Im1lc3NhZ2UiLCJ0aWQiOiJUMDI2NkZSR00iLCJhaWQiOiJBMDlLVzNaSkxMUSIsImNpZCI6IkMwOFNLQzZQODVWIn0',
 'event_id': 'Ev09KDK79PRS',
 'event_time': 1759878316,
 'is_ext_shared_channel': False,
 'team_id': 'T0266FRGM',
 'token': 'Ip7vQhaJfENkuSOYZOCAvY3R',
 'type': 'event_callback'}

@dataclass(frozen=True)
class Edited:
    user: SlackID
    ts: Arrow

@dataclass(frozen=True)
class MessageData:
    """Represents the data content of a message, ignoring blockkit."""
    user: SlackID
    ts: str
    text: str
    thread_ts: SlackID | None
    edited: Edited | None
    room: Room | None
    subtype: str | None

    @classmethod
    def parse(cls, data: dict) -> Self:

        edited_data = data.get("edited")
        room_data = data.get("room")
        return cls(
            ts=data.get("ts", ""),
            user=data.get("user", ""),
            text=data.get("text", ""),
            thread_ts=data.get("thread_ts"),
            edited=Edited(user=edited_data["user"], ts=Arrow.fromtimestamp(float(edited_data["ts"]))) if edited_data else None,
            room=Room.parse(room_data) if room_data else None,
            subtype=data.get("subtype"),
        )


@dataclass(frozen=True)
class MessageEvent(Event):
    """
    Represents a message event from Slack.
    This can be a new message, an edited message, a deleted message, etc.
    """
    __EVENT__ = "message"

    event_ts: Arrow
    channel: SlackID
    channel_type: str
    subtype: str | None
    hidden: bool | None

    client_msg_id: str | None

    message: MessageData
    previous_message: MessageData | None

    @classmethod
    def parse(cls, data: dict):
        event_data = data.get("event", {})
        subtype = event_data.get("subtype")

        if subtype in ("message_changed", "huddle_thread"):
            current_message_data = event_data.get("message", {})
        else:
            current_message_data = event_data

        previous_message_data = event_data.get("previous_message")
        previous_message = MessageData.parse(previous_message_data) if previous_message_data else None

        return cls(
            event_ts=Arrow.fromtimestamp(float(event_data.get("event_ts", 0))),
            channel=event_data.get("channel"),
            channel_type=event_data.get("channel_type"),
            subtype=subtype,
            hidden=event_data.get("hidden"),
            client_msg_id=event_data.get("client_msg_id"),
            message=MessageData.parse(current_message_data),
            previous_message=previous_message,
        )