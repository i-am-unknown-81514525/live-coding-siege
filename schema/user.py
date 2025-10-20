from dataclasses import dataclass

@dataclass(frozen=True)
class UserFieldEntry:
    value: str
    alt: str

    @classmethod
    def parse(cls, data: dict):
        return cls(
            value=data["value"],
            alt=data["alt"],
        )

@dataclass(frozen=True)
class UserAvatar:
    image_192: str
    image_24: str
    image_32: str
    image_48: str
    image_512: str
    image_72: str

    @classmethod
    def parse(cls, data: dict):
        return cls(
            image_192=data["image_192"],
            image_24=data["image_24"],
            image_32=data["image_32"],
            image_48=data["image_48"],
            image_512=data["image_512"],
            image_72=data["image_72"],
        )

@dataclass(frozen=True)
class UserFlag:
    is_admin: bool
    is_app_user: bool
    is_bot: bool
    is_email_confirmed: bool
    is_owner: bool
    is_primary_owner: bool
    is_restricted: bool
    is_ultra_restricted: bool

    @classmethod
    def parse(cls, data: dict):
        return cls(
            is_admin=data.get("is_admin", False),
            is_app_user=data.get("is_app_user", False),
            is_bot=data.get("is_bot", False),
            is_email_confirmed=data.get("is_email_confirmed", False),
            is_owner=data.get("is_owner", False),
            is_primary_owner=data.get("is_primary_owner", False),
            is_restricted=data.get("is_restricted", False),
            is_ultra_restricted=data.get("is_ultra_restricted", False),
        )


@dataclass(frozen=True)
class UserProfile:
    avatar_hash: str
    display_name: str
    display_name_normalized: str
    first_name: str
    last_name: str
    fields: dict[str, UserFieldEntry]
    avatars: UserAvatar
    pronouns: str | None
    phone: str | None
    team: str
    real_name: str
    real_name_normalized: str
    skype: str | None
    status_text: str | None
    status_emoji: str | None
    status_expiration: int | None
    title: str | None

    @classmethod
    def parse(cls, data: dict):
        return cls(
            avatar_hash=data["avatar_hash"],
            display_name=data["display_name"],
            display_name_normalized=data["display_name_normalized"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            fields={
                k: UserFieldEntry.parse(v) for k, v in data["fields"].items()
            } if "fields" in data else {},
            avatars=UserAvatar.parse(data),
            pronouns=data.get("pronouns"),
            phone=data.get("phone"),
            team=data["team"],
            real_name=data["real_name"],
            real_name_normalized=data["real_name_normalized"],
            skype=data.get("skype"),
            status_text=data.get("status_text"),
            status_emoji=data.get("status_emoji"),
            status_expiration=data.get("status_expiration"),
            title=data.get("title"),
        )

@dataclass(frozen=True)
class User:
    id: str
    deleted: bool
    real_name: str | None
    name: str
    tz: str | None
    tz_label: str | None
    tz_offset: int | None
    updated: int
    profile: UserProfile
    flags: UserFlag

    @classmethod
    def parse(cls, data: dict):
        return cls(
            id=data["id"],
            deleted=data.get("deleted", False),
            real_name=data.get("real_name"),
            name=data["name"],
            tz=data.get("tz"),
            tz_label=data.get("tz_label"),
            tz_offset=data.get("tz_offset"),
            updated=data["updated"],
            profile=UserProfile.parse(data["profile"]),
            flags=UserFlag.parse(data)
        )
    
