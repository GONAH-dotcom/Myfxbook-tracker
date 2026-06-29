import os
import requests
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

# ------------------------------------------------------------------ CONFIG ---
API_KEY        = os.environ.get("TWELVE_DATA_API_KEY")
GMAIL_USER     = "gonahcharo1993@gmail.com"
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

ALL_PAIRS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "USD/CAD", "AUD/USD", "NZD/USD", "XAU/USD"
]

FOREX_SL_PIPS = 15
GOLD_SL_MIN   = 60
GOLD_SL_MAX   = 150
MIN_CONDITIONS = 4   # out of 6

API_DELAY = 15   # seconds between each API call (safe for 8/min limit)

# ------------------------------------------------------------------- EMAIL ---
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
        print(f"  Email sent: {subject}")
    except Exception as e:
        print(f"  Email error: {e}")

# --------------------------------------------------------------- TWELVE DATA --
def fetch_candles(symbol, interval, outputsize=50):
    """Fetch candles with rate-limit delay."""
    time.sleep(API_DELAY)
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol":     symbol,
        "interval":   interval,
        "outputsize": outputsize,
        "apikey":     API_KEY,
        "format":     "JSON"
    }
    try:
        r    = requests.get(url, params=params, timeout=20)
        data = r.json()
        if "values" not in data:
            print(f"    No data {symbol} {interval}: {data.get('message','unknown')}")
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
        print(f"    Fetch error {symbol} {interval}: {e}")
        return []

def fetch_price(symbol):
    time.sleep(API_DELAY)
    try:
        r    = requests.get("https://api.twelvedata.com/price",
                            params={"symbol": symbol, "apikey": API_KEY}, timeout=10)
        data = r.json()
        return float(data.get("price", 0))
    except:
        return 0.0

# -------------------------------------------------------- QUARTERLY THEORY ---
def get_session_info(hour):
    sessions = [
        {"name": "Asian",       "start": 0,  "end": 6},
        {"name": "London",      "start": 6,  "end": 12},
        {"name": "New York AM", "start": 12, "end": 18},
        {"name": "New York PM", "start": 18, "end": 24},
    ]
    for s in sessions:
        if s["start"] <= hour < s["end"]:
            elapsed      = (hour - s["start"]) * 60
            cycle_num    = elapsed // 90 + 1          # 1-4
            cycle_start  = s["start"] + (cycle_num - 1) * 1.5
            cycle_q2_h   = cycle_start + 0.75         # 45 min into cycle
            session_q2_h = s["start"] + 1.5           # 90 min into session
            return {
                "name":           s["name"],
                "start":          s["start"],
                "end":            s["end"],
                "session_q":      int(cycle_num),
                "cycle_start":    cycle_start,
                "cycle_q2_h":     cycle_q2_h,
                "session_q2_h":   session_q2_h,
            }
    return {"name": "Unknown", "start": 0, "end": 6,
            "session_q": 1, "cycle_start": 0,
            "cycle_q2_h": 0.75, "session_q2_h": 1.5}

def get_yearly_q(month):  return (month - 1) // 3 + 1
def get_monthly_q(day):   return min((day - 1) // 7 + 1, 4)
def get_weekly_q(wday):   return wday + 1 if wday < 4 else None

def detect_pattern(candles, htf_bias):
    """XAMD if Q1 is strongly directional, else AMDX."""
    if not candles or len(candles) < 3:
        return "AMDX"
    hi    = max(c["high"]  for c in candles)
    lo    = min(c["low"]   for c in candles)
    rng   = hi - lo
    body  = abs(candles[-1]["close"] - candles[0]["open"])
    ratio = body / rng if rng > 0 else 0
    return "XAMD" if ratio > 0.4 else "AMDX"

def phase_label(pattern, q):
    xamd = {1:"X", 2:"A", 3:"M", 4:"D"}
    amdx = {1:"A", 2:"M", 3:"D", 4:"X"}
    return (xamd if pattern == "XAMD" else amdx).get(q, "?")

def build_stack(now, c4h, c1h, c15m, c5m, session_info):
    """Build 6-level fractal stack using available candles."""
    wday = now.weekday()
    yq   = get_yearly_q(now.month)
    mq   = get_monthly_q(now.day)
    wq   = get_weekly_q(wday) or 1
    dq   = wq
    sq   = session_info["session_q"]
    cq   = sq

    # HTF bias from 4H
    if c4h and len(c4h) >= 2:
        htf_bias = "bullish" if c4h[-1]["close"] > c4h[0]["open"] else "bearish"
    else:
        htf_bias = "bearish"

    # Yearly pattern â€” use first quarter of year candles (4H)
    y_q1 = c4h[:int(len(c4h)*0.25)] if c4h else []
    y_pat = detect_pattern(y_q1, htf_bias)
    y_phase = phase_label(y_pat, yq)

    # Monthly pattern â€” use first week of candles (4H)
    m_q1 = c4h[:int(len(c4h)*0.25)] if c4h else []
    m_pat = detect_pattern(m_q1, htf_bias)
    m_phase = phase_label(m_pat, mq)

    # Weekly pattern â€” use Monday candles (4H)
    w_q1 = [c for c in c4h if
            datetime.strptime(c["time"], "%Y-%m-%d %H:%M:%S").weekday() == 0][:6] if c4h else []
    w_pat = detect_pattern(w_q1, htf_bias)
    w_phase = phase_label(w_pat, wq)

    # Daily pattern â€” use Asian session (1H)
    d_q1 = [c for c in c1h if
            0 <= datetime.strptime(c["time"], "%Y-%m-%d %H:%M:%S").hour < 6][:6] if c1h else []
    d_pat = detect_pattern(d_q1, htf_bias)
    d_phase = phase_label(d_pat, dq)

    # Session pattern â€” use first 90-min of session (15min)
    s_start = session_info["start"]
    s_q1 = [c for c in c15m if
            s_start <= datetime.strptime(c["time"], "%Y-%m-%d %H:%M:%S").hour < s_start + 2][:6] if c15m else []
    s_pat = detect_pattern(s_q1, htf_bias)
    s_phase = phase_label(s_pat, sq)

    # 90-min cycle pattern â€” use first 45-min of cycle (5min)
    c_start = int(session_info["cycle_start"])
    cy_q1 = [c for c in c5m if
             int(session_info["cycle_start"]) <= datetime.strptime(c["time"], "%Y-%m-%d %H:%M:%S").hour <= c_start + 1][:9] if c5m else []
    cy_pat = detect_pattern(cy_q1, htf_bias)
    cy_phase = phase_label(cy_pat, cq)

    # Alignment score â€” count M or D phases
    phases = [y_phase, m_phase, w_phase, d_phase, s_phase, cy_phase]
    score  = sum(1 for p in phases if p in ["M", "D"])

    # Overall bias â€” majority
    biases = [htf_bias] * 6
    overall = "bearish" if biases.count("bearish") >= 3 else "bullish"

    return {
        "yearly":  {"q": yq,  "pattern": y_pat,  "phase": y_phase},
        "monthly": {"q": mq,  "pattern": m_pat,  "phase": m_phase},
        "weekly":  {"q": wq,  "pattern": w_pat,  "phase": w_phase},
        "daily":   {"q": dq,  "pattern": d_pat,  "phase": d_phase},
        "session": {"q": sq,  "pattern": s_pat,  "phase": s_phase,
                    "name": session_info["name"]},
        "90min":   {"q": cq,  "pattern": cy_pat, "phase": cy_phase},
        "score":   score,
        "bias":    overall,
        "htf_bias": htf_bias,
    }

# --------------------------------------------------------- TRUE OPENS -------
def get_true_opens(now, c4h, c1h, c15m, c5m, session_info):
    opens = {}
    dp_fmt = "%Y-%m-%d %H:%M:%S"

    # True Week Open = Tuesday open (Q2 of week) from 4H
    if c4h:
        for c in reversed(c4h):
            try:
                dt = datetime.strptime(c["time"], dp_fmt)
                if dt.weekday() == 1 and dt.hour == 0:
                    opens["week"] = c["open"]
                    break
            except: pass

    # True Day Open = Tuesday open from 1H (Q2 of week = trading day 2)
    if c1h:
        for c in reversed(c1h):
            try:
                dt = datetime.strptime(c["time"], dp_fmt)
                if dt.weekday() == 1 and dt.hour == 0:
                    opens["day"] = c["open"]
                    break
            except: pass

    # True Session Open = open of Q2 of session (90 min in) from 15min
    if c15m and session_info:
        q2_hour = int(session_info["session_q2_h"])
        for c in reversed(c15m):
            try:
                dt = datetime.strptime(c["time"], dp_fmt)
                if dt.hour == q2_hour and dt.minute == 0:
                    opens["session"] = c["open"]
                    break
            except: pass
        if "session" not in opens and c15m:
            opens["session"] = c15m[-1]["open"]

    # True 90-min Open = open of Q2 of 90-min cycle (45 min in) from 5min
    if c5m and session_info:
        cq2_hour = int(session_info["cycle_q2_h"])
        cq2_min  = int((session_info["cycle_q2_h"] % 1) * 60)
        for c in reversed(c5m):
            try:
                dt = datetime.strptime(c["time"], dp_fmt)
                if dt.hour == cq2_hour and dt.minute >= cq2_min:
                    opens["90min"] = c["open"]
                    break
            except: pass
        if "90min" not in opens and c5m:
            opens["90min"] = c5m[-1]["open"]

    return opens

# ------------------------------------------------------ MARKET STRUCTURE ----
def find_swings(candles, lookback=5):
    highs, lows = [], []
    for i in range(lookback, len(candles) - lookback):
        if all(candles[i]["high"] >= candles[j]["high"]
               for j in range(i-lookback, i+lookback+1) if j != i):
            highs.append({"price": candles[i]["high"], "time": candles[i]["time"]})
        if all(candles[i]["low"] <= candles[j]["low"]
               for j in range(i-lookback, i+lookback+1) if j != i):
            lows.append({"price": candles[i]["low"], "time": candles[i]["time"]})
    return highs, lows

def detect_fvg(candles, direction=None):
    fvgs = []
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        if c1["high"] < c3["low"]:
            fvgs.append({"type":"bullish","top":c3["low"],"bottom":c1["high"],
                         "mid":(c3["low"]+c1["high"])/2,"ob":c2,"time":c2["time"]})
        if c1["low"] > c3["high"]:
            fvgs.append({"type":"bearish","top":c1["low"],"bottom":c3["high"],
                         "mid":(c1["low"]+c3["high"])/2,"ob":c2,"time":c2["time"]})
    if direction:
        fvgs = [f for f in fvgs if f["type"] == direction]
    return fvgs[-10:]

def detect_ob(candles, direction):
    obs = []
    for i in range(1, len(candles)-1):
        c, cn = candles[i], candles[i+1]
        body  = abs(c["close"] - c["open"])
        if body == 0: continue
        if direction == "bullish" and c["close"] < c["open"]:
            if abs(cn["close"]-cn["open"]) > body * 1.5 and cn["close"] > cn["open"]:
                obs.append({"high":c["high"],"low":c["low"],"mid":(c["high"]+c["low"])/2,"time":c["time"]})
        if direction == "bearish" and c["close"] > c["open"]:
            if abs(cn["close"]-cn["open"]) > body * 1.5 and cn["close"] < cn["open"]:
                obs.append({"high":c["high"],"low":c["low"],"mid":(c["high"]+c["low"])/2,"time":c["time"]})
    return obs[-5:]

def detect_choch_mss(candles, direction):
    if len(candles) < 10: return False, False
    recent = candles[-20:]
    choch = mss = False
    if direction == "bullish":
        prev_highs = [c["high"] for c in recent[:-3]]
        last_high  = max(prev_highs) if prev_highs else 0
        for c in recent[-5:]:
            if c["close"] > last_high:
                choch = True
                body  = abs(c["close"] - c["open"])
                wick  = c["high"] - c["close"]
                if body > wick * 2: mss = True
                break
    else:
        prev_lows = [c["low"] for c in recent[:-3]]
        last_low  = min(prev_lows) if prev_lows else 999999
        for c in recent[-5:]:
            if c["close"] < last_low:
                choch = True
                body  = abs(c["close"] - c["open"])
                wick  = c["close"] - c["low"]
                if body > wick * 2: mss = True
                break
    return choch, mss

def detect_sweep(candles, highs, lows, price):
    sweeps = []
    rh = max(c["high"] for c in candles[-5:]) if candles else 0
    rl = min(c["low"]  for c in candles[-5:]) if candles else 0
    for h in highs[-5:]:
        if rh > h["price"] and price < h["price"]:
            sweeps.append({"type":"sell_side_swept","level":h["price"],"dir":"bearish"})
    for l in lows[-5:]:
        if rl < l["price"] and price > l["price"]:
            sweeps.append({"type":"buy_side_swept","level":l["price"],"dir":"bullish"})
    return sweeps

def fib_levels(hi, lo):
    d = hi - lo
    return {"0.618": hi - 0.618*d, "0.705": hi - 0.705*d,
            "0.5": hi - 0.5*d, "0.382": hi - 0.382*d}

def in_golden_zone(price, hi, lo):
    fibs = fib_levels(hi, lo)
    lo_z = min(fibs["0.618"], fibs["0.705"])
    hi_z = max(fibs["0.618"], fibs["0.705"])
    return lo_z <= price <= hi_z, fibs

# ------------------------------------------------------- SL / TP CALC ------
def pip_size(symbol):
    if "XAU" in symbol: return 0.01
    if "JPY" in symbol: return 0.01
    return 0.0001

def calc_sl_tp(direction, entry, symbol, highs, lows, fvg):
    ps      = pip_size(symbol)
    is_gold = "XAU" in symbol
    dp      = 2 if is_gold else 5

    if is_gold:
        ob = fvg["ob"]
        if direction == "bullish":
            sl_raw  = ob["low"] - 5 * ps
            sl_pips = (entry - sl_raw) / ps
            if sl_pips < GOLD_SL_MIN: sl_raw = entry - GOLD_SL_MIN * ps
            elif sl_pips > GOLD_SL_MAX: return None, None, None
        else:
            sl_raw  = ob["high"] + 5 * ps
            sl_pips = (sl_raw - entry) / ps
            if sl_pips < GOLD_SL_MIN: sl_raw = entry + GOLD_SL_MIN * ps
            elif sl_pips > GOLD_SL_MAX: return None, None, None
        sl = round(sl_raw, dp)
    else:
        dist = FOREX_SL_PIPS * ps
        sl   = round(entry - dist, dp) if direction=="bullish" else round(entry + dist, dp)

    if direction == "bullish":
        c1 = [h["price"] for h in highs if h["price"] > entry]
        tp1 = round(min(c1), dp) if c1 else round(entry + 30*ps, dp)
        c2 = [h["price"] for h in highs if h["price"] > tp1]
        tp2 = round(min(c2), dp) if c2 else round(entry + 60*ps, dp)
    else:
        c1 = [l["price"] for l in lows if l["price"] < entry]
        tp1 = round(max(c1), dp) if c1 else round(entry - 30*ps, dp)
        c2 = [l["price"] for l in lows if l["price"] < tp1]
        tp2 = round(max(c2), dp) if c2 else round(entry - 60*ps, dp)

    return sl, tp1, tp2

# -------------------------------------------------------- FORMAT EMAILS -----
def f(v, dp=5):
    return f"{v:.{dp}f}" if v is not None else "N/A"

def stack_str(stack):
    rows = []
    for key, label in [("yearly","Yearly"),("monthly","Monthly"),("weekly","Weekly"),
                        ("daily","Daily"),("session","Session"),("90min","90-min")]:
        v   = stack[key]
        ph  = v["phase"]
        mk  = "[M/D]" if ph in ["M","D"] else "[ - ]"
        nm  = f" ({v['name']})" if "name" in v else ""
        rows.append(f"{mk} {label}{nm}: Q{v['q']} | {v['pattern']} | {ph}")
    rows.append(f"     Alignment: {stack['score']}/6 | Overall: {stack['bias'].upper()}")
    return "\n".join(rows)

def watching_email(r):
    dp  = 2 if "XAU" in r["sym"] else 5
    d   = "BUY" if r["dir"] == "bullish" else "SELL"
    sw  = r["sweeps"][0]["type"].replace("_"," ").upper() if r["sweeps"] else "None"
    to  = r["opens"]
    return f"""
[WATCHING] {r['sym']} | {r['session']}
{'='*45}
Price         : {f(r['price'], dp)}
Bias          : {d}
Conditions    : {r['conds']}/6

FRACTAL STACK:
{stack_str(r['stack'])}

TRUE OPENS (Key Reaction Zones):
True Week Open    : {f(to.get('week'), dp)}
True Day Open     : {f(to.get('day'), dp)}
True Session Open : {f(to.get('session'), dp)}
True 90-min Open  : {f(to.get('90min'), dp)}

CHECKLIST:
[{'OK' if r['c_qtr']  else '--'}] Quarterly M/D phase
[{'OK' if r['c_liq']  else '--'}] Liquidity sweep: {sw}
[{'OK' if r['c_htf']  else '--'}] HTF FVG/iFVG/OB tapped
[{'OK' if r['c_fib']  else '--'}] Fibonacci golden zone (0.618-0.705)
[{'OK' if r['c_choch']else '--'}] ChoCh / MSS confirmed
[{'OK' if r['c_fvg']  else '--'}] Entry FVG (15min/5min)

Waiting for remaining conditions...
Signal may fire soon!
{'='*45}
""".strip()

def signal_email(r):
    dp    = 2 if "XAU" in r["sym"] else 5
    d     = "BUY" if r["dir"] == "bullish" else "SELL"
    sw    = r["sweeps"][0]["type"].replace("_"," ").upper() if r["sweeps"] else "Swept"
    swl   = f(r["sweeps"][0]["level"], dp) if r["sweeps"] else "N/A"
    to    = r["opens"]
    fibs  = r.get("fibs", {})
    ob    = r["fvg"]["ob"] if r["fvg"] else {}
    phase = "Manipulation" if any(
        r["stack"][k]["phase"] == "M" for k in ["session","90min","daily"]
    ) else "Distribution"

    return f"""
[A+ SIGNAL] {r['sym']} {d} | {r['session']}
{'='*45}
FRACTAL STACK ({r['conds']}/6):
{stack_str(r['stack'])}

TRUE OPENS (Key Reaction Zones):
True Week Open    : {f(to.get('week'), dp)}
True Day Open     : {f(to.get('day'), dp)}
True Session Open : {f(to.get('session'), dp)}
True 90-min Open  : {f(to.get('90min'), dp)}

SETUP:
Phase         : {phase}
Liq Swept     : {sw} at {swl}
HTF FVG/OB    : {'Tapped' if r['c_htf'] else 'Near zone'}
OB Level      : {f(ob.get('high' if r['dir']=='bearish' else 'low', 0), dp)}
Fib 0.618     : {f(fibs.get('0.618'), dp)}
Fib 0.705     : {f(fibs.get('0.705'), dp)}
Golden Zone   : {'YES' if r['in_fib'] else 'Near'}
ChoCh         : {'Confirmed' if r['choch'] else 'No'}
MSS           : {'Confirmed' if r['mss'] else 'No'}
Entry FVG     : {f(r['fvg']['bottom'] if r['fvg'] else 0, dp)} - {f(r['fvg']['top'] if r['fvg'] else 0, dp)}

TRADE:
Direction : {d}
Entry     : {f(r['entry'], dp)}
SL        : {f(r['sl'], dp)} ({r['sl_pips']} pips)
TP1       : {f(r['tp1'], dp)} ({r['tp1_pips']} pips) - Internal liquidity
TP2       : {f(r['tp2'], dp)} ({r['tp2_pips']} pips) - Opposing liquidity
RR        : 1:{r['rr1']} / 1:{r['rr2']}

REASON:
{r['sym']} {phase} phase. {sw} at {swl}.
HTF FVG/OB confluence + Fib golden zone.
{'ChoCh + MSS' if r['choch'] and r['mss'] else 'ChoCh' if r['choch'] else 'Structure shift'} on 15min/5min.
{r['stack']['score']}/6 fractal levels aligned {r['dir'].upper()}.

!! Confirm setup on MT5 before entering !!
{'='*45}
""".strip()

# ---------------------------------------------------------- PAIR ANALYSIS ---
def analyze_pair(symbol, now, session_info):
    print(f"\n  [{symbol}] Fetching data...")

    # Fetch with delays between each call
    c4h  = fetch_candles(symbol, "4h",    50)
    c1h  = fetch_candles(symbol, "1h",    48)
    c15m = fetch_candles(symbol, "15min", 50)
    c5m  = fetch_candles(symbol, "5min",  36)

    if not c4h or not c1h:
        print(f"  [{symbol}] Insufficient data - skipping")
        return None

    price = fetch_price(symbol)
    if not price:
        print(f"  [{symbol}] No price - skipping")
        return None

    print(f"  [{symbol}] Price: {price} | Building fractal stack...")

    # Build fractal stack
    stack  = build_stack(now, c4h, c1h, c15m, c5m, session_info)
    direction = stack["bias"]

    # True opens
    opens  = get_true_opens(now, c4h, c1h, c15m, c5m, session_info)

    # Swing highs/lows
    h4, l4 = find_swings(c4h)
    h1, l1 = find_swings(c1h)
    all_h  = sorted(h4 + h1, key=lambda x: x["price"])
    all_l  = sorted(l4 + l1, key=lambda x: x["price"])

    # Liquidity sweep
    sweeps  = detect_sweep(c4h, h4, l4, price) + detect_sweep(c1h, h1, l1, price)
    if sweeps: direction = sweeps[-1]["dir"]

    # HTF FVG/OB tap
    htf_fvgs = detect_fvg(c4h, direction) + detect_fvg(c1h, direction)
    htf_obs  = detect_ob(c4h, direction)  + detect_ob(c1h, direction)
    htf_hit  = None
    buf = 1.0 if "XAU" in symbol else 0.001
    for fvg in reversed(htf_fvgs):
        lo, hi = min(fvg["top"],fvg["bottom"]), max(fvg["top"],fvg["bottom"])
        if lo - buf <= price <= hi + buf:
            htf_hit = fvg
            break
    ob_hit = None
    for ob in reversed(htf_obs):
        if ob["low"] <= price <= ob["high"]:
            ob_hit = ob
            break

    # Fibonacci
    in_fib, fibs = False, {}
    if all_h and all_l:
        in_fib, fibs = in_golden_zone(price, all_h[-1]["price"], all_l[-1]["price"])

    # ChoCh / MSS
    choch_15, mss_15 = detect_choch_mss(c15m, direction) if c15m else (False, False)
    choch_5,  mss_5  = detect_choch_mss(c5m,  direction) if c5m  else (False, False)
    choch = choch_15 or choch_5
    mss   = mss_15   or mss_5

    # Entry FVG (15min / 5min)
    entry_fvgs = detect_fvg(c15m, direction) + detect_fvg(c5m, direction) if c15m else []
    entry_fvg  = None
    for fvg in reversed(entry_fvgs):
        lo, hi = min(fvg["top"],fvg["bottom"]), max(fvg["top"],fvg["bottom"])
        if lo - buf <= price <= hi + buf:
            entry_fvg = fvg
            break
    if not entry_fvg and entry_fvgs:
        entry_fvg = entry_fvgs[-1]

    # Conditions
    c_qtr  = stack["score"] >= 2
    c_liq  = bool(sweeps)
    c_htf  = htf_hit is not None or ob_hit is not None
    c_fib  = in_fib
    c_choch= choch or mss
    c_fvg  = entry_fvg is not None
    conds  = sum([c_qtr, c_liq, c_htf, c_fib, c_choch, c_fvg])

    print(f"  [{symbol}] Conditions: {conds}/6 | Stack score: {stack['score']}/6")

    result = {
        "sym": symbol, "price": price, "dir": direction,
        "stack": stack, "opens": opens, "sweeps": sweeps,
        "htf": htf_hit, "ob": ob_hit, "choch": choch, "mss": mss,
        "fvg": entry_fvg, "in_fib": in_fib, "fibs": fibs,
        "conds": conds, "session": session_info["name"],
        "c_qtr": c_qtr, "c_liq": c_liq, "c_htf": c_htf,
        "c_fib": c_fib, "c_choch": c_choch, "c_fvg": c_fvg,
    }

    # A+ Signal â€” 5 or 6/6
    if conds >= 5 and entry_fvg:
        entry = entry_fvg["mid"]
        sl, tp1, tp2 = calc_sl_tp(direction, entry, symbol, all_h, all_l, entry_fvg)
        if sl and tp1 and tp2:
            ps = pip_size(symbol)
            sp = round((entry - sl)/ps) if direction=="bullish" else round((sl - entry)/ps)
            t1 = round((tp1 - entry)/ps) if direction=="bullish" else round((entry - tp1)/ps)
            t2 = round((tp2 - entry)/ps) if direction=="bullish" else round((entry - tp2)/ps)
            result.update({
                "type": "signal", "entry": entry, "sl": sl,
                "tp1": tp1, "tp2": tp2, "sl_pips": sp,
                "tp1_pips": t1, "tp2_pips": t2,
                "rr1": round(t1/sp, 1) if sp else 0,
                "rr2": round(t2/sp, 1) if sp else 0,
            })
            return result

    # Watching â€” 2+ conditions near zone
    if conds >= 2 and (c_htf or c_liq or c_fib):
        result["type"] = "watching"
        return result

    return None

# -------------------------------------------------------------- MAIN --------
def main():
    print("=" * 55)
    print("FX Signal Bot â€” Full Fractal + 90-min Cycle")
    print("Scanning one pair at a time (rate limit safe)")
    print("=" * 55)

    now          = datetime.now(timezone.utc)
    weekday      = now.weekday()
    session_info = get_session_info(now.hour)
    day_names    = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

    print(f"UTC      : {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"Day      : {day_names[weekday]}")
    print(f"Session  : {session_info['name']}")
    print(f"90-min Q : {session_info['session_q']}")

    # Skip Friday and weekend
    if weekday >= 4:
        print("Not a trading day â€” bot resting.")
        send_email(
            "FX Bot - No Trading Today",
            f"Today is {day_names[weekday]}.\nBot is resting. See you Monday!"
        )
        return

    signals  = []
    watching = []

    for symbol in ALL_PAIRS:
        try:
            print(f"\n{'â”€'*40}")
            print(f"Scanning {symbol}...")
            result = analyze_pair(symbol, now, session_info)
            if result:
                if result.get("type") == "signal":
                    signals.append(result)
                    print(f"  [{symbol}] *** A+ SIGNAL FOUND! ***")
                elif result.get("type") == "watching":
                    watching.append(result)
                    print(f"  [{symbol}] Watching alert queued.")
            else:
                print(f"  [{symbol}] No setup found.")

            # Wait between pairs to respect rate limit
            print(f"  Waiting 60s before next pair...")
            time.sleep(60)

        except Exception as e:
            print(f"  [{symbol}] Error: {e}")
            time.sleep(60)

    print(f"\n{'='*55}")
    print(f"Scan complete: {len(signals)} signals, {len(watching)} watching")

    # Send A+ signals
    for r in signals:
        d = "BUY" if r["dir"] == "bullish" else "SELL"
        send_email(
            f"[A+ SIGNAL] {r['sym']} {d} | {r['conds']}/6 | {r['session']}",
            signal_email(r)
        )

    # Send watching alerts
    for r in watching:
        send_email(
            f"[WATCHING] {r['sym']} {r['conds']}/6 conditions | {r['session']}",
            watching_email(r)
        )

    if not signals and not watching:
        print("No setups found this scan.")

if __name__ == "__main__":
    main()
