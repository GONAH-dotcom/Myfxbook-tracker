# signal_bot.py â€” FX Signal Bot v4
# Updated: 2026-07-04 16:40 Nairobi Time
# Author: Built for Gonah by Claude
# Strategy: Daye Quarterly Theory + ICT Concepts
# Pairs: GBP/USD, EUR/USD, AUD/JPY
# ================================================================

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

FOREX_SL_PIPS = 15
GOLD_SL_MIN   = 60
GOLD_SL_MAX   = 150
API_DELAY     = 15   # seconds between API calls (free tier 8/min)
PAIR_DELAY    = 45   # seconds between pairs

# ================================================================ EMAIL =====
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
        print(f"  [EMAIL SENT] {subject}")
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
        return [{"time":  v["datetime"],
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

# ============================================================ CANDLE UTILS ==
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
# Daye Quarterly Theory official 90-min cycle times
# All times in New York (NY) time â€” EDT = UTC-4
# UTC = NY + 4 hours

NY_UTC_OFFSET = 4  # EDT: add 4 to NY to get UTC. Change to 5 for EST (Nov-Mar)

def utc_to_ny(utc_dt):
    """Convert UTC datetime to NY datetime."""
    return utc_dt - timedelta(hours=NY_UTC_OFFSET)

# Daye QT Sessions and 90-min blocks (NY time â†’ UTC)
# Asia:      6:00PM - 12:00AM NY = 22:00 - 04:00 UTC
# London:   12:00AM -  6:00AM NY = 04:00 - 10:00 UTC
# New York:  6:00AM - 12:00PM NY = 10:00 - 16:00 UTC
# Afternoon:12:00PM -  6:00PM NY = 16:00 - 22:00 UTC

SESSIONS = [
    {
        "name": "Asia",
        "start_ny": 18, "end_ny": 24,
        "start_utc": 22, "end_utc": 28,
        "tso_utc_h": 23, "tso_utc_m": 30,  # TSO = 7:30PM NY = 23:30 UTC
        "blocks_ny": [
            (18.0, 19.5),  # Block 1: 6:00PM - 7:30PM NY
            (19.5, 21.0),  # Block 2: 7:30PM - 9:00PM NY  â† TSO
            (21.0, 22.5),  # Block 3: 9:00PM - 10:30PM NY
            (22.5, 24.0),  # Block 4: 10:30PM - 12:00AM NY
        ],
        "blocks_utc_min": [
            (22*60,      23*60+30),  # 22:00-23:30 UTC
            (23*60+30,   25*60),     # 23:30-01:00 UTC
            (25*60,      26*60+30),  # 01:00-02:30 UTC
            (26*60+30,   28*60),     # 02:30-04:00 UTC
        ],
    },
    {
        "name": "London",
        "start_ny": 0, "end_ny": 6,
        "start_utc": 4, "end_utc": 10,
        "tso_utc_h": 5, "tso_utc_m": 30,   # TSO = 1:30AM NY = 05:30 UTC
        "blocks_ny": [
            (0.0, 1.5),   # Block 1: 12:00AM - 1:30AM NY
            (1.5, 3.0),   # Block 2: 1:30AM - 3:00AM NY  â† TSO
            (3.0, 4.5),   # Block 3: 3:00AM - 4:30AM NY
            (4.5, 6.0),   # Block 4: 4:30AM - 6:00AM NY
        ],
        "blocks_utc_min": [
            (4*60,      5*60+30),   # 04:00-05:30 UTC
            (5*60+30,   7*60),      # 05:30-07:00 UTC
            (7*60,      8*60+30),   # 07:00-08:30 UTC
            (8*60+30,   10*60),     # 08:30-10:00 UTC
        ],
    },
    {
        "name": "New York",
        "start_ny": 6, "end_ny": 12,
        "start_utc": 10, "end_utc": 16,
        "tso_utc_h": 11, "tso_utc_m": 30,  # TSO = 7:30AM NY = 11:30 UTC
        "blocks_ny": [
            (6.0,  7.5),   # Block 1: 6:00AM - 7:30AM NY
            (7.5,  9.0),   # Block 2: 7:30AM - 9:00AM NY  â† TSO
            (9.0,  10.5),  # Block 3: 9:00AM - 10:30AM NY
            (10.5, 12.0),  # Block 4: 10:30AM - 12:00PM NY
        ],
        "blocks_utc_min": [
            (10*60,      11*60+30),  # 10:00-11:30 UTC
            (11*60+30,   13*60),     # 11:30-13:00 UTC
            (13*60,      14*60+30),  # 13:00-14:30 UTC
            (14*60+30,   16*60),     # 14:30-16:00 UTC
        ],
    },
    {
        "name": "Afternoon",
        "start_ny": 12, "end_ny": 18,
        "start_utc": 16, "end_utc": 22,
        "tso_utc_h": 17, "tso_utc_m": 30,  # TSO = 1:30PM NY = 17:30 UTC
        "blocks_ny": [
            (12.0, 13.5),  # Block 1: 12:00PM - 1:30PM NY
            (13.5, 15.0),  # Block 2: 1:30PM - 3:00PM NY  â† TSO
            (15.0, 16.5),  # Block 3: 3:00PM - 4:30PM NY
            (16.5, 18.0),  # Block 4: 4:30PM - 6:00PM NY
        ],
        "blocks_utc_min": [
            (16*60,      17*60+30),  # 16:00-17:30 UTC
            (17*60+30,   19*60),     # 17:30-19:00 UTC
            (19*60,      20*60+30),  # 19:00-20:30 UTC
            (20*60+30,   22*60),     # 20:30-22:00 UTC
        ],
    },
]

def get_session(utc_now):
    """Get current session based on UTC time (Daye QT official times)."""
    utc_min = utc_now.hour * 60 + utc_now.minute
    for s in SESSIONS:
        for b_start, b_end in s["blocks_utc_min"]:
            bs = b_start % (24*60)
            be = b_end   % (24*60)
            if bs <= be:
                if bs <= utc_min < be:
                    return s
            else:
                if utc_min >= bs or utc_min < be:
                    return s
    return SESSIONS[0]

def get_90min_block(utc_now):
    """Get current 90-min block (1-4) within current session."""
    utc_min = utc_now.hour * 60 + utc_now.minute
    session = get_session(utc_now)
    for i, (b_start, b_end) in enumerate(session["blocks_utc_min"]):
        bs = b_start % (24*60)
        be = b_end   % (24*60)
        if bs <= be:
            if bs <= utc_min < be:
                return session, i+1, bs, be
        else:
            if utc_min >= bs or utc_min < be:
                return session, i+1, bs, be
    b0 = session["blocks_utc_min"][0]
    return session, 1, b0[0]%(24*60), b0[1]%(24*60)

def block_ny_label(session, block_num):
    """Return NY time label for a block e.g. '1:30AM-3:00AM NY'."""
    blocks = session.get("blocks_ny", [])
    if block_num < 1 or block_num > len(blocks):
        return ""
    s, e = blocks[block_num - 1]
    def fmt(h):
        hh = int(h); mm = int((h % 1) * 60)
        p = "AM" if hh < 12 else "PM"
        h12 = hh % 12 or 12
        return f"{h12}:{mm:02d}{p}"
    return f"{fmt(s)}-{fmt(e)} NY"

def candles_in_block(candles, start_utc_min, end_utc_min, ref_date):
    """Get 15min candles within a UTC minute range."""
    out = []
    for c in candles:
        try:
            d = to_dt(c)
            cm = d.hour * 60 + d.minute
            if start_utc_min <= end_utc_min:
                if d.date() == ref_date and start_utc_min <= cm < end_utc_min:
                    out.append(c)
            else:
                prev = ref_date - timedelta(days=1)
                if (d.date() == prev and cm >= start_utc_min) or \
                   (d.date() == ref_date and cm < end_utc_min):
                    out.append(c)
        except:
            pass
    return out

# ======================================================== TRUE OPENS ========
def get_true_week_open(h1, today_utc):
    """True Week Open = Tuesday 00:00 NY = Tuesday 04:00 UTC."""
    for c in h1:
        try:
            d = to_dt(c)
            if d.weekday() == 1 and d.hour == 4 and d.minute == 0 and d.date() <= today_utc:
                return c["open"], d
        except:
            pass
    return None, None

def get_true_day_open(h1, today_utc):
    """True Day Open = 00:00 NY daily = 04:00 UTC."""
    for c in h1:
        try:
            d = to_dt(c)
            if d.date() == today_utc and d.hour == 4 and d.minute == 0:
                return c["open"], d
        except:
            pass
    return None, None

def get_true_session_open(m15, session, today_utc):
    """
    True Session Open (TSO) = Block 2 start of each session (Q2 of session).
    Asia TSO:      7:30PM NY = 23:30 UTC
    London TSO:    1:30AM NY = 05:30 UTC
    New York TSO:  7:30AM NY = 11:30 UTC
    Afternoon TSO: 1:30PM NY = 17:30 UTC
    """
    tso_h = session["tso_utc_h"]
    tso_m = session["tso_utc_m"]
    # Asia TSO at 23:30 UTC may be on previous UTC date
    search_dates = [today_utc - timedelta(days=1), today_utc] \
                   if session["name"] == "Asia" else [today_utc]
    for sd in search_dates:
        for c in m15:
            try:
                d = to_dt(c)
                if d.date() == sd and d.hour == tso_h and d.minute == tso_m:
                    return c["open"], d
            except:
                pass
    return None, None

def get_true_90min_open(m15, block_start_utc_min, today_utc):
    """True 90-min Open = first 15min candle of current block."""
    bh = (block_start_utc_min // 60) % 24
    bm =  block_start_utc_min % 60
    for offset in [0, -1]:
        sd = today_utc + timedelta(days=offset)
        for c in m15:
            try:
                d = to_dt(c)
                if d.date() == sd and d.hour == bh and d.minute == bm:
                    return c["open"], d
            except:
                pass
    return None, None

# ======================================================= SWING POINTS =======
def find_swings(candles, lookback=3):
    """
    Swing High: at least 'lookback' candles on LEFT have increasing highs
                leading up to reference candle (highest high),
                and at least 'lookback' candles on RIGHT have decreasing highs.
    Swing Low:  at least 'lookback' candles on LEFT have decreasing lows
                leading down to reference candle (lowest low),
                and at least 'lookback' candles on RIGHT have increasing lows.
    Applied on 4H and 1H only â€” these are the institutional swing points.
    """
    highs, lows = [], []
    for i in range(lookback, len(candles) - lookback):
        c = candles[i]

        # ---- SWING HIGH ----
        # Left side: each candle's high must be lower than the next (increasing into pivot)
        left_highs_increasing = all(
            candles[i - lookback + j]["high"] < candles[i - lookback + j + 1]["high"]
            for j in range(lookback - 1)
        )
        # Right side: each candle's high must be lower than the previous (decreasing from pivot)
        right_highs_decreasing = all(
            candles[i + j]["high"] > candles[i + j + 1]["high"]
            for j in range(1, lookback)
        )
        # Reference candle must be the highest point
        is_highest = all(c["high"] >= candles[i + k]["high"]
                         for k in range(-lookback, lookback + 1) if k != 0)

        if left_highs_increasing and right_highs_decreasing and is_highest:
            highs.append({
                "price": c["high"],
                "time":  c["time"],
                "idx":   i,
                "candle": c,
            })

        # ---- SWING LOW ----
        # Left side: each candle's low must be higher than the next (decreasing into pivot)
        left_lows_decreasing = all(
            candles[i - lookback + j]["low"] > candles[i - lookback + j + 1]["low"]
            for j in range(lookback - 1)
        )
        # Right side: each candle's low must be higher than the previous (increasing from pivot)
        right_lows_increasing = all(
            candles[i + j]["low"] < candles[i + j + 1]["low"]
            for j in range(1, lookback)
        )
        # Reference candle must be the lowest point
        is_lowest = all(c["low"] <= candles[i + k]["low"]
                        for k in range(-lookback, lookback + 1) if k != 0)

        if left_lows_decreasing and right_lows_increasing and is_lowest:
            lows.append({
                "price": c["low"],
                "time":  c["time"],
                "idx":   i,
                "candle": c,
            })

    return highs, lows

def get_structure_bias(candles, lookback=3):
    """
    Determine structural bias using last 2 swing highs and lows.
    HH + HL = bullish (Higher Highs + Higher Lows)
    LH + LL = bearish (Lower Highs + Lower Lows)
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

# ================================================ FVG â€” CORRECTED LOGIC =====
def detect_fvg(candles, direction=None):
    """
    Fair Value Gap (FVG) â€” Gonah's exact 3-candle rule:
    C1 = opposing color to trade direction
    C2 = displacement candle â€” engulfs C1 body (opposing color to C1)
         body_high(C2) > body_high(C1) AND body_low(C2) < body_low(C1)
    C3 = continuation candle â€” wicks do NOT fill the gap
    Gap: Bullish = C1.high < C3.low (empty space above C1, below C3)
         Bearish = C1.low > C3.high (empty space below C1, above C3)
    Only UNFILLED FVGs are returned (body has not closed back through).
    """
    fvgs = []
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        c1_col = candle_color(c1)
        c2_col = candle_color(c2)

        # C2 must be opposing color to C1
        if c2_col == c1_col:
            continue

        # C2 body must engulf C1 body
        if not (body_high(c2) > body_high(c1) and body_low(c2) < body_low(c1)):
            continue

        # Bullish FVG: C2 is bull, gap between C1.high and C3.low
        if c2_col == "bull" and c1["high"] < c3["low"]:
            fvgs.append({
                "type":   "bullish",
                "top":    c3["low"],
                "bottom": c1["high"],
                "mid":    (c3["low"] + c1["high"]) / 2,
                "ob":     c2,
                "c1":     c1,
                "c3":     c3,
                "time":   c2["time"],
                "filled": False,
            })

        # Bearish FVG: C2 is bear, gap between C3.high and C1.low
        if c2_col == "bear" and c1["low"] > c3["high"]:
            fvgs.append({
                "type":   "bearish",
                "top":    c1["low"],
                "bottom": c3["high"],
                "mid":    (c1["low"] + c3["high"]) / 2,
                "ob":     c2,
                "c1":     c1,
                "c3":     c3,
                "time":   c2["time"],
                "filled": False,
            })

    # Mark filled FVGs (body closed back through the gap)
    if candles:
        last_close = candles[-1]["close"]
        for fvg in fvgs:
            lo = min(fvg["top"], fvg["bottom"])
            hi = max(fvg["top"], fvg["bottom"])
            if fvg["type"] == "bullish" and last_close < lo:
                fvg["filled"] = True
            if fvg["type"] == "bearish" and last_close > hi:
                fvg["filled"] = True

    if direction:
        fvgs = [f for f in fvgs if f["type"] == direction]

    # Return only unfilled FVGs
    return [f for f in fvgs if not f["filled"]][-8:]

# ============================================== iFVG â€” CORRECTED LOGIC ======
def detect_ifvg(candles, direction=None):
    """
    Inverse FVG (iFVG) â€” A filled FVG that FLIPS its role:
    Bullish FVG â†’ price body-closes BELOW it â†’ becomes BEARISH resistance (iFVG)
    Bearish FVG â†’ price body-closes ABOVE it â†’ becomes BULLISH support (iFVG)

    When price RETURNS to the iFVG zone:
    iFVG bullish â†’ expect bounce UP  â†’ BUY zone
    iFVG bearish â†’ expect reject DOWN â†’ SELL zone

    direction="bullish" returns iFVG bullish zones (buy zones)
    direction="bearish" returns iFVG bearish zones (sell zones)
    """
    if not candles:
        return []

    # Step 1: Find ALL FVGs including filled ones
    all_fvgs = []
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        c1_col = candle_color(c1)
        c2_col = candle_color(c2)
        if c2_col == c1_col:
            continue
        if not (body_high(c2) > body_high(c1) and body_low(c2) < body_low(c1)):
            continue
        if c2_col == "bull" and c1["high"] < c3["low"]:
            all_fvgs.append({"type": "bullish", "top": c3["low"],
                              "bottom": c1["high"], "ob": c2,
                              "time": c2["time"], "idx": i-1})
        if c2_col == "bear" and c1["low"] > c3["high"]:
            all_fvgs.append({"type": "bearish", "top": c1["low"],
                              "bottom": c3["high"], "ob": c2,
                              "time": c2["time"], "idx": i-1})

    # Step 2: Find FVGs that were filled by a body close â†’ these become iFVGs
    ifvgs = []
    for fvg in all_fvgs:
        flo = min(fvg["top"], fvg["bottom"])
        fhi = max(fvg["top"], fvg["bottom"])
        filled_by = None
        for c in candles[fvg["idx"] + 2:]:
            if fvg["type"] == "bullish":
                if body_low(c) < flo:  # body closed below bullish FVG = filled
                    filled_by = c; break
            else:
                if body_high(c) > fhi:  # body closed above bearish FVG = filled
                    filled_by = c; break
        if not filled_by:
            continue

        # Step 3: Flip the role
        # Bullish FVG filled â†’ iFVG bearish (resistance)
        # Bearish FVG filled â†’ iFVG bullish (support)
        ifvg_dir = "bearish" if fvg["type"] == "bullish" else "bullish"
        ifvgs.append({
            **fvg,
            "type":      f"ifvg_{ifvg_dir}",
            "ifvg_dir":  ifvg_dir,
            "filled_by": filled_by["time"],
            "top":       fhi,
            "bottom":    flo,
            "mid":       (fhi + flo) / 2,
        })

    if direction:
        ifvgs = [f for f in ifvgs if f["ifvg_dir"] == direction]
    return ifvgs[-8:]

# ================================================== ORDER BLOCK =============
def detect_ob(candles, direction):
    """
    Order Block = last opposing-color candle BEFORE a strong displacement move.
    Displacement confirmed = next candle engulfs the OB candle's body.
    OB zone = full high-to-low range of that opposing candle.
    direction = trade direction (bullish OB = bearish candle before bull move)
    """
    obs = []
    for i in range(1, len(candles) - 1):
        c     = candles[i]
        c_nxt = candles[i+1]
        c_col   = candle_color(c)
        nxt_col = candle_color(c_nxt)

        if direction == "bullish" and c_col != "bear": continue
        if direction == "bearish" and c_col != "bull": continue
        if nxt_col == c_col: continue

        # Displacement: next candle engulfs OB body
        if not (body_high(c_nxt) > body_high(c) and body_low(c_nxt) < body_low(c)):
            continue

        obs.append({
            "high":  c["high"],
            "low":   c["low"],
            "mid":   (c["high"] + c["low"]) / 2,
            "open":  c["open"],
            "close": c["close"],
            "time":  c["time"],
        })
    return obs[-5:]

# ================================================= LIQUIDITY =================
def detect_liquidity_sweep(candles, highs, lows, price):
    """
    Liquidity Sweep = WICK takes out a swing high/low,
    but candle BODY closes back inside the range.
    (Body close through = breakout/run, NOT a sweep)

    BUY SIDE swept  (wick above swing high, body closed below) â†’ expect SELL
    SELL SIDE swept (wick below swing low,  body closed above) â†’ expect BUY
    """
    sweeps = []
    if not candles:
        return sweeps
    for c in candles[-6:]:
        for h in highs[-8:]:
            if c["high"] > h["price"] and body_high(c) <= h["price"]:
                sweeps.append({"type":   "buy_side_swept",
                                "level":  h["price"],
                                "dir":    "bearish",
                                "candle": c})
        for l in lows[-8:]:
            if c["low"] < l["price"] and body_low(c) >= l["price"]:
                sweeps.append({"type":   "sell_side_swept",
                                "level":  l["price"],
                                "dir":    "bullish",
                                "candle": c})
    return sweeps

def detect_liquidity_run(candles, direction):
    """
    Liquidity Run = price breaks range with a strong BODY CLOSE,
    then 2nd or 3rd candle pulls back to retest the OB/FVG formed,
    before continuing in breakout direction.
    Confirmed by body close candles (NOT just wicks).
    """
    if len(candles) < 4:
        return False, None
    recent = candles[-6:]
    for i in range(1, len(recent) - 1):
        bo = recent[i]; pb = recent[i+1]
        if direction == "bullish" and candle_color(bo) != "bull": continue
        if direction == "bearish" and candle_color(bo) != "bear": continue
        prev = recent[i-1]
        if body_size(prev) > 0 and body_size(bo) < body_size(prev) * 1.5: continue
        is_pb = pb["close"] < bo["close"] if direction == "bullish" else pb["close"] > bo["close"]
        if is_pb:
            return True, {"breakout": bo, "pullback": pb}
    return False, None

# ================================================= ChoCh / MSS ==============
def detect_choch(candles, direction):
    """
    Change of Character (ChoCh) = price BODY CLOSES beyond a recent swing level.
    NOT just a wick â€” must be a confirmed body close.
    direction = new direction being confirmed
    Bullish ChoCh = body close above recent lower high (bear structure broken)
    Bearish ChoCh = body close below recent higher low (bull structure broken)
    """
    if len(candles) < 8:
        return False, None
    recent = candles[-20:]
    if direction == "bullish":
        prev_highs = [body_high(c) for c in recent[:-4]]
        if not prev_highs: return False, None
        last_lh = max(prev_highs)
        for c in recent[-5:]:
            if body_high(c) > last_lh and candle_color(c) == "bull":
                return True, c
    else:
        prev_lows = [body_low(c) for c in recent[:-4]]
        if not prev_lows: return False, None
        last_hl = min(prev_lows)
        for c in recent[-5:]:
            if body_low(c) < last_hl and candle_color(c) == "bear":
                return True, c
    return False, None

def detect_mss(candles, direction):
    """
    Market Structure Shift (MSS) = aggressive ChoCh.
    The ChoCh candle ALSO engulfs the previous candle's body.
    Stronger confirmation than ChoCh alone.
    """
    choch, cc = detect_choch(candles, direction)
    if not choch or not cc:
        return False, None
    for i, c in enumerate(candles):
        if c["time"] == cc["time"] and i > 0:
            prev = candles[i-1]
            if body_high(cc) > body_high(prev) and body_low(cc) < body_low(prev):
                return True, cc
    return False, None

# ================================================= Q1 CLASSIFICATION ========
def classify_q1(q1_candles, prev_high, prev_low):
    """
    After Q1 closes, classify the price action to predict session pattern.

    X_BULLISH  = strong body close ABOVE previous block high â†’ XAMD
    X_BEARISH  = strong body close BELOW previous block low  â†’ XAMD
    M_SPIKE_HIGH = wick above prev high, body closed back inside â†’ AMDX
    M_SPIKE_LOW  = wick below prev low,  body closed back inside â†’ AMDX
    A_RANGING  = small bodies, no structural breakout â†’ AMDX

    XAMD: Q1=X, Q2=A, Q3=M(HUNT), Q4=D(HUNT)
    AMDX: Q1=A, Q2=M(HUNT), Q3=D(HUNT), Q4=X
    """
    if not q1_candles or prev_high is None or prev_low is None:
        return "UNCLEAR", {}

    q1_high      = max(c["high"]   for c in q1_candles)
    q1_low       = min(c["low"]    for c in q1_candles)
    q1_body_high = max(body_high(c) for c in q1_candles)
    q1_body_low  = min(body_low(c)  for c in q1_candles)
    bodies       = [body_size(c) for c in q1_candles]
    avg_body     = sum(bodies)/len(bodies) if bodies else 0
    q1_range     = q1_high - q1_low if q1_high > q1_low else 0.0001

    # Strong move: body closed beyond previous structure
    if q1_body_high > prev_high:
        return "X_BULLISH", {"reason": f"Body closed above prev high {prev_high:.5f}",
                              "q1_high": q1_high, "q1_low": q1_low}
    if q1_body_low < prev_low:
        return "X_BEARISH", {"reason": f"Body closed below prev low {prev_low:.5f}",
                              "q1_high": q1_high, "q1_low": q1_low}

    # Manipulation spike: wick beyond but body closed back inside
    if q1_high > prev_high and q1_body_high <= prev_high:
        return "M_SPIKE_HIGH", {"reason": f"Wick above {prev_high:.5f}, body returned inside",
                                 "q1_high": q1_high, "q1_low": q1_low}
    if q1_low < prev_low and q1_body_low >= prev_low:
        return "M_SPIKE_LOW", {"reason": f"Wick below {prev_low:.5f}, body returned inside",
                                "q1_high": q1_high, "q1_low": q1_low}

    # Ranging: small bodies, no breakout of previous structure
    if avg_body < (q1_range * 0.35):
        return "A_RANGING", {"reason": "Small body candles, no structural breakout â€” accumulation",
                              "q1_high": q1_high, "q1_low": q1_low}

    return "UNCLEAR", {"reason": "Price action unclear", "q1_high": q1_high, "q1_low": q1_low}

def get_pattern_and_phase(q1_class, block_num):
    """Map Q1 classification to pattern and current phase."""
    if q1_class in ["X_BULLISH", "X_BEARISH"]:
        pattern = "XAMD"
        phases  = {1: "X", 2: "A", 3: "M", 4: "D"}
    elif q1_class in ["M_SPIKE_HIGH", "M_SPIKE_LOW", "A_RANGING"]:
        pattern = "AMDX"
        phases  = {1: "A", 2: "M", 3: "D", 4: "X"}
    else:
        pattern = "UNKNOWN"
        phases  = {1: "?", 2: "?", 3: "?", 4: "?"}
    curr_phase  = phases.get(block_num, "?")
    next_phases = {k: v for k, v in phases.items() if k > block_num}
    return pattern, curr_phase, phases, next_phases

# ================================================= FIBONACCI ================
def fib_zone(price, hi, lo):
    """Check if price is in the golden zone (0.618-0.705 retracement)."""
    d    = hi - lo
    f618 = hi - 0.618 * d
    f705 = hi - 0.705 * d
    lo_z = min(f618, f705)
    hi_z = max(f618, f705)
    return lo_z <= price <= hi_z, {"0.618": f618, "0.705": f705, "0.5": hi - 0.5*d}

# ================================================= SL / TP ==================
def pip_size(symbol):
    return 0.01 if ("XAU" in symbol or "JPY" in symbol) else 0.0001

def calc_sl_tp(direction, entry, symbol, highs, lows, fvg):
    """
    SL = 15 pips fixed for forex, 60-150 pips logical for gold.
    TP1 = nearest internal liquidity (closest swing beyond entry).
    TP2 = opposing liquidity (next swing beyond TP1).
    """
    ps   = pip_size(symbol)
    dp   = 2 if "XAU" in symbol else 5
    is_g = "XAU" in symbol

    if is_g:
        ob = fvg.get("ob", {}) if fvg else {}
        if direction == "bullish":
            sl_raw  = ob.get("low", entry - GOLD_SL_MIN*ps) - 5*ps
            sp      = (entry - sl_raw) / ps
            if sp < GOLD_SL_MIN: sl_raw = entry - GOLD_SL_MIN*ps
            elif sp > GOLD_SL_MAX: return None, None, None
        else:
            sl_raw  = ob.get("high", entry + GOLD_SL_MIN*ps) + 5*ps
            sp      = (sl_raw - entry) / ps
            if sp < GOLD_SL_MIN: sl_raw = entry + GOLD_SL_MIN*ps
            elif sp > GOLD_SL_MAX: return None, None, None
        sl = round(sl_raw, dp)
    else:
        dist = FOREX_SL_PIPS * ps
        sl   = round(entry - dist, dp) if direction == "bullish" else round(entry + dist, dp)

    if direction == "bullish":
        c1 = sorted([h["price"] for h in highs if h["price"] > entry])
        tp1 = round(c1[0], dp) if c1 else round(entry + 30*ps, dp)
        c2  = sorted([h["price"] for h in highs if h["price"] > tp1])
        tp2 = round(c2[0], dp) if c2 else round(entry + 60*ps, dp)
    else:
        c1  = sorted([l["price"] for l in lows if l["price"] < entry], reverse=True)
        tp1 = round(c1[0], dp) if c1 else round(entry - 30*ps, dp)
        c2  = sorted([l["price"] for l in lows if l["price"] < tp1], reverse=True)
        tp2 = round(c2[0], dp) if c2 else round(entry - 60*ps, dp)

    return sl, tp1, tp2

# ============================================================= ANALYSIS ======
def analyze_pair(symbol, now):
    print(f"\n  [{symbol}] ---- scanning ----")

    # Fetch all timeframes
    daily = fetch_candles(symbol, "1day",  30)  # weekly/daily bias
    h4    = fetch_candles(symbol, "4h",    60)  # daily bias + HTF structure
    h1    = fetch_candles(symbol, "1h",    60)  # HTF zone refinement
    m15   = fetch_candles(symbol, "15min", 96)  # entry + Q1 classification
    price = fetch_price(symbol)                 # live price

    if not h4 or not h1 or not m15 or not price:
        print(f"  [{symbol}] insufficient data â€” skip")
        return None

    today  = now.date()
    now_ny = utc_to_ny(now)
    session, block_num, b_start, b_end = get_90min_block(now)

    print(f"  [{symbol}] UTC:{now.strftime('%H:%M')} NY:{now_ny.strftime('%H:%M')} | "
          f"{session['name']} Block {block_num}/4 | {block_ny_label(session, block_num)}")

    # ---- TRUE OPENS (NY time â€” non-negotiable reaction zones) ----
    two, _ = get_true_week_open(h1, today)
    tdo, _ = get_true_day_open(h1, today)
    tso, _ = get_true_session_open(m15, session, today)
    t90, _ = get_true_90min_open(m15, b_start, today)

    # ---- STEP 1: STRUCTURAL BIAS ----
    # Weekly bias = daily candle structure (HH/HL vs LH/LL)
    # Daily bias  = 4H candle structure
    weekly_bias, _, _ = get_structure_bias(daily, lookback=3)
    daily_bias,  _, _ = get_structure_bias(h4,    lookback=3)

    # Conflict = skip (avoid counter-trend traps)
    if weekly_bias != "neutral" and daily_bias != "neutral" and weekly_bias != daily_bias:
        print(f"  [{symbol}] bias conflict W={weekly_bias} D={daily_bias} â€” skip")
        return None

    overall_bias = daily_bias if daily_bias != "neutral" else weekly_bias
    if overall_bias == "neutral":
        overall_bias = "bullish" if h4[-1]["close"] > h4[0]["open"] else "bearish"

    # Swing points
    # 4H swings = primary (used for TP1 and TP2 calculation)
    # 1H swings = secondary (used for liquidity pool detection only)
    h4_highs, h4_lows = find_swings(h4, 3)
    h1_highs, h1_lows = find_swings(h1, 3)

    # TP targets from 4H structure ONLY (per strategy rules)
    tp_highs = sorted(h4_highs, key=lambda x: x["price"])
    tp_lows  = sorted(h4_lows,  key=lambda x: x["price"])

    # Liquidity pools = 4H + 1H combined (for sweep detection)
    all_highs = sorted(h4_highs + h1_highs, key=lambda x: x["price"])
    all_lows  = sorted(h4_lows  + h1_lows,  key=lambda x: x["price"])

    # HTF zones (4H = primary anchor, 1H = secondary refinement)
    h4_fvgs = detect_fvg(h4,  overall_bias)
    h4_ifvg = detect_ifvg(h4, overall_bias)
    h4_obs  = detect_ob(h4,   overall_bias)
    h1_fvgs = detect_fvg(h1,  overall_bias)
    h1_ifvg = detect_ifvg(h1, overall_bias)
    h1_obs  = detect_ob(h1,   overall_bias)
    all_htf_zones = h4_fvgs + h4_ifvg + h1_fvgs + h1_ifvg

    # Fibonacci golden zone (4H swings only)
    in_fib, fibs = False, {}
    if h4_highs and h4_lows:
        in_fib, fibs = fib_zone(price, h4_highs[-1]["price"], h4_lows[-1]["price"])

    # ---- STEP 3: Q1 CLASSIFICATION & PATTERN PREDICTION ----
    prev_s = b_start - 90; prev_e = b_start
    if prev_s < 0:
        pd = today - timedelta(days=1)
        prev_c = candles_in_block(m15, prev_s+1440, prev_e+1440, pd)
    else:
        prev_c = candles_in_block(m15, prev_s, prev_e, today)
    curr_c = candles_in_block(m15, b_start, b_end, today)

    prev_h = max((c["high"] for c in prev_c), default=None)
    prev_l = min((c["low"]  for c in prev_c), default=None)

    q1_class, q1_det = classify_q1(curr_c, prev_h, prev_l)
    pattern, curr_phase, phase_map, next_phases = get_pattern_and_phase(q1_class, block_num)
    is_hunt = curr_phase in ["M", "D"]

    print(f"  [{symbol}] Q1={q1_class} | Pattern={pattern} | Phase={curr_phase} | Bias={overall_bias}")

    # ---- STEP 4: LIQUIDITY ANALYSIS ----
    h4_sw = detect_liquidity_sweep(h4, h4_highs, h4_lows, price)
    h1_sw = detect_liquidity_sweep(h1, h1_highs, h1_lows, price)
    all_sw = h4_sw + h1_sw

    # Trade direction â€” sweep direction overrides structural bias
    trade_dir = overall_bias
    if all_sw:
        trade_dir = all_sw[-1]["dir"]

    liq_run, _ = detect_liquidity_run(h1, trade_dir)

    # ---- STEP 5: HTF ZONE TAP ----
    htf_zone = None
    buf = 0.5 if "XAU" in symbol else 0.0008
    for z in reversed(all_htf_zones):
        lo = min(z["top"], z["bottom"]); hi = max(z["top"], z["bottom"])
        if lo - buf <= price <= hi + buf:
            htf_zone = z; break

    ob_hit = None
    for ob in reversed(h4_obs + h1_obs):
        if ob["low"] - buf <= price <= ob["high"] + buf:
            ob_hit = ob
            if not htf_zone:
                htf_zone = {"type": overall_bias, "top": ob["high"],
                             "bottom": ob["low"], "mid": ob["mid"], "ob": ob}
            break

    # True open proximity (price near key NY time level)
    near_to = any(abs(price - v) <= (0.5 if "XAU" in symbol else 0.0010)
                  for v in [two, tdo, tso, t90] if v is not None)

    # ---- STEP 6: LTF CONFIRMATION (15min ChoCh / MSS) ----
    choch, _ = detect_choch(m15, trade_dir)
    mss,   _ = detect_mss(m15,   trade_dir)

    # ---- STEP 7: ENTRY FVG on 15min ----
    # Two valid types: normal FVG or iFVG â€” BOTH must align with 4H/1H zone
    m15_fvgs  = detect_fvg(m15,   trade_dir)
    m15_ifvgs = detect_ifvg(m15,  trade_dir)
    entry_fvg = None; entry_type = None
    buf2 = 1.0 if "XAU" in symbol else 0.0010

    htf_check = h4_fvgs + h4_ifvg + h4_obs + h1_fvgs + h1_ifvg + h1_obs
    htf_conf  = htf_zone is not None or near_to

    def overlaps_htf(flo, fhi):
        for z in htf_check:
            zl = min(z.get("top", z.get("high", 0)), z.get("bottom", z.get("low", 0)))
            zh = max(z.get("top", z.get("high", 0)), z.get("bottom", z.get("low", 0)))
            if flo <= zh and fhi >= zl:
                return True
        return False

    # Priority 1: normal 15min FVG near price + HTF confluence
    for fvg in reversed(m15_fvgs):
        lo = min(fvg["top"], fvg["bottom"]); hi = max(fvg["top"], fvg["bottom"])
        if lo - buf2 <= price <= hi + buf2 and (overlaps_htf(lo, hi) or htf_conf):
            entry_fvg = fvg; entry_type = "FVG"; break

    # Priority 2: 15min iFVG near price + must overlap 4H/1H zone (non-negotiable)
    if not entry_fvg:
        for fvg in reversed(m15_ifvgs):
            lo = min(fvg["top"], fvg["bottom"]); hi = max(fvg["top"], fvg["bottom"])
            if lo - buf2 <= price <= hi + buf2 and overlaps_htf(lo, hi):
                entry_fvg = fvg; entry_type = "iFVG"; break

    # Fallback: nearest 15min FVG (only if HTF confluence confirmed)
    if not entry_fvg and m15_fvgs and htf_conf:
        entry_fvg = m15_fvgs[-1]; entry_type = "FVG(fallback)"

    # ---- 7-CONDITION SCORECARD ----
    c1b = overall_bias != "neutral"           # 1. Structural bias confirmed
    c2b = is_hunt                              # 2. In M or D phase
    c3b = bool(all_sw) or liq_run             # 3. Liquidity swept or run
    c4b = htf_zone is not None or near_to     # 4. HTF zone / True Open tapped
    c5b = in_fib                              # 5. Fib golden zone (0.618-0.705)
    c6b = choch or mss                        # 6. ChoCh or MSS confirmed (body close)
    c7b = entry_fvg is not None               # 7. Valid entry FVG on 15min
    conds = sum([c1b, c2b, c3b, c4b, c5b, c6b, c7b])

    print(f"  [{symbol}] Conds:{conds}/7 | hunt={is_hunt} | sweep={c3b} | htf={c4b} | choch={c6b} | fvg={c7b}")

    result = {
        "sym": symbol, "price": price, "dir": trade_dir,
        "weekly_bias": weekly_bias, "daily_bias": daily_bias, "overall_bias": overall_bias,
        "session": session["name"], "block_num": block_num,
        "block_label": block_ny_label(session, block_num),
        "pattern": pattern, "q1_class": q1_class,
        "q1_reason": q1_det.get("reason", ""),
        "curr_phase": curr_phase, "next_phases": next_phases,
        "two": two, "tdo": tdo, "tso": tso, "t90": t90,
        "sweeps": all_sw, "liq_run": liq_run,
        "htf_zone": htf_zone, "ob_hit": ob_hit, "near_to": near_to,
        "in_fib": in_fib, "fibs": fibs,
        "choch": choch, "mss": mss,
        "fvg": entry_fvg, "entry_type": entry_type,
        "conds": conds,
        "c1b": c1b, "c2b": c2b, "c3b": c3b, "c4b": c4b,
        "c5b": c5b, "c6b": c6b, "c7b": c7b,
    }

    # A+ SIGNAL: 6-7/7, must be hunt phase, must have entry FVG
    if conds >= 6 and is_hunt and entry_fvg:
        entry = entry_fvg["mid"]
        sl, tp1, tp2 = calc_sl_tp(trade_dir, entry, symbol, tp_highs, tp_lows, entry_fvg)
        if sl and tp1 and tp2:
            ps = pip_size(symbol)
            if trade_dir == "bullish":
                sp = round((entry-sl)/ps);   t1 = round((tp1-entry)/ps); t2 = round((tp2-entry)/ps)
            else:
                sp = round((sl-entry)/ps);   t1 = round((entry-tp1)/ps); t2 = round((entry-tp2)/ps)
            result.update({
                "type": "signal", "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2,
                "sl_pips": sp, "tp1_pips": t1, "tp2_pips": t2,
                "rr1": round(t1/sp, 1) if sp else 0,
                "rr2": round(t2/sp, 1) if sp else 0,
            })
            return result

    # WATCHING: in hunt phase, 3+ conditions
    if is_hunt and conds >= 3:
        result["type"] = "watching"; return result

    # PREDICTION: pattern identified, hunt blocks coming
    if pattern != "UNKNOWN" and not is_hunt and next_phases:
        upcoming = [f"Q{k}={v}" for k, v in next_phases.items() if v in ["M", "D"]]
        if upcoming:
            result["type"] = "prediction"; result["upcoming"] = upcoming; return result

    return None

# =========================================================== EMAIL FORMAT ====
def f(v, dp=5):
    return f"{v:.{dp}f}" if v is not None else "N/A"

def to_str(r, dp):
    return (
        f"True Week Open (Tue 00:00 NY) : {f(r['two'], dp)}\n"
        f"True Day Open  (00:00 NY)     : {f(r['tdo'], dp)}\n"
        f"True Session Open (TSO)       : {f(r['tso'], dp)}  [{r['session']} Q2 start]\n"
        f"True 90-min Open              : {f(r['t90'], dp)}"
    )

def chk(r):
    sw = r["sweeps"][0]["type"].replace("_"," ").upper() if r["sweeps"] else \
         ("LIQ RUN" if r["liq_run"] else "None detected")
    return (
        f"[{'OK' if r['c1b'] else '--'}] Weekly + Daily structural bias ({r['overall_bias'].upper()})\n"
        f"[{'OK' if r['c2b'] else '--'}] M or D phase ({r['curr_phase']}) â€” HUNT block\n"
        f"[{'OK' if r['c3b'] else '--'}] Liquidity: {sw}\n"
        f"[{'OK' if r['c4b'] else '--'}] HTF zone tapped (4H/1H FVG/iFVG/OB or True Open)\n"
        f"[{'OK' if r['c5b'] else '--'}] Fibonacci golden zone (0.618-0.705)\n"
        f"[{'OK' if r['c6b'] else '--'}] ChoCh{'+ MSS' if r['mss'] else ''} confirmed (body close)\n"
        f"[{'OK' if r['c7b'] else '--'}] Entry FVG on 15min (3-candle rule, HTF aligned)"
    )

def email_prediction(r):
    dp = 2 if "XAU" in r["sym"] else 5
    return f"""
[PREDICTION] {r['sym']} | {r['session']} Block {r['block_num']}/4 | {r['block_label']}
{'='*50}
Q1 Read   : {r['q1_class']}
Reason    : {r['q1_reason']}
Pattern   : {r['pattern']}
Now       : Q{r['block_num']} = {r['curr_phase']} (not a hunt block)
HUNT Soon : {', '.join(r.get('upcoming', []))}
Bias      : {r['overall_bias'].upper()} (W={r['weekly_bias']} D={r['daily_bias']})
Price     : {f(r['price'], dp)}

{to_str(r, dp)}

Prepare your chart â€” HUNT blocks are coming!
Watch for liquidity sweep into HTF FVG/OB,
then 15min ChoCh to confirm entry direction.
{'='*50}""".strip()

def email_watching(r):
    dp = 2 if "XAU" in r["sym"] else 5
    d  = "BUY" if r["dir"] == "bullish" else "SELL"
    return f"""
[WATCHING] {r['sym']} {d} | {r['session']} Block {r['block_num']}/4 | {r['block_label']}
{'='*50}
Pattern   : {r['pattern']}  |  Q1: {r['q1_class']}
Bias      : {r['overall_bias'].upper()} (W={r['weekly_bias']} D={r['daily_bias']})
Price     : {f(r['price'], dp)}
Conditions: {r['conds']}/7

{to_str(r, dp)}

CHECKLIST:
{chk(r)}

Waiting for remaining conditions...
Stay alert â€” signal may fire soon!
{'='*50}""".strip()

def email_signal(r):
    dp   = 2 if "XAU" in r["sym"] else 5
    d    = "BUY" if r["dir"] == "bullish" else "SELL"
    sw   = r["sweeps"][0]["type"].replace("_"," ").upper() if r["sweeps"] else \
           ("LIQUIDITY RUN" if r["liq_run"] else "None")
    swl  = f(r["sweeps"][0]["level"], dp) if r["sweeps"] else "N/A"
    fibs = r.get("fibs", {})
    fvg  = r.get("fvg") or {}
    ob   = fvg.get("ob") or {}
    pn   = "Manipulation" if r["curr_phase"] == "M" else "Distribution"
    return f"""
[A+ SIGNAL] {r['sym']} {d} | {r['session']} Block {r['block_num']}/4 | {r['block_label']}
{'='*50}
Pattern   : {r['pattern']}  |  Q1: {r['q1_class']}
Phase     : {pn} ({r['curr_phase']})
Bias      : {r['overall_bias'].upper()} (W={r['weekly_bias']} D={r['daily_bias']})
Conditions: {r['conds']}/7

{to_str(r, dp)}

SETUP:
Liquidity : {sw} at {swl}
            (wick swept â€” body closed back inside)
HTF Zone  : {'4H/1H FVG/iFVG/OB tapped' if r['htf_zone'] else 'True Open reaction zone'}
OB Zone   : {f(ob.get('low', 0), dp)} - {f(ob.get('high', 0), dp)}
Fib 0.618 : {f(fibs.get('0.618'), dp)}
Fib 0.705 : {f(fibs.get('0.705'), dp)}
Fib Zone  : {'YES â€” price in golden zone' if r['in_fib'] else 'Near zone'}
ChoCh     : {'YES â€” body close confirmed' if r['choch'] else 'No'}
MSS       : {'YES â€” engulfing ChoCh' if r['mss'] else 'No'}
Entry FVG : {f(fvg.get('bottom', 0), dp)} - {f(fvg.get('top', 0), dp)}
Type      : {r.get('entry_type', 'FVG')}
OB Candle : {ob.get('time', 'N/A')}

TRADE:
Direction : {d}
Entry     : {f(r['entry'], dp)}
SL        : {f(r['sl'], dp)}  ({r['sl_pips']} pips â€” beyond OB)
TP1       : {f(r['tp1'], dp)} ({r['tp1_pips']} pips â€” internal liquidity)
TP2       : {f(r['tp2'], dp)} ({r['tp2_pips']} pips â€” opposing liquidity)
RR        : 1:{r['rr1']} / 1:{r['rr2']}

REASON:
{r['sym']} in {pn} phase ({r['pattern']} pattern).
{sw} at {swl} â€” wick confirmed, body closed back inside.
HTF 4H/1H {'FVG/OB confluence + Fib golden zone.' if r['in_fib'] else 'FVG/OB confluence.'}
{'ChoCh + MSS' if r['mss'] else 'ChoCh'} on 15min confirms {r['dir']} direction.
{r['conds']}/7 A+ conditions confirmed.

!! Always verify on MT5 chart before entering !!
{'='*50}""".strip()

# ================================================================ MAIN =======
def main():
    print("=" * 55)
    print("FX Signal Bot v4 | Updated 2026-07-04")
    print("Daye QT + ICT | GBP/USD EUR/USD AUD/JPY")
    print("=" * 55)

    now     = datetime.now(timezone.utc)
    now_ny  = utc_to_ny(now)
    weekday = now_ny.weekday()  # use NY time for trading day
    days    = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    session, block_num, _, _ = get_90min_block(now)

    print(f"UTC     : {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"NY Time : {now_ny.strftime('%Y-%m-%d %H:%M')} (EDT UTC-4)")
    print(f"Day(NY) : {days[weekday]}")
    print(f"Session : {session['name']} | Block {block_num}/4")
    print(f"Block   : {block_ny_label(session, block_num)}")

    # Friday + weekend = no trading
    if weekday >= 4:
        print("Friday/Weekend (NY) â€” no trading.")
        send_email("FX Bot â€” No Trading Today",
                   f"Today is {days[weekday]} NY time.\nBot resting. See you Monday! ðŸ’¤")
        return

    signals, watching, predictions = [], [], []

    for symbol in ALL_PAIRS:
        try:
            r = analyze_pair(symbol, now)
            if r:
                t = r.get("type", "")
                if   t == "signal":     signals.append(r)
                elif t == "watching":   watching.append(r)
                elif t == "prediction": predictions.append(r)
            print(f"  Waiting {PAIR_DELAY}s before next pair...")
            time.sleep(PAIR_DELAY)
        except Exception as e:
            print(f"  [{symbol}] ERROR: {e}")
            time.sleep(PAIR_DELAY)

    print(f"\nScan complete: {len(signals)} signals | {len(watching)} watching | {len(predictions)} predictions")

    # Send A+ signals first (highest priority)
    for r in signals:
        d = "BUY" if r["dir"] == "bullish" else "SELL"
        send_email(
            f"[A+ SIGNAL] {r['sym']} {d} | {r['conds']}/7 | {r['session']} | {r['curr_phase']}",
            email_signal(r)
        )

    # Send watching alerts
    for r in watching:
        send_email(
            f"[WATCHING] {r['sym']} {r['conds']}/7 | {r['session']} Blk{r['block_num']} | {r['curr_phase']}",
            email_watching(r)
        )

    # One combined prediction email
    if predictions:
        body = "\n\n" + ("="*50 + "\n\n").join(email_prediction(r) for r in predictions)
        send_email(
            f"[PREDICTIONS] {len(predictions)} pairs | {session['name']} Blk{block_num}",
            body
        )

    if not signals and not watching and not predictions:
        print("No setups found this scan.")

if __name__ == "__main__":
    main()
