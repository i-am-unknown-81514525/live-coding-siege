from slack_sdk.web import WebClient
from slack.schema.user import User
import logging


def get_user_info(client: WebClient, user_id: str) -> User:
    response = client.users_info(user=user_id)

    if not response["ok"]:
        raise ValueError(f"Failed to fetch user: {response['error']}")
    return User.parse(response.data["user"]) # type: ignore