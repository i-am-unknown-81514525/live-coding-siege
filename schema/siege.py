from dataclasses import dataclass
from enum import StrEnum
from arrow import Arrow
import arrow
import re
from typing import Self


class ProjectStatus(StrEnum):
    BUILDING = "building"
    SUMMITED = "submitted"
    FINISHED = "finished"
    PENDING_VOTING = "pending_voting"
    WAITING_FOR_REVIEW = "waiting_for_review"

    @property
    def readable(self) -> str:
        match self:
            case ProjectStatus.BUILDING:
                return "Building"
            case ProjectStatus.SUMMITED:
                return "Submitted for review"
            case ProjectStatus.FINISHED:
                return "Finished"
            case ProjectStatus.PENDING_VOTING:
                return "Pending Voting"
            case ProjectStatus.WAITING_FOR_REVIEW:
                return "Waiting for Finalization"
            case _:
                return "Unknown"

    @property
    def readable_long(self) -> str:
        match self:
            case ProjectStatus.BUILDING:
                return "Building - Project is not submitted"
            case ProjectStatus.SUMMITED:
                return "Submitted for review - Please wait patiently for the stonemason to review this!"
            case ProjectStatus.FINISHED:
                return "Finished - Your coin have been awarded for the project"
            case ProjectStatus.PENDING_VOTING:
                return "Pending Voting - Your project will be in waiting until end of Friday EDT"
            case ProjectStatus.WAITING_FOR_REVIEW:
                return "Waiting for Finalization - Please wait patiently for the reviewer to set you the reviewer bonus!"
            case _:
                return "Unknown"


type URL = str

# For future reference
# https://github.com/hackclub/siege/blob/2c186ae9f863a73be8dc43b53cdd25127a383b80/app/models/user.rb#L5


class SiegeUserRank(StrEnum):
    USER = "user"
    VIEWER = "viewer"  # Stonemason
    REVIEWER = "reviewer"  # Reviewer
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

    @property
    def readable(self) -> str:
        match self:
            case SiegeUserRank.USER:
                return "User"
            case SiegeUserRank.VIEWER:
                return "Stonemason"
            case SiegeUserRank.REVIEWER:
                return "Reviewer"
            case SiegeUserRank.ADMIN:
                return "Admin"
            case SiegeUserRank.SUPER_ADMIN:
                return "Super Admin (Basically Olive)"
            case _:
                return "Unknown"


class SiegeUserStatus(StrEnum):
    WORKING = "working"
    OUT = "out"
    NEW = "new"
    BANNED = "banned"

    @property
    def readable(self) -> str:
        match self:
            case SiegeUserStatus.WORKING:
                return "Working"
            case SiegeUserStatus.OUT:
                return "Out"
            case SiegeUserStatus.NEW:
                return "New"
            case SiegeUserStatus.BANNED:
                return "Banned"
            case _:
                return "Unknown"


@dataclass(frozen=True, eq=True)
class SiegePartialUser:
    id: int
    name: str
    display_name: str

    @classmethod
    def parse(cls, data: dict) -> Self:
        return cls(id=data["id"], name=data["name"], display_name=data["display_name"])


@dataclass(frozen=True, eq=True)
class SiegePartialUser2(SiegePartialUser):  # -> lb
    slack_id: str
    coins: int
    rank: SiegeUserRank

    @classmethod
    def parse(cls, data: dict) -> Self:
        return cls(
            id=data["id"],
            name=data["name"],
            display_name=data["display_name"],
            slack_id=data["slack_id"],
            coins=data["coins"],
            rank=SiegeUserRank(data["rank"]),
        )


@dataclass(frozen=True, eq=True)
class SiegePartialProject:
    id: int
    name: str
    status: ProjectStatus
    created_at: Arrow
    week_badge_text: str

    @property
    def week(self) -> int:
        match = re.match(r"^Week (\d+)$", self.week_badge_text)
        if match:
            return int(match.group(1))
        raise ValueError(
            f"Invalid week_badge_text for project {self.name} ({self.id}) with {self.week_badge_text}"
        )

    @property
    def project_url(self) -> URL:
        return f"https://siege.hackclub.com/armory/{self.id}"

    @property
    def stonemason_review_url(self) -> URL:
        return f"https://siege.hackclub.com/review/projects/{self.id}"

    @classmethod
    def parse(cls, data: dict) -> Self:
        return cls(
            id=data["id"],
            name=data["name"],
            status=ProjectStatus(data["status"]),
            created_at=arrow.get(data["created_at"]),
            week_badge_text=data["week_badge_text"],
        )


@dataclass(frozen=True, eq=True)
class SiegeUser(SiegePartialUser2):
    status: SiegeUserStatus
    created_at: Arrow
    projects: frozenset[SiegePartialProject]

    @classmethod
    def parse(cls, data: dict) -> Self:
        return cls(
            id=data["id"],
            name=data["name"],
            display_name=data["display_name"],
            slack_id=data["slack_id"],
            coins=data["coins"],
            rank=SiegeUserRank(data["rank"]),
            status=SiegeUserStatus(data["status"]),
            created_at=arrow.get(data["created_at"]),
            projects=frozenset(map(SiegePartialProject.parse, data["projects"])),
        )


@dataclass(frozen=True, eq=True)
class SiegeProject(SiegePartialProject):
    description: str
    repo_url: URL
    demo_url: URL
    updated_at: Arrow
    user: SiegePartialUser
    coin_value: float
    is_update: bool

    @property
    def reviewer_url(self) -> URL:
        return f"https://siege.hackclub.com/ysws-review/{self.week}/{self.user.id}"

    @classmethod
    def parse(cls, data: dict) -> Self:
        return cls(
            id=data["id"],
            name=data["name"],
            status=ProjectStatus(data["status"]),
            created_at=arrow.get(data["created_at"]),
            week_badge_text=data["week_badge_text"],
            description=data["description"],
            repo_url=data["repo_url"],
            demo_url=data["demo_url"],
            updated_at=arrow.get(data["updated_at"]),
            user=SiegePartialUser.parse(data["user"]),
            coin_value=data["coin_value"],
            is_update=data["is_update"],
        )
