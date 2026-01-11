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

def get_user(user_id: UserAlike) -> User | None:
    user_id = _as_user(user_id)
    projects = get_all_projs()
    def filter_fn(proj: Project):
        return proj.user.id == user_id or proj.user.slack_id == user_id
    filtered = list(filter(filter_fn, projects))
    total_s = sum(map(lambda x: x.time_s, filtered))
    if not projects:
        return None
    hl_id = projects[0].user.id
    slack_id = projects[0].user.slack_id
    return User(id=hl_id, slack_id=slack_id, total_time_s=total_s, projects=filtered)

def get_project(proj_id: ProjAlike) -> Project:
    proj_id = _as_project(proj_id)
    projects = get_all_projs()
    def filter_fn(proj: Project):
        return proj.proj_id == proj_id
    filtered = list(filter(filter_fn, projects))
    if not filtered:
        raise ValueError(f"Project {proj_id} not found")
    return filtered[0]