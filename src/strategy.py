"""
FT 波段策略判斷模組
從 Pine Script FT_pineScript_V1 移植並強化的策略邏輯

策略四大條件：
  1. RD 趨勢判斷 (statusRD)  — EMA10/EMA20 與 K 棒位置（持態機制：無中性 ⚪，持續維持 🟢 或 🔴）
     - 已過河拆橋天數：從最近一次明確翻轉起算到今日的天數（剛穿越當天為 1 天）
     - 已掉入河中次數：趨勢中 K 棒（多頭陰K/空頭陽K）收盤價跌入/升入 EMA 夾層後再次回到正常趨勢的次數
     - 注意事項：掉河次數 >= 2 特別警告
  2. MACD DEA 破零 (statusMACD) — Signal Line > 0 (多) 或 < 0 (空)
  3. SR 突破 (60天最高/最低)   — (Close + Open)/2 突破 60 天最高價 / 跌破最低價
  4. VOL 成交量 (statusVOL)    — 綠色柱/紅色柱 且 VOL > MA10

進出場訊號：
  - 現貨做多進場: statusRD==3 AND statusMACD==1 AND isBreakup AND 綠色成交量柱 AND VOL > MA10
  - 現貨出場: statusRD==-3
  - 1X做空進場: statusRD==-3 AND statusMACD==-1 AND isBrokedown AND 紅色成交量柱 AND VOL > MA10
  - 做空出場: statusRD==3
"""

import datetime

try:
    from config import SR_LOOKBACK_BARS
except ImportError:
    SR_LOOKBACK_BARS = 60


def calculate_ema(prices, period):
    """計算指數移動平均線 (EMA)"""
    if not prices or len(prices) == 0:
        return []
    ema = [prices[0]]
    multiplier = 2.0 / (period + 1.0)
    for price in prices[1:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return ema


def calculate_macd(prices, fast=12, slow=26, signal=9):
    """
    計算 MACD 指標
    Returns:
        tuple: (macd_line, signal_line, hist_line) 最新一根的數值
    """
    if len(prices) < slow + signal:
        return 0.0, 0.0, 0.0
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_series = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_series = calculate_ema(macd_series, signal)
    hist_series = [m - s for m, s in zip(macd_series, signal_series)]
    return macd_series[-1], signal_series[-1], hist_series[-1]


def analyze_coin(coin):
    """
    分析單一幣種，計算完整技術指標、RD 歷史天數與掉河次數、進出場訊號。

    Args:
        coin (dict): 包含 ohlcv 日 K 線資料與基本資料的字典

    Returns:
        dict: 策略分析結果
    """
    ohlcv = coin.get("ohlcv", [])
    if not ohlcv or len(ohlcv) < 30:
        raise ValueError(f"K 線資料不足: {len(ohlcv)} 根")

    closes = [b[4] for b in ohlcv]
    opens = [b[1] for b in ohlcv]
    highs = [b[2] for b in ohlcv]
    lows = [b[3] for b in ohlcv]
    vols = [b[5] for b in ohlcv]
    n_bars = len(ohlcv)

    # 技術指標計算
    ema10_series = calculate_ema(closes, 10)
    ema20_series = calculate_ema(closes, 20)
    macd_val, signal_line, macd_hist = calculate_macd(closes)

    # 最新完成日 K 數值
    close = closes[-1]
    open_price = opens[-1]
    high = highs[-1]
    low = lows[-1]
    ema10 = ema10_series[-1]
    ema20 = ema20_series[-1]

    # 24h 漲跌幅（以最新完成日 K 計算）
    prev_close = closes[-2] if n_bars >= 2 else close
    change = (close - prev_close) / prev_close if prev_close > 0 else 0.0

    # ===== 1. RD 趨勢持態機制 (State Machine) =====
    # 規則：
    # - is_up: low > ema10 且 low > ema20
    # - is_down: high < ema10 且 high < ema20
    # 一但確認為 🟢 (多頭) 後持續維持，直到轉型為 🔴 (空頭)；反之亦然。無中性 (⚪)。
    state = 0  # 3 = 🟢 多頭, -3 = 🔴 空頭
    flip_idx = 0

    for i in range(n_bars):
        is_up = (lows[i] > ema10_series[i] and lows[i] > ema20_series[i])
        is_down = (highs[i] < ema10_series[i] and highs[i] < ema20_series[i])

        old_state = state
        if is_up:
            state = 3
        elif is_down:
            state = -3

        # 紀錄最新一次翻轉的時間點
        if old_state != state and state != 0:
            flip_idx = i

    # 若歷史中從未明確翻轉過，預設以第 0 根開始
    status_rd = state if state != 0 else (3 if close >= ema10 else -3)

    # 已過河拆橋天數：從翻轉日到最新完成日 K 的天數（當天穿越即為第 1 天）
    trend_days = n_bars - flip_idx

    flip_timestamp = ohlcv[flip_idx][0]
    flip_date = datetime.datetime.fromtimestamp(
        flip_timestamp / 1000, tz=datetime.timezone.utc
    ).strftime("%Y-%m-%d")

    # 最新完成日 K 棒的日期
    latest_bar_date = datetime.datetime.fromtimestamp(
        ohlcv[-1][0] / 1000, tz=datetime.timezone.utc
    ).strftime("%m/%d")
    latest_bar_date_full = datetime.datetime.fromtimestamp(
        ohlcv[-1][0] / 1000, tz=datetime.timezone.utc
    ).strftime("%Y-%m-%d")

    # ===== 已掉入河中次數計算（含日期標註 — 即時觸發制） =====
    # 🟢 多頭：從回看歷史找到最近一次明確穿越後，當 K 棒（必須是陰 K）滿足以下條件之一：
    #          1. 收盤價夾在兩條 EMA 中間 (EMA_min <= close <= EMA_max)
    #          2. 收盤價 < EMA10 且 < EMA20 (close < EMA_min)
    #          3. 最低價跌入或貫穿兩條 EMA (low <= EMA_max，包含夾在中間與插針跌破河底)
    #          一掉入河中立即計入次數並記錄日期；在重回河面 (low > EMA_max) 前不重複累加。
    # 🔴 空頭：從回看歷史找到最近一次明確穿越後，當 K 棒（必須是陽 K）滿足以下條件之一：
    #          1. 收盤價夾在兩條 EMA 中間 (EMA_min <= close <= EMA_max)
    #          2. 收盤價 > EMA10 且 > EMA20 (close > EMA_max)
    #          3. 最高價升入或貫穿兩條 EMA (high >= EMA_min，包含夾在中間與插針突破河頂)
    #          一掉入河中立即計入次數並記錄日期；在重回河面 (high < EMA_min) 前不重複累加。
    dips_completed = 0
    dip_dates = []
    in_dip = False

    chinese_nums = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三", "十四", "十五"]

    if status_rd == 3:  # 多頭
        for i in range(flip_idx, n_bars):
            e_min = min(ema10_series[i], ema20_series[i])
            e_max = max(ema10_series[i], ema20_series[i])
            is_above = (lows[i] > e_max)

            # 陰 K 且滿足條件之一（收盤掉入、收盤跌破、或最低價跌入/貫穿河面）:
            cond1 = (e_min <= closes[i] <= e_max)      # 收盤價夾在兩條 EMA 中間
            cond2 = (closes[i] < e_min)                # 收盤價 < EMA10 且 < EMA20
            cond3 = (lows[i] <= e_max)                 # 最低價跌入或貫穿兩條 EMA (含夾在中間與插針跌破河底)
            is_dip_bar = (closes[i] < opens[i]) and (cond1 or cond2 or cond3)

            dt_str = datetime.datetime.fromtimestamp(
                ohlcv[i][0] / 1000, tz=datetime.timezone.utc
            ).strftime("%m/%d")

            if not in_dip:
                if is_dip_bar:
                    in_dip = True
                    dips_completed += 1
                    dip_dates.append(dt_str)
            else:
                if is_above:
                    in_dip = False

    elif status_rd == -3:  # 空頭
        for i in range(flip_idx, n_bars):
            e_min = min(ema10_series[i], ema20_series[i])
            e_max = max(ema10_series[i], ema20_series[i])
            is_below = (highs[i] < e_min)

            # 陽 K 且滿足條件之一（收盤升入、收盤突破、或最高價升入/貫穿河面）:
            cond1 = (e_min <= closes[i] <= e_max)      # 收盤價夾在兩條 EMA 中間
            cond2 = (closes[i] > e_max)                # 收盤價 > EMA10 且 > EMA20
            cond3 = (highs[i] >= e_min)                # 最高價升入或貫穿兩條 EMA (含夾在中間與插針突破河頂)
            is_dip_bar = (closes[i] >= opens[i]) and (cond1 or cond2 or cond3)

            dt_str = datetime.datetime.fromtimestamp(
                ohlcv[i][0] / 1000, tz=datetime.timezone.utc
            ).strftime("%m/%d")

            if not in_dip:
                if is_dip_bar:
                    in_dip = True
                    dips_completed += 1
                    dip_dates.append(dt_str)
            else:
                if is_below:
                    in_dip = False

    # 格式化日期標註字串，例如：3 次（掉入第一次(07/28)、掉入第二次(08/11)、掉入第三次(09/02)）
    if len(dip_dates) > 0:
        dates_detail = "、".join(
            f"掉入第{chinese_nums[k] if k < len(chinese_nums) else str(k+1)}次({d})"
            for k, d in enumerate(dip_dates)
        )
        dips_str = f"{len(dip_dates)} 次（{dates_detail}）"
    else:
        dips_str = "0 次"

    # 注意事項：掉河次數 >= 2
    has_warning = (dips_completed >= 2)

    # ===== 2. MACD DEA 破零 (statusMACD) =====
    if signal_line > 0:
        status_macd = 1
    elif signal_line < 0:
        status_macd = -1
    else:
        status_macd = 0

    # ===== 3. SR 突破（60天最高/最低）=====
    # 取當前日 K 之前的 60 根日 K
    lookback_sr = SR_LOOKBACK_BARS
    if n_bars >= lookback_sr + 1:
        past_sr_bars = ohlcv[-(lookback_sr + 1):-1]
    else:
        past_sr_bars = ohlcv[:-1]

    high_srd = max(b[2] for b in past_sr_bars) if past_sr_bars else high
    low_srd = min(b[3] for b in past_sr_bars) if past_sr_bars else low

    mid_price = (close + open_price) * 0.5
    is_breakup = mid_price > high_srd
    is_brokedown = mid_price < low_srd

    # ===== 4. VOL 成交量判斷 (statusVOL) =====
    vol = vols[-1]
    vol_prev = vols[-2] if n_bars >= 2 else vol
    vol_ma10 = sum(vols[-10:]) / 10.0 if n_bars >= 10 else vol

    is_bullish_vol = (close >= open_price)               # 綠色成交量柱（陽線買量）
    is_bearish_vol = (close < open_price)                # 紅色成交量柱（陰線賣量）
    vol_gt_ma10 = (vol > vol_ma10) and (vol > 0)        # 成交量高於 MA10
    vol_is_increasing = (vol > vol_prev) and (vol > 0)
    vol_is_decreasing = (vol < vol_prev) and (vol > 0)

    # ===== 進出場訊號 =====
    # 現貨做多進場: RD多 + MACD多 + SR突破 + 綠柱且VOL>MA10
    spot_entry = (
        (status_rd == 3) and
        (status_macd == 1) and
        is_breakup and
        is_bullish_vol and
        vol_gt_ma10
    )

    # 現貨出場（RD 剛翻轉為空頭的第一天）
    spot_exit = (status_rd == -3 and trend_days == 1)

    # 1X 做空進場: RD空 + MACD空 + SR跌破 + 紅柱且VOL>MA10
    short_entry = (
        (status_rd == -3) and
        (status_macd == -1) and
        is_brokedown and
        is_bearish_vol and
        vol_gt_ma10
    )

    # 做空出場（RD 剛翻轉為多頭的第一天）
    short_exit = (status_rd == 3 and trend_days == 1)


    # ===== 尋找趨勢波段中歷史進場訊號日期（以生成精確操作建議） =====
    entry_dates_in_trend = []
    first_entry_date = None
    if status_rd == 3:
        for k in range(flip_idx, n_bars):
            c_k, o_k, v_k = closes[k], opens[k], vols[k]
            _, sig_k, _ = calculate_macd(closes[:k+1])
            sr_start = max(0, k - lookback_sr)
            hh_k = max(highs[sr_start:k]) if k > sr_start else 0
            is_bo_k = ((c_k + o_k) * 0.5 > hh_k)
            is_bull_v_k = (c_k >= o_k)
            ma10_k = sum(vols[max(0, k-9):k+1]) / min(10, k+1)
            is_v_gt_k = (v_k > ma10_k)
            if (sig_k > 0) and is_bo_k and is_bull_v_k and is_v_gt_k:
                d = datetime.datetime.fromtimestamp(ohlcv[k][0]/1000, tz=datetime.timezone.utc)
                entry_dates_in_trend.append(f"{d.month}/{d.day}")
        if entry_dates_in_trend:
            first_entry_date = entry_dates_in_trend[0]
    elif status_rd == -3:
        for k in range(flip_idx, n_bars):
            c_k, o_k, v_k = closes[k], opens[k], vols[k]
            _, sig_k, _ = calculate_macd(closes[:k+1])
            sr_start = max(0, k - lookback_sr)
            ll_k = min(lows[sr_start:k]) if k > sr_start else 0
            is_bd_k = ((c_k + o_k) * 0.5 < ll_k)
            is_bear_v_k = (c_k < o_k)
            ma10_k = sum(vols[max(0, k-9):k+1]) / min(10, k+1)
            is_v_gt_k = (v_k > ma10_k)
            if (sig_k < 0) and is_bd_k and is_bear_v_k and is_v_gt_k:
                d = datetime.datetime.fromtimestamp(ohlcv[k][0]/1000, tz=datetime.timezone.utc)
                entry_dates_in_trend.append(f"{d.month}/{d.day}")
        if entry_dates_in_trend:
            first_entry_date = entry_dates_in_trend[0]

    # ===== 判斷首次進場 vs 再次進場 =====
    entry_signal_count = len(entry_dates_in_trend)  # 本波趨勢中累計觸發進場訊號的次數
    # 如果今天滿足進場條件，且歷史中不含今天 → 只有 1 次（即今天自己），就是首次
    # 如果歷史中已有 >= 2 次，代表之前已觸發過，今天是「再次進場」
    if spot_entry or short_entry:
        is_first_entry = (entry_signal_count <= 1)
        # 過去歷史進場日（不含今天）
        past_entry_dates = entry_dates_in_trend[:-1] if entry_signal_count > 1 else []
    else:
        is_first_entry = False
        past_entry_dates = entry_dates_in_trend

    # ===== 4 大條件狀態檢核 (卡片顯示 (2/4) 與打勾打叉) =====
    if status_rd == 3:  # 多頭
        cond1_ok = (close > ema10 and ema10 > ema20)
        cond2_ok = (status_macd == 1)
        cond3_ok = is_breakup
        cond4_ok = (is_bullish_vol and vol_gt_ma10)
        checklist = [
            f"(1) 價格 > EMA10 > EMA20 {'✅' if cond1_ok else '❌'}",
            f"(2) MACD DEA > 0 {'✅' if cond2_ok else '❌'}",
            f"(3) 突破{lookback_sr}日高點 {'✅' if cond3_ok else '❌'}",
            f"(4) 買方VOL > MA10 {'✅' if cond4_ok else '❌'}"
        ]
    else:  # 空頭
        cond1_ok = (close < ema10 and ema10 < ema20)
        cond2_ok = (status_macd == -1)
        cond3_ok = is_brokedown
        cond4_ok = (is_bearish_vol and vol_gt_ma10)
        checklist = [
            f"(1) 價格 < EMA10 < EMA20 {'✅' if cond1_ok else '❌'}",
            f"(2) MACD DEA < 0 {'✅' if cond2_ok else '❌'}",
            f"(3) 跌破{lookback_sr}日低點 {'✅' if cond3_ok else '❌'}",
            f"(4) 賣方VOL > MA10 {'✅' if cond4_ok else '❌'}"
        ]
    conditions_met_count = sum([1 for ok in [cond1_ok, cond2_ok, cond3_ok, cond4_ok] if ok])

    # ===== 操作建議與注意事項自動生成 =====
    if status_rd == 3:  # 多頭
        if spot_entry:
            if is_first_entry:
                action_advice = "今日滿足全數共振條件，觸發“現貨做多首次進場訊號”，可考慮分批建倉現貨。"
            else:
                cn = ["一","二","三","四","五","六","七","八","九","十"]
                past_dates_str = "、".join(f"第{cn[k] if k < len(cn) else str(k+1)}次:{d}" for k, d in enumerate(past_entry_dates))
                action_advice = f"今日再次滿足全數共振條件，觸發\u201c現貨做多再次進場訊號\u201d（本波第{entry_signal_count}次，{past_dates_str}），可考慮加碼或確認持倉方向。"
        elif first_entry_date:
            action_advice = f"自{first_entry_date}訊號出現“現貨做多進場訊號”後，目前趨勢尚未反轉向下，因此現貨可續抱。"
        else:
            action_advice = "目前趨勢為多頭向上，但尚未滿足放量突破買訊，建議觀望等待突破或回測不破均線時布局。"

        if dips_completed >= 2:
            if in_dip:
                caution_note = f"⚠️已掉入河中達{dips_completed}次，且目前回測河中，注意趨勢轉折風險！"
            else:
                caution_note = f"⚠️已掉入河中達{dips_completed}次，多頭動能稍顯疲態，注意高檔轉折風險！"
        else:
            caution_note = "均線支撐良好，目前尚未出現動能竭盡警示。"
    else:  # 空頭
        if spot_exit:
            action_advice = "今日趨勢翻空觸發“現貨出場訊號”，建議現貨停損/獲利了結離場觀望。"
        elif short_entry:
            if is_first_entry:
                action_advice = "今日跌破支撐且放量，觸發“1X做空首次進場訊號”，空方動能強勁。"
            else:
                cn = ["一","二","三","四","五","六","七","八","九","十"]
                past_dates_str = "、".join(f"第{cn[k] if k < len(cn) else str(k+1)}次:{d}" for k, d in enumerate(past_entry_dates))
                action_advice = f"今日再次跌破支撐且放量，觸發\u201c1X做空再次進場訊號\u201d（本波第{entry_signal_count}次，{past_dates_str}），空方動能持續。"
        elif first_entry_date:
            action_advice = f"自{first_entry_date}訊號出現“做空進場訊號”後，目前趨勢向下，空頭格局尚未扭轉，現貨宜空倉觀望。"
        else:
            action_advice = "目前趨勢向下，空頭格局尚未扭轉，現貨宜空倉觀望，切勿盲目抄底。"

        if dips_completed >= 2:
            if in_dip:
                caution_note = f"⚠️已反彈升入河中達{dips_completed}次，且目前回測河中，注意可能轉折風險！"
            else:
                caution_note = f"⚠️已反彈升入河中達{dips_completed}次，空頭動能減弱，注意反彈風險！"
        else:
            caution_note = "均線下行順暢，目前尚未出現竭盡警示。"

    return {
        "symbol": coin.get("symbol", ""),
        "name": coin.get("name", ""),
        "pair": coin.get("pair", ""),
        "trade_symbol": coin.get("trade_symbol", ""),
        "rank": coin.get("rank", 0),
        "market_cap": coin.get("market_cap", 0),
        "close": close,
        "open": open_price,
        "high": high,
        "low": low,
        "change": change,
        "ema10": ema10,
        "ema20": ema20,
        "macd_line": macd_val,
        "signal_line": signal_line,
        "macd_hist": macd_hist,
        "high_3m": high_srd,
        "low_3m": low_srd,
        "high_sr": high_srd,
        "low_sr": low_srd,
        "sr_lookback": lookback_sr,
        "vol": vol,
        "vol_prev": vol_prev,
        "vol_ma10": vol_ma10,
        # RD 歷史指標
        "status_rd": status_rd,
        "trend_days": trend_days,
        "flip_date": flip_date,
        "dips_completed": dips_completed,
        "dip_dates": dip_dates,
        "dips_str": dips_str,
        "in_dip": in_dip,
        "has_warning": has_warning,
        "latest_bar_date": latest_bar_date,
        "latest_bar_date_full": latest_bar_date_full,
        # 其他狀態
        "status_macd": status_macd,
        "vol_gt_ma10": vol_gt_ma10,
        "is_bullish_vol": is_bullish_vol,
        "is_bearish_vol": is_bearish_vol,
        "vol_is_increasing": vol_is_increasing,
        "vol_is_decreasing": vol_is_decreasing,
        "is_breakup": is_breakup,
        "is_brokedown": is_brokedown,
        # 進出場訊號
        "spot_entry": spot_entry,
        "spot_exit": spot_exit,
        "short_entry": short_entry,
        "short_exit": short_exit,
        "is_first_entry": is_first_entry,
        "entry_signal_count": entry_signal_count,
        "entry_signal_dates": entry_dates_in_trend,
        # 個幣卡片擴充欄位
        "ohlcv": ohlcv,
        "first_entry_date": first_entry_date,
        "checklist": checklist,
        "conditions_met_count": conditions_met_count,
        "action_advice": action_advice,
        "caution_note": caution_note,
    }


def analyze_all(coins):
    """
    分析所有幣種，回傳分析結果列表。

    Args:
        coins (list[dict]): scanner 取得的幣種列表

    Returns:
        list[dict]: 每個幣的分析結果
    """
    results = []
    for coin in coins:
        try:
            result = analyze_coin(coin)
            results.append(result)
        except (KeyError, TypeError, ValueError) as e:
            print(f"⚠️ 分析 {coin.get('symbol', '???')} 時出錯: {e}")
    return results


def get_signals(results):
    """
    從分析結果中提取有訊號的幣種。

    Args:
        results (list[dict]): analyze_all 的回傳值

    Returns:
        dict: 按訊號類型分類的結果
    """
    signals = {
        "spot_entry": [],
        "spot_exit": [],
        "short_entry": [],
        "short_exit": [],
    }

    for r in results:
        if r["spot_entry"]:
            signals["spot_entry"].append(r)
        if r["spot_exit"]:
            signals["spot_exit"].append(r)
        if r["short_entry"]:
            signals["short_entry"].append(r)
        if r["short_exit"]:
            signals["short_exit"].append(r)

    return signals


if __name__ == "__main__":
    from scanner import fetch_top_coins

    coins = fetch_top_coins(5)
    results = analyze_all(coins)

    print("=" * 65)
    print("FT 波段策略分析結果（CoinGecko + Bitget CCXT）")
    print("=" * 65)

    for r in results:
        rd_color = "🟢" if r["status_rd"] == 3 else "🔴"
        macd_color = "🟢" if r["status_macd"] == 1 else "🔴"
        vol_color = "🟢 綠柱" if r["is_bullish_vol"] else "🔴 紅柱"
        vol_ma = "✅ >MA10" if r["vol_gt_ma10"] else "❌ ≤MA10"
        warn_str = " ⚠️【注意：已掉入河中 2 次以上】" if r["has_warning"] else ""

        print(f"\n{r['symbol']} ({r['name']}) — {r['pair']}")
        print(f"  💰 價格: ${r['close']:,.2f}  漲跌: {r['change']*100:+.2f}%")
        print(f"  RD趨勢: {rd_color}  |  已過河拆橋天數: {r['trend_days']} 天 (翻轉日: {r['flip_date']})")
        print(f"  已掉入河中次數: {r['dips_completed']} 次{warn_str}")
        print(f"  MACD: {macd_color} ({r['signal_line']:.4f})  |  SR {r.get('sr_lookback', 60)}D: 突破={r['is_breakup']}, 跌破={r['is_brokedown']}")
        print(f"  VOL: {r['vol']:,.1f}  |  MA10: {r['vol_ma10']:,.1f}  |  {vol_color}  |  {vol_ma}")

        if r["spot_entry"]:
            print(f"  🚀 >>> 現貨做多進場 <<<")
        if r["spot_exit"]:
            print(f"  🛑 >>> 現貨出場 <<<")
        if r["short_entry"]:
            print(f"  📉 >>> 1X做空進場 <<<")
        if r["short_exit"]:
            print(f"  🔄 >>> 做空出場 <<<")
