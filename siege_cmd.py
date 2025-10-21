from reg import action_listen, action_prefix_listen, smart_msg_listen, MessageContext
import blockkit
from api import get_project, get_user
import re
from schema.interactive import BlockActionEvent
from slack_sdk.web import WebClient
import logging

@smart_msg_listen("siege.user")
def get_siege_user_info(ctx: MessageContext):
    user_id = ctx.event.message.user
    left_over = ctx.event.message.text.removeprefix("siege.user").strip()
    if left_over:
        if re.match(r"<@(U\w+)>", left_over):
            user_id = left_over.removeprefix("<@").removesuffix(">")
        else:
            user_id = left_over

    user = get_user(user_id)
    
    proj_list = [(proj.week, proj.id, proj.name) for proj in user.projects]

    buttons : list = [
            blockkit.Button(f"W{item[0]} - {item[2]}").value(str(item[1])).action_id(f"siege_proj_view_{item[0]}") for item in sorted(proj_list, key=lambda x: x[0])
        ]

    message = blockkit.Message().add_block(
        blockkit.Section(f"""*User info:*
*Slack ID:* `{user.slack_id}`
*User ID:* `{user.id}`
*Name:* {user.name}
*Display Name:* {user.display_name}
*Coins:* {user.coins}
*Rank:* {user.rank.readable}
*Status:* {user.status.readable}""")
    )

    if buttons:
        message.add_block(blockkit.Actions(buttons))


    ctx.public_send(
        **message.build()
    )

@action_prefix_listen("siege_proj_view")
def handle_siege_proj_view(event: BlockActionEvent, client: WebClient):
    v = event.actions[0].value
    if not v:
        logging.warning("siege_proj_view missing project id")
        return
    proj_id = int(v)
    proj = get_project(proj_id)

    channel = event.container.channel_id
    thread_ts = event.message.thread_ts if event.message else None


    kv = [("Project Page", proj.project_url), ("Repo", proj.repo_url), ("Demo", proj.demo_url), ("Stonemason Page", proj.stonemason_review_url), ("Reviewer Page", proj.reviewer_url)]

    client.chat_postMessage(
        channel=channel, 
        thread_ts=thread_ts,
        **blockkit.Message()
        .add_block(
            blockkit.Section(f"""*Week {proj.week} - {proj.name}*
*ID:* `{proj.id}`
*Status:* {proj.status.readable}
*Created At:* {proj.created_at.format('YYYY-MM-DD HH:mm:ss')}
*Description:* {proj.description}
*Coin Value:* {proj.coin_value or "N/A"}
"""         )
        )
        .add_block(
            blockkit.Actions(
                [
                    blockkit.Button(k).url(v)
                    for k, v in kv
                    if v
                ]
            )
        ).build()
    )