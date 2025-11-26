## Redacted — W14 Full-Week Live Coding

The live coding event runs for the entirety of Siege W14, from Monday 00:00 ET through Sunday 23:59:59 ET. To qualify for the full-week bonus, the huddle must remain “running” as defined below.

Changes for the W14 event compare to previous live coding:
- Round length is randomized between 20 and 40 minutes (1200–2400 seconds).
- You earn **4 coin per stream**. If the huddle runs continuously for the entire week, **the stream payouts are doubled**.
- Your ticket count is directly tied to your Siege project so please create a project when you start coding (10 ticket for project creation, 1 additional ticket for every 0.1h coded **on your W14 project**)
- You can opt-in or out of the event at any time, however the consecutive-skip limit still applies.

Any Stonemason can manage the stream when available with additional game managers being added as needed.

If there are no stonemason available, the event will pause (until stonemason/other manager join) but **the huddle must still remain active**.

### What counts as “running”:
- The huddle must remain active (If everyone left, thr event end immediately as the huddle will be deleted)
- A Stonemason (or other event manager) able to select the next user with `live.pick.
- If `live.pick` fails, the Stonemason will wait 15 minutes and retry. If no one can be selected after that, the event ends.

### Exceptions
- Slack is unavailable which cause multiple participants cannot connect or are disconnected.
- Widespread or large regional internet outages preventing multiple participants from connecting.
- The bot is down.
- Any other logic error, outage, or unexpected issue that causes the huddle to end.
If an exception occurs:

Start a new huddle in #siege and ping me or (...) to run `live.reloc` so the event points to the new huddle. Huddle ended due to the exceptions do not break the “running” requirement until the huddle is relocated.

## Internal memo
Unless the event have been offically declare to be ended, **do not run `live.end` in any circumstance**

> If you do, please immediately run `live.init` and follow the prompt to restart the event
> 
> If the above doesn't work, ping me to resolve it


<br>


If a user is not recorded by the bot to be in the huddle, ask them to re-join the huddle so the bot can record the event

If the timer didn't pop up after the time ended, run `live.pick` which would show you the button (alternatively it is also in the web dashboard)

Please don't run `live.add_mgr` (if you did, ask Olive/me/One For Freedom/lamalive to run `live.rm_mgr` to remove them)

If you accidentally marked people wrongly, there are currently no way to fix it, please mark it in the internal channel to be handled later

If you encounter any weird behaviour, ping me to have a look (Note that I might not be always available)

Even if `live.pick` was not able to pick anyone, wait for 15 mins. and re-try before declaring the event to be ended.

You are **allowed** to also participate in the event while moderate it (But please don't commit fraud) ^_^
