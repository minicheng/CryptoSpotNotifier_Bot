"""
FT 波段策略 — K 線指標圖表產生模組
使用 Matplotlib (Agg headless) 繪製 TradingView 暗黑風格三子圖：
  1. 主圖：日 K 棒 + EMA10 (藍) + EMA20 (紅) + 60日阻力線 (紅虛線) + 60日支撐線 (綠虛線)
  2. 成交量：成交量柱狀圖 (陽綠/陰紅) + MA10 均線 (黃)
  3. MACD：MACD 快慢線 + 柱狀圖 + 0 軸虛線
"""

import os
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter
from strategy import calculate_ema, calculate_macd
from config import SR_LOOKBACK_BARS


def _format_chart_price(price):
    """圖表標題專用價格格式化"""
    if price is None:
        return "N/A"
    if price >= 1000:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:.4f}"
    elif price >= 0.001:
        return f"${price:.6f}"
    else:
        return f"${price:.8f}"


def _format_sr_val(price):
    """阻力/支撐標示專用數值格式化"""
    if price is None:
        return "N/A"
    if price >= 1000:
        return f"{price:,.2f}"
    elif price >= 1:
        return f"{price:.4f}"
    else:
        return f"{price:.6f}"


def generate_coin_chart(coin_data, output_dir="charts", n_display=75):
    """
    為單一幣種產生暗黑風格日 K 線指標圖。

    Args:
        coin_data (dict): analyze_coin 回傳的策略分析字典（含 ohlcv 資料）
        output_dir (str): 圖表儲存目錄
        n_display (int): 圖表顯示的日 K 棒數量（預設 75 根）

    Returns:
        str: 產生的圖表絕對路徑，若失敗則回傳 None
    """
    ohlcv = coin_data.get("ohlcv", [])
    if not ohlcv or len(ohlcv) < 30:
        return None

    symbol = coin_data.get("symbol", "COIN")
    name = coin_data.get("name", symbol)
    close_price = coin_data.get("close", ohlcv[-1][4])
    change = coin_data.get("change", 0.0)
    status_rd = coin_data.get("status_rd", 3)
    conditions_met = coin_data.get("conditions_met_count", 2)

    # 顯示範圍截取
    display_bars = ohlcv[-n_display:] if len(ohlcv) >= n_display else ohlcv
    n_bars_disp = len(display_bars)

    closes = [b[4] for b in display_bars]
    opens = [b[1] for b in display_bars]
    highs = [b[2] for b in display_bars]
    lows = [b[3] for b in display_bars]
    vols = [b[5] for b in display_bars]
    dates = [
        datetime.datetime.fromtimestamp(b[0] / 1000, tz=datetime.timezone.utc)
        for b in display_bars
    ]

    # EMA 計算（基於完整歷史後取顯示段）
    full_closes = [b[4] for b in ohlcv]
    full_ema10 = calculate_ema(full_closes, 10)[-n_bars_disp:]
    full_ema20 = calculate_ema(full_closes, 20)[-n_bars_disp:]

    # MACD 序列計算
    full_macd, full_sig, full_hist = [], [], []
    start_idx = len(ohlcv) - n_bars_disp
    for k in range(start_idx, len(ohlcv)):
        m, s, h = calculate_macd(full_closes[:k + 1])
        full_macd.append(m)
        full_sig.append(s)
        full_hist.append(h)

    # Volume MA10 計算
    full_vols = [b[5] for b in ohlcv]
    vol_ma10 = []
    for k in range(start_idx, len(ohlcv)):
        if k >= 9:
            ma = sum(full_vols[k - 9:k + 1]) / 10.0
        else:
            ma = full_vols[k]
        vol_ma10.append(ma)

    # 60日阻力/支撐線（取最新 60 根高低）
    sr_len = min(SR_LOOKBACK_BARS, len(highs))
    res_line = max(highs[-sr_len:])
    sup_line = min(lows[-sr_len:])

    # 繪圖設定 (暗黑風格)
    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(10, 7.5),
        gridspec_kw={"height_ratios": [3.2, 1.1, 1.1]},
        facecolor="#131722"
    )

    bull_color = "#26a69a"
    bear_color = "#ef5350"
    grid_color = "#2a2e39"
    x_indices = list(range(n_bars_disp))

    # ===== Subplot 1: K 棒與均線 =====
    ax1.set_facecolor("#131722")
    ax1.grid(True, linestyle="--", alpha=0.25, color=grid_color)

    # 價格自適應最小實體高度（依顯示區間比例計算，避免低價幣被固定數值扭曲）
    price_range = max(highs) - min(lows)
    min_body_h = price_range * 0.0035

    for idx in x_indices:
        o, h, l, c = opens[idx], highs[idx], lows[idx], closes[idx]
        color = bull_color if c >= o else bear_color
        # 影線
        ax1.plot([idx, idx], [l, h], color=color, linewidth=1.1)
        # 實體（十字星對稱擴展，正常實體保證忠實於開收盤價）
        body_diff = abs(c - o)
        if body_diff < min_body_h:
            body_low = (o + c) / 2.0 - min_body_h / 2.0
            body_height = min_body_h
        else:
            body_low = min(o, c)
            body_height = body_diff
        rect = Rectangle(
            (idx - 0.35, body_low), 0.7, body_height,
            facecolor=color, edgecolor=color, alpha=0.92
        )
        ax1.add_patch(rect)

    # 繪製均線與支撐阻力線
    ax1.plot(x_indices, full_ema10, color="#2962ff", linewidth=1.4, label="EMA10")
    ax1.plot(x_indices, full_ema20, color="#ff5252", linewidth=1.4, label="EMA20")
    ax1.axhline(res_line, color="#ef5350", linestyle=":", linewidth=1.1, alpha=0.85)
    ax1.axhline(sup_line, color="#26a69a", linestyle=":", linewidth=1.1, alpha=0.85)

    # 邊界外擴 padding
    p_pad = price_range * 0.05
    ax1.set_ylim(min(lows) - p_pad, max(highs) + p_pad)

    # 標題
    trend_tag = "TREND UP" if status_rd == 3 else "TREND DOWN"
    change_pct = change * 100
    title_text = f"[{trend_tag}] {symbol} ({name}) | {_format_chart_price(close_price)} ({change_pct:+.1f}%) | {conditions_met}/4"
    ax1.set_title(title_text, color="#ffffff", fontsize=12, fontweight="bold", pad=10)

    # 次標題 (均線與阻力支撐數值)
    sub_text = f"EMA10 (Blue)  EMA20 (Red) | Resistance: {_format_sr_val(res_line)}  Support: {_format_sr_val(sup_line)}"
    ax1.text(0.5, -0.06, sub_text, transform=ax1.transAxes, color="#848e9c", fontsize=8.5, ha="center")

    # 根據價格範圍動態調整 Y 軸小數點精度
    def _price_tick_fmt(x, pos):
        if price_range >= 100:
            return f"{x:,.0f}" if price_range >= 1000 else f"{x:,.1f}"
        elif price_range >= 1:
            return f"{x:.2f}"
        elif price_range >= 0.01:
            return f"{x:.4f}"
        else:
            return f"{x:.6f}"

    ax1.yaxis.set_major_formatter(FuncFormatter(_price_tick_fmt))
    ax1.yaxis.tick_right()
    ax1.yaxis.set_label_position("right")
    ax1.set_ylabel("Price", color="#848e9c", fontsize=8.5)
    ax1.tick_params(colors="#848e9c", labelsize=8.5)


    # ===== Subplot 2: 成交量 =====
    ax2.set_facecolor("#131722")
    ax2.grid(True, linestyle="--", alpha=0.25, color=grid_color)
    v_colors = [bull_color if c >= o else bear_color for o, c in zip(opens, closes)]
    ax2.bar(x_indices, vols, color=v_colors, width=0.7, alpha=0.85)
    ax2.plot(x_indices, vol_ma10, color="#f0b90b", linewidth=1.1)
    ax2.yaxis.tick_right()
    ax2.yaxis.set_label_position("right")
    ax2.set_ylabel("Volume", color="#848e9c", fontsize=8.5)
    ax2.tick_params(colors="#848e9c", labelsize=8.5)

    # ===== Subplot 3: MACD =====
    ax3.set_facecolor("#131722")
    ax3.grid(True, linestyle="--", alpha=0.25, color=grid_color)
    h_colors = [bull_color if h_val >= 0 else bear_color for h_val in full_hist]
    ax3.bar(x_indices, full_hist, color=h_colors, width=0.7, alpha=0.85)
    ax3.plot(x_indices, full_macd, color="#2962ff", linewidth=1.1)
    ax3.plot(x_indices, full_sig, color="#ff9800", linewidth=1.1)
    ax3.axhline(0, color="#5d606b", linestyle="--", linewidth=0.7)
    ax3.yaxis.tick_right()
    ax3.yaxis.set_label_position("right")
    ax3.set_ylabel("MACD", color="#848e9c", fontsize=8.5)
    ax3.tick_params(colors="#848e9c", labelsize=8.5)

    # X 軸時間標籤
    tick_step = max(n_bars_disp // 8, 1)
    tick_positions = list(range(0, n_bars_disp, tick_step))
    tick_labels = [dates[p].strftime("%b %d") for p in tick_positions]
    ax3.set_xticks(tick_positions)
    ax3.set_xticklabels(tick_labels, rotation=30, color="#848e9c", fontsize=8.5)

    ax1.set_xticks([])
    ax2.set_xticks([])

    plt.subplots_adjust(left=0.03, right=0.91, top=0.93, bottom=0.08, hspace=0.18)

    os.makedirs(output_dir, exist_ok=True)
    clean_symbol = symbol.replace("/", "_").replace(":", "_")
    output_path = os.path.abspath(os.path.join(output_dir, f"{clean_symbol}.png"))

    plt.savefig(output_path, dpi=140, facecolor="#131722")
    plt.close(fig)

    return output_path
