from dataclasses import dataclass
from enum import StrEnum
from arrow import Arrow
import re

class ProjectStatus(StrEnum):
    BUILDING = "building"
    SUMMITED = "submitted"
    FINISHED = "finished"
    PENDING_VOTING = "pending_voting"
    WAITING_FOR_REVIEW = "waiting_for_review"

type URL = str

# For future reference
# https://github.com/hackclub/siege/blob/2c186ae9f863a73be8dc43b53cdd25127a383b80/app/models/user.rb#L5

class SiegeUserRank(StrEnum):
    USER = "user"
    VIEWER = "viewer" # Stonemason
    REVIEWER = "reviewer" # Reviewer
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class SiegeUserStatus(StrEnum):
    WORKING = "working"
    OUT = "out"
    NEW = "new"
    BANNED = "banned"

@dataclass(frozen=True, eq=True)
class SiegePartialUser:
    id: int
    name: str
    display_name: str
    
@dataclass(frozen=True, eq=True)
class SiegePartialUser2(SiegePartialUser): # -> lb 
    slack_id: str
    coins: int
    rank: SiegeUserRank

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
        raise ValueError(f"Invalid week_badge_text for project {self.name} ({self.id}) with {self.week_badge_text}")

    @property
    def project_url(self) -> URL:
        return f"https://siege.hackclub.com/armory/{self.id}"

    @property
    def stonemason_review_url(self) -> URL:
        return f"https://siege.hackclub.com/review/projects/{self.id}"


@dataclass(frozen=True, eq=True)
class SiegeUser(SiegePartialUser2):
    status: SiegeUserStatus
    created_at: Arrow
    projects: frozenset[SiegePartialProject]


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
    

