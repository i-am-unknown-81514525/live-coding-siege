import requests
import json
from schema.siege import SiegePartialProject, SiegePartialUser, SiegePartialUser2, SiegeProject, SiegeUser, SiegeUserRank, SiegeUserStatus

def get_user(user_id: str | int):
    url = f"https://siege.hackclub.com/api/public-beta/user/{user_id}" # https://siege.hackclub.com/api/public-beta/user/U084PTWSWR5
    response = requests.get(url)
    data = response.json()


