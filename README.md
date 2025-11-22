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
CONFIG_FILE=config.toml # Optional default to `config.toml`, can be change to point to different config

REMIND_CHANNEL=
REMIND_THREAD=
REMIND_USER=
UPLOAD_CHANNEL= # A public channel for uploads
```

Do `docker compose up -d --build` to start with docker setup, or `uv run main.py`

### How to use
You do `live.init` to start a show, and then use `live.pick` to pick a user, use `live.end` to fianlly end the entirely event. The rest should be fairly intuative, just click the correct button for the rule specified.
As a game manager, you can use `live.mgr_secret` to get the JWT secret for dashboard on https://livecode.relay7f98.us.to/ (or `http://127.0.0.1:13724` when run locally)

### Public command list
Use `siege.helps` or `/help` for the full list

### Main change for W11
- Rewrite permission system to indivdual group based on namespaces
- Code refactor for better permission check
- Track all change via Siege API to allow live coding event to get all project time on event start instead of their join time, to be more fair
- `siege.shop`, `siege.user_details` and `siege.proj_details`

### How does it follow the space theme
Every module is rewritten to separate to their own space, with isolated access space for each user (see `config.toml`, `live_blank.py` and `siege.py`)
This is mostly backend however, and It would be fair to reject this

### Demo?
I prefer you test on Slack instead, it would take same amount of time to a demo video, and just start a empty huddle, for the better experience :)
If you are lazy like me, check the image below:

<img width="558" height="806" alt="w6" src="https://github.com/user-attachments/assets/4cde9022-2973-4cba-9344-bdf8dc0c3a56" />

<img width="686" height="530" alt="5a37783ff5996b718d1a51313156194800138354bcad4a3aff476d9eba41c3c2" src="https://github.com/user-attachments/assets/c1cd0e96-7316-47c9-955f-97d004ac2c48" />

<img src="https://github.com/user-attachments/files/23173993/clipboard_2025-10-27_21-43.bmp">

<img width="1426" height="1414" alt="224e139aaff22a0dba354487b8b45ad14070eff3c2f97c403c9f9490109ad5fb" src="https://github.com/user-attachments/assets/2cdeb755-d037-4b39-8393-05972b3f41c3" />

<img src="https://github.com/user-attachments/files/23443113/clipboard_2025-11-09_23-44.bmp">

<img width="958" height="1340" alt="8380a6f9fedf1e5e99b357dde5dac8f3dac5240e0ca7eae6b68df95f4c4ef534" src="https://github.com/user-attachments/assets/30bd79bc-ab00-4a0f-b134-7d25698b3b71" />

(Idk why some of the background got significantly whiter than it actually is)

