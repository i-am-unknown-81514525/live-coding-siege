from dataclasses import dataclass
from enum import StrEnum
from arrow import Arrow
import arrow

@dataclass(frozen=True)
class SimpleUser:
    slack_id: str
    id: int

    @classmethod
    def parse(cls, data: dict):
        return cls(slack_id=data["slack_id"], id=data["user_id"])

class ProjectStatus(StrEnum):
    BUILDING = "Building"
    SHIPPED = "Shipped"
    PENDING = "Pending Review"

def defmt_time(span: str) -> int:
    h, m, s = map(int, span.split(":"))
    return h * 3600 + m * 60 + s


@dataclass(frozen=True)
class Project:
    created_at: Arrow
    demo_link: str
    description: str
    time_s: int
    github_link: str 
    hackatime_project: str
    proj_id: int
    title: str
    status: ProjectStatus
    user: SimpleUser

    @classmethod
    def parse(cls, data: dict):
        return cls(
            created_at=arrow.get(data["created_at"]),
            demo_link=data["demo_link"],
            description=data["description"],
            time_s=defmt_time(data["digital_hours"]),
            github_link=data["github_link"],
            hackatime_project=data["hackatime_project"],
            proj_id=data["id"],
            title=data["title"],
            status=ProjectStatus(data["status"]),
            user=SimpleUser.parse(data)
        )

@dataclass(frozen=True)
class User(SimpleUser):
    projects: list[Project]
    total_time_s: int