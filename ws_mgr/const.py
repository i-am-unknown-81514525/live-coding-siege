from . import signals

ws_mgr_broadcast: signals.Broadcast = signals.ROOT.create_sub_broadcast("ws_mgr")
