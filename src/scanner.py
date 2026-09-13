"""
CoinGecko + CCXT (Bitget) 數據抓取模組
1. 使用 CoinGecko API 依照市值排名篩選前 N 名加密貨幣（排除穩定幣與包裝代幣）
2. 使用 CCXT 連接 Bitget 抓取日 K 線 (OHLCV) 歷史資料（預設 300 根）
"""

import time
import requests
import ccxt
from config import (
    COINGECKO_API_URL,
    TOP_N_COINS,
    EXCLUDED_SYMBOLS,
    EXCHANGE_ID,
    LOOKBACK_BARS,
)


def get_exchange():
    """初始化並回傳 CCXT exchange 實例"""
    exchange_class = getattr(ccxt, EXCHANGE_ID, ccxt.bitget)
    exchange = exchange_class({
        "enableRateLimit": True,
        "timeout": 15000,
    })
    return exchange


def fetch_coingecko_candidates(limit=100):
    """
    從 CoinGecko 取得市值排名前列的代幣資料。

    Args:
        limit (int): 查詢筆數，預設 100

    Returns:
        list[dict]: CoinGecko 回傳的代幣列表
    """
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": limit,
        "page": 1,
        "sparkline": "false",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    try:
        resp = requests.get(COINGECKO_API_URL, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"⚠️ CoinGecko API 請求失敗: {e}")
        return []


def is_excluded_coin(item):
    """判斷代幣是否為穩定幣或包裝/質押代幣"""
    sym = (item.get("symbol") or "").lower()
    cid = (item.get("id") or "").lower()
    name = (item.get("name") or "").lower()

    if sym in EXCLUDED_SYMBOLS or cid in EXCLUDED_SYMBOLS:
        return True

    # 包含特定關鍵字過濾
    keywords = ["usd", "tether", "stable", "wrapped", "staked", "bridged"]
    if any(k in sym for k in ["usd", "eur"]) and sym not in {"usd", "eur"}:
        return True
    if any(k in name for k in ["wrapped", "staked", "bridged"]):
        return True

    return False


def fetch_top_coins(top_n=TOP_N_COINS, lookback=LOOKBACK_BARS):
    """
    1. 從 CoinGecko 抓取市值排名，篩選前 top_n 個非穩定幣
    2. 從 Bitget 抓取每個幣種對應的日 K 線資料 (OHLCV)

    Returns:
        list[dict]: 每個幣的完整資訊與日 K 棒資料
    """
    exchange = get_exchange()
    print(f"📡 載入 {EXCHANGE_ID.capitalize()} 現貨市場交易對...")
    try:
        markets = exchange.load_markets()
    except Exception as e:
        print(f"❌ 載入 {EXCHANGE_ID} 市場失敗: {e}")
        return []

    # 取得 Bitget 現貨活躍交易對
    spot_pairs = {
        s for s, m in markets.items()
        if m.get("spot") and m.get("active", True)
    }

    print("📊 正在向 CoinGecko 查詢加密貨幣市值排名...")
    cg_data = fetch_coingecko_candidates(limit=100)
    if not cg_data:
        print("❌ 無法取得 CoinGecko 數據")
        return []

    selected_candidates = []
    for item in cg_data:
        if is_excluded_coin(item):
            continue

        symbol = item.get("symbol", "").upper()
        name = item.get("name", "")
        rank = item.get("market_cap_rank", 0)
        pair = f"{symbol}/USDT"

        # 確認在 Bitget 現貨是否有交易對
        if pair not in spot_pairs:
            continue

        selected_candidates.append({
            "rank": rank,
            "symbol": symbol,
            "name": name,
            "pair": pair,
            "market_cap": item.get("market_cap", 0),
            "price_cg": item.get("current_price", 0),
            "change_24h_cg": (item.get("price_change_percentage_24h") or 0) / 100.0,
            "trade_symbol": f"BITGET:{symbol}USDT",
        })

        if len(selected_candidates) >= top_n:
            break

    print(f"✅ 已篩選出前 {len(selected_candidates)} 檔幣種，開始抓取 Bitget 日 K 線資料...")

    coins = []
    for c in selected_candidates:
        pair = c["pair"]
        try:
            ohlcv = exchange.fetch_ohlcv(pair, timeframe="1d", limit=lookback)
            if not ohlcv or len(ohlcv) < 30:
                print(f"⚠️ {pair} K 線資料不足 (僅 {len(ohlcv)} 根)，略過")
                continue

            # 排除最新一根正在形成的當天 K 棒（日 K 結算於 00:00 UTC / 08:00 台北時間）
            # 若最後一根的 timestamp 為今日未收盤，則以前一根作為最新完成日 K
            completed_bars = ohlcv[:-1] if len(ohlcv) > 1 else ohlcv

            c["ohlcv"] = completed_bars
            # 最新完成日 K 數值
            latest_bar = completed_bars[-1]
            c["open"] = latest_bar[1]
            c["high"] = latest_bar[2]
            c["low"] = latest_bar[3]
            c["close"] = latest_bar[4]
            c["vol"] = latest_bar[5]

            # 前一日 K 成交量
            if len(completed_bars) >= 2:
                c["vol_prev"] = completed_bars[-2][5]
            else:
                c["vol_prev"] = c["vol"]

            # 10 日均量 (MA10)
            if len(completed_bars) >= 10:
                c["vol_ma10"] = sum(b[5] for b in completed_bars[-10:]) / 10.0
            else:
                c["vol_ma10"] = c["vol"]

            coins.append(c)
        except Exception as e:
            print(f"⚠️ 抓取 {pair} K 線失敗: {e}")

        time.sleep(0.05)  # 避免過於頻繁請求

    print(f"🎉 成功完成 {len(coins)} 個幣種的歷史 K 線數據抓取！")
    return coins


if __name__ == "__main__":
    top_coins = fetch_top_coins(5)
    for i, c in enumerate(top_coins, 1):
        print(f"{i}. [CG #{c['rank']}] {c['symbol']} ({c['name']}) — {c['pair']}")
        print(f"   收盤價: ${c['close']:,.2f}  市值: ${c['market_cap']/1e9:.2f}B")
        print(f"   日 K 數量: {len(c['ohlcv'])} 根")
        print(f"   VOL: {c['vol']:,.1f} | MA10: {c['vol_ma10']:,.1f} | >MA10: {'✅' if c['vol'] > c['vol_ma10'] else '❌'}")
        print()
