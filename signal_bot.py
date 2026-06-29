import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
import json

# â”€â”€â”€ CONFIG â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
API_KEY        = os.environ.get("TWELVE_DATA_API_KEY")
GMAIL_USER     = "gonahcharo1993@gmail.com"
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

FOREX_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
               "USD/CAD", "AUD/USD", "NZD/USD"]
GOLD_PAIR   = "XAU/USD"
ALL_PAIRS   = FOREX_PAIRS + [GOLD_PAIR]

FOREX_SL_PIPS  = 15
GOLD_SL_MIN    = 60
GOLD_SL_MAX    = 150
FIB_GOLDEN_MIN = 0.618
FIB_GOLDEN_MAX = 0.705
MIN_ALIGNMENT  = 4   # minimum levels aligned to fire signal

# â”€â”€â”€ EMAIL â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From']    = GMAIL_USER
        msg['To']      = GMAIL_USER
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.starttls()
        s.login(GMAIL_USER, GMAIL_PASSWORD)
        s.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        s.quit()
        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"Email error: {e}")

# â”€â”€â”€ TWELVE DATA â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def fetch_candles(symbol, interval, outputsize=100):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol":     symbol,
        "interval":   interval,
        "outputsize": outputsize,
        "apikey":     API_KEY,
        "format":     "JSON"
    }
    try:
        r    = requests.get(url, params=params, timeout=15)
        data = r.json()
        if "values" not in data:
            print(f"  No data {symbol} {interval}: {data.get('message','')}")
            return []
        candles = []
        for v in reversed(data["values"]):
            candles.append({
                "time":  v["datetime"],
                "open":  float(v["open"]),
                "high":  float(v["high"]),
                "low":   float(v["low"]),
                "close": float(v["close"])
            })
        return candles
    except Exception as e:
        print(f"  Fetch error {symbol} {interval}: {e}")
        return []

def fetch_price(symbol):
    try:
        r    = requests.get("https://api.twelvedata.com/price",
                            params={"symbol": symbol, "apikey": API_KEY}, timeout=10)
        data = r.json()
        return float(data.get("price", 0))
    except:
        return 0.0

# â”€â”€â”€ QUARTERLY THEORY â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def get_yearly_quarter(month):
    return (month - 1) // 3 + 1   # Q1=Jan-Mar â€¦ Q4=Oct-Dec

def get_monthly_quarter(day):
    return min((day - 1) // 7 + 1, 4)   # Q1=days1-7 â€¦ Q4=days22+

def get_weekly_quarter(weekday):
    # Mon=0â€¦Thu=3 â†’ Q1â€¦Q4  (Fri=4 skipped)
    return weekday + 1 if weekday < 4 else None

def get_session_info(hour):
    """Return session name, quarter number, and 90-min cycle details."""
    sessions = [
        {"name": "Asian",        "start": 0,  "end": 6},
        {"name": "London",       "start": 6,  "end": 12},
        {"name": "New York AM",  "start": 12, "end": 18},
        {"name": "New York PM",  "start": 18, "end": 24},
    ]
    for s in sessions:
        if s["start"] <= hour < s["end"]:
            elapsed_minutes = (hour - s["start"]) * 60
            cycle_num   = elapsed_minutes // 90 + 1   # 1-4
            within_cycle = elapsed_minutes % 90
            # True session open = open of Q2 of session
            session_q2_hour = s["start"] + (90 / 60)   # 1.5 hours in
            # True 90-min open = open of Q2 of current cycle
            cycle_start_hour = s["start"] + ((cycle_num - 1) * 1.5)
            cycle_q2_hour    = cycle_start_hour + (90 / 60 / 2)  # 45 min in
            return {
                "name":            s["name"],
                "start":           s["start"],
                "end":             s["end"],
                "session_q":       cycle_num,         # which 90-min we're in (1-4)
                "within_cycle_min": within_cycle,
                "cycle_start_hour": cycle_start_hour,
                "session_q2_hour": session_q2_hour,
                "cycle_q2_hour":   cycle_q2_hour,
                "is_q1":           cycle_num == 1,
            }
    return None

def detect_xamd_amdx(q1_candles, htf_bias):
    """
    Option C: HTF bias + Q1 behaviour combined.
    q1_candles: candles from Q1 of current period
    htf_bias: 'bullish' or 'bearish'
    Returns: 'XAMD' or 'AMDX', q1_phase
    """
    if not q1_candles:
        return "UNKNOWN", "?"

    # Measure Q1 range vs body
    highs  = [c["high"]  for c in q1_candles]
    lows   = [c["low"]   for c in q1_candles]
    opens  = [c["open"]  for c in q1_candles]
    closes = [c["close"] for c in q1_candles]

    total_range = max(highs) - min(lows) if highs else 0
    body        = abs(closes[-1] - opens[0]) if closes and opens else 0
    directional = body / total_range if total_range > 0 else 0

    # Strong directional move = XAMD (X happened in Q1)
    # Ranging/consolidation = AMDX (A happening in Q1)
    if directional > 0.4:
        return "XAMD", "X"
    else:
        return "AMDX", "A"

def get_phase_label(pattern, quarter_num):
    """Get XAMD or AMDX phase label for given quarter."""
    xamd = {1: "X", 2: "A", 3: "M", 4: "D"}
    amdx = {1: "A", 2: "M", 3: "D", 4: "X"}
    if pattern == "XAMD":
        return xamd.get(quarter_num, "?")
    elif pattern == "AMDX":
        return amdx.get(quarter_num, "?")
    return "?"

def is_target_phase(phase_label):
    return phase_label in ["M", "D"]

# â”€â”€â”€ TRUE OPENS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def get_true_opens(symbol, now, session_info):
    """
    True open = open price of Q2 of each timeframe period.
    For weekly: Tuesday open
    For monthly: start of 2nd week
    For yearly: start of Q2 (April 1)
    For session: open of 2nd 90-min cycle
    For 90-min: open of 2nd 45-min half
    """
    opens = {}

    # Daily candles for yearly/monthly/weekly
    daily = fetch_candles(symbol, "1day", outputsize=60)
    if daily:
        # True Week Open = Tuesday (index 1 of week, Mon=0)
        for c in reversed(daily):
            dt = datetime.strptime(c["time"], "%Y-%m-%d")
            if dt.weekday() == 1:  # Tuesday
                opens["true_week_open"] = c["open"]
                break

        # True Month Open = 8th day of month (approx Q2 start)
        month_candles = [c for c in daily if c["time"].startswith(now.strftime("%Y-%m"))]
        if len(month_candles) >= 2:
            opens["true_month_open"] = month_candles[1]["open"]  # Q2 of month

        # True Year Open = April 1st open (Q2 of year)
        year_str = now.strftime("%Y")
        april_candles = [c for c in daily if c["time"].startswith(f"{year_str}-04")]
        if april_candles:
            opens["true_year_open"] = april_candles[0]["open"]

    # 1H candles for session open
    hourly = fetch_candles(symbol, "1h", outputsize=24)
    if hourly and session_info:
        # True Session Open = open of Q2 of session (1.5 hours after session start)
        q2_hour = int(session_info["session_q2_hour"])
        for c in reversed(hourly):
            try:
                dt = datetime.strptime(c["time"], "%Y-%m-%d %H:%M:%S")
                if dt.hour == q2_hour:
                    opens["true_session_open"] = c["open"]
                    break
            except:
                pass

    # 15min candles for 90-min cycle true open
    m15 = fetch_candles(symbol, "15min", outputsize=24)
    if m15 and session_info:
        # True 90-min open = 45 min into current cycle (Q2 of 90-min)
        cycle_q2_hour = int(session_info["cycle_q2_hour"])
        cycle_q2_min  = int((session_info["cycle_q2_hour"] % 1) * 60)
        for c in reversed(m15):
            try:
                dt = datetime.strptime(c["time"], "%Y-%m-%d %H:%M:%S")
                if dt.hour == cycle_q2_hour and dt.minute >= cycle_q2_min:
                    opens["true_90min_open"] = c["open"]
                    break
            except:
                pass

    # True Day Open = open of Tuesday (Q2 of week = day 2)
    if daily:
        for c in reversed(daily[-7:]):
            dt = datetime.strptime(c["time"], "%Y-%m-%d")
            if dt.weekday() == 1:
                opens["true_day_open"] = c["open"]
                break

    return opens

# â”€â”€â”€ MARKET STRUCTURE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def find_swing_highs_lows(candles, lookback=5):
    highs, lows = [], []
    for i in range(lookback, len(candles) - lookback):
        if all(candles[i]["high"] >= candles[j]["high"]
               for j in range(i-lookback, i+lookback+1) if j != i):
            highs.append({"price": candles[i]["high"], "time": candles[i]["time"]})
        if all(candles[i]["low"] <= candles[j]["low"]
               for j in range(i-lookback, i+lookback+1) if j != i):
            lows.append({"price": candles[i]["low"], "time": candles[i]["time"]})
    return highs, lows

def detect_fvg(candles):
    fvgs = []
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        if c1["high"] < c3["low"]:   # Bullish FVG
            fvgs.append({
                "type":      "bullish",
                "top":       c3["low"],
                "bottom":    c1["high"],
                "mid":       (c3["low"] + c1["high"]) / 2,
                "ob_candle": c2,
                "time":      c2["time"]
            })
        if c1["low"] > c3["high"]:   # Bearish FVG
            fvgs.append({
                "type":      "bearish",
                "top":       c1["low"],
                "bottom":    c3["high"],
                "mid":       (c1["low"] + c3["high"]) / 2,
                "ob_candle": c2,
                "time":      c2["time"]
            })
    return fvgs[-15:]

def detect_ifvg(candles):
    """Inverse FVG â€” a FVG that has been partially filled"""
    fvgs  = detect_fvg(candles)
    ifvgs = []
    if not fvgs or not candles:
        return ifvgs
    last_close = candles[-1]["close"]
    for fvg in fvgs:
        lo = min(fvg["top"], fvg["bottom"])
        hi = max(fvg["top"], fvg["bottom"])
        # Partially filled = price entered but didn't fully close through
        if fvg["type"] == "bullish" and lo <= last_close <= hi:
            ifvgs.append({**fvg, "type": "iFVG_bullish"})
        elif fvg["type"] == "bearish" and lo <= last_close <= hi:
            ifvgs.append({**fvg, "type": "iFVG_bearish"})
    return ifvgs

def detect_order_block(candles, direction):
    """Last opposing candle before a strong move â€” the OB"""
    obs = []
    for i in range(1, len(candles) - 1):
        c     = candles[i]
        c_next = candles[i+1]
        body  = abs(c["close"] - c["open"])
        if body == 0:
            continue
        if direction == "bullish":
            # Bearish candle before strong bullish move
            if c["close"] < c["open"] and c_next["close"] > c_next["open"]:
                if (c_next["close"] - c_next["open"]) > body * 1.5:
                    obs.append({"high": c["high"], "low": c["low"],
                                "mid": (c["high"] + c["low"]) / 2,
                                "time": c["time"], "type": "bullish_ob"})
        else:
            # Bullish candle before strong bearish move
            if c["close"] > c["open"] and c_next["close"] < c_next["open"]:
                if (c_next["open"] - c_next["close"]) > body * 1.5:
                    obs.append({"high": c["high"], "low": c["low"],
                                "mid": (c["high"] + c["low"]) / 2,
                                "time": c["time"], "type": "bearish_ob"})
    return obs[-5:]

def detect_choch_mss(candles, direction):
    if len(candles) < 10:
        return False, False, None
    recent = candles[-20:]
    choch, mss = False, False
    candle_ref  = None

    if direction == "bullish":
        recent_highs = [c["high"] for c in recent[:-3]]
        last_high    = max(recent_highs) if recent_highs else 0
        for c in recent[-5:]:
            if c["close"] > last_high:
                choch     = True
                candle_ref = c
                # MSS = strong momentum + FVG left behind
                body = abs(c["close"] - c["open"])
                wick = c["high"] - c["close"]
                if body > wick * 2:
                    mss = True
                break
    else:
        recent_lows = [c["low"] for c in recent[:-3]]
        last_low    = min(recent_lows) if recent_lows else 999999
        for c in recent[-5:]:
            if c["close"] < last_low:
                choch     = True
                candle_ref = c
                body = abs(c["close"] - c["open"])
                wick = c["close"] - c["low"]
                if body > wick * 2:
                    mss = True
                break

    return choch, mss, candle_ref

def detect_liquidity_sweep(candles, highs, lows, price):
    sweeps = []
    recent_high = max(c["high"] for c in candles[-5:]) if candles else 0
    recent_low  = min(c["low"]  for c in candles[-5:]) if candles else 0
    for sh in highs[-5:]:
        if recent_high > sh["price"] and price < sh["price"]:
            sweeps.append({"type": "sell_side_swept", "level": sh["price"],
                           "direction": "bearish"})
    for sl in lows[-5:]:
        if recent_low < sl["price"] and price > sl["price"]:
            sweeps.append({"type": "buy_side_swept", "level": sl["price"],
                           "direction": "bullish"})
    return sweeps

def fibonacci_levels(swing_high, swing_low):
    diff = swing_high - swing_low
    return {
        "0.0":   swing_high,
        "0.236": swing_high - 0.236 * diff,
        "0.382": swing_high - 0.382 * diff,
        "0.5":   swing_high - 0.5   * diff,
        "0.618": swing_high - 0.618 * diff,
        "0.705": swing_high - 0.705 * diff,
        "0.786": swing_high - 0.786 * diff,
        "1.0":   swing_low
    }

def in_golden_zone(price, swing_high, swing_low):
    fibs = fibonacci_levels(swing_high, swing_low)
    lo   = min(fibs["0.618"], fibs["0.705"])
    hi   = max(fibs["0.618"], fibs["0.705"])
    return lo <= price <= hi, fibs

# â”€â”€â”€ FULL FRACTAL ANALYSIS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def build_fractal_stack(now, candles_daily, candles_4h, candles_1h,
                        candles_15m, candles_5m, session_info):
    """
    Build complete XAMD/AMDX fractal stack for all 6 levels.
    Returns dict with phase info per level.
    """
    stack = {}

    # â”€â”€ YEARLY â”€â”€
    y_q = get_yearly_quarter(now.month)
    # Q1 candles = Jan-Mar (first 3 months)
    y_q1 = [c for c in candles_daily if c["time"][5:7] in ["01","02","03"]]
    y_htf = "bearish" if candles_daily and candles_daily[-1]["close"] < candles_daily[0]["open"] else "bullish"
    y_pattern, _ = detect_xamd_amdx(y_q1, y_htf)
    y_phase = get_phase_label(y_pattern, y_q)
    stack["yearly"] = {"q": y_q, "pattern": y_pattern, "phase": y_phase, "bias": y_htf}

    # â”€â”€ MONTHLY â”€â”€
    m_q = get_monthly_quarter(now.day)
    m_candles = [c for c in candles_daily if c["time"].startswith(now.strftime("%Y-%m"))]
    m_q1 = m_candles[:7]
    m_htf = y_htf  # monthly follows yearly bias
    m_pattern, _ = detect_xamd_amdx(m_q1, m_htf)
    m_phase = get_phase_label(m_pattern, m_q)
    stack["monthly"] = {"q": m_q, "pattern": m_pattern, "phase": m_phase, "bias": m_htf}

    # â”€â”€ WEEKLY â”€â”€
    w_q = get_weekly_quarter(now.weekday())
    # Q1 of week = Monday candles on 4H
    w_q1 = [c for c in candles_4h if
            datetime.strptime(c["time"], "%Y-%m-%d %H:%M:%S").weekday() == 0][:6]
    w_htf = m_htf
    w_pattern, _ = detect_xamd_amdx(w_q1, w_htf)
    w_phase = get_phase_label(w_pattern, w_q) if w_q else "?"
    stack["weekly"] = {"q": w_q, "pattern": w_pattern, "phase": w_phase, "bias": w_htf}

    # â”€â”€ DAILY â”€â”€
    d_q = w_q  # daily quarter = same as weekly day quarter
    # Q1 of day = first session (Asian)
    d_q1 = [c for c in candles_1h if
            0 <= datetime.strptime(c["time"], "%Y-%m-%d %H:%M:%S").hour < 6]
    d_htf = w_htf
    d_pattern, _ = detect_xamd_amdx(d_q1, d_htf)
    d_phase = get_phase_label(d_pattern, d_q) if d_q else "?"
    stack["daily"] = {"q": d_q, "pattern": d_pattern, "phase": d_phase, "bias": d_htf}

    # â”€â”€ SESSION â”€â”€
    s_q = session_info["session_q"] if session_info else 1
    # Q1 of session = first 90-min (candles in first 90 min of session)
    s_start = session_info["start"] if session_info else 0
    s_q1 = [c for c in candles_15m if
            s_start <= datetime.strptime(c["time"], "%Y-%m-%d %H:%M:%S").hour < s_start + 2][:6]
    s_htf = d_htf
    s_pattern, _ = detect_xamd_amdx(s_q1, s_htf)
    s_phase = get_phase_label(s_pattern, s_q)
    stack["session"] = {"q": s_q, "pattern": s_pattern, "phase": s_phase,
                        "name": session_info["name"] if session_info else "Unknown",
                        "bias": s_htf}

    # â”€â”€ 90-MIN CYCLE â”€â”€
    c_q = s_q  # which 90-min cycle we're in = same as session quarter
    # Q1 of 90-min = first 45 min
    cycle_start = session_info["cycle_start_hour"] if session_info else 0
    c_q1 = [c for c in candles_5m if
            abs(datetime.strptime(c["time"], "%Y-%m-%d %H:%M:%S").hour - int(cycle_start)) <= 1][:9]
    c_htf = s_htf
    c_pattern, _ = detect_xamd_amdx(c_q1, c_htf)
    c_phase = get_phase_label(c_pattern, c_q)
    stack["90min"] = {"q": c_q, "pattern": c_pattern, "phase": c_phase, "bias": c_htf}

    # â”€â”€ ALIGNMENT SCORE â”€â”€
    target_levels   = [v["phase"] for v in stack.values() if isinstance(v, dict)]
    alignment_score = sum(1 for p in target_levels if p in ["M", "D"])
    overall_bias    = "bearish" if sum(1 for v in stack.values()
                                       if isinstance(v, dict) and v.get("bias") == "bearish") >= 3 else "bullish"

    stack["alignment_score"] = alignment_score
    stack["overall_bias"]    = overall_bias
    return stack

# â”€â”€â”€ SL / TP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def pip_size(symbol):
    if "XAU" in symbol:
        return 0.01
    if "JPY" in symbol:
        return 0.01
    return 0.0001

def calculate_sl_tp(direction, entry, symbol, highs, lows, fvg):
    ps      = pip_size(symbol)
    is_gold = "XAU" in symbol

    if is_gold:
        ob = fvg["ob_candle"]
        if direction == "bullish":
            sl_raw  = ob["low"] - (5 * ps)
            sl_pips = (entry - sl_raw) / ps
            if sl_pips < GOLD_SL_MIN:
                sl_raw = entry - GOLD_SL_MIN * ps
            elif sl_pips > GOLD_SL_MAX:
                return None, None, None
        else:
            sl_raw  = ob["high"] + (5 * ps)
            sl_pips = (sl_raw - entry) / ps
            if sl_pips < GOLD_SL_MIN:
                sl_raw = entry + GOLD_SL_MIN * ps
            elif sl_pips > GOLD_SL_MAX:
                return None, None, None
        sl = round(sl_raw, 2)
    else:
        dist = FOREX_SL_PIPS * ps
        sl   = round(entry - dist, 5) if direction == "bullish" else round(entry + dist, 5)

    dp = 2 if is_gold else 5
    if direction == "bullish":
        tp1_candidates = [h["price"] for h in highs if h["price"] > entry]
        tp1 = round(min(tp1_candidates), dp) if tp1_candidates else round(entry + 30 * ps, dp)
        tp2_candidates = [h["price"] for h in highs if h["price"] > tp1]
        tp2 = round(min(tp2_candidates), dp) if tp2_candidates else round(entry + 60 * ps, dp)
    else:
        tp1_candidates = [l["price"] for l in lows if l["price"] < entry]
        tp1 = round(max(tp1_candidates), dp) if tp1_candidates else round(entry - 30 * ps, dp)
        tp2_candidates = [l["price"] for l in lows if l["price"] < tp1]
        tp2 = round(max(tp2_candidates), dp) if tp2_candidates else round(entry - 60 * ps, dp)

    return sl, tp1, tp2

# â”€â”€â”€ MAIN PAIR ANALYSIS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def analyze_pair(symbol, now, session_info):
    print(f"\n  Analyzing {symbol}...")
    results = []

    # Fetch all timeframes
    candles_monthly = fetch_candles(symbol, "1month", outputsize=12)
    candles_weekly  = fetch_candles(symbol, "1week",  outputsize=12)
    candles_daily   = fetch_candles(symbol, "1day",   outputsize=60)
    candles_4h      = fetch_candles(symbol, "4h",     outputsize=60)
    candles_1h      = fetch_candles(symbol, "1h",     outputsize=48)
    candles_15m     = fetch_candles(symbol, "15min",  outputsize=50)
    candles_5m      = fetch_candles(symbol, "5min",   outputsize=36)

    if not candles_4h or not candles_1h or not candles_15m:
        print(f"  Insufficient data for {symbol}")
        return results

    current_price = fetch_price(symbol)
    if not current_price:
        return results

    # â”€â”€ BUILD FRACTAL STACK â”€â”€
    stack = build_fractal_stack(now, candles_daily, candles_4h,
                                candles_1h, candles_15m, candles_5m, session_info)
    overall_bias    = stack["overall_bias"]
    alignment_score = stack["alignment_score"]
    trade_direction = overall_bias

    # â”€â”€ TRUE OPENS â”€â”€
    true_opens = get_true_opens(symbol, now, session_info)

    # â”€â”€ HTF SWING HIGHS/LOWS (liquidity pools) â”€â”€
    highs_4h, lows_4h = find_swing_highs_lows(candles_4h)
    highs_1h, lows_1h = find_swing_highs_lows(candles_1h)
    all_highs = sorted(list({h["price"]: h for h in highs_4h + highs_1h}.values()),
                       key=lambda x: x["price"])
    all_lows  = sorted(list({l["price"]: l for l in lows_4h  + lows_1h}.values()),
                       key=lambda x: x["price"])

    # â”€â”€ HTF FVGs & iFVGs â”€â”€
    fvgs_4h  = detect_fvg(candles_4h)
    fvgs_1h  = detect_fvg(candles_1h)
    ifvgs_1h = detect_ifvg(candles_1h)

    # â”€â”€ ORDER BLOCKS (HTF) â”€â”€
    obs_4h = detect_order_block(candles_4h, trade_direction)
    obs_1h = detect_order_block(candles_1h, trade_direction)

    # â”€â”€ FIBONACCI â”€â”€
    in_fib, fib_levels = False, {}
    if all_highs and all_lows:
        recent_high = all_highs[-1]["price"]
        recent_low  = all_lows[-1]["price"]
        in_fib, fib_levels = in_golden_zone(current_price, recent_high, recent_low)

    # â”€â”€ LIQUIDITY SWEEP â”€â”€
    sweeps_4h = detect_liquidity_sweep(candles_4h, highs_4h, lows_4h, current_price)
    sweeps_1h = detect_liquidity_sweep(candles_1h, highs_1h, lows_1h, current_price)
    all_sweeps = sweeps_4h + sweeps_1h
    liq_swept  = bool(all_sweeps)

    # Check sweep direction matches overall bias
    if all_sweeps:
        sweep_dir = all_sweeps[-1]["direction"]
        if sweep_dir != trade_direction:
            trade_direction = sweep_dir  # sweep overrides

    # â”€â”€ HTF ZONE TAP â”€â”€
    htf_zone_tapped = False
    htf_fvg_hit     = None
    for fvg in reversed(fvgs_4h + fvgs_1h + ifvgs_1h):
        lo = min(fvg["top"], fvg["bottom"])
        hi = max(fvg["top"], fvg["bottom"])
        buf = 0.5 if "XAU" in symbol else 0.0005
        if lo - buf <= current_price <= hi + buf:
            htf_zone_tapped = True
            htf_fvg_hit     = fvg
            break

    # Check OB tap
    ob_tapped = None
    for ob in reversed(obs_4h + obs_1h):
        if ob["low"] <= current_price <= ob["high"]:
            ob_tapped       = ob
            htf_zone_tapped = True
            break

    # â”€â”€ ChoCh / MSS (15min & 5min) â”€â”€
    choch_15m, mss_15m, _ = detect_choch_mss(candles_15m, trade_direction)
    choch_5m,  mss_5m,  _ = detect_choch_mss(candles_5m,  trade_direction)
    choch_confirmed = choch_15m or choch_5m
    mss_confirmed   = mss_15m  or mss_5m

    # â”€â”€ ENTRY FVG (15min / 5min) â”€â”€
    fvgs_15m   = detect_fvg(candles_15m)
    fvgs_5m    = detect_fvg(candles_5m)
    entry_fvgs = [f for f in fvgs_15m + fvgs_5m if f["type"] == trade_direction]
    entry_fvg  = None
    for fvg in reversed(entry_fvgs):
        lo  = min(fvg["top"], fvg["bottom"])
        hi  = max(fvg["top"], fvg["bottom"])
        buf = 1.0 if "XAU" in symbol else 0.001
        if lo - buf <= current_price <= hi + buf:
            entry_fvg = fvg
            break
    if not entry_fvg and entry_fvgs:
        entry_fvg = entry_fvgs[-1]

    # â”€â”€ CHECK ALL 6 CONDITIONS â”€â”€
    cond_quarterly  = alignment_score >= MIN_ALIGNMENT
    cond_liq_sweep  = liq_swept
    cond_htf_zone   = htf_zone_tapped
    cond_fib        = in_fib
    cond_choch_mss  = choch_confirmed or mss_confirmed
    cond_entry_fvg  = entry_fvg is not None

    conditions_met = sum([cond_quarterly, cond_liq_sweep, cond_htf_zone,
                          cond_fib, cond_choch_mss, cond_entry_fvg])

    all_confirmed = conditions_met >= 5  # 5 or 6 out of 6

    # â”€â”€ WATCHING ALERT â”€â”€
    near_zone = htf_zone_tapped or liq_swept or (in_fib and conditions_met >= 2)
    if near_zone and not all_confirmed:
        results.append({
            "type":            "watching",
            "symbol":          symbol,
            "price":           current_price,
            "direction":       trade_direction,
            "stack":           stack,
            "true_opens":      true_opens,
            "sweeps":          all_sweeps,
            "htf_fvg":         htf_fvg_hit,
            "ob_tapped":       ob_tapped,
            "choch":           choch_confirmed,
            "mss":             mss_confirmed,
            "entry_fvg":       entry_fvg,
            "in_fib":          in_fib,
            "fib_levels":      fib_levels,
            "conditions_met":  conditions_met,
            "cond_quarterly":  cond_quarterly,
            "cond_liq_sweep":  cond_liq_sweep,
            "cond_htf_zone":   cond_htf_zone,
            "cond_fib":        cond_fib,
            "cond_choch_mss":  cond_choch_mss,
            "cond_entry_fvg":  cond_entry_fvg,
        })

    # â”€â”€ A+ SIGNAL â”€â”€
    if all_confirmed and entry_fvg:
        entry    = entry_fvg["mid"]
        sl, tp1, tp2 = calculate_sl_tp(trade_direction, entry, symbol,
                                        all_highs, all_lows, entry_fvg)
        if sl and tp1 and tp2:
            ps      = pip_size(symbol)
            is_gold = "XAU" in symbol
            if trade_direction == "bullish":
                sl_pips  = round((entry - sl)  / ps)
                tp1_pips = round((tp1 - entry) / ps)
                tp2_pips = round((tp2 - entry) / ps)
            else:
                sl_pips  = round((sl - entry)  / ps)
                tp1_pips = round((entry - tp1) / ps)
                tp2_pips = round((entry - tp2) / ps)

            rr1 = round(tp1_pips / sl_pips, 1) if sl_pips else 0
            rr2 = round(tp2_pips / sl_pips, 1) if sl_pips else 0

            results.append({
                "type":           "signal",
                "symbol":         symbol,
                "price":          current_price,
                "direction":      trade_direction,
                "entry":          entry,
                "sl":             sl,
                "tp1":            tp1,
                "tp2":            tp2,
                "sl_pips":        sl_pips,
                "tp1_pips":       tp1_pips,
                "tp2_pips":       tp2_pips,
                "rr1":            rr1,
                "rr2":            rr2,
                "stack":          stack,
                "true_opens":     true_opens,
                "sweeps":         all_sweeps,
                "htf_fvg":        htf_fvg_hit,
                "ob_tapped":      ob_tapped,
                "entry_fvg":      entry_fvg,
                "choch":          choch_confirmed,
                "mss":            mss_confirmed,
                "in_fib":         in_fib,
                "fib_levels":     fib_levels,
                "conditions_met": conditions_met,
            })

    return results

# â”€â”€â”€ EMAIL FORMATTERS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def fmt(val, dp=5):
    if val is None:
        return "N/A"
    return f"{val:.{dp}f}"

def format_stack(stack):
    lines = []
    levels = [
        ("Yearly",  "yearly"),
        ("Monthly", "monthly"),
        ("Weekly",  "weekly"),
        ("Daily",   "daily"),
        ("Session", "session"),
        ("90-min",  "90min"),
    ]
    for label, key in levels:
        v = stack.get(key, {})
        if not isinstance(v, dict):
            continue
        phase   = v.get("phase", "?")
        pattern = v.get("pattern", "?")
        q       = v.get("q", "?")
        bias    = v.get("bias", "?").upper()
        name    = v.get("name", "")
        target  = "âœ…" if phase in ["M", "D"] else "âšª"
        name_str = f" ({name})" if name else ""
        lines.append(f"{target} {label}{name_str}: Q{q} | {pattern} | {phase} phase | {bias}")
    return "\n".join(lines)

def format_watching_email(r):
    dp  = 2 if "XAU" in r["symbol"] else 5
    d   = "BUY ðŸ“ˆ" if r["direction"] == "bullish" else "SELL ðŸ“‰"
    sw  = r["sweeps"][0]["type"].replace("_"," ").upper() if r["sweeps"] else "None detected"
    to  = r["true_opens"]
    stack_str = format_stack(r["stack"])

    return f"""
ðŸ‘€ WATCHING â€” {r['symbol']} | {r['stack'].get('session',{}).get('name','?')} Session
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
Current Price : {fmt(r['price'], dp)}
Bias          : {d}
Conditions Met: {r['conditions_met']}/6

ðŸ“Š FRACTAL STACK:
{stack_str}
Alignment Score: {r['stack'].get('alignment_score','?')}/6

ðŸ“Œ TRUE OPENS:
True Year Open   : {fmt(to.get('true_year_open'), dp)}
True Month Open  : {fmt(to.get('true_month_open'), dp)}
True Week Open   : {fmt(to.get('true_week_open'), dp)}
True Day Open    : {fmt(to.get('true_day_open'), dp)}
True Session Open: {fmt(to.get('true_session_open'), dp)}
True 90-min Open : {fmt(to.get('true_90min_open'), dp)}

âœ… CHECKLIST:
{'âœ…' if r['cond_quarterly']  else 'âŒ'} Quarterly M/D phase alignment
{'âœ…' if r['cond_liq_sweep']  else 'âŒ'} Liquidity sweep: {sw}
{'âœ…' if r['cond_htf_zone']   else 'âŒ'} HTF FVG/iFVG/OB zone tapped
{'âœ…' if r['cond_fib']        else 'âŒ'} Fibonacci golden zone (0.618-0.705)
{'âœ…' if r['cond_choch_mss']  else 'âŒ'} ChoCh/MSS confirmed
{'âœ…' if r['cond_entry_fvg']  else 'âŒ'} Entry FVG (15min/5min)

â³ Waiting for remaining conditions...
Stay alert â€” signal may fire soon! ðŸŽ¯
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
""".strip()

def format_signal_email(r):
    dp        = 2 if "XAU" in r["symbol"] else 5
    d         = "BUY ðŸ“ˆ" if r["direction"] == "bullish" else "SELL ðŸ“‰"
    sw        = r["sweeps"][0]["type"].replace("_"," ").upper() if r["sweeps"] else "Swept"
    sw_level  = fmt(r["sweeps"][0]["level"], dp) if r["sweeps"] else "N/A"
    fvg_type  = r["entry_fvg"]["type"].upper() if r["entry_fvg"] else "FVG"
    ob        = r["entry_fvg"]["ob_candle"] if r["entry_fvg"] else {}
    ob_level  = fmt(ob.get("high", 0) if r["direction"]=="bearish" else ob.get("low", 0), dp)
    to        = r["true_opens"]
    stack_str = format_stack(r["stack"])
    phase_str = "Manipulation" if any(
        r["stack"].get(k, {}).get("phase") == "M"
        for k in ["session","90min","daily"]
    ) else "Distribution"
    fibs      = r.get("fib_levels", {})

    return f"""
ðŸŽ¯ A+ SIGNAL â€” {r['symbol']} {('BUY' if r['direction']=='bullish' else 'SELL')} | {r['stack'].get('session',{}).get('name','?')} Session
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”

ðŸ“Š FRACTAL ALIGNMENT ({r['conditions_met']}/6):
{stack_str}
â­ Alignment Score: {r['stack'].get('alignment_score','?')}/6

ðŸ“Œ TRUE OPENS (Key Reaction Zones):
True Year Open   : {fmt(to.get('true_year_open'), dp)}
True Month Open  : {fmt(to.get('true_month_open'), dp)}
True Week Open   : {fmt(to.get('true_week_open'), dp)}
True Day Open    : {fmt(to.get('true_day_open'), dp)}
True Session Open: {fmt(to.get('true_session_open'), dp)}
True 90-min Open : {fmt(to.get('true_90min_open'), dp)}

ðŸ” SETUP DETAILS:
Phase          : {phase_str}
Liquidity      : {sw} at {sw_level}
HTF Zone       : {'FVG/OB tapped âœ…' if r['htf_fvg'] or r['ob_tapped'] else 'Near zone'}
OB Level       : {ob_level}
Fib 0.618      : {fmt(fibs.get('0.618'), dp)}
Fib 0.705      : {fmt(fibs.get('0.705'), dp)}
In Golden Zone : {'âœ… YES' if r['in_fib'] else 'âš ï¸ Near'}
ChoCh          : {'âœ… Confirmed' if r['choch'] else 'âšª Not confirmed'}
MSS            : {'âœ… Confirmed' if r['mss'] else 'âšª Not confirmed'}
Entry FVG      : {fvg_type} at {fmt(r['entry_fvg']['bottom'] if r['entry_fvg'] else 0, dp)}-{fmt(r['entry_fvg']['top'] if r['entry_fvg'] else 0, dp)}

ðŸ“ˆ TRADE PARAMETERS:
Direction : {d}
Entry     : {fmt(r['entry'], dp)}
SL        : {fmt(r['sl'], dp)} ({r['sl_pips']} pips)
TP1       : {fmt(r['tp1'], dp)} ({r['tp1_pips']} pips) â€” Internal liquidity
TP2       : {fmt(r['tp2'], dp)} ({r['tp2_pips']} pips) â€” Opposing liquidity
RR        : 1:{r['rr1']} / 1:{r['rr2']}

ðŸ’¡ REASON:
{r['symbol']} {phase_str} phase detected.
{sw} at {sw_level} â€” price reversed.
HTF FVG/OB confluence with Fib golden zone.
{'ChoCh + MSS' if r['choch'] and r['mss'] else 'ChoCh' if r['choch'] else 'Structure shift'} confirmed on 15min/5min.
{r['stack'].get('alignment_score','?')}/6 fractal levels aligned {('BEARISH' if r['direction']=='bearish' else 'BULLISH')}.

âš ï¸ ALWAYS confirm on MT5 before entering!
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
""".strip()

# â”€â”€â”€ MAIN â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def main():
    print("=" * 55)
    print("FX Signal Bot â€” Full Fractal + 90-min Cycle Scan")
    print("=" * 55)

    now          = datetime.now(timezone.utc)
    weekday      = now.weekday()
    session_info = get_session_info(now.hour)

    print(f"UTC Time   : {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"Weekday    : {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][weekday]}")
    print(f"Session    : {session_info['name'] if session_info else 'None'}")
    print(f"90-min Q   : {session_info['session_q'] if session_info else 'N/A'}")

    # Skip Friday (4) and weekend (5,6)
    if weekday >= 4:
        print("Friday/Weekend â€” no signals.")
        send_email(
            "ðŸ“Š FX Bot â€” No Trading Today",
            f"Today is {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][weekday]}.\n"
            f"Bot is resting. See you Monday! ðŸ’¤"
        )
        return

    watching_alerts = []
    signal_alerts   = []

    for symbol in ALL_PAIRS:
        try:
            results = analyze_pair(symbol, now, session_info)
            for r in results:
                if r["type"] == "watching":
                    watching_alerts.append(r)
                elif r["type"] == "signal":
                    signal_alerts.append(r)
        except Exception as e:
            print(f"  Error {symbol}: {e}")

    print(f"\nResults: {len(signal_alerts)} signals, {len(watching_alerts)} watching")

    # Send A+ signals first
    for r in signal_alerts:
        direction = 'BUY' if r['direction'] == 'bullish' else 'SELL'
        subject   = f"ðŸŽ¯ A+ SIGNAL: {r['symbol']} {direction} | {r['conditions_met']}/6 | {r['stack'].get('session',{}).get('name','?')}"
        send_email(subject, format_signal_email(r))

    # Send watching alerts
    for r in watching_alerts:
        subject = f"ðŸ‘€ WATCHING: {r['symbol']} {r['conditions_met']}/6 conditions â€” {r['stack'].get('session',{}).get('name','?')}"
        send_email(subject, format_watching_email(r))

    if not signal_alerts and not watching_alerts:
        print("No setups found this scan â€” market not in position.")

if __name__ == "__main__":
    main()
