import requests
from hackatime.schema.stats import UserData
import logging

def fetch_hackatime_stats(slack_user_id: str) -> UserData | None:
    url = f"https://api.hackatime.com/api/v1/users/{slack_user_id}/stats"
    response = requests.get(url)
    if not response.ok:
        return None
    try:
        data = response.json()
    except:
        logging.warning("Failed to parse JSON response from Hackatime API", exc_info=True)
        return None
    return UserData.parse(data)
    