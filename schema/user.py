from dataclasses import dataclass

@dataclass(frozen=True)
class UserFieldEntry:
    value: str
    alt: str

@dataclass(frozen=True)
class UserAvatar:
    image_192: str
    image_24: str
    image_32: str
    image_48: str
    image_512: str
    image_72: str


@dataclass(frozen=True)
class UserProfile:
    avatar_hash: str
    display_name: str
    display_name_normalized: str
    first_name: str
    last_name: str
    fields: dict[str, UserFieldEntry]
    avatars: UserAvatar
    pronouns: str
    phone: str
    team: str
    real_name: str
    real_name_normalized: str
    skype: str

@dataclass(frozen=True)
class User:
    id: str
    deleted: bool
    real_name: str
    name: str
    tz: str
    tz_label: str
    tz_offset: int
    updated: int
    profile: UserProfile
    
