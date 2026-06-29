import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

# ─── CONFIG ───────────────────────────────────────────────
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
EXTREME_THRESHOLD = 75  # sentiment %

# ─── EMAIL ────────────────────────────────────────────────
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

# ─── QUARTERLY THEORY ─────────────────────────────────────
def get_quarterly_phase():
    now    = datetime.now(timezone.utc)
    month  = now.month
    day    = now.weekday()  # 0=Mon,1=Tue,2=Wed,3=Thu,4=Fri

    # Yearly quarter
    yearly_q = (month - 1) // 3 + 1  # Q1=Jan-Mar, Q2=Apr-Jun etc

    # Monthly quarter (week of month)
    monthly_q = min((now.day - 1) // 7 + 1, 4)

    # Daily quarter (day of week Mon=1,Tue=2,Wed=3,Thu=4)
    daily_q = day + 1  # 1=Mon,2=Tue,3=Wed,4=Thu

    # Session quarter
    hour = now.hour
    if 0 <= hour < 6:
        session = "Asian (Q1)"
        session_q = 1
    elif 6 <= hour < 12:
        session = "London (Q2)"
        session_q = 2
    elif 12 <= hour < 18:
        session = "New York AM (Q3)"
        session_q = 3
    else:
        session = "New York PM (Q4)"
        session_q = 4

    # Detect XAMD vs AMDX based on Monday price action
    # We approximate: if weekly_q==1 (Mon) strong move = XAMD, ranging = AMDX
    # Bot tracks this via price range on Monday
    # For now we return both possibilities and check daily phase
    phases_xamd = {1: "X", 2: "A", 3: "M", 4: "D"}
    phases_amdx = {1: "A", 2: "M", 3: "D", 4: "X"}

    return {
        "now": now,
        "yearly_q": yearly_q,
        "monthly_q": monthly_q,
        "daily_q": daily_q,
        "day_name": ["Monday","Tuesday","Wednesday","Thursday","Friday"][day] if day < 5 else "Weekend",
        "session": session,
        "session_q": session_q,
        "phase_xamd": phases_xamd.get(daily_q, "?"),
        "phase_amdx": phases_amdx.get(daily_q, "?"),
        "is_trading_day": day < 4,  # Mon-Thu only
        "hour": hour
    }

def is_target_phase(phase_info):
    """Only trade M and D phases in both patterns"""
    xamd = phase_info["phase_xamd"]
    amdx = phase_info["phase_amdx"]
    # Target if either pattern puts us in M or D
    return xamd in ["M", "D"] or amdx in ["M", "D"]

# ─── TWELVE DATA API ──────────────────────────────────────
def fetch_candles(symbol, interval, outputsize=50):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": API_KEY,
        "format": "JSON"
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if "values" not in data:
            print(f"No data for {symbol} {interval}: {data.get('message','')}")
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
        print(f"Fetch error {symbol} {interval}: {e}")
        return []

def fetch_price(symbol):
    url = "https://api.twelvedata.com/price"
    try:
        r = requests.get(url, params={"symbol": symbol, "apikey": API_KEY}, timeout=10)
        data = r.json()
        return float(data.get("price", 0))
    except:
        return 0.0

# ─── MARKET STRUCTURE ─────────────────────────────────────
def find_swing_highs_lows(candles, lookback=5):
    highs, lows = [], []
    for i in range(lookback, len(candles) - lookback):
        if all(candles[i]["high"] >= candles[j]["high"] for j in range(i-lookback, i+lookback+1) if j != i):
            highs.append({"price": candles[i]["high"], "time": candles[i]["time"], "idx": i})
        if all(candles[i]["low"] <= candles[j]["low"] for j in range(i-lookback, i+lookback+1) if j != i):
            lows.append({"price": candles[i]["low"], "time": candles[i]["time"], "idx": i})
    return highs, lows

def detect_fvg(candles):
    """Fair Value Gaps — 3 candle pattern"""
    fvgs = []
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        # Bullish FVG: c1 high < c3 low (gap up)
        if c1["high"] < c3["low"]:
            fvgs.append({
                "type":    "bullish",
                "top":     c3["low"],
                "bottom":  c1["high"],
                "mid":     (c3["low"] + c1["high"]) / 2,
                "ob_candle": c2,  # middle candle is OB
                "time":    c2["time"],
                "idx":     i-1
            })
        # Bearish FVG: c1 low > c3 high (gap down)
        if c1["low"] > c3["high"]:
            fvgs.append({
                "type":    "bearish",
                "top":     c1["low"],
                "bottom":  c3["high"],
                "mid":     (c1["low"] + c3["high"]) / 2,
                "ob_candle": c2,
                "time":    c2["time"],
                "idx":     i-1
            })
    return fvgs[-10:] if fvgs else []  # last 10 FVGs

def detect_choch_mss(candles, direction):
    """
    Detect Change of Character / Market Structure Shift
    direction: 'bullish' or 'bearish'
    """
    if len(candles) < 10:
        return False, None

    recent = candles[-15:]
    if direction == "bullish":
        # Look for break of recent lower high (bullish ChoCh)
        recent_highs = [c["high"] for c in recent[:-3]]
        last_high    = max(recent_highs) if recent_highs else 0
        last_3       = recent[-3:]
        if any(c["close"] > last_high for c in last_3):
            return True, last_3[-1]
    else:
        # Look for break of recent higher low (bearish ChoCh)
        recent_lows = [c["low"] for c in recent[:-3]]
        last_low    = min(recent_lows) if recent_lows else 999999
        last_3      = recent[-3:]
        if any(c["close"] < last_low for c in last_3):
            return True, last_3[-1]
    return False, None

def detect_liquidity_sweep(candles, swing_highs, swing_lows, current_price):
    """Check if price recently swept a swing high or low"""
    sweeps = []
    recent_high = max(c["high"] for c in candles[-5:])
    recent_low  = min(c["low"]  for c in candles[-5:])

    for sh in swing_highs[-5:]:
        if recent_high > sh["price"] and current_price < sh["price"]:
            sweeps.append({"type": "sell_side_swept", "level": sh["price"], "direction": "bearish"})

    for sl in swing_lows[-5:]:
        if recent_low < sl["price"] and current_price > sl["price"]:
            sweeps.append({"type": "buy_side_swept", "level": sl["price"], "direction": "bullish"})

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
    fibs  = fibonacci_levels(swing_high, swing_low)
    upper = fibs["0.618"]
    lower = fibs["0.705"]
    lo, hi = min(upper, lower), max(upper, lower)
    return lo <= price <= hi, fibs

def get_true_open(symbol, timeframe="1day"):
    """Get true open = open of current period"""
    candles = fetch_candles(symbol, timeframe, outputsize=5)
    if candles:
        return candles[-1]["open"]
    return None

# ─── SL / TP CALCULATION ──────────────────────────────────
def pip_size(symbol):
    if "XAU" in symbol or "JPY" in symbol:
        return 0.01
    return 0.0001

def pips_to_price(pips, symbol):
    return pips * pip_size(symbol)

def calculate_sl_tp(direction, entry, symbol, swing_highs, swing_lows, fvg):
    ps   = pip_size(symbol)
    is_gold = "XAU" in symbol

    # SL
    if is_gold:
        ob  = fvg["ob_candle"]
        if direction == "bullish":
            sl_raw  = ob["low"] - (5 * ps)
            sl_pips = (entry - sl_raw) / ps
            if sl_pips < GOLD_SL_MIN:
                sl_raw = entry - GOLD_SL_MIN * ps
            elif sl_pips > GOLD_SL_MAX:
                return None, None, None  # Invalid setup
        else:
            sl_raw  = ob["high"] + (5 * ps)
            sl_pips = (sl_raw - entry) / ps
            if sl_pips < GOLD_SL_MIN:
                sl_raw = entry + GOLD_SL_MIN * ps
            elif sl_pips > GOLD_SL_MAX:
                return None, None, None
        sl = round(sl_raw, 2)
    else:
        sl_distance = FOREX_SL_PIPS * ps
        sl = round(entry - sl_distance, 5) if direction == "bullish" else round(entry + sl_distance, 5)

    # TP1 — nearest internal liquidity
    if direction == "bullish":
        candidates = [sh["price"] for sh in swing_highs if sh["price"] > entry]
        tp1 = round(min(candidates), 5) if candidates else round(entry + 30 * ps, 5)
        candidates2 = [sh["price"] for sh in swing_highs if sh["price"] > tp1]
        tp2 = round(min(candidates2), 5) if candidates2 else round(entry + 60 * ps, 5)
    else:
        candidates = [sl2["price"] for sl2 in swing_lows if sl2["price"] < entry]
        tp1 = round(max(candidates), 5) if candidates else round(entry - 30 * ps, 5)
        candidates2 = [sl2["price"] for sl2 in swing_lows if sl2["price"] < tp1]
        tp2 = round(max(candidates2), 5) if candidates2 else round(entry - 60 * ps, 5)

    return sl, tp1, tp2

# ─── MAIN ANALYSIS ────────────────────────────────────────
def analyze_pair(symbol, phase_info):
    print(f"\nAnalyzing {symbol}...")
    results = []

    # Fetch candles for multiple timeframes
    candles_4h  = fetch_candles(symbol, "4h",  outputsize=50)
    candles_1h  = fetch_candles(symbol, "1h",  outputsize=50)
    candles_15m = fetch_candles(symbol, "15min", outputsize=50)
    candles_5m  = fetch_candles(symbol, "5min",  outputsize=30)

    if not candles_4h or not candles_1h or not candles_15m:
        print(f"  Insufficient data for {symbol}")
        return results

    current_price = fetch_price(symbol)
    if not current_price:
        return results

    # ── STEP 1: Quarterly phase already determined ──
    xamd_phase = phase_info["phase_xamd"]
    amdx_phase = phase_info["phase_amdx"]
    in_target  = is_target_phase(phase_info)

    # ── STEP 2: HTF swing highs/lows (liquidity pools) ──
    highs_4h, lows_4h = find_swing_highs_lows(candles_4h)
    highs_1h, lows_1h = find_swing_highs_lows(candles_1h)
    all_highs = sorted(highs_4h + highs_1h, key=lambda x: x["price"])
    all_lows  = sorted(lows_4h  + lows_1h,  key=lambda x: x["price"])

    # HTF FVGs
    fvgs_4h = detect_fvg(candles_4h)
    fvgs_1h = detect_fvg(candles_1h)

    # ── STEP 3: Liquidity sweep on 4H/1H ──
    sweeps_4h = detect_liquidity_sweep(candles_4h, highs_4h, lows_4h, current_price)
    sweeps_1h = detect_liquidity_sweep(candles_1h, highs_1h, lows_1h, current_price)
    all_sweeps = sweeps_4h + sweeps_1h

    # True opens
    true_daily_open   = candles_1h[-1]["open"]  if candles_1h  else None
    true_session_open = candles_15m[-1]["open"] if candles_15m else None

    # Check price near HTF FVG or OB
    htf_fvg_hit = None
    trade_direction = None

    for fvg in reversed(fvgs_4h + fvgs_1h):
        lo = min(fvg["top"], fvg["bottom"])
        hi = max(fvg["top"], fvg["bottom"])
        if lo <= current_price <= hi:
            htf_fvg_hit   = fvg
            trade_direction = fvg["type"]
            break

    # If not in FVG check if close to swing level
    if not htf_fvg_hit and all_sweeps:
        trade_direction = all_sweeps[-1]["direction"]

    if not trade_direction:
        # Determine from price vs true open
        if true_daily_open and current_price > true_daily_open:
            trade_direction = "bullish"
        elif true_daily_open and current_price < true_daily_open:
            trade_direction = "bearish"
        else:
            print(f"  {symbol}: No clear direction")
            return results

    # ── STEP 4: ChoCh/MSS on 15min or 5min ──
    choch_15m, choch_candle_15m = detect_choch_mss(candles_15m, trade_direction)
    choch_5m,  choch_candle_5m  = detect_choch_mss(candles_5m,  trade_direction)
    choch_confirmed = choch_15m or choch_5m
    choch_candle    = choch_candle_15m or choch_candle_5m

    # ── STEP 5: Entry FVG on 15min or 5min ──
    fvgs_15m   = detect_fvg(candles_15m)
    fvgs_5m    = detect_fvg(candles_5m)
    entry_fvgs = [f for f in fvgs_15m + fvgs_5m if f["type"] == trade_direction]

    entry_fvg = None
    for fvg in reversed(entry_fvgs):
        lo = min(fvg["top"], fvg["bottom"])
        hi = max(fvg["top"], fvg["bottom"])
        buf = 0.002 if "XAU" not in symbol else 2.0
        if lo - buf <= current_price <= hi + buf:
            entry_fvg = fvg
            break

    if not entry_fvg and entry_fvgs:
        entry_fvg = entry_fvgs[-1]

    # Fibonacci check
    if all_highs and all_lows:
        recent_high = all_highs[-1]["price"]
        recent_low  = all_lows[-1]["price"]
        in_fib, fib_levels = in_golden_zone(current_price, recent_high, recent_low)
    else:
        in_fib, fib_levels = False, {}

    # ── CHECK: Watching alert ──
    # Price near HTF zone but not all conditions met
    near_htf = htf_fvg_hit is not None or bool(all_sweeps)
    all_conditions = (
        in_target and
        bool(all_sweeps) and
        choch_confirmed and
        entry_fvg is not None
    )

    if near_htf and not all_conditions:
        results.append({
            "type":      "watching",
            "symbol":    symbol,
            "price":     current_price,
            "direction": trade_direction,
            "phase_info": phase_info,
            "sweeps":    all_sweeps,
            "htf_fvg":  htf_fvg_hit,
            "choch":     choch_confirmed,
            "entry_fvg": entry_fvg,
            "in_fib":    in_fib,
            "in_target": in_target
        })

    # ── STEP 6: Full A+ Signal ──
    if all_conditions and entry_fvg:
        entry = entry_fvg["mid"]
        sl, tp1, tp2 = calculate_sl_tp(
            trade_direction, entry, symbol,
            all_highs, all_lows, entry_fvg
        )

        if sl and tp1 and tp2:
            ps = pip_size(symbol)
            if trade_direction == "bullish":
                sl_pips = round((entry - sl) / ps)
                tp1_pips = round((tp1 - entry) / ps)
                tp2_pips = round((tp2 - entry) / ps)
            else:
                sl_pips = round((sl - entry) / ps)
                tp1_pips = round((entry - tp1) / ps)
                tp2_pips = round((entry - tp2) / ps)

            rr1 = round(tp1_pips / sl_pips, 1) if sl_pips else 0
            rr2 = round(tp2_pips / sl_pips, 1) if sl_pips else 0

            results.append({
                "type":       "signal",
                "symbol":     symbol,
                "price":      current_price,
                "direction":  trade_direction,
                "entry":      entry,
                "sl":         sl,
                "tp1":        tp1,
                "tp2":        tp2,
                "sl_pips":    sl_pips,
                "tp1_pips":   tp1_pips,
                "tp2_pips":   tp2_pips,
                "rr1":        rr1,
                "rr2":        rr2,
                "phase_info": phase_info,
                "sweeps":     all_sweeps,
                "entry_fvg":  entry_fvg,
                "choch":      choch_confirmed,
                "in_fib":     in_fib,
                "true_daily_open": true_daily_open,
                "true_session_open": true_session_open
            })

    return results

# ─── EMAIL FORMATTERS ─────────────────────────────────────
def format_watching_email(r):
    p  = r["phase_info"]
    d  = "BUY 📈" if r["direction"] == "bullish" else "SELL 📉"
    sw = r["sweeps"][0]["type"].replace("_", " ").upper() if r["sweeps"] else "None"
    return f"""
👀 WATCHING — {r['symbol']} | {p['session']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Day: {p['day_name']} | Yearly Q{p['yearly_q']} | Monthly Q{p['monthly_q']}
📊 XAMD Phase: {p['phase_xamd']} | AMDX Phase: {p['phase_amdx']}
💰 Current Price: {r['price']}
📐 Bias: {d}

✅ Checklist:
{'✅' if r['in_target'] else '❌'} Quarterly phase (M or D)
{'✅' if r['sweeps'] else '❌'} Liquidity sweep: {sw}
{'✅' if r['htf_fvg'] else '❌'} HTF FVG/OB zone hit
{'✅' if r['choch'] else '❌'} ChoCh/MSS confirmed
{'✅' if r['entry_fvg'] else '❌'} Entry FVG (15min/5min)
{'✅' if r['in_fib'] else '❌'} Fibonacci golden zone

⏳ Waiting for remaining conditions...
Stay alert! Signal may fire soon! 🎯
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""".strip()

def format_signal_email(r):
    p  = r["phase_info"]
    d  = "BUY 📈" if r["direction"] == "bullish" else "SELL 📉"
    sw = r["sweeps"][0]["type"].replace("_", " ").upper() if r["sweeps"] else "Swept"
    fvg_type = r["entry_fvg"]["type"].upper()
    dp = 2 if "XAU" in r["symbol"] else 5

    return f"""
🎯 A+ SIGNAL — {r['symbol']} | {p['session']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Day: {p['day_name']} | Yearly Q{p['yearly_q']} | Monthly Q{p['monthly_q']}
📊 Weekly Pattern detected
🔥 Phase: {'Manipulation' if 'M' in [p['phase_xamd'], p['phase_amdx']] else 'Distribution'}

✅ ALL 6 CONDITIONS MET:
✅ Quarterly phase: M/D confirmed
✅ Liquidity: {sw} at {r['price']:.{dp}f}
✅ HTF FVG/OB zone tapped
✅ ChoCh/MSS confirmed on 15min/5min
✅ {fvg_type} FVG entry formed
✅ Fibonacci golden zone: {'Yes' if r['in_fib'] else 'Near zone'}

📈 TRADE DETAILS:
Direction : {d}
Entry     : {r['entry']:.{dp}f}
SL        : {r['sl']:.{dp}f} ({r['sl_pips']} pips)
TP1       : {r['tp1']:.{dp}f} ({r['tp1_pips']} pips) — Internal liquidity
TP2       : {r['tp2']:.{dp}f} ({r['tp2_pips']} pips) — Opposing liquidity
RR        : 1:{r['rr1']} / 1:{r['rr2']}

📌 True Daily Open : {r['true_daily_open']}
📌 True Session Open: {r['true_session_open']}

💡 REASON:
{r['symbol']} liquidity swept during {p['day_name']} 
{'Manipulation' if 'M' in [p['phase_xamd'], p['phase_amdx']] else 'Distribution'} phase.
{fvg_type} FVG + Order Block confluence detected.
ChoCh confirmed — price expected to move {'up' if r['direction']=='bullish' else 'down'}.

⚠️ Confirm setup on MT5 before entering!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""".strip()

# ─── MAIN ─────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("FX Signal Bot — Starting scan...")
    print("=" * 50)

    phase_info = get_quarterly_phase()
    now = phase_info["now"]

    print(f"Time (UTC): {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"Day: {phase_info['day_name']}")
    print(f"Session: {phase_info['session']}")
    print(f"XAMD phase: {phase_info['phase_xamd']}")
    print(f"AMDX phase: {phase_info['phase_amdx']}")
    print(f"Trading day: {phase_info['is_trading_day']}")

    # Skip weekends and Friday
    if not phase_info["is_trading_day"]:
        print(f"Not a trading day ({phase_info['day_name']}) — skipping.")
        return

    # Skip if not M or D phase
    if not is_target_phase(phase_info):
        print(f"Not in M or D phase today — skipping.")
        send_email(
            f"📊 FX Bot — {phase_info['day_name']} Phase Update",
            f"Today is {phase_info['day_name']}.\n"
            f"XAMD: {phase_info['phase_xamd']} phase | AMDX: {phase_info['phase_amdx']} phase\n"
            f"Not targeting today — waiting for Manipulation or Distribution phase.\n"
            f"Session: {phase_info['session']}"
        )
        return

    watching_alerts = []
    signal_alerts   = []

    for symbol in ALL_PAIRS:
        try:
            results = analyze_pair(symbol, phase_info)
            for r in results:
                if r["type"] == "watching":
                    watching_alerts.append(r)
                elif r["type"] == "signal":
                    signal_alerts.append(r)
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")

    print(f"\nResults: {len(signal_alerts)} signals, {len(watching_alerts)} watching")

    # Send signal emails first (priority)
    for r in signal_alerts:
        body    = format_signal_email(r)
        subject = f"🎯 A+ SIGNAL: {r['symbol']} {'BUY' if r['direction']=='bullish' else 'SELL'} — {phase_info['session']}"
        send_email(subject, body)

    # Send watching alerts
    for r in watching_alerts:
        body    = format_watching_email(r)
        subject = f"👀 WATCHING: {r['symbol']} — {phase_info['session']}"
        send_email(subject, body)

    if not signal_alerts and not watching_alerts:
        print("No setups found this scan.")

if __name__ == "__main__":
    main()
