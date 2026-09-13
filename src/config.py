"""
FT 波段策略 — 設定檔
對應 Pine Script 的 input 參數
"""

# === EMA 參數 ===
EMA_SMALL_LEN = 10   # EMA 快線長度 (Pine: SmallLen)
EMA_BIG_LEN = 20     # EMA 慢線長度 (Pine: BigLen)

# === MACD 參數 ===
MACD_FAST = 12        # MACD 快線 (Pine: fastMACD)
MACD_SLOW = 26        # MACD 慢線 (Pine: slowMACD)
MACD_SIGNAL = 9       # Signal 長度 (Pine: SigLen)

# === Scanner 設定 ===
TOP_N_COINS = 20      # 掃描市值前 N 名（排除穩定幣後）
COINGECKO_API_URL = "https://api.coingecko.com/api/v3/coins/markets"
EXCHANGE_ID = "bitget"  # 使用 Bitget 作為 K 線資料來源
LOOKBACK_BARS = 300     # 抓取日 K 棒數量（預設 300 根日 K）
SR_LOOKBACK_BARS = 60   # SR 突破回看天數（過去 60 根日 K 最高/最低價）

# === 穩定幣與包裝代幣排除清單 (Symbol 小寫) ===
EXCLUDED_SYMBOLS = {
    # 穩定幣
    "usdt", "usdc", "dai", "busd", "tusd", "fdusd", "usdd", "usde", "pyusd",
    "eurc", "usds", "rlusd", "xaut", "paxg", "frax", "usdp", "cusd", "susde",
    "sdai", "crvusd", "usdee", "usad2", "usd1w", "usdt0", "usdgo", "usdgg",
    # Wrapped / Staked / Bridged
    "wbtc", "weth", "wsteth", "cbbtc", "cbeth", "steth", "weeth", "wbeth",
    "beth", "jitosol", "bsol", "msol", "stbtc", "btcb", "webtc", "lseth",
    "wegld", "cdceth",
}

# === Telegram 設定 ===
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_PHOTO_URL = "https://api.telegram.org/bot{token}/sendPhoto"

# === 個幣圖文卡片推播設定 ===
# "featured": 模式 A（推薦）今日新訊號幣種 + 市值前 3 大幣 (BTC, ETH, BNB) + 掉河≥2次警告幣（每日約 3~5 張重點卡片，避免洗版）
# "all": 前 20 檔全數發送個幣圖文卡片
# "signals_only": 僅發送今日有新訊號的幣種
CARD_SEND_MODE = "featured"
CARD_TOP_N = 3          # featured 模式下固定包含前 N 大幣（如 BTC, ETH, BNB）
CARD_MAX_FEATURED = 5   # featured 模式每日最大發送張數（預設 5 張，避免大量洗版；設為 0 則不限張數）
CHARTS_DIR = "charts"   # 圖表快取儲存目錄

# === TradingView 圖表連結前綴 ===
TV_CHART_URL = "https://tw.tradingview.com/chart/?symbol={symbol}"

