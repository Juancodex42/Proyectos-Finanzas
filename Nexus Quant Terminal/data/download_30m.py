import urllib.request, urllib.parse, json, csv, os, time
from datetime import datetime, timedelta, timezone

SYMBOL = "BTCUSDT"
INTERVAL = "30m"
BASE_URL = "https://api.binance.com/api/v3/klines"
LIMIT = 1000
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
os.makedirs(OUTPUT_DIR, exist_ok=True)

end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
start_time = int((datetime.now(timezone.utc) - timedelta(days=730)).timestamp() * 1000)
all_candles = []
current_start = start_time
batch = 0

print(f"Descargando {SYMBOL} {INTERVAL}...")

while current_start < end_time:
    batch += 1
    params = {"symbol": SYMBOL, "interval": INTERVAL, "startTime": current_start, "limit": LIMIT}
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "BinSim/1.0")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
        continue
    if not data:
        break
    for c in data:
        all_candles.append([
            c[0], float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5]),
            c[6], float(c[7]), int(c[8]), float(c[9]), float(c[10]),
            datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        ])
    print(f"  Batch {batch}: {len(data)} velas (total: {len(all_candles)})")
    current_start = data[-1][0] + 1
    time.sleep(0.25)

seen = set()
unique = []
for c in all_candles:
    if c[0] not in seen:
        seen.add(c[0])
        unique.append(c)
unique.sort(key=lambda x: x[0])

outf = os.path.join(OUTPUT_DIR, f"{SYMBOL}_{INTERVAL}.csv")
with open(outf, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["open_time","open","high","low","close","volume","close_time","quote_volume","trades","taker_buy_base","taker_buy_quote","datetime"])
    w.writerows(unique)

print(f"Guardado: {outf} - {len(unique)} velas")
