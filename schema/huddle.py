from enum import StrEnum
from .user import User
from .base import Event
from .base import SlackID
from dataclasses import dataclass
from typing import Final, ClassVar
from arrow import Arrow


# events_api 
sample = {'api_app_id': 'A09KW3ZJLLQ',
 'authorizations': [{'enterprise_id': None,
                     'is_bot': True,
                     'is_enterprise_install': False,
                     'team_id': 'T0266FRGM',
                     'user_id': 'U09K5HC2FRS'}],
 'event': {'cache_ts': 1759867374,
           'event_ts': '1759867374.064300',
           'type': 'user_huddle_changed',
           'user': {'color': '43761b',
                    'deleted': False,
                    'id': 'U092BGL0UUQ',
                    'is_admin': False,
                    'is_app_user': False,
                    'is_bot': False,
                    'is_email_confirmed': True,
                    'is_owner': False,
                    'is_primary_owner': False,
                    'is_restricted': False,
                    'is_ultra_restricted': False,
                    'locale': 'en-GB',
                    'name': 'iamaunknownpeople',
                    'profile': {'avatar_hash': 'ga78fcb1486e',
                                'display_name': '',
                                'display_name_normalized': '',
                                'fields': {},
                                'first_name': 'i-am-unknown-81514525',
                                'guest_invited_by': '',
                                'huddle_state': 'in_a_huddle',
                                'huddle_state_call_id': 'R09K73DJVUN',
                                'huddle_state_expiration_ts': 1759868694,
                                'image_192': 'https://secure.gravatar.com/avatar/a78fcb1486ec48ef10df47d4edee78ac.jpg?s=192&d=https%3A%2F%2Fa.slack-edge.com%2Fdf10d%2Fimg%2Favatars%2Fava_0005-192.png',
                                'image_24': 'https://secure.gravatar.com/avatar/a78fcb1486ec48ef10df47d4edee78ac.jpg?s=24&d=https%3A%2F%2Fa.slack-edge.com%2Fdf10d%2Fimg%2Favatars%2Fava_0005-24.png',
                                'image_32': 'https://secure.gravatar.com/avatar/a78fcb1486ec48ef10df47d4edee78ac.jpg?s=32&d=https%3A%2F%2Fa.slack-edge.com%2Fdf10d%2Fimg%2Favatars%2Fava_0005-32.png',
                                'image_48': 'https://secure.gravatar.com/avatar/a78fcb1486ec48ef10df47d4edee78ac.jpg?s=48&d=https%3A%2F%2Fa.slack-edge.com%2Fdf10d%2Fimg%2Favatars%2Fava_0005-48.png',
                                'image_512': 'https://secure.gravatar.com/avatar/a78fcb1486ec48ef10df47d4edee78ac.jpg?s=512&d=https%3A%2F%2Fa.slack-edge.com%2Fdf10d%2Fimg%2Favatars%2Fava_0005-512.png',
                                'image_72': 'https://secure.gravatar.com/avatar/a78fcb1486ec48ef10df47d4edee78ac.jpg?s=72&d=https%3A%2F%2Fa.slack-edge.com%2Fdf10d%2Fimg%2Favatars%2Fava_0005-72.png',
                                'last_name': '',
                                'phone': '',
                                'pronouns': 'any',
                                'real_name': 'i-am-unknown-81514525',
                                'real_name_normalized': 'i-am-unknown-81514525',
                                'skype': '',
                                'status_emoji': '',
                                'status_emoji_display_info': [],
                                'status_expiration': 0,
                                'status_text': '',
                                'status_text_canonical': '',
                                'team': 'T0266FRGM',
                                'title': ''},
                    'real_name': 'i-am-unknown-81514525',
                    'team_id': 'T0266FRGM',
                    'tz': 'Europe/London',
                    'tz_label': 'British Summer Time',
                    'tz_offset': 3600,
                    'updated': 1759867374,
                    'who_can_share_contact_card': 'EVERYONE'}},
 'event_id': 'Ev09K2PM5Y1Z',
 'event_time': 1759867374,
 'is_ext_shared_channel': False,
 'team_id': 'T0266FRGM',
 'token': 'REDACTED_IDK_IF_IT_IS_SECRET_OR_NOT_:)',
 'type': 'event_callback'}

class HuddleState(StrEnum):
    IN_HUDDLE = "huddle_state"
    NOT_IN_HUDDLE = "default_unset"

    @classmethod
    def parse(cls, data: str):
        if data == "in_a_huddle":
            return cls.IN_HUDDLE
        return cls.NOT_IN_HUDDLE

@dataclass(frozen=True)
class HuddleChange(Event):
    event_timestamp: Arrow
    user: User
    event_id: str
    huddle_state: HuddleState
    call_id: str
    huddle_state_expiration_ts: Arrow
    __EVENT__ = "user_huddle_changed"

    @classmethod
    def parse(cls, data: dict):
        event_data = data.get("event", {})
        user_profile = event_data.get("user",{}).get("profile", {})
        huddle_state_str = user_profile.get("huddle_state", "default_unset")

        return cls(
            event_timestamp=Arrow.fromtimestamp(float(event_data.get("event_ts", 0))),
            user=User.parse(event_data.get("user", {})),
            event_id=data.get("event_id", ""),
            huddle_state=HuddleState.parse(huddle_state_str),
            call_id=user_profile.get("huddle_state_call_id"),
            huddle_state_expiration_ts=Arrow.fromtimestamp(int(user_profile.get("huddle_state_expiration_ts", 0))),
        )

@dataclass(frozen=True)
class ParticipantEvent:
    has_joined: bool
    has_turned_camera_on: bool
    has_turned_camera_off: bool
    has_started_screenshare: bool
    has_stopped_screenshare: bool

    @classmethod
    def parse(cls, data: dict):
        return cls(
            has_joined=data.get("joined", False),
            has_turned_camera_on=data.get("camera_on", False),
            has_turned_camera_off=data.get("camera_off", False),
            has_started_screenshare=data.get("screenshare_on", False),
            has_stopped_screenshare=data.get("screenshare_off", False),
        )

@dataclass(frozen=True)
class Room:
    id: SlackID
    name: str
    app_id: str
    call_family: str
    channels: list[SlackID]
    created_by: SlackID
    date_start: Arrow
    date_end: Arrow
    participants_events: dict[SlackID, ParticipantEvent]
    participants: list[SlackID]
    has_ended: bool
    huddle_link: str
    is_dm_call: bool
    participant_history: list[SlackID]

    @classmethod
    def parse(cls, data: dict):
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            app_id=data.get("app_id", ""),
            call_family=data.get("call_family", ""),
            channels=data.get("channels", []),
            created_by=data.get("created_by", ""),
            date_start=Arrow.fromtimestamp(data.get("date_start", 0)),
            date_end=Arrow.fromtimestamp(data.get("date_end", 0)),
            participants_events={
                k: ParticipantEvent.parse(v) for k, v in data.get("participants_events", {}).items()
            },
            participants=data.get("participants", []),
            has_ended=data.get("has_ended", False),
            huddle_link=data.get("huddle_link", ""),
            is_dm_call=data.get("is_dm_call", False),
            participant_history=data.get("participant_history", []),
        )
