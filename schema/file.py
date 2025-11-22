from dataclasses import dataclass
from typing import TypedDict
from io import IOBase
from os import PathLike

@dataclass(frozen=True)
class UploadedFile:
    file_id: str
    file_external_id: str

    @classmethod
    def parse(cls, data: dict) -> "UploadedFile":
        return cls(
            file_id=data["id"],
            file_external_id=data["title"],
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