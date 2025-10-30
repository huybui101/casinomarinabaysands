from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import pytz
from ..models import Game, Bet
from .. import db

betting_bp = Blueprint('betting', __name__)

VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')


def current_round_info():
    now = datetime.now(VN_TZ)
    # Round starts at midnight VN time, each 10 minutes -> index 0..143
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    minutes_since = int((now - midnight).total_seconds() // 60)
    slot = minutes_since // 10
    round_id = now.strftime('%Y%m%d') + f"{slot:03d}"
    # time remaining until next 10-min boundary
    next_slot_minute = ((slot + 1) * 10)
    next_time = midnight + timedelta(minutes=next_slot_minute)
    remaining = int((next_time - now).total_seconds())
    next_round_id = now.strftime('%Y%m%d') + f"{(slot+1):03d}"
    return round_id, remaining, slot, next_round_id


@betting_bp.route('/bet/<game_key>', methods=['GET', 'POST'])
@login_required
def bet_page(game_key):
    game = Game.query.filter_by(key=game_key).first_or_404()
    round_id, remaining, slot, next_round_id = current_round_info()

    # Define betting pairs and odds mapping per UI spec
    # Allow per-user override of primary/secondary odds
    user_primary = current_user.override_odds_primary if getattr(current_user, 'override_odds_primary', None) is not None else game.odds_primary
    user_secondary = current_user.override_odds_secondary if getattr(current_user, 'override_odds_secondary', None) is not None else game.odds_secondary

    # Format odds as strings without trailing zeros (server-side guarantee for display)
    def fmt_odds(v: float) -> str:
        try:
            return (f"{float(v):.2f}".rstrip('0').rstrip('.'))
        except Exception:
            return str(v)

    pairs = [
        [("LỚN", fmt_odds(user_primary)), ("NHỎ", fmt_odds(user_primary))],
        [("LỚN TO", fmt_odds(user_secondary)), ("NHỎ BÉ", fmt_odds(user_secondary))],
        [("SỔ XỐ TO", fmt_odds(4.2)), ("SỔ XỐ NHỎ", fmt_odds(4.6))],
        [("CON TO", fmt_odds(4.2)), ("CON NHỎ", fmt_odds(4.6))],
        [("NÓNG", fmt_odds(4.6)), ("LẠNH", fmt_odds(4.2))],
    ]
    triplet = [("LÀN SÓNG ĐỎ", fmt_odds(2.8)), ("LÀN SÓNG XANH", fmt_odds(2.9)), ("LÀN SÓNG TÍM", fmt_odds(2.9))]

    odds_map = {label: odds for row in pairs for (label, odds) in row}
    odds_map.update({label: odds for (label, odds) in triplet})
    # Build mapping label -> pair id (row index) for server-side validation
    pair_map = {}
    for idx, row in enumerate(pairs):
        pair_map[row[0][0]] = str(idx)
        pair_map[row[1][0]] = str(idx)
    for label, _ in triplet:
        pair_map[label] = 'waves'

    if request.method == 'POST':
        from flask import flash
        selections = request.form.getlist('selection')
        try:
            stake = float(request.form.get('stake') or 0)
        except Exception:
            stake = 0
        # Validate selections: must be within same row (pair) and 1..2 options
        if len(selections) == 0:
            flash('Vui lòng chọn ít nhất 1 cửa (tối đa 2 cửa)', 'danger')
            return redirect(url_for('betting.bet_page', game_key=game_key))
        if len(selections) > 2:
            flash('Chỉ được chọn tối đa 2 cửa cho mỗi vé', 'danger')
            return redirect(url_for('betting.bet_page', game_key=game_key))
        # All selections must belong to same pair id
        pair_ids = { pair_map.get(sel, 'unknown') for sel in selections }
        if len(pair_ids) != 1:
            flash('Chỉ được đặt trong cùng một hàng (1 cặp). Không được đặt dọc/khác hàng.', 'danger')
            return redirect(url_for('betting.bet_page', game_key=game_key))
        if stake <= 0:
            flash('Vui lòng nhập số tiền hợp lệ', 'danger')
            return redirect(url_for('betting.bet_page', game_key=game_key))
        # Check balance per selection (stake counts per cửa)
        total_needed = stake * len(selections)
        if current_user.balance < total_needed:
            flash('Số dư không đủ', 'danger')
            return redirect(url_for('betting.bet_page', game_key=game_key))
        # Deduct and create one Bet per selection
        current_user.balance -= total_needed
        for sel in selections:
            # Convert back to float for calculation if stored as formatted string
            odds = float(odds_map.get(sel, game.odds_primary))
            b = Bet(user_id=current_user.id, game_id=game.id, round_id=round_id, selection=sel, stake=stake, odds=odds, result='PENDING')
            db.session.add(b)
        db.session.commit()
        flash('Đặt cược thành công', 'success')
        return redirect(url_for('main.history_bets'))

    return render_template(
        'main/bet_page.html',
        game=game,
        round_id=round_id,
        remaining=remaining,
        slot=slot,
        next_round_id=next_round_id,
        pairs=pairs,
        triplet=triplet,
        hide_logout=True,
        hide_balance=True,
        page_title=game.name_vi,
    )
