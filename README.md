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
Do `uv run main.py`

### How to use
Go to siege channel and start a huddle, and do `live.init`

### How is it magical
I have made basically all user visible message magic theme like :) (Idk if that count)

### Demo vid
TBD
