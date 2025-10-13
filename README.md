### LiveCoding

---

LiveCoding huddle event bot for Siege & Siege W6(and 7?) project

### What does it do?

It handle all the countdown and user selection process for the entire huddle event (For detail of the entire event rules, check [rule.md](./rule.md))

### How to setup the bot

Oh god it is complex
First made a bot
Next, enable socket mode, the bot, slach command, interactive, enough OAuth that allow it to chat and listen to user huddle status change (I don't remember everything... Gl ig?)
Put these in `.env`, how to get them? Somewhere in the dashboard I already forgot :)

```env
SLACK_CLIENT_SECRET=
SLACK_SIGN_SECRET=
SLACK_CLIENT_ID=
SLACK_APP_ID=
SLACK_APP_LEVEL_TOKEN=
SLACK_BOT_OAUTH_TOKEN=
```

Yep I think most of them but not all is necessary :)

Optionally
```env
RIG=1
```

This would set so anyone can run live.init with no restriction, and also the run time would be < 3 minutes

Do `uv run main.py`

### How to use
Go to siege channel and start a huddle, and do `live.init` (It should have `RIG` enabled to allow you test it, unless I am hosting one and forgot to turn it back on)

### How is it magical
I have made basically all user visible message magic theme like :) (Idk if that count)

### Demo?
I prefer you test on Slack instead, it would take same amount of time to a demo video, and just start a empty huddle, for the better experience :)
If you are lazy like me, check the image below:

[clipboard_2025-10-13_22-20.bmp](https://github.com/user-attachments/files/22893303/clipboard_2025-10-13_22-20.bmp)
