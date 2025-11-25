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

### Main change for W12
- File upload support in framework `Context`
- Built a bunch of graph
- REDACTED
Check `changelist/CHANGE_LIST_W12.md` for full list

### How does it follow the framework theme
The bot is built based upon a custom slack bot framework which is more useful than slack-bolt in some aspect (built with `slack-sdk` and `blockkit`), which support
- Huddle event
- Message event
- Interaction
- File sending (Which slack bolt is bad at, literally didn't even mention it in docs from what I can find)
with a custom permission system.
This can be used to make other slack bot (given you don't need other capability) by:
Copying `main.py`(Bot launchor with the module loader), `config.py`(Config loader), `utils.py`(Permission decorator based on context namespace), `reg.py`(Command decorator // `Context` which provide a unified interaction interface to send message public/privately, between message/slash command and interaction) and `schema/`(All the different slack schema for this limited subsrt of capability)
(Side noteL even the platform is made agnositic right now, and the specific implementation is described in `slack/`, (or `irc/` which is WIP for W13))

There is also a different, more specific framework, which is in the live module (yes, framework in a framework), which allow custom behaviour of a live coding event and can be customized entirely (See `impl/live_blank.py` and `impl/siege.py`, which one just give everyone a single ticket while in siege is based on the coding time during the huddle)

### Demo?
I prefer you test on Slack instead, it would take same amount of time to a demo video, and just start a empty huddle, for the better experience :)
If you are lazy like me, check the image below:

<img width="558" height="806" alt="w6" src="https://github.com/user-attachments/assets/4cde9022-2973-4cba-9344-bdf8dc0c3a56" />

<img width="686" height="530" alt="5a37783ff5996b718d1a51313156194800138354bcad4a3aff476d9eba41c3c2" src="https://github.com/user-attachments/assets/c1cd0e96-7316-47c9-955f-97d004ac2c48" />

<img src="https://github.com/user-attachments/files/23173993/clipboard_2025-10-27_21-43.bmp">

<img width="1426" height="1414" alt="224e139aaff22a0dba354487b8b45ad14070eff3c2f97c403c9f9490109ad5fb" src="https://github.com/user-attachments/assets/2cdeb755-d037-4b39-8393-05972b3f41c3" />

<img src="https://github.com/user-attachments/files/23443113/clipboard_2025-11-09_23-44.bmp">

<img width="958" height="1340" alt="8380a6f9fedf1e5e99b357dde5dac8f3dac5240e0ca7eae6b68df95f4c4ef534" src="https://github.com/user-attachments/assets/30bd79bc-ab00-4a0f-b134-7d25698b3b71" />

<img width="1210" height="828" alt="c9a2f0ded73813c9e79febc35faa035f62c332bc59b253b15fb0c1ffff2054a4" src="https://github.com/user-attachments/assets/5183eb9d-99b1-4bd2-924b-cdab355cadfd" />

<img width="680" height="734" alt="752151953d7aba0b4a9d0752b3da270fb1508d60697856987e556d3ec6d6d8f4" src="https://github.com/user-attachments/assets/49878059-6f0c-4b04-86c1-618d6ea8a727" />

(Idk why some of the background got significantly whiter than it actually is)

