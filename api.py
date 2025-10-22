import requests
import json
from schema.siege import (
    SiegePartialUser2,
    SiegeProject,
    SiegeUser,
    SiegePartialProject,
    SiegePartialUser,
)
import bs4, re, os

type UserId = int | str
type UserAlike = UserId | SiegeProject | SiegePartialUser
type ProjId = int
type ProjAlike = SiegePartialProject | ProjId


def _as_user(user: UserAlike) -> UserId:
    if isinstance(user, int):
        return user
    elif isinstance(user, SiegeProject):
        return user.user.id
    elif isinstance(user, SiegePartialUser):
        return user.id
    return user


def _as_project(project: ProjAlike) -> ProjId:
    if isinstance(project, SiegePartialProject):
        return project.id
    return project


def get_user(user_id: UserAlike) -> SiegeUser:
    user_id = _as_user(user_id)
    url = f"https://siege.hackclub.com/api/public-beta/user/{user_id}"  # https://siege.hackclub.com/api/public-beta/user/138
    response = requests.get(url)
    data = response.json()
    return SiegeUser.parse(data)


def get_project(project_id: ProjAlike) -> SiegeProject:
    project_id = _as_project(project_id)
    url = f"https://siege.hackclub.com/api/public-beta/project/{project_id}"  # https://siege.hackclub.com/api/public-beta/project/1262
    response = requests.get(url)
    data = response.json()
    return SiegeProject.parse(data)


def get_coin_leaderboard() -> list[SiegePartialUser2]:
    url = "https://siege.hackclub.com/api/public-beta/leaderboard"
    response = requests.get(url)
    data = response.json()
    return list(map(SiegePartialUser2.parse, data.get("leaderboard", [])))


# def get_project_time(project: ProjAlike) -> float: # Useless 
#     project_id = _as_project(project)
#     url = f"https://siege.hackclub.com/api/project_hours/{project_id}"  # https://siege.hackclub.com/api/project_hours/1262
#     response = requests.get(url)
#     data = response.json()
#     return data.get("hours", 0.0)

def get_project_time_prec(project: ProjAlike) -> float:
    project_id = _as_project(project)
    url = f"https://siege.hackclub.com/armory/{project_id}"
    response = requests.get(url, cookies={"_siege_session": os.environ["SIEGE_SESSION"]})
    if not response.ok:
        raise ValueError(f"Armory link return error with status {response.status_code}, proj_id={project_id}")
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    ele = soup.find("div", {"class": "project-week-time"})
    if ele is None:
        raise ValueError(f"Cannot find project-week-time class, proj_id={project_id}")
    raw_text = ele.get_text().strip().removeprefix("Time spent: ").strip()
    result = re.match(r"(?:(\d*)h)? (?:(\d*)m)?", raw_text)
    if result is None:
        raise ValueError(f"Cannot find project time infomation, content=\"{raw_text}\"")
    return int(result.group(1)) + int(result.group(2)) / 60


def get_all_projs() -> list[SiegeProject]:
    url = "https://siege.hackclub.com/api/public-beta/projects"
    response = requests.get(url)
    data = response.json().get("projects", [])
    return list(map(SiegeProject.parse, data))