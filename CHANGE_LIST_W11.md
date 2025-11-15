[x] - Setup schema for siege project logging
[ ] - Task loop to auto fetch update for projects and user (5m/projs request // 10s/user request weighted by 1.3**(k-1) for each project where k is the project week)
[ ] - `siege.summary` for the summary of work done during the time
[ ] - Modulise the siege part out of live coding 
[ ] - Remove magical theme if necessary (?)
[ ] - Attempt to connect live coding to hackatime server for generic live coding 
[ ] - Rewrite live coding database schema to remove siege/YSWS specific reference - should only track the ticket hold for each user
[ ] - Put hour tracking on siege database
[ ] - Check and fix more rounding issue
[ ] - Post project change in a separate channel which can be publicly searchable like som bulletin
[ ] - `siege.shop` ???? (idk if it even necessary but well, it is an api so I must use it)
[ ] - `siege.user_search` for user searching
[ ] - Improve the timer system?
[ ] - Convert `SIEGE_MODE` to something handled by per game instance
[ ] - Fix random after doing a statistical analysis of the current one
[ ] - Transaction web page + server (address apce)
[x] - decorator for permission check
[x] - `Context` for interaction
[ ] - Slack client transfer to web API so a message is sent on accept/reject
[ ] - `live.add_mgr all` for all allowed user
[ ] - `live.transaction`
[ ] - Fix prefix command get recognised as link
[x] - `no_prefix` change to `value` in favuor for `Context` for interaction
[ ] - `siege.define` / `/define` - get dictionary definition of word