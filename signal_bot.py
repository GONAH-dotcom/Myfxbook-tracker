# signal_bot.py â€” FX Signal Bot v5
# Updated: 2026-07-09
# Strategy: Daye Quarterly Theory + ICT Concepts
# Pairs: GBP/USD, EUR/USD, AUD/JPY
# Author: Built for Gonah by Claude

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
ALL_PAIRS      = ["GBP/USD", "EUR/USD", "AUD/JPY"]
FOREX_SL_PIPS  = 15
GOLD_SL_MIN    = 60
GOLD_SL_MAX    = 150
API_DELAY      = 15
PAIR_DELAY     = 45

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
            timeout=20)
        data = r.json()
        if "values" not in data:
            print(f"    [NO DATA] {symbol} {interval}: {data.get('message','')[:60]}")
            return []
        return [{"time": v["datetime"], "open": float(v["open"]),
                 "high": float(v["high"]), "low": float(v["low"]),
                 "close": float(v["close"])} for v in reversed(data["values"])]
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

# =========================================================== CANDLE UTILS ===
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
# New York time (EDT = UTC-4)
# UTC = NY + 4 hours

NY_UTC_OFFSET = 4  # EDT. Change to 5 for EST (Nov-Mar)

def utc_to_ny(utc_dt):
    return utc_dt - timedelta(hours=NY_UTC_OFFSET)

# Sessions defined in NY time with UTC equivalents
SESSIONS = [
    {
        "name": "Asia",
        "tso_utc_h": 23, "tso_utc_m": 30,  # TSO = 7:30PM NY = 23:30 UTC
        "blocks_ny": [(18.0,19.5),(19.5,21.0),(21.0,22.5),(22.5,24.0)],
        "blocks_utc_min": [
            (22*60, 23*60+30),   # Block 1: 6:00PM-7:30PM NY
            (23*60+30, 25*60),   # Block 2: 7:30PM-9:00PM NY  <- TSO
            (25*60, 26*60+30),   # Block 3: 9:00PM-10:30PM NY
            (26*60+30, 28*60),   # Block 4: 10:30PM-12:00AM NY
        ],
    },
    {
        "name": "London",
        "tso_utc_h": 5, "tso_utc_m": 30,   # TSO = 1:30AM NY = 05:30 UTC
        "blocks_ny": [(0.0,1.5),(1.5,3.0),(3.0,4.5),(4.5,6.0)],
        "blocks_utc_min": [
            (4*60, 5*60+30),     # Block 1: 12:00AM-1:30AM NY
            (5*60+30, 7*60),     # Block 2: 1:30AM-3:00AM NY  <- TSO
            (7*60, 8*60+30),     # Block 3: 3:00AM-4:30AM NY
            (8*60+30, 10*60),    # Block 4: 4:30AM-6:00AM NY
        ],
    },
    {
        "name": "New York",
        "tso_utc_h": 11, "tso_utc_m": 30,  # TSO = 7:30AM NY = 11:30 UTC
        "blocks_ny": [(6.0,7.5),(7.5,9.0),(9.0,10.5),(10.5,12.0)],
        "blocks_utc_min": [
            (10*60, 11*60+30),   # Block 1: 6:00AM-7:30AM NY
            (11*60+30, 13*60),   # Block 2: 7:30AM-9:00AM NY  <- TSO
            (13*60, 14*60+30),   # Block 3: 9:00AM-10:30AM NY
            (14*60+30, 16*60),   # Block 4: 10:30AM-12:00PM NY
        ],
    },
    {
        "name": "Afternoon",
        "tso_utc_h": 17, "tso_utc_m": 30,  # TSO = 1:30PM NY = 17:30 UTC
        "blocks_ny": [(12.0,13.5),(13.5,15.0),(15.0,16.5),(16.5,18.0)],
        "blocks_utc_min": [
            (16*60, 17*60+30),   # Block 1: 12:00PM-1:30PM NY
            (17*60+30, 19*60),   # Block 2: 1:30PM-3:00PM NY  <- TSO
            (19*60, 20*60+30),   # Block 3: 3:00PM-4:30PM NY
            (20*60+30, 22*60),   # Block 4: 4:30PM-6:00PM NY
        ],
    },
]

def get_session(utc_now):
    """Get current session based on UTC time."""
    utc_min = utc_now.hour * 60 + utc_now.minute
    for s in SESSIONS:
        for b_start, b_end in s["blocks_utc_min"]:
            bs = b_start % (24*60)
            be = b_end   % (24*60)
            if bs <= be:
                if bs <= utc_min < be: return s
            else:
                if utc_min >= bs or utc_min < be: return s
    return SESSIONS[0]

def get_90min_block(utc_now):
    """Get current 90-min block (1-4) and its UTC minute boundaries."""
    utc_min = utc_now.hour * 60 + utc_now.minute
    session = get_session(utc_now)
    for i, (b_start, b_end) in enumerate(session["blocks_utc_min"]):
        bs = b_start % (24*60)
        be = b_end   % (24*60)
        if bs <= be:
            if bs <= utc_min < be: return session, i+1, bs, be
        else:
            if utc_min >= bs or utc_min < be: return session, i+1, bs, be
    b0 = session["blocks_utc_min"][0]
    return session, 1, b0[0]%(24*60), b0[1]%(24*60)

def block_ny_label(session, block_num):
    """Return NY time label e.g. '1:30AM-3:00AM NY'."""
    blocks = session.get("blocks_ny", [])
    if block_num < 1 or block_num > len(blocks): return ""
    s, e = blocks[block_num - 1]
    def fmt(h):
        hh = int(h); mm = int((h % 1) * 60)
        p = "AM" if hh < 12 else "PM"; h12 = hh % 12 or 12
        return f"{h12}:{mm:02d}{p}"
    return f"{fmt(s)}-{fmt(e)} NY"

def candles_in_block(candles, start_utc_min, end_utc_min, ref_date):
    """Get 15min candles within a UTC minute range."""
    out = []
    for c in candles:
        try:
            d = to_dt(c); cm = d.hour * 60 + d.minute
            if start_utc_min <= end_utc_min:
                if d.date() == ref_date and start_utc_min <= cm < end_utc_min:
                    out.append(c)
            else:
                prev = ref_date - timedelta(days=1)
                if (d.date() == prev and cm >= start_utc_min) or \
                   (d.date() == ref_date and cm < end_utc_min):
                    out.append(c)
        except: pass
    return out

def is_trading_time(now_ny):
    """
    Trading window: Sunday 6:00PM NY to Friday 6:00PM NY.
    Asia session on Monday starts Sunday 6PM NY.
    Friday after 6PM NY = weekend begins.
    """
    weekday = now_ny.weekday()  # 0=Mon...6=Sun
    hour    = now_ny.hour

    if weekday == 6:   # Sunday
        return hour >= 18  # Only trade from 6PM NY (Monday Asia starts)
    if weekday == 5:   # Saturday
        return False
    if weekday == 4:   # Friday
        return hour < 18   # Stop at 6PM NY
    return True        # Mon-Thu always trade

# ======================================================== TRUE OPENS ========
def get_true_week_open(h1, today_utc):
    """
    True Week Open = OPEN PRICE of Tuesday 00:00 NY candle
                   = OPEN PRICE of Tuesday 04:00 UTC candle
    This is the Q2 start of the trading week.
    """
    for c in h1:
        try:
            d = to_dt(c)
            # Tuesday 04:00 UTC = Tuesday 00:00 NY
            if d.weekday() == 1 and d.hour == 4 and d.minute == 0 \
               and d.date() <= today_utc:
                return c["open"]  # Return the OPEN PRICE only
        except: pass
    return None

def get_true_day_open(h1, today_utc):
    """
    True Day Open = OPEN PRICE of 00:00 NY candle (daily)
                  = OPEN PRICE of 04:00 UTC candle
    Most important daily reference price â€” non-negotiable reaction zone.
    """
    for c in h1:
        try:
            d = to_dt(c)
            # 04:00 UTC = 00:00 NY (EDT)
            if d.date() == today_utc and d.hour == 4 and d.minute == 0:
                return c["open"]  # Return the OPEN PRICE only
        except: pass
    return None

def get_true_session_open(m15, session, today_utc):
    """
    True Session Open (TSO) = OPEN PRICE of FIRST candle of Q2 (Block 2)
    This is the candle that opens exactly at Block 2 start time.

    Asia TSO      = OPEN PRICE of 7:30PM NY candle  = 23:30 UTC
    London TSO    = OPEN PRICE of 1:30AM NY candle  = 05:30 UTC
    New York TSO  = OPEN PRICE of 7:30AM NY candle  = 11:30 UTC
    Afternoon TSO = OPEN PRICE of 1:30PM NY candle  = 17:30 UTC
    """
    tso_h = session["tso_utc_h"]
    tso_m = session["tso_utc_m"]
    # Asia TSO at 23:30 UTC may fall on previous UTC date
    search_dates = [today_utc - timedelta(days=1), today_utc] \
                   if session["name"] == "Asia" else [today_utc]
    for sd in search_dates:
        for c in m15:
            try:
                d = to_dt(c)
                if d.date() == sd and d.hour == tso_h and d.minute == tso_m:
                    return c["open"]  # Return the OPEN PRICE only
            except: pass
    return None

# ======================================================= SWING POINTS =======
def find_swings(candles, lookback=3):
    """
    Swing High: left side has INCREASING highs (at least 'lookback' candles),
                reference candle has the HIGHEST high,
                right side has DECREASING highs (at least 'lookback' candles).

    Swing Low:  left side has DECREASING lows (at least 'lookback' candles),
                reference candle has the LOWEST low,
                right side has INCREASING lows (at least 'lookback' candles).

    Applied on 4H and 1H only.
    """
    highs, lows = [], []
    for i in range(lookback, len(candles) - lookback):
        c = candles[i]

        # SWING HIGH
        left_inc  = all(candles[i-lookback+j]["high"] < candles[i-lookback+j+1]["high"]
                        for j in range(lookback-1))
        right_dec = all(candles[i+j]["high"] > candles[i+j+1]["high"]
                        for j in range(1, lookback))
        is_peak   = all(c["high"] >= candles[i+k]["high"]
                        for k in range(-lookback, lookback+1) if k != 0)
        if left_inc and right_dec and is_peak:
            highs.append({"price": c["high"], "time": c["time"], "idx": i, "candle": c})

        # SWING LOW
        left_dec  = all(candles[i-lookback+j]["low"] > candles[i-lookback+j+1]["low"]
                        for j in range(lookback-1))
        right_inc = all(candles[i+j]["low"] < candles[i+j+1]["low"]
                        for j in range(1, lookback))
        is_valley = all(c["low"] <= candles[i+k]["low"]
                        for k in range(-lookback, lookback+1) if k != 0)
        if left_dec and right_inc and is_valley:
            lows.append({"price": c["low"], "time": c["time"], "idx": i, "candle": c})

    return highs, lows

def get_structure_bias(candles, lookback=3):
    """
    HH + HL = bullish (Higher Highs + Higher Lows)
    LH + LL = bearish (Lower Highs + Lower Lows)
    Based on last 2 swing highs and lows.
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
    return "neutral", highs, lows

# ======================================================== ORDER BLOCKS ======
def detect_ob(candles, swing_highs, swing_lows, trend, max_obs=3):
    """
    Professional Order Block detection using swing points and trend.

    BEARISH OB (trend = bullish):
    - Price is in BULLISH trend (HH + HL)
    - Find recent SWING HIGHS (last max_obs)
    - At each swing high, look LEFT for the impulsive bearish move
    - The LAST BULLISH candle before that bearish impulse = BEARISH OB
    - When price RETURNS to that zone = SELL opportunity

    BULLISH OB (trend = bearish):
    - Price is in BEARISH trend (LH + LL)
    - Find recent SWING LOWS (last max_obs)
    - At each swing low, look LEFT for the impulsive bullish move
    - The LAST BEARISH candle before that bullish impulse = BULLISH OB
    - When price RETURNS to that zone = BUY opportunity
    """
    obs = []

    if trend == "bullish":
        # Look at last max_obs swing highs for BEARISH OBs
        recent_highs = swing_highs[-max_obs:] if len(swing_highs) >= max_obs \
                       else swing_highs
        for sh in recent_highs:
            sh_idx = sh["idx"]
            # Scan left from swing high to find impulsive bearish move
            # then find last bullish candle before it
            last_bull = None
            for j in range(sh_idx - 1, max(0, sh_idx - 20), -1):
                c     = candles[j]
                c_col = candle_color(c)
                # Check if next candle (j+1) started an impulsive bearish move
                if j + 1 <= sh_idx:
                    c_nxt = candles[j+1]
                    # Impulsive bearish = strong bearish body significantly
                    # larger than current candle
                    if candle_color(c_nxt) == "bear" and \
                       body_size(c_nxt) > body_size(c) * 0.8:
                        if c_col == "bull":
                            last_bull = c
                            break
                if c_col == "bull":
                    last_bull = c

            if last_bull:
                obs.append({
                    "type":       "bearish",
                    "high":       last_bull["high"],
                    "low":        last_bull["low"],
                    "mid":        (last_bull["high"] + last_bull["low"]) / 2,
                    "open":       last_bull["open"],
                    "close":      last_bull["close"],
                    "time":       last_bull["time"],
                    "swing_ref":  sh["price"],
                    "swing_time": sh["time"],
                })

    elif trend == "bearish":
        # Look at last max_obs swing lows for BULLISH OBs
        recent_lows = swing_lows[-max_obs:] if len(swing_lows) >= max_obs \
                      else swing_lows
        for sl in recent_lows:
            sl_idx = sl["idx"]
            # Scan left from swing low to find impulsive bullish move
            # then find last bearish candle before it
            last_bear = None
            for j in range(sl_idx - 1, max(0, sl_idx - 20), -1):
                c     = candles[j]
                c_col = candle_color(c)
                if j + 1 <= sl_idx:
                    c_nxt = candles[j+1]
                    # Impulsive bullish = strong bullish body
                    if candle_color(c_nxt) == "bull" and \
                       body_size(c_nxt) > body_size(c) * 0.8:
                        if c_col == "bear":
                            last_bear = c
                            break
                if c_col == "bear":
                    last_bear = c

            if last_bear:
                obs.append({
                    "type":       "bullish",
                    "high":       last_bear["high"],
                    "low":        last_bear["low"],
                    "mid":        (last_bear["high"] + last_bear["low"]) / 2,
                    "open":       last_bear["open"],
                    "close":      last_bear["close"],
                    "time":       last_bear["time"],
                    "swing_ref":  sl["price"],
                    "swing_time": sl["time"],
                })

    return obs

# ================================================ FVG â€” 3-CANDLE RULE =======
def detect_fvg(candles, direction=None):
    """
    Fair Value Gap (FVG):
    C1 = opposing color to C2
    C2 = engulfs C1 body (body_high(C2) > body_high(C1) AND body_low(C2) < body_low(C1))
    C3 = does NOT fill the gap (wicks don't close through)
    Bullish FVG = C1.high < C3.low  (gap above C1, below C3)
    Bearish FVG = C1.low  > C3.high (gap below C1, above C3)
    Only UNFILLED FVGs returned (last body close has not closed through gap).
    """
    fvgs = []
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        c1_col = candle_color(c1)
        c2_col = candle_color(c2)
        if c2_col == c1_col: continue
        if not (body_high(c2) > body_high(c1) and body_low(c2) < body_low(c1)):
            continue
        if c2_col == "bull" and c1["high"] < c3["low"]:
            fvgs.append({"type": "bullish", "top": c3["low"], "bottom": c1["high"],
                         "mid": (c3["low"]+c1["high"])/2, "ob": c2,
                         "time": c2["time"], "filled": False})
        if c2_col == "bear" and c1["low"] > c3["high"]:
            fvgs.append({"type": "bearish", "top": c1["low"], "bottom": c3["high"],
                         "mid": (c1["low"]+c3["high"])/2, "ob": c2,
                         "time": c2["time"], "filled": False})

    # Mark filled FVGs
    if candles:
        lc = candles[-1]["close"]
        for fvg in fvgs:
            lo = min(fvg["top"], fvg["bottom"])
            hi = max(fvg["top"], fvg["bottom"])
            if fvg["type"] == "bullish" and lc < lo: fvg["filled"] = True
            if fvg["type"] == "bearish" and lc > hi: fvg["filled"] = True

    if direction:
        fvgs = [f for f in fvgs if f["type"] == direction]
    return [f for f in fvgs if not f["filled"]][-8:]

# ============================================== iFVG â€” FLIPPED ROLE =========
def detect_ifvg(candles, direction=None):
    """
    Inverse FVG (iFVG):
    A FVG that price BODY-CLOSED through (filled it).
    That zone FLIPS its role:
    Bullish FVG filled by body close below â†’ becomes BEARISH resistance (iFVG)
    Bearish FVG filled by body close above â†’ becomes BULLISH support (iFVG)
    direction = "bullish" returns iFVG bullish (buy zones)
    direction = "bearish" returns iFVG bearish (sell zones)
    """
    if not candles: return []
    all_fvgs = []
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        c1_col = candle_color(c1); c2_col = candle_color(c2)
        if c2_col == c1_col: continue
        if not (body_high(c2) > body_high(c1) and body_low(c2) < body_low(c1)): continue
        if c2_col == "bull" and c1["high"] < c3["low"]:
            all_fvgs.append({"type":"bullish","top":c3["low"],"bottom":c1["high"],
                              "ob":c2,"time":c2["time"],"idx":i-1})
        if c2_col == "bear" and c1["low"] > c3["high"]:
            all_fvgs.append({"type":"bearish","top":c1["low"],"bottom":c3["high"],
                              "ob":c2,"time":c2["time"],"idx":i-1})

    ifvgs = []
    for fvg in all_fvgs:
        flo = min(fvg["top"],fvg["bottom"]); fhi = max(fvg["top"],fvg["bottom"])
        filled_by = None
        for c in candles[fvg["idx"]+2:]:
            if fvg["type"] == "bullish" and body_low(c) < flo:
                filled_by = c; break
            if fvg["type"] == "bearish" and body_high(c) > fhi:
                filled_by = c; break
        if not filled_by: continue
        ifvg_dir = "bearish" if fvg["type"] == "bullish" else "bullish"
        ifvgs.append({**fvg, "type": f"ifvg_{ifvg_dir}", "ifvg_dir": ifvg_dir,
                      "top": fhi, "bottom": flo, "mid": (fhi+flo)/2,
                      "filled_by": filled_by["time"]})
    if direction:
        ifvgs = [f for f in ifvgs if f["ifvg_dir"] == direction]
    return ifvgs[-8:]

# ================================================= LIQUIDITY =================
def detect_liquidity_sweep(candles, highs, lows):
    """
    Liquidity Sweep = WICK takes out a swing high/low
    but candle BODY closes back inside the range.
    BUY SIDE swept  (wick above swing high, body below) â†’ expect SELL
    SELL SIDE swept (wick below swing low,  body above) â†’ expect BUY
    """
    sweeps = []
    if not candles: return sweeps
    for c in candles[-6:]:
        for h in highs[-8:]:
            if c["high"] > h["price"] and body_high(c) <= h["price"]:
                sweeps.append({"type": "buy_side_swept", "level": h["price"],
                                "dir": "bearish", "candle": c})
        for l in lows[-8:]:
            if c["low"] < l["price"] and body_low(c) >= l["price"]:
                sweeps.append({"type": "sell_side_swept", "level": l["price"],
                                "dir": "bullish", "candle": c})
    return sweeps

def detect_liquidity_run(candles, direction):
    """
    Liquidity Run = strong BODY CLOSE breakout of range,
    then 2nd/3rd candle pulls back to retest OB/FVG,
    then continues in breakout direction.
    """
    if len(candles) < 4: return False, None
    recent = candles[-6:]
    for i in range(1, len(recent)-1):
        bo = recent[i]; pb = recent[i+1]
        if direction == "bullish" and candle_color(bo) != "bull": continue
        if direction == "bearish" and candle_color(bo) != "bear": continue
        prev = recent[i-1]
        if body_size(prev) > 0 and body_size(bo) < body_size(prev) * 1.5: continue
        is_pb = pb["close"] < bo["close"] if direction == "bullish" \
                else pb["close"] > bo["close"]
        if is_pb: return True, {"breakout": bo, "pullback": pb}
    return False, None

# ================================================= ChoCh / MSS ==============
def detect_choch(candles, direction):
    """
    Change of Character = BODY CLOSE beyond a recent swing level.
    NOT just a wick â€” must be confirmed body close.
    Bullish ChoCh = body close above recent lower high
    Bearish ChoCh = body close below recent higher low
    """
    if len(candles) < 8: return False, None
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
    Market Structure Shift = ChoCh candle also engulfs previous candle body.
    Stronger confirmation than ChoCh alone.
    """
    choch, cc = detect_choch(candles, direction)
    if not choch or not cc: return False, None
    for i, c in enumerate(candles):
        if c["time"] == cc["time"] and i > 0:
            prev = candles[i-1]
            if body_high(cc) > body_high(prev) and body_low(cc) < body_low(prev):
                return True, cc
    return False, None

# ================================================= Q1 CLASSIFICATION ========
def classify_q1(q1_candles, prev_high, prev_low):
    """
    After Q1 closes, classify to predict session pattern:
    X_BULLISH  = body closed ABOVE previous block high â†’ XAMD
    X_BEARISH  = body closed BELOW previous block low  â†’ XAMD
    M_SPIKE_HIGH = wick above prev high, body returned  â†’ AMDX
    M_SPIKE_LOW  = wick below prev low,  body returned  â†’ AMDX
    A_RANGING  = small bodies, no breakout              â†’ AMDX
    """
    if not q1_candles or prev_high is None or prev_low is None:
        return "UNCLEAR", {}
    q1_high      = max(c["high"]    for c in q1_candles)
    q1_low       = min(c["low"]     for c in q1_candles)
    q1_body_high = max(body_high(c) for c in q1_candles)
    q1_body_low  = min(body_low(c)  for c in q1_candles)
    bodies       = [body_size(c)    for c in q1_candles]
    avg_body     = sum(bodies)/len(bodies) if bodies else 0
    q1_range     = q1_high - q1_low if q1_high > q1_low else 0.0001

    if q1_body_high > prev_high:
        return "X_BULLISH", {"reason": f"Body closed above prev high {prev_high:.5f}",
                              "q1_high": q1_high, "q1_low": q1_low}
    if q1_body_low < prev_low:
        return "X_BEARISH", {"reason": f"Body closed below prev low {prev_low:.5f}",
                              "q1_high": q1_high, "q1_low": q1_low}
    if q1_high > prev_high and q1_body_high <= prev_high:
        return "M_SPIKE_HIGH", {"reason": f"Wick above {prev_high:.5f}, body returned",
                                 "q1_high": q1_high, "q1_low": q1_low}
    if q1_low < prev_low and q1_body_low >= prev_low:
        return "M_SPIKE_LOW", {"reason": f"Wick below {prev_low:.5f}, body returned",
                                "q1_high": q1_high, "q1_low": q1_low}
    if avg_body < (q1_range * 0.35):
        return "A_RANGING", {"reason": "Small bodies, no breakout â€” accumulation",
                              "q1_high": q1_high, "q1_low": q1_low}
    return "UNCLEAR", {"reason": "Price action unclear",
                        "q1_high": q1_high, "q1_low": q1_low}

def get_pattern_and_phase(q1_class, block_num):
    if q1_class in ["X_BULLISH", "X_BEARISH"]:
        pattern = "XAMD"; phases = {1:"X", 2:"A", 3:"M", 4:"D"}
    elif q1_class in ["M_SPIKE_HIGH", "M_SPIKE_LOW", "A_RANGING"]:
        pattern = "AMDX"; phases = {1:"A", 2:"M", 3:"D", 4:"X"}
    else:
        pattern = "UNKNOWN"; phases = {1:"?", 2:"?", 3:"?", 4:"?"}
    curr_phase  = phases.get(block_num, "?")
    next_phases = {k: v for k, v in phases.items() if k > block_num}
    return pattern, curr_phase, phases, next_phases

# ================================================= FIBONACCI ================
def fib_zone(price, hi, lo):
    """Golden zone = 0.618 to 0.705 retracement. Uses 4H swings only."""
    d    = hi - lo
    f618 = hi - 0.618*d
    f705 = hi - 0.705*d
    return min(f618,f705) <= price <= max(f618,f705), \
           {"0.618": f618, "0.705": f705, "0.5": hi-0.5*d}

# ================================================= SL / TP ==================
def pip_size(symbol):
    return 0.01 if ("XAU" in symbol or "JPY" in symbol) else 0.0001

def calc_sl_tp(direction, entry, symbol, h4_highs, h4_lows, fvg):
    """
    SL = 15 pips fixed (forex). 60-150 pips logical for gold.
    TP1 = nearest 4H swing high/low beyond entry (internal liquidity).
    TP2 = next 4H swing high/low beyond TP1 (opposing liquidity).
    TP calculated from 4H structure ONLY.
    """
    ps   = pip_size(symbol)
    dp   = 2 if "XAU" in symbol else 5
    is_g = "XAU" in symbol

    # SL calculation
    if is_g:
        ob = fvg.get("ob", {}) if fvg else {}
        if direction == "bullish":
            sl_raw  = ob.get("low", entry - GOLD_SL_MIN*ps) - 5*ps
            sl_pips = (entry - sl_raw) / ps
            if sl_pips < GOLD_SL_MIN: sl_raw = entry - GOLD_SL_MIN*ps
            elif sl_pips > GOLD_SL_MAX: return None, None, None
        else:
            sl_raw  = ob.get("high", entry + GOLD_SL_MIN*ps) + 5*ps
            sl_pips = (sl_raw - entry) / ps
            if sl_pips < GOLD_SL_MIN: sl_raw = entry + GOLD_SL_MIN*ps
            elif sl_pips > GOLD_SL_MAX: return None, None, None
        sl = round(sl_raw, dp)
    else:
        dist = FOREX_SL_PIPS * ps
        sl   = round(entry - dist, dp) if direction == "bullish" \
               else round(entry + dist, dp)

    # TP from 4H swings only
    if direction == "bullish":
        c1  = sorted([h["price"] for h in h4_highs if h["price"] > entry])
        tp1 = round(c1[0], dp) if c1 else round(entry + 30*ps, dp)
        c2  = sorted([h["price"] for h in h4_highs if h["price"] > tp1])
        tp2 = round(c2[0], dp) if c2 else round(entry + 60*ps, dp)
    else:
        c1  = sorted([l["price"] for l in h4_lows if l["price"] < entry], reverse=True)
        tp1 = round(c1[0], dp) if c1 else round(entry - 30*ps, dp)
        c2  = sorted([l["price"] for l in h4_lows if l["price"] < tp1], reverse=True)
        tp2 = round(c2[0], dp) if c2 else round(entry - 60*ps, dp)

    return sl, tp1, tp2

# ============================================================= ANALYSIS ======
def analyze_pair(symbol, now):
    print(f"\n  [{symbol}] ---- scanning ----")

    # Fetch candles
    daily = fetch_candles(symbol, "1day",  30)
    h4    = fetch_candles(symbol, "4h",    100)  # more history for OB detection
    h1    = fetch_candles(symbol, "1h",    60)
    m15   = fetch_candles(symbol, "15min", 96)
    price = fetch_price(symbol)

    if not h4 or not h1 or not m15 or not price:
        print(f"  [{symbol}] insufficient data â€” skip")
        return None

    today  = now.date()
    now_ny = utc_to_ny(now)
    session, block_num, b_start, b_end = get_90min_block(now)

    print(f"  [{symbol}] UTC:{now.strftime('%H:%M')} NY:{now_ny.strftime('%H:%M')} | "
          f"{session['name']} Block {block_num}/4 | {block_ny_label(session,block_num)}")

    # ---- TRUE OPENS (open PRICE of specific candles â€” NY time) ----
    two = get_true_week_open(h1, today)      # open price of Tue 00:00 NY
    tdo = get_true_day_open(h1, today)       # open price of 00:00 NY daily
    tso = get_true_session_open(m15, session, today)  # open price of Q2 start

    # ---- STEP 1: STRUCTURAL BIAS ----
    # Weekly bias = daily candle structure
    # Daily bias  = 4H candle structure
    weekly_bias, w_highs, w_lows = get_structure_bias(daily, lookback=3)
    daily_bias,  d_highs, d_lows = get_structure_bias(h4,    lookback=3)

    # Bias conflict = skip (no counter-trend trades)
    if weekly_bias != "neutral" and daily_bias != "neutral" \
       and weekly_bias != daily_bias:
        print(f"  [{symbol}] bias conflict W={weekly_bias} D={daily_bias} â€” skip")
        return None

    overall_bias = daily_bias if daily_bias != "neutral" else weekly_bias
    if overall_bias == "neutral":
        overall_bias = "bullish" if h4[-1]["close"] > h4[0]["open"] else "bearish"

    # ---- STEP 2: 4H/1H STRUCTURAL SHAPE ----
    # Swing points (4H primary, 1H secondary)
    h4_highs, h4_lows = find_swings(h4, lookback=3)
    h1_highs, h1_lows = find_swings(h1, lookback=3)

    # Liquidity pools = 4H + 1H combined (for sweep detection)
    all_highs = sorted(h4_highs + h1_highs, key=lambda x: x["price"])
    all_lows  = sorted(h4_lows  + h1_lows,  key=lambda x: x["price"])

    # ORDER BLOCKS (4H only, last 3 swing points, trend-based)
    h4_obs = detect_ob(h4, h4_highs, h4_lows, overall_bias, max_obs=3)
    h1_obs = detect_ob(h1, h1_highs, h1_lows, overall_bias, max_obs=3)

    # FVGs and iFVGs (4H and 1H)
    h4_fvgs = detect_fvg(h4, overall_bias)
    h4_ifvg = detect_ifvg(h4, overall_bias)
    h1_fvgs = detect_fvg(h1, overall_bias)
    h1_ifvg = detect_ifvg(h1, overall_bias)

    all_htf_zones = h4_fvgs + h4_ifvg + h1_fvgs + h1_ifvg

    # Fibonacci golden zone (4H swings only)
    in_fib, fibs = False, {}
    if h4_highs and h4_lows:
        in_fib, fibs = fib_zone(price, h4_highs[-1]["price"], h4_lows[-1]["price"])

    # ---- STEP 3: Q1 CLASSIFICATION ----
    prev_s = b_start - 90; prev_e = b_start
    if prev_s < 0:
        pd     = today - timedelta(days=1)
        prev_c = candles_in_block(m15, prev_s+1440, prev_e+1440, pd)
    else:
        prev_c = candles_in_block(m15, prev_s, prev_e, today)
    curr_c = candles_in_block(m15, b_start, b_end, today)

    prev_h = max((c["high"] for c in prev_c), default=None)
    prev_l = min((c["low"]  for c in prev_c), default=None)

    q1_class, q1_det = classify_q1(curr_c, prev_h, prev_l)
    pattern, curr_phase, phase_map, next_phases = \
        get_pattern_and_phase(q1_class, block_num)
    is_hunt = curr_phase in ["M", "D"]

    print(f"  [{symbol}] Q1={q1_class} | {pattern} | Phase={curr_phase} | "
          f"Bias={overall_bias}")

    # ---- STEP 4: LIQUIDITY ----
    h4_sweeps = detect_liquidity_sweep(h4, h4_highs, h4_lows)
    h1_sweeps = detect_liquidity_sweep(h1, h1_highs, h1_lows)
    all_sweeps = h4_sweeps + h1_sweeps

    trade_dir = overall_bias
    if all_sweeps:
        trade_dir = all_sweeps[-1]["dir"]

    liq_run, _ = detect_liquidity_run(h1, trade_dir)

    # ---- STEP 5: HTF ZONE TAP ----
    htf_zone = None
    buf = 0.5 if "XAU" in symbol else 0.0008

    # Check OB tap first (highest priority)
    ob_hit = None
    for ob in reversed(h4_obs + h1_obs):
        if ob["type"] == trade_dir and \
           ob["low"] - buf <= price <= ob["high"] + buf:
            ob_hit   = ob
            htf_zone = {"type": trade_dir, "top": ob["high"],
                        "bottom": ob["low"], "mid": ob["mid"], "ob": ob}
            break

    # Then check FVG/iFVG zones
    if not htf_zone:
        for z in reversed(all_htf_zones):
            lo = min(z["top"], z["bottom"]); hi = max(z["top"], z["bottom"])
            if lo - buf <= price <= hi + buf:
                htf_zone = z; break

    # Check true open proximity
    near_to = any(abs(price - v) <= (0.5 if "XAU" in symbol else 0.0010)
                  for v in [two, tdo, tso] if v is not None)

    # ---- STEP 6: LTF CONFIRMATION ----
    choch, _ = detect_choch(m15, trade_dir)
    mss,   _ = detect_mss(m15,   trade_dir)

    # ---- STEP 7: ENTRY FVG on 15min (must align with 4H/1H zone) ----
    m15_fvgs  = detect_fvg(m15,  trade_dir)
    m15_ifvgs = detect_ifvg(m15, trade_dir)
    entry_fvg = None; entry_type = None
    buf2 = 1.0 if "XAU" in symbol else 0.0010

    htf_for_check = h4_fvgs + h4_ifvg + h4_obs + h1_fvgs + h1_ifvg + h1_obs
    htf_conf = htf_zone is not None or near_to

    def overlaps_htf(flo, fhi):
        for z in htf_for_check:
            zl = min(z.get("top",z.get("high",0)), z.get("bottom",z.get("low",0)))
            zh = max(z.get("top",z.get("high",0)), z.get("bottom",z.get("low",0)))
            if flo <= zh and fhi >= zl: return True
        return False

    # Priority 1: normal 15min FVG
    for fvg in reversed(m15_fvgs):
        lo = min(fvg["top"],fvg["bottom"]); hi = max(fvg["top"],fvg["bottom"])
        if lo-buf2 <= price <= hi+buf2 and (overlaps_htf(lo,hi) or htf_conf):
            entry_fvg = fvg; entry_type = "FVG"; break

    # Priority 2: 15min iFVG (must overlap 4H/1H zone â€” non-negotiable)
    if not entry_fvg:
        for fvg in reversed(m15_ifvgs):
            lo = min(fvg["top"],fvg["bottom"]); hi = max(fvg["top"],fvg["bottom"])
            if lo-buf2 <= price <= hi+buf2 and overlaps_htf(lo,hi):
                entry_fvg = fvg; entry_type = "iFVG"; break

    # Fallback: nearest 15min FVG if HTF confluence confirmed
    if not entry_fvg and m15_fvgs and htf_conf:
        entry_fvg = m15_fvgs[-1]; entry_type = "FVG(fallback)"

    # ---- 7-CONDITION SCORECARD ----
    c1b = overall_bias != "neutral"
    c2b = is_hunt
    c3b = bool(all_sweeps) or liq_run
    c4b = htf_zone is not None or near_to
    c5b = in_fib
    c6b = choch or mss
    c7b = entry_fvg is not None
    conds = sum([c1b, c2b, c3b, c4b, c5b, c6b, c7b])

    print(f"  [{symbol}] Conds:{conds}/7 | hunt={is_hunt} | "
          f"sweep={c3b} | htf={c4b} | choch={c6b} | fvg={c7b}")

    result = {
        "sym": symbol, "price": price, "dir": trade_dir,
        "weekly_bias": weekly_bias, "daily_bias": daily_bias,
        "overall_bias": overall_bias,
        "session": session["name"], "block_num": block_num,
        "block_label": block_ny_label(session, block_num),
        "pattern": pattern, "q1_class": q1_class,
        "q1_reason": q1_det.get("reason",""),
        "curr_phase": curr_phase, "next_phases": next_phases,
        "two": two, "tdo": tdo, "tso": tso,
        "sweeps": all_sweeps, "liq_run": liq_run,
        "htf_zone": htf_zone, "ob_hit": ob_hit, "near_to": near_to,
        "in_fib": in_fib, "fibs": fibs,
        "choch": choch, "mss": mss,
        "fvg": entry_fvg, "entry_type": entry_type,
        "conds": conds,
        "c1b":c1b,"c2b":c2b,"c3b":c3b,"c4b":c4b,
        "c5b":c5b,"c6b":c6b,"c7b":c7b,
    }

    # A+ SIGNAL: 6-7/7, hunt phase, entry FVG confirmed
    if conds >= 6 and is_hunt and entry_fvg:
        entry = entry_fvg["mid"]
        sl, tp1, tp2 = calc_sl_tp(trade_dir, entry, symbol,
                                   h4_highs, h4_lows, entry_fvg)
        if sl and tp1 and tp2:
            ps = pip_size(symbol)
            if trade_dir == "bullish":
                sp=round((entry-sl)/ps); t1=round((tp1-entry)/ps); t2=round((tp2-entry)/ps)
            else:
                sp=round((sl-entry)/ps); t1=round((entry-tp1)/ps); t2=round((entry-tp2)/ps)
            result.update({
                "type":"signal","entry":entry,"sl":sl,"tp1":tp1,"tp2":tp2,
                "sl_pips":sp,"tp1_pips":t1,"tp2_pips":t2,
                "rr1":round(t1/sp,1) if sp else 0,
                "rr2":round(t2/sp,1) if sp else 0,
            })
            return result

    # WATCHING: hunt phase, 3+ conditions
    if is_hunt and conds >= 3:
        result["type"] = "watching"; return result

    # PREDICTION: pattern known, hunt coming
    if pattern != "UNKNOWN" and not is_hunt and next_phases:
        upcoming = [f"Q{k}={v}" for k,v in next_phases.items() if v in ["M","D"]]
        if upcoming:
            result["type"] = "prediction"
            result["upcoming"] = upcoming
            return result

    return None

# =========================================================== EMAIL FORMAT ====
def f(v, dp=5):
    return f"{v:.{dp}f}" if v is not None else "N/A"

def to_str(r, dp):
    return (
        f"True Week Open (Tue 00:00 NY) : {f(r['two'],dp)}\n"
        f"True Day Open  (00:00 NY)     : {f(r['tdo'],dp)}\n"
        f"True Session Open (TSO)       : {f(r['tso'],dp)}  "
        f"[{r['session']} Q2 open price]"
    )

def chk(r):
    sw = r["sweeps"][0]["type"].replace("_"," ").upper() if r["sweeps"] else \
         ("LIQ RUN" if r["liq_run"] else "None detected")
    return (
        f"[{'OK' if r['c1b'] else '--'}] Weekly+Daily structural bias "
        f"({r['overall_bias'].upper()})\n"
        f"[{'OK' if r['c2b'] else '--'}] M or D phase ({r['curr_phase']}) "
        f"â€” HUNT block\n"
        f"[{'OK' if r['c3b'] else '--'}] Liquidity: {sw}\n"
        f"[{'OK' if r['c4b'] else '--'}] HTF zone tapped "
        f"(4H/1H OB/FVG/iFVG or True Open)\n"
        f"[{'OK' if r['c5b'] else '--'}] Fibonacci golden zone (0.618-0.705)\n"
        f"[{'OK' if r['c6b'] else '--'}] "
        f"ChoCh{'+ MSS' if r['mss'] else ''} confirmed (body close)\n"
        f"[{'OK' if r['c7b'] else '--'}] Entry FVG on 15min "
        f"(3-candle rule, 4H/1H aligned)"
    )

def email_prediction(r):
    dp = 2 if "XAU" in r["sym"] else 5
    return f"""
[PREDICTION] {r['sym']} | {r['session']} Block {r['block_num']}/4
{r['block_label']}
{'='*50}
Q1 Read   : {r['q1_class']}
Reason    : {r['q1_reason']}
Pattern   : {r['pattern']}
Now       : Q{r['block_num']} = {r['curr_phase']} (not hunt)
HUNT Soon : {', '.join(r.get('upcoming',[]))}
Bias      : {r['overall_bias'].upper()}
Price     : {f(r['price'],dp)}

{to_str(r,dp)}

Prepare chart â€” HUNT blocks coming!
Watch for liquidity sweep into 4H OB/FVG,
then 15min ChoCh to confirm direction.
{'='*50}""".strip()

def email_watching(r):
    dp = 2 if "XAU" in r["sym"] else 5
    d  = "BUY" if r["dir"] == "bullish" else "SELL"
    return f"""
[WATCHING] {r['sym']} {d} | {r['session']} Block {r['block_num']}/4
{r['block_label']} | {r['curr_phase']} phase
{'='*50}
Pattern   : {r['pattern']}  Q1: {r['q1_class']}
Bias      : {r['overall_bias'].upper()} (W={r['weekly_bias']} D={r['daily_bias']})
Price     : {f(r['price'],dp)}
Conditions: {r['conds']}/7

{to_str(r,dp)}

CHECKLIST:
{chk(r)}

Waiting for remaining conditions...
{'='*50}""".strip()

def email_signal(r):
    dp   = 2 if "XAU" in r["sym"] else 5
    d    = "BUY" if r["dir"] == "bullish" else "SELL"
    sw   = r["sweeps"][0]["type"].replace("_"," ").upper() if r["sweeps"] else \
           ("LIQ RUN" if r["liq_run"] else "None")
    swl  = f(r["sweeps"][0]["level"],dp) if r["sweeps"] else "N/A"
    fibs = r.get("fibs",{})
    fvg  = r.get("fvg") or {}
    ob   = r.get("ob_hit") or {}
    pn   = "Manipulation" if r["curr_phase"]=="M" else "Distribution"
    return f"""
[A+ SIGNAL] {r['sym']} {d} | {r['session']} Block {r['block_num']}/4
{r['block_label']} | {pn} phase
{'='*50}
Pattern   : {r['pattern']}  Q1: {r['q1_class']}
Bias      : {r['overall_bias'].upper()} (W={r['weekly_bias']} D={r['daily_bias']})
Conditions: {r['conds']}/7

{to_str(r,dp)}

SETUP:
Liquidity : {sw} at {swl}
            (wick swept â€” body closed back inside)
4H OB Zone: {f(ob.get('low',0),dp)} - {f(ob.get('high',0),dp)}
            Swing ref: {f(ob.get('swing_ref'),dp)}
HTF Zone  : {'OB tapped' if r['ob_hit'] else 'FVG/iFVG tapped' if r['htf_zone'] else 'True Open'}
Fib 0.618 : {f(fibs.get('0.618'),dp)}
Fib 0.705 : {f(fibs.get('0.705'),dp)}
Fib Zone  : {'YES' if r['in_fib'] else 'Near'}
ChoCh     : {'YES (body close)' if r['choch'] else 'No'}
MSS       : {'YES (engulfing)' if r['mss'] else 'No'}
Entry FVG : {f(fvg.get('bottom',0),dp)} - {f(fvg.get('top',0),dp)}
Type      : {r.get('entry_type','FVG')}

TRADE:
Direction : {d}
Entry     : {f(r['entry'],dp)}
SL        : {f(r['sl'],dp)}  ({r['sl_pips']} pips)
TP1       : {f(r['tp1'],dp)} ({r['tp1_pips']} pips â€” 4H internal liq)
TP2       : {f(r['tp2'],dp)} ({r['tp2_pips']} pips â€” 4H opposing liq)
RR        : 1:{r['rr1']} / 1:{r['rr2']}

REASON:
{r['sym']} in {pn} phase ({r['pattern']} pattern).
{sw} at {swl} â€” wick confirmed, body closed back.
4H OB + {'Fib golden zone' if r['in_fib'] else 'HTF zone'} confluence.
{'ChoCh+MSS' if r['mss'] else 'ChoCh'} on 15min confirms {r['dir']}.
{r['conds']}/7 A+ conditions confirmed.

!! Verify on MT5 chart before entering !!
{'='*50}""".strip()

# ================================================================ MAIN =======
def main():
    print("=" * 55)
    print("FX Signal Bot v5 | Updated 2026-07-09")
    print("Daye QT + ICT | GBP/USD EUR/USD AUD/JPY")
    print("=" * 55)

    now     = datetime.now(timezone.utc)
    now_ny  = utc_to_ny(now)
    days    = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    weekday = now_ny.weekday()
    session, block_num, _, _ = get_90min_block(now)

    print(f"UTC     : {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"NY Time : {now_ny.strftime('%Y-%m-%d %H:%M')} (EDT UTC-4)")
    print(f"Day(NY) : {days[weekday]}")
    print(f"Session : {session['name']} | Block {block_num}/4")
    print(f"Block   : {block_ny_label(session,block_num)}")

    if not is_trading_time(now_ny):
        print("Weekend/no trading period â€” bot resting.")
        send_email("FX Bot â€” No Trading",
                   f"Today is {days[weekday]} NY.\nBot resting. "
                   f"Trading resumes Sunday 6PM NY (Monday Asia).")
        return

    signals, watching, predictions = [], [], []

    for symbol in ALL_PAIRS:
        try:
            r = analyze_pair(symbol, now)
            if r:
                t = r.get("type","")
                if   t == "signal":     signals.append(r)
                elif t == "watching":   watching.append(r)
                elif t == "prediction": predictions.append(r)
            print(f"  Waiting {PAIR_DELAY}s...")
            time.sleep(PAIR_DELAY)
        except Exception as e:
            print(f"  [{symbol}] ERROR: {e}")
            time.sleep(PAIR_DELAY)

    print(f"\nDone: {len(signals)} signals | {len(watching)} watching | "
          f"{len(predictions)} predictions")

    for r in signals:
        d = "BUY" if r["dir"]=="bullish" else "SELL"
        send_email(
            f"[A+ SIGNAL] {r['sym']} {d} | {r['conds']}/7 | "
            f"{r['session']} | {r['curr_phase']}",
            email_signal(r))

    for r in watching:
        send_email(
            f"[WATCHING] {r['sym']} {r['conds']}/7 | "
            f"{r['session']} Blk{r['block_num']} | {r['curr_phase']}",
            email_watching(r))

    if predictions:
        body = ("\n\n"+"="*50+"\n\n").join(email_prediction(r) for r in predictions)
        send_email(
            f"[PREDICTIONS] {len(predictions)} pairs | "
            f"{session['name']} Blk{block_num}",
            body)

    if not signals and not watching and not predictions:
        print("No setups found this scan.")

if __name__ == "__main__":
    main()
