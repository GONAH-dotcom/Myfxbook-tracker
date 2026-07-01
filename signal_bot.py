import os
import requests
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

# ================================================================ CONFIG ====
API_KEY        = os.environ.get("TWELVE_DATA_API_KEY")
GMAIL_USER     = "gonahcharo1993@gmail.com"
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

ALL_PAIRS = ["GBP/USD", "EUR/USD", "AUD/JPY"]

FOREX_SL_PIPS      = 15
GOLD_SL_MIN        = 60
GOLD_SL_MAX        = 150
API_DELAY          = 15   # seconds between API calls (free tier: 8/min)
PAIR_DELAY         = 45   # seconds between pairs

# ================================================================== EMAIL ===
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
        print(f"  [EMAIL] {subject}")
    except Exception as e:
        print(f"  [EMAIL ERROR] {e}")

# ============================================================= API FETCH ====
def fetch_candles(symbol, interval, outputsize=60):
    time.sleep(API_DELAY)
    try:
        r = requests.get(
            "https://api.twelvedata.com/time_series",
            params={"symbol": symbol, "interval": interval,
                    "outputsize": outputsize, "apikey": API_KEY, "format": "JSON"},
            timeout=20
        )
        data = r.json()
        if "values" not in data:
            print(f"    [NO DATA] {symbol} {interval}: {data.get('message','')[:60]}")
            return []
        return [{"time": v["datetime"],
                 "open":  float(v["open"]),
                 "high":  float(v["high"]),
                 "low":   float(v["low"]),
                 "close": float(v["close"])}
                for v in reversed(data["values"])]
    except Exception as e:
        print(f"    [FETCH ERR] {symbol} {interval}: {e}")
        return []

def fetch_price(symbol):
    time.sleep(API_DELAY)
    try:
        r = requests.get("https://api.twelvedata.com/price",
                         params={"symbol": symbol, "apikey": API_KEY}, timeout=10)
        return float(r.json().get("price", 0))
    except:
        return 0.0

def to_dt(c):
    return datetime.strptime(c["time"], "%Y-%m-%d %H:%M:%S")

def candle_color(c):
    return "bull" if c["close"] >= c["open"] else "bear"

def body_high(c):
    return max(c["open"], c["close"])

def body_low(c):
    return min(c["open"], c["close"])

def body_size(c):
    return abs(c["close"] - c["open"])

# ======================================================== SESSION / TIME ====
SESSIONS = [
    {"name": "Asian",       "start": 0,  "end": 6},
    {"name": "London",      "start": 6,  "end": 12},
    {"name": "New York AM", "start": 12, "end": 18},
    {"name": "New York PM", "start": 18, "end": 24},
]

def get_session(hour):
    for s in SESSIONS:
        if s["start"] <= hour < s["end"]:
            return s
    return SESSIONS[0]

def get_90min_block(now):
    session = get_session(now.hour)
    elapsed = (now.hour - session["start"]) * 60 + now.minute
    block   = min(int(elapsed // 90) + 1, 4)
    b_start = session["start"] * 60 + (block - 1) * 90
    b_end   = b_start + 90
    return session, block, b_start, b_end

def candles_in_block(candles, start_min, end_min, date):
    out = []
    for c in candles:
        try:
            d = to_dt(c)
            if d.date() != date:
                continue
            m = d.hour * 60 + d.minute
            if start_min <= m < end_min:
                out.append(c)
        except:
            pass
    return out

# ======================================================== TRUE OPENS ========
def get_true_week_open(daily, today_date):
    """True Week Open = Tuesday's daily open (Q2 of week)."""
    for c in reversed(daily):
        try:
            d = datetime.strptime(c["time"], "%Y-%m-%d")
            if d.weekday() == 1 and d.date() <= today_date:
                return c["open"]
        except:
            pass
    return None

def get_true_day_open(h1, today_date):
    """True Day Open = first 1H candle of today (00:00 UTC)."""
    for c in h1:
        try:
            d = to_dt(c)
            if d.date() == today_date and d.hour == 0:
                return c["open"]
        except:
            pass
    return None

def get_true_session_open(m15, session, today_date):
    """True Session Open = open of Q2 of session = 90 min into session."""
    tso_min = session["start"] * 60 + 90
    for c in m15:
        try:
            d = to_dt(c)
            if d.date() == today_date and (d.hour * 60 + d.minute) == tso_min:
                return c["open"]
        except:
            pass
    return None

def get_true_90min_open(m15, block_start_min, today_date):
    """True 90-min Open = open of current 90-min block's first candle."""
    for c in m15:
        try:
            d = to_dt(c)
            if d.date() == today_date and (d.hour * 60 + d.minute) == block_start_min:
                return c["open"]
        except:
            pass
    return None

# ======================================================== STRUCTURE =========
def find_swings(candles, lookback=3):
    highs, lows = [], []
    for i in range(lookback, len(candles) - lookback):
        if all(candles[i]["high"] >= candles[j]["high"]
               for j in range(i-lookback, i+lookback+1) if j != i):
            highs.append({"price": candles[i]["high"], "time": candles[i]["time"], "idx": i})
        if all(candles[i]["low"] <= candles[j]["low"]
               for j in range(i-lookback, i+lookback+1) if j != i):
            lows.append({"price": candles[i]["low"], "time": candles[i]["time"], "idx": i})
    return highs, lows

def get_structure_bias(candles, lookback=3):
    """
    HH + HL = bullish structure
    LH + LL = bearish structure
    Based on last 2 swing highs and last 2 swing lows.
    """
    highs, lows = find_swings(candles, lookback)
    if len(highs) < 2 or len(lows) < 2:
        return "neutral", highs, lows
    hh = highs[-1]["price"] > highs[-2]["price"]
    hl = lows[-1]["price"]  > lows[-2]["price"]
    lh = highs[-1]["price"] < highs[-2]["price"]
    ll = lows[-1]["price"]  < lows[-2]["price"]
    if hh and hl: return "bullish", highs, lows
    if lh and ll: return "bearish", highs, lows
    return "neutral",  highs, lows

# ======================================================= FVG / OB / iFVG ===
def detect_fvg(candles, direction=None):
    """
    Correct FVG detection per Gonah's rules:
    C1 = opposing color candle
    C2 = engulfs C1 body (body_high(C2) > body_high(C1) AND body_low(C2) < body_low(C1))
    C3 = wicks do NOT fill the gap between C1 and C3
    Gap (bullish): C1.high < C3.low  (unfilled space)
    Gap (bearish): C1.low  > C3.high (unfilled space)
    C2 must be opposing color to C1 (C2 is the displacement candle).
    """
    fvgs = []
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]

        c1_col = candle_color(c1)
        c2_col = candle_color(c2)

        # C2 must be opposing color to C1 (displacement)
        if c2_col == c1_col:
            continue

        # C2 body must engulf C1 body
        c2_engulfs_c1 = (body_high(c2) > body_high(c1) and
                         body_low(c2)  < body_low(c1))
        if not c2_engulfs_c1:
            continue

        # BULLISH FVG: C2 is bullish (green), gap between C1.high and C3.low
        if c2_col == "bull":
            gap_exists = c1["high"] < c3["low"]
            if gap_exists:
                gap_top    = c3["low"]
                gap_bottom = c1["high"]
                fvgs.append({
                    "type":   "bullish",
                    "top":    gap_top,
                    "bottom": gap_bottom,
                    "mid":    (gap_top + gap_bottom) / 2,
                    "ob":     c2,       # OB = the displacement candle (C2)
                    "c1":     c1,
                    "c3":     c3,
                    "time":   c2["time"],
                    "filled": False,
                })

        # BEARISH FVG: C2 is bearish (red), gap between C3.high and C1.low
        if c2_col == "bear":
            gap_exists = c1["low"] > c3["high"]
            if gap_exists:
                gap_top    = c1["low"]
                gap_bottom = c3["high"]
                fvgs.append({
                    "type":   "bearish",
                    "top":    gap_top,
                    "bottom": gap_bottom,
                    "mid":    (gap_top + gap_bottom) / 2,
                    "ob":     c2,
                    "c1":     c1,
                    "c3":     c3,
                    "time":   c2["time"],
                    "filled": False,
                })

    # Mark filled FVGs (price closed back through the gap)
    if candles:
        last_close = candles[-1]["close"]
        for fvg in fvgs:
            lo = min(fvg["top"], fvg["bottom"])
            hi = max(fvg["top"], fvg["bottom"])
            if fvg["type"] == "bullish" and last_close < lo:
                fvg["filled"] = True   # price closed below the gap = filled
            if fvg["type"] == "bearish" and last_close > hi:
                fvg["filled"] = True   # price closed above the gap = filled

    if direction:
        fvgs = [f for f in fvgs if f["type"] == direction]

    # Return only UNFILLED FVGs â€” filled ones are no longer valid zones
    fvgs = [f for f in fvgs if not f["filled"]]
    return fvgs[-8:]

def detect_ifvg(candles, direction=None):
    """
    iFVG = Inverse Fair Value Gap.
    A regular FVG that price has FULLY CLOSED THROUGH (body close, not just wick).
    That filled FVG FLIPS its role:
      - Bullish FVG (was support) â†’ price body closes BELOW it â†’ flips to RESISTANCE (iFVG bearish)
      - Bearish FVG (was resistance) â†’ price body closes ABOVE it â†’ flips to SUPPORT (iFVG bullish)

    When price RETURNS to the iFVG zone:
      iFVG bullish (flipped support) â†’ expect BOUNCE UP  â†’ use as BUY zone
      iFVG bearish (flipped resist.) â†’ expect REJECT DOWN â†’ use as SELL zone

    We scan ALL candles in the dataset to find any FVG that was subsequently filled
    by a body close, then check if price is now returning to that zone.
    """
    if not candles:
        return []

    # Step 1: Find ALL FVGs (unfiltered â€” including filled ones)
    all_fvgs = []
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        c1_col = candle_color(c1)
        c2_col = candle_color(c2)
        if c2_col == c1_col:
            continue
        c2_engulfs_c1 = (body_high(c2) > body_high(c1) and
                         body_low(c2)  < body_low(c1))
        if not c2_engulfs_c1:
            continue
        if c2_col == "bull" and c1["high"] < c3["low"]:
            all_fvgs.append({
                "type":   "bullish",
                "top":    c3["low"],
                "bottom": c1["high"],
                "mid":    (c3["low"] + c1["high"]) / 2,
                "ob":     c2,
                "time":   c2["time"],
                "idx":    i - 1,
            })
        if c2_col == "bear" and c1["low"] > c3["high"]:
            all_fvgs.append({
                "type":   "bearish",
                "top":    c1["low"],
                "bottom": c3["high"],
                "mid":    (c1["low"] + c3["high"]) / 2,
                "ob":     c2,
                "time":   c2["time"],
                "idx":    i - 1,
            })

    # Step 2: For each FVG, scan candles AFTER it formed to see if price
    # body-closed through it (filling it) â†’ that makes it an iFVG
    ifvgs = []
    for fvg in all_fvgs:
        fvg_lo = min(fvg["top"], fvg["bottom"])
        fvg_hi = max(fvg["top"], fvg["bottom"])
        filled_by = None

        # Scan candles after this FVG formed
        for c in candles[fvg["idx"] + 2:]:
            if fvg["type"] == "bullish":
                # Bullish FVG filled = body closes BELOW the bottom of the gap
                if body_low(c) < fvg_lo:
                    filled_by = c
                    break
            else:
                # Bearish FVG filled = body closes ABOVE the top of the gap
                if body_high(c) > fvg_hi:
                    filled_by = c
                    break

        if not filled_by:
            continue  # Not filled = still a regular FVG, not an iFVG

        # Step 3: Determine the FLIPPED role
        # Bullish FVG filled â†’ flips to BEARISH iFVG (now resistance)
        # Bearish FVG filled â†’ flips to BULLISH iFVG (now support)
        if fvg["type"] == "bullish":
            ifvg_type = "ifvg_bearish"   # flipped to resistance
            ifvg_dir  = "bearish"
        else:
            ifvg_type = "ifvg_bullish"   # flipped to support
            ifvg_dir  = "bullish"

        ifvgs.append({
            **fvg,
            "type":      ifvg_type,
            "ifvg_dir":  ifvg_dir,
            "filled_by": filled_by["time"],
            "top":       fvg_hi,
            "bottom":    fvg_lo,
            "mid":       (fvg_hi + fvg_lo) / 2,
        })

    # Filter by direction if specified
    # direction="bullish" â†’ want iFVG bullish (flipped support = BUY zone)
    # direction="bearish" â†’ want iFVG bearish (flipped resistance = SELL zone)
    if direction:
        ifvgs = [f for f in ifvgs if f["ifvg_dir"] == direction]

    return ifvgs[-8:]
def detect_ob(candles, direction):
    """
    Order Block = last opposing-color candle BEFORE a strong displacement move.
    Strong displacement = next candle engulfs the OB candle's body.
    The OB zone = full range (high to low) of that last opposing candle.
    """
    obs = []
    for i in range(1, len(candles) - 1):
        c     = candles[i]
        c_nxt = candles[i + 1]

        c_col   = candle_color(c)
        nxt_col = candle_color(c_nxt)

        # OB must be opposing color to trade direction
        if direction == "bullish" and c_col != "bear":
            continue
        if direction == "bearish" and c_col != "bull":
            continue

        # Next candle must be opposing color (displacement)
        if nxt_col == c_col:
            continue

        # Next candle must engulf OB's body (displacement confirmation)
        engulfs = (body_high(c_nxt) > body_high(c) and
                   body_low(c_nxt)  < body_low(c))
        if not engulfs:
            continue

        obs.append({
            "high":  c["high"],
            "low":   c["low"],
            "mid":   (c["high"] + c["low"]) / 2,
            "open":  c["open"],
            "close": c["close"],
            "time":  c["time"],
            "dir":   direction,
        })
    return obs[-5:]

# ======================================================= LIQUIDITY =========
def detect_liquidity_sweep(candles, highs, lows, price):
    """
    Liquidity sweep = wick takes out a swing high/low but candle BODY closes back inside.
    (Body close through = breakout/continuation, not sweep/reversal)
    BUY SIDE swept  (wick above swing high, body closes below) -> bearish reversal
    SELL SIDE swept (wick below swing low,  body closes above) -> bullish reversal
    """
    sweeps = []
    if not candles:
        return sweeps

    recent = candles[-6:]
    for c in recent:
        # BUY SIDE LIQUIDITY SWEEP: wick above swing high, body closes below
        for h in highs[-8:]:
            if c["high"] > h["price"] and body_high(c) <= h["price"]:
                sweeps.append({
                    "type":  "buy_side_swept",
                    "level": h["price"],
                    "dir":   "bearish",   # sweep of buy side = expect sell
                    "candle": c,
                })
        # SELL SIDE LIQUIDITY SWEEP: wick below swing low, body closes above
        for l in lows[-8:]:
            if c["low"] < l["price"] and body_low(c) >= l["price"]:
                sweeps.append({
                    "type":  "sell_side_swept",
                    "level": l["price"],
                    "dir":   "bullish",   # sweep of sell side = expect buy
                    "candle": c,
                })

    return sweeps

def detect_liquidity_run(candles, direction):
    """
    Liquidity Run = price breaks range aggressively WITH BODY CLOSE (not just wick),
    then 2nd or 3rd candle pulls back to test the formed OB/FVG before continuing.
    Identified by: strong body-close breakout candle, then a pullback candle.
    """
    if len(candles) < 4:
        return False, None

    recent = candles[-6:]
    for i in range(1, len(recent) - 1):
        breakout = recent[i]
        pullback = recent[i + 1]

        b_col = candle_color(breakout)
        p_col = candle_color(pullback)

        # Breakout must be strong body close in trade direction
        if direction == "bullish" and b_col != "bull":
            continue
        if direction == "bearish" and b_col != "bear":
            continue

        # Breakout body must be significantly larger than previous candle
        prev      = recent[i - 1]
        prev_body = body_size(prev)
        break_body = body_size(breakout)
        if prev_body > 0 and break_body < prev_body * 1.5:
            continue

        # Pullback candle retraces (opposite color or doji)
        if direction == "bullish":
            is_pullback = pullback["close"] < breakout["close"]
        else:
            is_pullback = pullback["close"] > breakout["close"]

        if is_pullback:
            return True, {"breakout": breakout, "pullback": pullback}

    return False, None

# ==================================================== ChoCh / MSS ===========
def detect_choch(candles, direction):
    """
    Change of Character = price closes BEYOND a recent swing level,
    officially confirming structure has shifted.
    NOT just a wick â€” must be a BODY CLOSE beyond the level.
    direction = new direction being confirmed (bullish = ChoCh from bear to bull)
    """
    if len(candles) < 8:
        return False, None

    recent = candles[-20:]
    if direction == "bullish":
        # Look for body close above recent lower high (bear structure broken)
        prev_highs = [body_high(c) for c in recent[:-4]]
        if not prev_highs:
            return False, None
        last_lh = max(prev_highs)   # the recent lower high to break
        for c in recent[-5:]:
            if body_high(c) > last_lh and candle_color(c) == "bull":
                return True, c
    else:
        # Look for body close below recent higher low (bull structure broken)
        prev_lows = [body_low(c) for c in recent[:-4]]
        if not prev_lows:
            return False, None
        last_hl = min(prev_lows)    # the recent higher low to break
        for c in recent[-5:]:
            if body_low(c) < last_hl and candle_color(c) == "bear":
                return True, c

    return False, None

def detect_mss(candles, direction):
    """
    Market Structure Shift = aggressive ChoCh with displacement.
    ChoCh candle must ALSO engulf the previous candle's body.
    """
    choch, choch_candle = detect_choch(candles, direction)
    if not choch or not choch_candle:
        return False, None

    # Find the candle before the ChoCh candle in the list
    for i, c in enumerate(candles):
        if c["time"] == choch_candle["time"] and i > 0:
            prev = candles[i - 1]
            engulfs = (body_high(choch_candle) > body_high(prev) and
                       body_low(choch_candle)  < body_low(prev))
            if engulfs:
                return True, choch_candle
    return False, None

# ==================================================== Q1 CLASSIFICATION =====
def classify_q1(q1_candles, prev_high, prev_low):
    """
    After Q1 closes, classify it to predict the session pattern.

    STRONG MOVE (X): broke previous 90-min high/low AND body closed beyond it
    MANIPULATION (M-spike): wick took out previous high/low, body closed back inside
    RANGING (A): no breakout of previous structure, small body zigzag candles

    Returns: classification string + details dict
    """
    if not q1_candles or prev_high is None or prev_low is None:
        return "UNCLEAR", {}

    q1_high  = max(c["high"]  for c in q1_candles)
    q1_low   = min(c["low"]   for c in q1_candles)
    q1_body_high = max(body_high(c) for c in q1_candles)
    q1_body_low  = min(body_low(c)  for c in q1_candles)
    bodies   = [body_size(c) for c in q1_candles]
    avg_body = sum(bodies) / len(bodies) if bodies else 0
    q1_range = q1_high - q1_low if q1_high > q1_low else 0.0001

    # --- STRONG MOVE (X): body closed beyond previous structure ---
    if q1_body_high > prev_high:
        return "X_BULLISH", {
            "reason": f"Body closed above prev block high ({prev_high:.5f})",
            "q1_high": q1_high, "q1_low": q1_low
        }
    if q1_body_low < prev_low:
        return "X_BEARISH", {
            "reason": f"Body closed below prev block low ({prev_low:.5f})",
            "q1_high": q1_high, "q1_low": q1_low
        }

    # --- MANIPULATION (M-spike): wick beyond but body closed back inside ---
    if q1_high > prev_high and q1_body_high <= prev_high:
        return "M_SPIKE_HIGH", {
            "reason": f"Wick above prev high ({prev_high:.5f}), body returned inside",
            "q1_high": q1_high, "q1_low": q1_low
        }
    if q1_low < prev_low and q1_body_low >= prev_low:
        return "M_SPIKE_LOW", {
            "reason": f"Wick below prev low ({prev_low:.5f}), body returned inside",
            "q1_high": q1_high, "q1_low": q1_low
        }

    # --- RANGING (A): no breakout, small bodies, zigzag ---
    small_bodies = avg_body < (q1_range * 0.35)
    if small_bodies:
        return "A_RANGING", {
            "reason": "Small body candles, no structural breakout â€” accumulation",
            "q1_high": q1_high, "q1_low": q1_low
        }

    return "UNCLEAR", {"reason": "Price action unclear", "q1_high": q1_high, "q1_low": q1_low}

def get_pattern_and_phase(q1_class, block_num):
    """
    Q1=X â†’ XAMD: Q1=X, Q2=A, Q3=M(HUNT), Q4=D(HUNT)
    Q1=A â†’ AMDX: Q1=A, Q2=M(HUNT), Q3=D(HUNT), Q4=X
    """
    if q1_class in ["X_BULLISH", "X_BEARISH"]:
        pattern = "XAMD"
        phases  = {1:"X", 2:"A", 3:"M", 4:"D"}
    elif q1_class in ["M_SPIKE_HIGH", "M_SPIKE_LOW", "A_RANGING"]:
        pattern = "AMDX"
        phases  = {1:"A", 2:"M", 3:"D", 4:"X"}
    else:
        pattern = "UNKNOWN"
        phases  = {1:"?", 2:"?", 3:"?", 4:"?"}

    current_phase = phases.get(block_num, "?")
    next_phases   = {k: v for k, v in phases.items() if k > block_num}
    return pattern, current_phase, phases, next_phases

# ================================================== FIB GOLDEN ZONE =========
def fib_zone(price, hi, lo):
    d    = hi - lo
    f618 = hi - 0.618 * d
    f705 = hi - 0.705 * d
    lo_z = min(f618, f705)
    hi_z = max(f618, f705)
    return lo_z <= price <= hi_z, {"0.618": f618, "0.705": f705, "0.5": hi - 0.5 * d}

# ======================================================= SL / TP =============
def pip_size(symbol):
    return 0.01 if ("XAU" in symbol or "JPY" in symbol) else 0.0001

def calc_sl_tp(direction, entry, symbol, highs, lows, fvg):
    ps      = pip_size(symbol)
    is_gold = "XAU" in symbol
    dp      = 2 if is_gold else 5

    if is_gold:
        ob = fvg.get("ob", {})
        if direction == "bullish":
            sl_raw  = ob.get("low", entry - GOLD_SL_MIN * ps) - 5 * ps
            sl_pips = (entry - sl_raw) / ps
            if sl_pips < GOLD_SL_MIN: sl_raw = entry - GOLD_SL_MIN * ps
            elif sl_pips > GOLD_SL_MAX: return None, None, None
        else:
            sl_raw  = ob.get("high", entry + GOLD_SL_MIN * ps) + 5 * ps
            sl_pips = (sl_raw - entry) / ps
            if sl_pips < GOLD_SL_MIN: sl_raw = entry + GOLD_SL_MIN * ps
            elif sl_pips > GOLD_SL_MAX: return None, None, None
        sl = round(sl_raw, dp)
    else:
        dist = FOREX_SL_PIPS * ps
        sl   = round(entry - dist, dp) if direction == "bullish" else round(entry + dist, dp)

    # TP1 = nearest internal liquidity beyond entry
    # TP2 = next liquidity pool beyond TP1
    if direction == "bullish":
        tp1_c = sorted([h["price"] for h in highs if h["price"] > entry])
        tp1   = round(tp1_c[0], dp) if tp1_c else round(entry + 30 * ps, dp)
        tp2_c = sorted([h["price"] for h in highs if h["price"] > tp1])
        tp2   = round(tp2_c[0], dp) if tp2_c else round(entry + 60 * ps, dp)
    else:
        tp1_c = sorted([l["price"] for l in lows if l["price"] < entry], reverse=True)
        tp1   = round(tp1_c[0], dp) if tp1_c else round(entry - 30 * ps, dp)
        tp2_c = sorted([l["price"] for l in lows if l["price"] < tp1], reverse=True)
        tp2   = round(tp2_c[0], dp) if tp2_c else round(entry - 60 * ps, dp)

    return sl, tp1, tp2

# ========================================================= MAIN ANALYSIS ====
def analyze_pair(symbol, now):
    print(f"\n  [{symbol}] analyzing...")

    # Fetch candles â€” 5 calls per pair with API delay
    daily = fetch_candles(symbol, "1day",  30)
    h4    = fetch_candles(symbol, "4h",    60)
    h1    = fetch_candles(symbol, "1h",    60)
    m15   = fetch_candles(symbol, "15min", 96)
    price = fetch_price(symbol)

    if not h4 or not h1 or not m15 or not price:
        print(f"  [{symbol}] insufficient data")
        return None

    today = now.date()
    session, block_num, b_start, b_end = get_90min_block(now)

    # ---- TRUE OPENS (non-negotiable reaction zones) ----
    two = get_true_week_open(daily, today)
    tdo = get_true_day_open(h1, today)
    tso = get_true_session_open(m15, session, today)
    t90 = get_true_90min_open(m15, b_start, today)

    # ---- STEP 1: BIAS â€” Weekly (daily candles) + Daily (4H candles) ----
    weekly_bias, w_highs, w_lows = get_structure_bias(daily, lookback=3)
    daily_bias,  d_highs, d_lows = get_structure_bias(h4,    lookback=3)

    # Must agree â€” if conflict, no trade (avoids counter-trend traps)
    if weekly_bias != "neutral" and daily_bias != "neutral" and weekly_bias != daily_bias:
        print(f"  [{symbol}] Weekly({weekly_bias}) vs Daily({daily_bias}) bias conflict â€” skip")
        return None

    overall_bias = daily_bias if daily_bias != "neutral" else weekly_bias
    if overall_bias == "neutral":
        overall_bias = "bullish" if h4[-1]["close"] > h4[0]["open"] else "bearish"

    # ---- STEP 2: STRUCTURAL SHAPE â€” 4H & 1H zones ----
    h4_highs, h4_lows = find_swings(h4, 3)
    h1_highs, h1_lows = find_swings(h1, 3)
    all_highs = sorted(h4_highs + h1_highs, key=lambda x: x["price"])
    all_lows  = sorted(h4_lows  + h1_lows,  key=lambda x: x["price"])

    # 4H FVGs and OBs (primary zones â€” the anchor)
    h4_fvgs = detect_fvg(h4, overall_bias)
    h4_obs  = detect_ob(h4, overall_bias)
    h4_ifvg = detect_ifvg(h4, overall_bias)

    # 1H FVGs and OBs (secondary zones â€” refine)
    h1_fvgs = detect_fvg(h1, overall_bias)
    h1_obs  = detect_ob(h1, overall_bias)
    h1_ifvg = detect_ifvg(h1, overall_bias)

    all_htf_zones = h4_fvgs + h4_ifvg + h1_fvgs + h1_ifvg

    # Fibonacci golden zone
    in_fib, fibs = False, {}
    if all_highs and all_lows:
        in_fib, fibs = fib_zone(price, all_highs[-1]["price"], all_lows[-1]["price"])

    # ---- STEP 3: Q1 CLASSIFICATION & PATTERN PREDICTION ----
    # Get previous 90-min block candles
    prev_start = b_start - 90
    prev_end   = b_start
    if prev_start < 0:
        prev_date  = today - timedelta(days=1)
        prev_cands = candles_in_block(m15, prev_start + 1440, prev_end + 1440, prev_date)
    else:
        prev_cands = candles_in_block(m15, prev_start, prev_end, today)

    curr_cands = candles_in_block(m15, b_start, b_end, today)

    prev_high = max((c["high"] for c in prev_cands), default=None)
    prev_low  = min((c["low"]  for c in prev_cands), default=None)

    q1_class, q1_det      = classify_q1(curr_cands, prev_high, prev_low)
    pattern, curr_phase, phase_map, next_phases = get_pattern_and_phase(q1_class, block_num)

    is_hunt_phase = curr_phase in ["M", "D"]

    print(f"  [{symbol}] Block {block_num}/4 | Q1={q1_class} | Pattern={pattern} | Phase={curr_phase} | Bias={overall_bias}")

    # ---- STEP 4: LIQUIDITY ANALYSIS ----
    # Sweeps = WICKS beyond swing level, body closed back inside (reversal signal)
    h4_sweeps = detect_liquidity_sweep(h4, h4_highs, h4_lows, price)
    h1_sweeps = detect_liquidity_sweep(h1, h1_highs, h1_lows, price)
    all_sweeps = h4_sweeps + h1_sweeps

    # Direction update from sweep (BUY SIDE swept = bearish, SELL SIDE swept = bullish)
    trade_dir = overall_bias
    if all_sweeps:
        # Most recent sweep dominates
        trade_dir = all_sweeps[-1]["dir"]

    # Liquidity run (body breakout then pullback to retest)
    liq_run, liq_run_det = detect_liquidity_run(h1, trade_dir)

    # ---- STEP 5: HTF ZONE TAP ----
    htf_zone_hit = None
    buf = 0.5 if "XAU" in symbol else 0.0008
    for zone in reversed(all_htf_zones):
        lo = min(zone["top"], zone["bottom"])
        hi = max(zone["top"], zone["bottom"])
        if lo - buf <= price <= hi + buf:
            htf_zone_hit = zone
            break

    # Also check OB tap
    ob_hit = None
    for ob in reversed(h4_obs + h1_obs):
        if ob["low"] - buf <= price <= ob["high"] + buf:
            ob_hit = ob
            if not htf_zone_hit:
                htf_zone_hit = {"type": overall_bias, "top": ob["high"],
                                "bottom": ob["low"], "mid": ob["mid"], "ob": ob}
            break

    # Check true opens as reaction zones
    near_true_open = False
    true_open_vals = [v for v in [two, tdo, tso, t90] if v is not None]
    for to_val in true_open_vals:
        dist = abs(price - to_val)
        threshold = 0.5 if "XAU" in symbol else 0.0010
        if dist <= threshold:
            near_true_open = True
            break

    # ---- STEP 6: LTF CONFIRMATION (15min ChoCh/MSS) ----
    choch, choch_c = detect_choch(m15, trade_dir)
    mss,   mss_c   = detect_mss(m15,   trade_dir)

    # ---- STEP 7: ENTRY FVG (15min â€” inside HTF zone) ----
    m15_fvgs   = detect_fvg(m15, trade_dir)
    entry_fvg  = None
    buf2 = 1.0 if "XAU" in symbol else 0.0010

    # Entry FVG must be inside or near an HTF zone for confluence
    for fvg in reversed(m15_fvgs):
        lo = min(fvg["top"], fvg["bottom"])
        hi = max(fvg["top"], fvg["bottom"])
        # Check if it's near current price
        if not (lo - buf2 <= price <= hi + buf2):
            continue
        # Check if it has HTF confluence (near an HTF zone)
        has_htf_confluence = htf_zone_hit is not None or near_true_open
        if has_htf_confluence:
            entry_fvg = fvg
            break

    if not entry_fvg and m15_fvgs:
        entry_fvg = m15_fvgs[-1]

    # ---- CONDITIONS SCORECARD (7 conditions) ----
    c_bias     = overall_bias != "neutral"                          # 1. HTF structural bias
    c_phase    = is_hunt_phase                                      # 2. In M or D phase
    c_sweep    = bool(all_sweeps) or liq_run                       # 3. Liquidity swept or run
    c_htf_zone = htf_zone_hit is not None or near_true_open        # 4. HTF zone / true open tapped
    c_fib      = in_fib                                            # 5. Fib golden zone
    c_choch    = choch or mss                                      # 6. ChoCh or MSS confirmed
    c_fvg      = entry_fvg is not None                             # 7. Valid entry FVG present

    conds = sum([c_bias, c_phase, c_sweep, c_htf_zone, c_fib, c_choch, c_fvg])
    print(f"  [{symbol}] Conditions: {conds}/7 | phase={curr_phase} | sweep={c_sweep} | choch={c_choch} | fvg={c_fvg}")

    # ---- BUILD RESULT ----
    result = {
        "sym":          symbol,
        "price":        price,
        "dir":          trade_dir,
        "weekly_bias":  weekly_bias,
        "daily_bias":   daily_bias,
        "overall_bias": overall_bias,
        "session":      session["name"],
        "block_num":    block_num,
        "pattern":      pattern,
        "q1_class":     q1_class,
        "q1_reason":    q1_det.get("reason", ""),
        "curr_phase":   curr_phase,
        "next_phases":  next_phases,
        "two":          two,
        "tdo":          tdo,
        "tso":          tso,
        "t90":          t90,
        "sweeps":       all_sweeps,
        "liq_run":      liq_run,
        "htf_zone":     htf_zone_hit,
        "ob_hit":       ob_hit,
        "near_to":      near_true_open,
        "in_fib":       in_fib,
        "fibs":         fibs,
        "choch":        choch,
        "mss":          mss,
        "fvg":          entry_fvg,
        "conds":        conds,
        "c_bias":       c_bias,
        "c_phase":      c_phase,
        "c_sweep":      c_sweep,
        "c_htf_zone":   c_htf_zone,
        "c_fib":        c_fib,
        "c_choch":      c_choch,
        "c_fvg":        c_fvg,
    }

    # A+ SIGNAL: 6 or 7/7, must be in hunt phase, must have entry FVG
    if conds >= 6 and is_hunt_phase and entry_fvg:
        entry = entry_fvg["mid"]
        sl, tp1, tp2 = calc_sl_tp(trade_dir, entry, symbol, all_highs, all_lows, entry_fvg)
        if sl and tp1 and tp2:
            ps = pip_size(symbol)
            dp = 2 if "XAU" in symbol else 5
            if trade_dir == "bullish":
                sp = round((entry - sl) / ps)
                t1 = round((tp1 - entry) / ps)
                t2 = round((tp2 - entry) / ps)
            else:
                sp = round((sl - entry) / ps)
                t1 = round((entry - tp1) / ps)
                t2 = round((entry - tp2) / ps)
            result.update({
                "type":     "signal",
                "entry":    entry,
                "sl":       sl,
                "tp1":      tp1,
                "tp2":      tp2,
                "sl_pips":  sp,
                "tp1_pips": t1,
                "tp2_pips": t2,
                "rr1":      round(t1 / sp, 1) if sp else 0,
                "rr2":      round(t2 / sp, 1) if sp else 0,
            })
            return result

    # WATCHING: in hunt phase, partial confluence (3+ conditions)
    if is_hunt_phase and conds >= 3:
        result["type"] = "watching"
        return result

    # PREDICTION: pattern identified, next hunt phases coming
    if pattern != "UNKNOWN" and not is_hunt_phase and next_phases:
        upcoming = [f"Q{k}={v}" for k, v in next_phases.items() if v in ["M", "D"]]
        if upcoming:
            result["type"]     = "prediction"
            result["upcoming"] = upcoming
            return result

    return None

# ============================================================= FORMATTERS ===
def f(v, dp=5):
    return f"{v:.{dp}f}" if v is not None else "N/A"

def true_opens_str(r, dp):
    return (
        f"True Week Open    : {f(r['two'], dp)}\n"
        f"True Day Open     : {f(r['tdo'], dp)}\n"
        f"True Session Open : {f(r['tso'], dp)}  ({r['session']})\n"
        f"True 90-min Open  : {f(r['t90'], dp)}"
    )

def checklist_str(r):
    sw = r["sweeps"][0]["type"].replace("_"," ").upper() if r["sweeps"] else \
         ("LIQ RUN" if r["liq_run"] else "None")
    return (
        f"[{'OK' if r['c_bias']     else '--'}] Weekly + Daily structural bias ({r['overall_bias'].upper()})\n"
        f"[{'OK' if r['c_phase']    else '--'}] In M or D phase ({r['curr_phase']}) â€” HUNT block\n"
        f"[{'OK' if r['c_sweep']    else '--'}] Liquidity: {sw}\n"
        f"[{'OK' if r['c_htf_zone'] else '--'}] HTF zone tapped (4H/1H FVG/iFVG/OB or True Open)\n"
        f"[{'OK' if r['c_fib']      else '--'}] Fibonacci golden zone (0.618-0.705)\n"
        f"[{'OK' if r['c_choch']    else '--'}] ChoCh{'+ MSS' if r['mss'] else ''} confirmed (body close, not just wick)\n"
        f"[{'OK' if r['c_fvg']      else '--'}] Entry FVG (15min, proper 3-candle structure)"
    )

def prediction_body(r):
    dp = 2 if "XAU" in r["sym"] else 5
    upcoming = r.get("upcoming", [])
    return f"""
[PREDICTION] {r['sym']} | {r['session']} Block {r['block_num']}/4
{'='*48}
Q1 Classification : {r['q1_class']}
Reason            : {r['q1_reason']}
Pattern Predicted : {r['pattern']}
Current Phase     : Q{r['block_num']} = {r['curr_phase']} (not a hunt block)
Upcoming HUNT     : {', '.join(upcoming)}
Bias              : {r['overall_bias'].upper()} (Weekly={r['weekly_bias']}, Daily={r['daily_bias']})
Price             : {f(r['price'], dp)}

{true_opens_str(r, dp)}

Prepare your chart â€” HUNT blocks are coming.
Watch for liquidity sweep into HTF FVG/OB zone,
then ChoCh on 15min to confirm entry.
{'='*48}
""".strip()

def watching_body(r):
    dp  = 2 if "XAU" in r["sym"] else 5
    d   = "BUY" if r["dir"] == "bullish" else "SELL"
    return f"""
[WATCHING] {r['sym']} {d} | {r['session']} Block {r['block_num']}/4 ({r['curr_phase']} phase)
{'='*48}
Pattern   : {r['pattern']}  |  Q1: {r['q1_class']}
Bias      : {r['overall_bias'].upper()} (Weekly={r['weekly_bias']}, Daily={r['daily_bias']})
Price     : {f(r['price'], dp)}
Conditions: {r['conds']}/7

{true_opens_str(r, dp)}

CHECKLIST:
{checklist_str(r)}

Waiting for remaining conditions...
Signal may fire soon â€” stay alert!
{'='*48}
""".strip()

def signal_body(r):
    dp   = 2 if "XAU" in r["sym"] else 5
    d    = "BUY" if r["dir"] == "bullish" else "SELL"
    sw   = r["sweeps"][0]["type"].replace("_"," ").upper() if r["sweeps"] else \
           ("LIQUIDITY RUN" if r["liq_run"] else "None")
    swl  = f(r["sweeps"][0]["level"], dp) if r["sweeps"] else "N/A"
    fibs = r.get("fibs", {})
    fvg  = r.get("fvg", {})
    ob   = fvg.get("ob", {}) if fvg else {}
    ob_h = f(ob.get("high", 0), dp)
    ob_l = f(ob.get("low",  0), dp)
    phase_name = "Manipulation" if r["curr_phase"] == "M" else "Distribution"

    return f"""
[A+ SIGNAL] {r['sym']} {d} | {r['session']} Block {r['block_num']}/4
{'='*48}
Pattern   : {r['pattern']}  |  Q1: {r['q1_class']}
Phase     : {phase_name} ({r['curr_phase']})
Bias      : {r['overall_bias'].upper()} (Weekly={r['weekly_bias']}, Daily={r['daily_bias']})
Conditions: {r['conds']}/7

{true_opens_str(r, dp)}

SETUP:
Liquidity      : {sw} at {swl}
                 (wick sweep â€” body closed back inside)
HTF Zone       : {'4H/1H FVG/iFVG/OB tapped' if r['htf_zone'] else 'True Open reaction'}
OB Zone        : {ob_l} - {ob_h}
Fib 0.618      : {f(fibs.get('0.618'), dp)}
Fib 0.705      : {f(fibs.get('0.705'), dp)}
Golden Zone    : {'YES' if r['in_fib'] else 'Near zone'}
ChoCh          : {'Confirmed (body close)' if r['choch'] else 'No'}
MSS            : {'Confirmed (engulfing ChoCh)' if r['mss'] else 'No'}
Entry FVG      : {f(fvg.get('bottom',0) if fvg else 0, dp)} - {f(fvg.get('top',0) if fvg else 0, dp)}
                 OB candle: {ob.get('time','N/A')}

TRADE:
Direction : {d}
Entry     : {f(r['entry'], dp)}
SL        : {f(r['sl'], dp)}  ({r['sl_pips']} pips â€” beyond OB)
TP1       : {f(r['tp1'], dp)} ({r['tp1_pips']} pips â€” internal liquidity)
TP2       : {f(r['tp2'], dp)} ({r['tp2_pips']} pips â€” opposing liquidity)
RR        : 1:{r['rr1']} / 1:{r['rr2']}

REASON:
{r['sym']} in {phase_name} phase ({r['pattern']} pattern).
{sw} at {swl} confirmed by wick (NOT body close).
HTF FVG/OB confluence with {'Fib golden zone.' if r['in_fib'] else 'True Open reaction zone.'}
{'ChoCh + MSS' if r['mss'] else 'ChoCh'} on 15min confirms structure shifted {r['dir']}.
{r['conds']}/7 conditions aligned.

!! Verify on MT5 chart before entering !!
{'='*48}
""".strip()

# ================================================================== MAIN ====
def main():
    print("=" * 55)
    print("FX Signal Bot v4 â€” Corrected Logic")
    print("Proper FVG/OB/Sweep/ChoCh/MSS/LiqRun/Pattern")
    print("=" * 55)

    now     = datetime.now(timezone.utc)
    weekday = now.weekday()
    days    = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    session, block_num, _, _ = get_90min_block(now)

    print(f"UTC     : {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"Day     : {days[weekday]}")
    print(f"Session : {session['name']} | Block {block_num}/4")

    if weekday >= 4:
        print("Friday/Weekend â€” no trading.")
        send_email("FX Bot - No Trading Today",
                   f"Today is {days[weekday]}. Bot resting. See you Monday!")
        return

    signals, watching, predictions = [], [], []

    for symbol in ALL_PAIRS:
        try:
            r = analyze_pair(symbol, now)
            if r:
                t = r.get("type", "")
                if t == "signal":     signals.append(r)
                elif t == "watching": watching.append(r)
                elif t == "prediction": predictions.append(r)
            print(f"  Waiting {PAIR_DELAY}s before next pair...")
            time.sleep(PAIR_DELAY)
        except Exception as e:
            print(f"  [{symbol}] ERROR: {e}")
            time.sleep(PAIR_DELAY)

    print(f"\nScan done: {len(signals)} signals | {len(watching)} watching | {len(predictions)} predictions")

    # A+ Signals â€” highest priority
    for r in signals:
        d = "BUY" if r["dir"] == "bullish" else "SELL"
        send_email(
            f"[A+ SIGNAL] {r['sym']} {d} | {r['conds']}/7 | {r['session']} | {r['curr_phase']} phase",
            signal_body(r)
        )

    # Watching alerts
    for r in watching:
        send_email(
            f"[WATCHING] {r['sym']} {r['conds']}/7 | {r['session']} Block {r['block_num']} | {r['curr_phase']} phase",
            watching_body(r)
        )

    # One combined prediction email
    if predictions:
        combined = "\n\n" + "="*48 + "\n\n".join(prediction_body(r) for r in predictions)
        send_email(
            f"[PREDICTIONS] {len(predictions)} pairs | {session['name']} Block {block_num}",
            combined
        )

    if not signals and not watching and not predictions:
        print("No setups found this scan.")

if __name__ == "__main__":
    main()
