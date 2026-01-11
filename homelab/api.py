import requests, logging
from homelab.schema.project import Project, SimpleUser, User

type UserId = int | str
type UserAlike = UserId | Project | SimpleUser
type ProjId = int
type ProjAlike = Project | ProjId


def _as_user(user: UserAlike) -> UserId:
    if isinstance(user, int):
        return user
    elif isinstance(user, Project):
        return user.user.id
    elif isinstance(user, SimpleUser):
        return user.id
    return user

def _as_project(project: ProjAlike) -> ProjId:
    if isinstance(project, Project):
        return project.proj_id
    return project

def get_all_projs() -> list[Project]:
    url = "https://homelab.hackclub.com/api/projects"
    response = requests.get(url)
    logging.info(f"GET {url} {response.status_code}")
    data = response.json().get("projects", [])
    return list(map(Project.parse, data))
