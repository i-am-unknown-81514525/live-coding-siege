from slack.client import SlackClient

def get_profile_picture(user_id: str, client: SlackClient) -> str | None:
    try:
        user_info = client.client.web_client.users_profile_get(user=user_id).data
        if not isinstance(user_info, dict):
            return None
        return user_info.get("profile", {}).get("image_1024")
    except:
        return None
