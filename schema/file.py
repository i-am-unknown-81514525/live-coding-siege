from dataclasses import dataclass
from typing import TypedDict
from io import IOBase
from os import PathLike

# https://github.com/slackapi/bolt-js/blob/6b0f985287301fd7e4b679822708b46aeca1421a/src/types/view/index.ts#L145 wtf
# https://docs.slack.dev/messaging/working-with-files/#sdks
@dataclass(frozen=True)
class UploadedFile:
    file_id: str # id
    file_external_id: str # title, this is internal behaviour for file identification
    created: int
    timestamp: int
    name: str
    title: str
    filetype: str
    mimetype: str
    pretty_type: str
    user: str
    user_team: str
    editable: bool | None
    size: int | None
    mode: str | None
    is_external: bool | None
    external_type: str | None
    is_public: bool | None
    public_url_shared: bool | None
    display_as_bot: bool | None
    username: str | None
    url_private: str
    url_private_download: str
    permalink: str
    permalink_public: str | None
    edit_link: str | None
    preview: str | None
    preview_highlight: str | None
    lines: int | None
    lines_more: int | None
    preview_is_truncated: bool | None
    comments_count: int | None
    is_starred: bool | None
    shares: dict | None # Idgaf at this point not like I care what inside this
    channels: list[str] | None
    groups: list[str] | None
    ims: list[str] | None
    has_more_shares: bool | None
    has_rich_preview: bool | None
    file_access: str | None

    @classmethod
    def parse(cls, data: dict) -> "UploadedFile":
        return cls(
            file_id=data["id"],
            file_external_id=data["title"],
            created=data["created"],
            timestamp=data["timestamp"],
            name=data["name"],
            title=data["title"],
            filetype=data["filetype"],
            mimetype=data["mimetype"],
            pretty_type=data["pretty_type"],
            user=data["user"],
            user_team=data["user_team"],
            editable=data.get("editable"),
            size=data.get("size"),
            mode=data.get("mode"),
            is_external=data.get("is_external"),
            external_type=data.get("external_type"),
            is_public=data.get("is_public"),
            public_url_shared=data.get("public_url_shared"),
            display_as_bot=data.get("display_as_bot"),
            username=data.get("username"),
            url_private=data["url_private"],
            url_private_download=data["url_private_download"],
            permalink=data["permalink"],
            permalink_public=data.get("permalink_public"),
            edit_link=data.get("edit_link"),
            preview=data.get("preview"),
            preview_highlight=data.get("preview_highlight"),
            lines=data.get("lines"),
            lines_more=data.get("lines_more"),
            preview_is_truncated=data.get("preview_is_truncated"),
            comments_count=data.get("comments_count"),
            is_starred=data.get("is_starred"),
            shares=data.get("shares"),
            channels=data.get("channels"),
            groups=data.get("groups"),
            ims=data.get("ims"),
            has_more_shares=data.get("has_more_shares"),
            has_rich_preview=data.get("has_rich_preview"),
            file_access=data.get("file_access"),
        )
    

class GetURLData(TypedDict):
    filename: str
    content: bytes | IOBase | PathLike | str
    alt_text: str | None
    snippet_type: str | None
    title: str


@dataclass(frozen=True)
class PendingFile:
    filename: str
    content: bytes | IOBase | PathLike | str
    alt_text: str | None = None
    snippet_type: str | None = None

    def export(self, r_id: str) -> GetURLData:
        return {
            "title": r_id,
            "filename": self.filename,
            "content": self.content,
            "alt_text": self.alt_text,
            "snippet_type": self.snippet_type,
        }