from enum import StrEnum
from .user import User
from .event import Event
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
            event_timestamp=Arrow.fromtimestamp(event_data["event_ts"]),
            user=User.parse(event_data["user"]),
            event_id=data["event_id"],
            huddle_state=HuddleState.parse(huddle_state_str),
            call_id=user_profile.get("huddle_state_call_id"),
            huddle_state_expiration_ts=Arrow.fromtimestamp(user_profile.get("huddle_state_expiration_ts")),
        )
