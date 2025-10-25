from api import get_all_projs

def guess_week() -> int:
    projs = get_all_projs()
    max_week_num = max(projs, key=lambda p:p.week).week
    return max_week_num