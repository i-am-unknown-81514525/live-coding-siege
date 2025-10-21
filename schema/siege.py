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


@dataclass(frozen=True, eq=True)
class SiegePartialUser:
    id: int
    name: str
    display_name: str
    
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


@dataclass(frozen=True, eq=True)
class SiegeProject(SiegePartialProject):
    description: str 
    repo_url: URL
    demo_url: URL
    updated_at: Arrow
    user: SiegePartialUser
    coin_value: float
    is_update: bool
    

