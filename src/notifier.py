"""
Telegram Bot 通知模組
1. 產生每日加密貨幣趨勢總覽報表（分開 🟢 RD向上 與 🔴 RD向下，置頂今日新訊號）
2. 產生個幣圖文卡片文案（包含 K 線指標圖、操作建議、掉河次數、注意事項、4大條件與 TradingView 連結）
3. 提供 Telegram 文字訊息 (sendMessage) 與圖片推播 (sendPhoto) API
"""

import os
import requests
import datetime
import urllib.parse
from config import TELEGRAM_API_URL, TELEGRAM_PHOTO_URL, TV_CHART_URL


def send_telegram_message(text, bot_token=None, chat_id=None, parse_mode="HTML"):
    """
    透過 Telegram Bot API 發送文字訊息。

    Args:
        text (str): 訊息內容（支援 HTML 格式）
        bot_token (str): Bot Token（預設從環境變數讀取）
        chat_id (str): Chat ID（預設從環境變數讀取）
        parse_mode (str): 解析模式，預設 HTML

    Returns:
        bool: 發送成功與否
    """
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    cid = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not cid:
        print("❌ 缺少 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
        return False

    url = TELEGRAM_API_URL.format(token=token)
    payload = {
        "chat_id": cid,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if result.get("ok"):
            print("✅ Telegram 總覽訊息發送成功")
            return True
        else:
            print(f"❌ Telegram API 錯誤: {result}")
            return False
    except requests.RequestException as e:
        print(f"❌ Telegram 發送失敗: {e}")
        return False


def send_telegram_photo(photo_path, caption="", bot_token=None, chat_id=None, parse_mode="HTML"):
    """
    透過 Telegram Bot API 發送照片與圖文卡片說明。

    Args:
        photo_path (str): 圖片檔案本機路徑
        caption (str): 圖片附帶說明文案（最高 1024 字元）
        bot_token (str): Bot Token
        chat_id (str): Chat ID
        parse_mode (str): 解析模式，預設 HTML

    Returns:
        bool: 發送成功與否
    """
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    cid = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not cid:
        print("❌ 缺少 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
        return False

    if not photo_path or not os.path.exists(photo_path):
        print(f"❌ 圖片檔案不存在: {photo_path}")
        return False

    url = TELEGRAM_PHOTO_URL.format(token=token)
    try:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            data = {
                "chat_id": cid,
                "caption": caption[:1024],
                "parse_mode": parse_mode,
            }
            resp = requests.post(url, data=data, files=files, timeout=35)
            resp.raise_for_status()
            result = resp.json()
            if result.get("ok"):
                print(f"✅ Telegram 圖文卡片發送成功 ({os.path.basename(photo_path)})")
                return True
            else:
                print(f"⚠️ Telegram Photo 回傳錯誤: {result.get('description')}")
                return False
    except Exception as e:
        print(f"❌ 發送 Telegram 圖片失敗: {e}")
        return False


def _format_price(price):
    """格式化價格顯示"""
    if price is None:
        return "N/A"
    if price >= 1000:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:.4f}"
    else:
        return f"${price:.6f}"


def _format_market_cap(cap):
    """格式化市值顯示"""
    if cap is None:
        return "N/A"
    if cap >= 1e12:
        return f"${cap/1e12:.2f}T"
    elif cap >= 1e9:
        return f"${cap/1e9:.2f}B"
    elif cap >= 1e6:
        return f"${cap/1e6:.2f}M"
    else:
        return f"${cap:,.0f}"


def _format_change(change):
    """格式化漲跌幅"""
    if change is None:
        return "N/A"
    pct = change * 100
    emoji = "📈" if pct > 0 else ("📉" if pct < 0 else "➖")
    return f"{emoji} {pct:+.2f}%"


def _format_vol(vol):
    """格式化成交量顯示 (K / M / B)"""
    if vol is None:
        return "N/A"
    if vol >= 1e9:
        return f"{vol/1e9:.2f}B"
    elif vol >= 1e6:
        return f"{vol/1e6:.2f}M"
    elif vol >= 1e3:
        return f"{vol/1e3:.1f}K"
    else:
        return f"{vol:,.1f}"


def _get_tv_link(coin):
    """產生 TradingView 圖表連結"""
    sym = coin.get("symbol", "") if isinstance(coin, dict) else str(coin)
    trade_symbol = coin.get("trade_symbol", "") if isinstance(coin, dict) else ""
    raw_sym = trade_symbol if trade_symbol else f"BITGET:{sym}USDT"
    encoded_sym = urllib.parse.quote(raw_sym, safe="")
    return TV_CHART_URL.format(symbol=encoded_sym)


def _format_overview_coin_line(i, r):
    """格式化總覽列表中的單一幣種資訊列"""
    rd_emoji = "🟢" if r["status_rd"] == 3 else "🔴"
    macd_emoji = "🟢" if r["status_macd"] == 1 else "🔴"
    change_str = _format_change(r["change"])

    if r.get("vol_gt_ma10") and r.get("is_bullish_vol"):
        vol_e = "🟢"
    elif r.get("vol_gt_ma10") and r.get("is_bearish_vol"):
        vol_e = "🔴"
    else:
        vol_e = "➖"

    dips_cnt = r.get("dips_completed", 0)
    dip_dates = r.get("dip_dates", [])
    if dips_cnt == 0:
        dips_tag = "掉河0"
    elif dips_cnt == 1:
        dips_tag = f"掉河1({dip_dates[0]})" if dip_dates else "掉河1"
    elif dips_cnt == 2:
        dips_tag = f"掉河2({','.join(dip_dates[:2])}⚠️)" if len(dip_dates) >= 2 else "掉河2⚠️"
    else:
        dips_tag = f"掉河{dips_cnt}({','.join(dip_dates[:3])}⚠️)"

    rd_history_str = f"RD{rd_emoji}({r['trend_days']}天|{dips_tag})"
    sym_display = f"{r['symbol'][:6]:<6s}"
    price_display = f"{_format_price(r['close'])}"

    sig = ""
    if r.get("spot_entry"):
        if r.get("is_first_entry"):
            sig = " | 訊號: 🚀現貨做多首次進場"
        else:
            cnt = r.get('entry_signal_count', 1)
            sig = f" | 訊號: 🚀現貨做多再次進場(第{cnt}次)"
    elif r.get("spot_exit"):
        sig = " | 訊號: 🛑現貨出場"
    elif r.get("short_entry"):
        if r.get("is_first_entry"):
            sig = " | 訊號: 📉1X做空首次進場"
        else:
            cnt = r.get('entry_signal_count', 1)
            sig = f" | 訊號: 📉1X做空再次進場(第{cnt}次)"
    elif r.get("short_exit"):
        sig = " | 訊號: 🔄做空出場"

    return (
        f"{i:2d}. {sym_display} | {price_display} | {change_str} | "
        f"{rd_history_str} | MACD DEA線{macd_emoji} | VOL>MA10{vol_e}{sig}"
    )


def format_signals_message(signals, results, scan_time=""):
    """
    將策略掃描總覽格式化為指定排版的 Telegram 訊息。
    包含：標題時間、⚡️今日新訊號（第1天）、🟢 RD向上分組、🔴 RD向下分組。

    Args:
        signals (dict): get_signals() 的回傳值
        results (list[dict]): 所有幣種的分析結果
        scan_time (str): 掃描時間

    Returns:
        str: 總覽文字訊息
    """
    sep = "———————————————————————————————————"
    lines = []

    lines.append("加密貨幣趨勢日報")
    if scan_time:
        time_clean = scan_time.replace("-", "/").replace(" (台北時間)", " (台北時區）")
        if "(台北" not in time_clean:
            time_clean += " (台北時區）"
        lines.append(time_clean)
    else:
        now_str = datetime.datetime.now().strftime("%Y/%m/%d 08:00 (台北時區）")
        lines.append(now_str)

    lines.append(sep)

    # ⚡️今日訊號:
    new_signals_first = []
    new_signals_reentry = []
    for r in results:
        sym = r.get("symbol", "")
        entry_dates = r.get("entry_signal_dates", [])
        if r.get("spot_entry"):
            if r.get("is_first_entry"):
                new_signals_first.append(f"🚀 {sym}(現貨做多首次進場)")
            else:
                past = '、'.join(entry_dates[:-1]) if len(entry_dates) > 1 else ''
                cnt = r.get('entry_signal_count', 1)
                new_signals_reentry.append(f"🚀 {sym}(現貨做多再次進場·第{cnt}次，首次:{entry_dates[0] if entry_dates else '?'})")
        elif r.get("spot_exit"):
            new_signals_first.append(f"🔴 {sym}(現貨出場)")
        elif r.get("short_entry"):
            if r.get("is_first_entry"):
                new_signals_first.append(f"📉 {sym}(1X做空首次進場)")
            else:
                cnt = r.get('entry_signal_count', 1)
                new_signals_reentry.append(f"📉 {sym}(1X做空再次進場·第{cnt}次，首次:{entry_dates[0] if entry_dates else '?'})")
        elif r.get("short_exit"):
            new_signals_first.append(f"🔄 {sym}(做空出場)")

    new_signals = new_signals_first + new_signals_reentry
    lines.append("⚡️今日訊號:")
    if new_signals:
        for s in new_signals:
            lines.append(s)
    else:
        lines.append("無")

    lines.append(sep)

    # 分開 RD 向上 與 RD 向下
    up_coins = [r for r in results if r.get("status_rd") == 3]
    down_coins = [r for r in results if r.get("status_rd") == -3]

    # 🟢 RD向上
    lines.append(f"🟢 RD向上：共{len(up_coins)}幣種")
    for i, r in enumerate(up_coins, 1):
        lines.append(_format_overview_coin_line(i, r))

    lines.append(sep)

    # 🔴 RD向下
    lines.append(f"🔴 RD向下：共{len(down_coins)}幣種")
    for i, r in enumerate(down_coins, 1):
        lines.append(_format_overview_coin_line(i, r))

    lines.append(sep)

    return "\n".join(lines)


def format_coin_card_caption(r):
    """
    產生個幣圖文卡片說明文案（包含收盤價、操作建議、掉河次數、注意事項、4大條件與 TradingView 連結）。

    Args:
        r (dict): analyze_coin 回傳的幣種分析結果

    Returns:
        str: 卡片文字內容
    """
    lines = []

    symbol = r.get("symbol", "")
    name = r.get("name", symbol)
    rank = r.get("rank", 1)
    close = r.get("close", 0.0)

    # 最新完成日 K 日期
    bar_date = r.get("latest_bar_date", "")  # e.g. "09/11"
    if bar_date.startswith("0"):
        bar_date_display = bar_date[1:]
    else:
        bar_date_display = bar_date if bar_date else "今日"

    lines.append(f"市值排名{rank}: {symbol} ({name})")
    lines.append(f"{bar_date_display}收盤價： {_format_price(close)}")

    status_rd = r.get("status_rd", 3)
    if status_rd == 3:
        lines.append("🟢 RD向上：")
    else:
        lines.append("🔴 RD向下：")

    lines.append(f"已過河拆橋天數：{r.get('trend_days', 0)}天")
    lines.append(f"操作建議：{r.get('action_advice', '')}")

    dips_cnt = r.get("dips_completed", 0)
    dip_dates = r.get("dip_dates", [])
    chinese_nums = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三", "十四", "十五"]
    if dips_cnt > 0 and dip_dates:
        dates_detail = "、".join(
            f"掉入第{chinese_nums[k] if k < len(chinese_nums) else str(k+1)}次({d})"
            for k, d in enumerate(dip_dates)
        )
        lines.append(f"已掉入河中次數：{dips_cnt}次；{dates_detail}。")
    else:
        lines.append(f"已掉入河中次數：0次。")

    lines.append(f"注意事項：{r.get('caution_note', '')}")
    lines.append("")
    lines.append(f'<a href="{_get_tv_link(r)}">🔗Tradingview</a>')

    return "\n".join(lines)
