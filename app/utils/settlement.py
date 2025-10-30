import json
import hashlib
from datetime import datetime, timedelta
import pytz
from typing import Dict, Tuple
from .. import db
from ..models import Bet, Game, User, RoundResult

VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Canonical labels used across the app. Keep in sync with betting UI.
PAIR_LABELS = [
    ("LỚN", "NHỎ"),
    ("LỚN TO", "NHỎ BÉ"),
    ("SỔ XỐ TO", "SỔ XỐ NHỎ"),
    ("CON TO", "CON NHỎ"),
    ("NÓNG", "LẠNH"),
]
WAVE_LABELS = ("LÀN SÓNG ĐỎ", "LÀN SÓNG XANH", "LÀN SÓNG TÍM")


def round_end_time(round_id: str) -> datetime:
    """Given round_id like YYYYMMDDSSS (slot index), return VN time end timestamp."""
    date_part = round_id[:8]
    slot = int(round_id[-3:])
    day = datetime.strptime(date_part, '%Y%m%d')
    day = VN_TZ.localize(day)
    end_time = day + timedelta(minutes=(slot + 1) * 10)
    return end_time


def _hash_to_int(secret: str, round_id: str, salt: str) -> int:
    h = hashlib.sha256((secret + '|' + round_id + '|' + salt).encode('utf-8')).hexdigest()
    return int(h[:16], 16)


def compute_winners(app_secret: str, round_id: str) -> Dict:
    """Deterministically compute winners for all groups based on secret and round_id.
    Returns a structure {"pairs": {"0": "LỚN", ...}, "waves": "LÀN SÓNG ĐỎ"}
    """
    winners: Dict[str, Dict[str, str]] = {"pairs": {}}
    # Pairs: choose side 0/1 per pair via independent hashes
    for idx, pair in enumerate(PAIR_LABELS):
        n = _hash_to_int(app_secret, round_id, f"pair-{idx}")
        side = n % 2
        winners["pairs"][str(idx)] = pair[side]
    # Waves: 3 outcomes
    n = _hash_to_int(app_secret, round_id, "waves")
    winners["waves"] = WAVE_LABELS[n % 3]
    return winners


def ensure_round_result(app_secret: str, round_id: str) -> RoundResult:
    rr = RoundResult.query.filter_by(round_id=round_id).first()
    if rr:
        return rr
    data = compute_winners(app_secret, round_id)
    rr = RoundResult(round_id=round_id, result_json=json.dumps(data, ensure_ascii=False), settled=False)
    db.session.add(rr)
    db.session.commit()
    return rr


def settle_due_rounds(app_secret: str):
    """Settle all PENDING bets whose round has ended. Idempotent by relying on deterministic winners.
    This will also create a RoundResult row if missing.
    """
    now_vn = datetime.now(VN_TZ)
    # distinct round ids with pending bets
    round_ids = [r[0] for r in db.session.query(Bet.round_id).filter(Bet.result == 'PENDING').distinct().all()]
    for rid in round_ids:
        try:
            if round_end_time(rid) > now_vn:
                continue
        except Exception:
            # If round_id malformed, settle anyway with deterministic fallback
            pass
        rr = ensure_round_result(app_secret, rid)
        winners = json.loads(rr.result_json)
        pair_winners = winners.get('pairs', {})
        waves_winner = winners.get('waves')

        # Build label->group index mapping to know if a selection is pair or wave
        label_to_group: Dict[str, Tuple[str, str]] = {}
        for idx, (a, b) in enumerate(PAIR_LABELS):
            label_to_group[a] = ('pair', str(idx))
            label_to_group[b] = ('pair', str(idx))
        for l in WAVE_LABELS:
            label_to_group[l] = ('waves', 'waves')

        pending = Bet.query.filter_by(round_id=rid, result='PENDING').all()
        if not pending:
            rr.settled = True
            db.session.commit()
            continue

        # Cache users to minimize queries
        users_cache: Dict[int, User] = {}

        for b in pending:
            gtype, gid = label_to_group.get(b.selection, ('pair', '0'))
            winning_label = pair_winners.get(gid) if gtype == 'pair' else waves_winner
            if b.selection == winning_label:
                b.result = 'WIN'
                b.payout = float(b.stake * b.odds)
                # credit user
                user = users_cache.get(b.user_id) or User.query.get(b.user_id)
                users_cache[b.user_id] = user
                if user:
                    user.balance += b.payout
                    # Track pnl as net profit: payout - stake
                    try:
                        user.pnl = float((user.pnl or 0.0) + (b.payout - b.stake))
                        user.income = float((user.income or 0.0) + max(b.payout - b.stake, 0.0))
                    except Exception:
                        pass
            else:
                b.result = 'LOSE'
                b.payout = 0.0
                user = users_cache.get(b.user_id) or User.query.get(b.user_id)
                users_cache[b.user_id] = user
                if user:
                    try:
                        user.pnl = float((user.pnl or 0.0) - b.stake)
                    except Exception:
                        pass
        rr.settled = True
        db.session.commit()

