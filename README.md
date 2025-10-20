### LiveCoding

---

LiveCoding huddle event bot for Siege & Siege W6(and 7) project

### What does it do?

It handle all the countdown and user selection process for the entire huddle event (For detail of the entire event rules, check [rule.md](./rule.md))

### How to setup the bot

Oh god it is complex
First made a bot
Next, enable socket mode, the bot, slach command, interactive, enough OAuth that allow it to chat and listen to user huddle status change (I don't remember everything... Gl ig? Check the manifest instead in `manifest.json`)
Put these in `.env`, how to get them? Somewhere in the dashboard I already forgot :>

```env
SLACK_CLIENT_SECRET=
SLACK_SIGN_SECRET=
SLACK_CLIENT_ID=
SLACK_APP_ID=
SLACK_APP_LEVEL_TOKEN=
SLACK_BOT_OAUTH_TOKEN=
```

Yep I think most of them but not all is necessary :)

Other
```env
JWT_SECRET= # for web dashboard
AUTHORIZED_USERS= # comma seperated list of user id that have special ability
ALLOWLIST= # comman seperated list of user id that can start a show
SIEGE_MODE=1 # Soon - it would query the user on siege API. Only user with a existing project would be selected, checked on each pick. The hour coded since game started/join is also tracked, checked on each pick for ticket count.
```

Optionally
```env
RIG=1
```
This would set so anyone can run `live.init` with no restriction, and also the run time would be < 3 minutes

Do `docker compose up -d --build` to start with docker setup, or `uv run main.py`

### How to use
You do `live.init` to start a show, and then use `live.pick` to pick a user, use `live.end` to fianlly end the entirely event. The rest should be fairly intuative, just click the correct button for the rule specified.
As a game manager, you can use `live.mgr_secret` to get the JWT secret for dashboard on https://livecode.relay7f98.us.to/ (or `http://127.0.0.1:13724` when run locally)

### Public command list

`live.init` - Start a game show \[Only allowlist user or authorised user\]

`live.pick` - Bot pick a user to do a new turn, or show status if started 

`live.rnd` - Pick a different server secret

`live.turn` - Get turn information

`live.eligible` - List of user for the next turn

`live.members` - List of all user in the huddle

`live.optout` - Optout from the event

`live.reject` - Reject a turn

`live.add_mgr` - Add a game manager 

`live.leave` - Remove yourself as a game manager

`live.force_leave` - Remove yourself as a game manager, and also end the event if you are the only manager

`live.summary` - Generate a summary for the game

`live.export` - Export the status to Olive (for dispatching coins)

`live.end` - End the event


### How does it follow the signal theme
Websocket, Slack Bot, *Live*Coding

### Demo?
I prefer you test on Slack instead, it would take same amount of time to a demo video, and just start a empty huddle, for the better experience :)
If you are lazy like me, check the image below:

<img width="558" height="806" alt="w6" src="https://github.com/user-attachments/assets/4cde9022-2973-4cba-9344-bdf8dc0c3a56" />

<img width="686" height="530" alt="5a37783ff5996b718d1a51313156194800138354bcad4a3aff476d9eba41c3c2" src="https://github.com/user-attachments/assets/c1cd0e96-7316-47c9-955f-97d004ac2c48" />

(Idk why the background got significantly whiter than it actually is)

