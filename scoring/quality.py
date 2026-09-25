"""Quality filter for value-bets (anti-noise)."""

MIN_EV = 0.03
MAX_EV = 0.25
MIN_KELLY = 0.005
MAX_KELLY = 0.03
MAX_BK_DIVERGENCE = 0.25


def is_high_quality_value(vb, event_odds_by_bk=None):
    ev = getattr(vb, "ev", None)
    if ev is None:
        return False, "no_ev"
    if ev < MIN_EV:
        return False, f"ev_low:{ev:.3f}"
    if ev > MAX_EV:
        return False, f"ev_high:{ev:.3f}"

    kelly = getattr(vb, "kelly", None)
    if kelly is None:
        return False, "no_kelly"
    if kelly < MIN_KELLY:
        return False, f"kelly_low:{kelly:.4f}"
    if kelly > MAX_KELLY:
        return False, f"kelly_high:{kelly:.4f}"

    if event_odds_by_bk:
        vals = [v for v in event_odds_by_bk.values() if v]
        if len(vals) >= 2:
            vmin, vmax = min(vals), max(vals)
            if vmin > 0 and (vmax - vmin) / vmin > MAX_BK_DIVERGENCE:
                return False, "bk_divergence"

    return True, "ok"


def filter_value_bets(vbs):
    out = []
    for vb in vbs:
        passed, _ = is_high_quality_value(vb)
        if passed:
            out.append(vb)
    return out
