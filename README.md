# 🏦 FT 波段策略 — 加密貨幣每日通知系統

透過 **CoinGecko 市值** 篩選前 20 的加密貨幣（排除穩定幣與包裝代幣），並透過 **CCXT (Bitget)** 取得完整日 K 線歷史資料，依照 FT 波段策略判斷進出場訊號，每天早上 08:00（台北時間）透過 Telegram Bot 推送通知。

---

## 📋 策略邏輯

FT 波段策略基於 **四大條件** 綜合判斷：

| 條件 | 多方 (🟢) | 空方 (🔴) | 指標來源 / 計算方式 |
|------|----------|----------|-------------------|
| **1. RD 趨勢** | 日 Low > EMA10 且 > EMA20 | 日 High < EMA10 且 < EMA20 | Bitget 日 K EMA10 / EMA20（持態無中性 ⚪） |
| **2. MACD DEA線** | Signal Line (DEA) > 0 | Signal Line (DEA) < 0 | MACD DEA線 (12, 26, 9) |
| **3. SR 突破** | (Close + Open) / 2 > 60天最高 | (Close + Open) / 2 < 60天最低 | 過去 60 天日 K 最高/最低價 |
| **4. VOL>MA10** | 綠色量能柱 且 VOL > MA10 | 紅色量能柱 且 VOL > MA10 | 日 K 成交量與過去 10 天成交量均線 (MA10) |

---

### 🌊 條件 1：RD 趨勢持態機制與歷史分析

- **無中性持態機制**：
  - 一但判斷為 🟢 RD（多頭），就持續維持 🟢，直到轉型為 🔴 RD（空頭）。
  - 一但判斷為 🔴 RD（空頭），就持續維持 🔴，直到轉型為 🟢 RD（多頭）。
  - 盤整或 K 棒觸碰 EMA 時，維持原趨勢方向，不顯示中性 ⚪。
- **已過河拆橋天數**：
  - 回看歷史找到最近一次明確翻轉（穿越）起算到今日的天數。
  - 例如：昨天剛明確穿越成為趨勢向上的那天，今天即顯示「已過河拆橋天數: 1」。
- **已掉入河中次數（含日期標註 — 即時觸發制）**：
  - **即時觸發與防重複機制**：
    - 當 K 棒一旦符合掉入河中條件，**當天立即計入次數並標註日期**，無需等待未來重回河面。
    - 在同一次回檔尚未完全站回河面之前，後續連續處於河中或陰 K 不會重複累加。
    - 待日 K 完全回到河面之後，下次再度掉入方累計為下一次。
  - **多頭 🟢 時**：趨勢確立後，當出現**陰 K** 且符合以下條件之一即觸發：
    1. 收盤價夾在兩條 EMA 中間（`EMA_min <= close <= EMA_max`）
    2. 收盤價 < EMA10 且 < EMA20（`close < EMA_min`）
    3. **最低價跌入或貫穿兩條 EMA**（`low <= EMA_max`，包含夾在兩線中間與插針跌破河底）
    （重回河面判定：日 K `Low > EMA10 且 > EMA20`）
  - **空頭 🔴 時**：趨勢確立後，當出現**陽 K** 且符合以下條件之一即觸發：
    1. 收盤價夾在兩條 EMA 中間（`EMA_min <= close <= EMA_max`）
    2. 收盤價 > EMA10 且 > EMA20（`close > EMA_max`）
    3. **最高價升入或貫穿兩條 EMA**（`high >= EMA_min`，包含夾在兩線中間與插針突破河頂）
    （重回河面判定：日 K `High < EMA10 且 < EMA20`）
  - **日期標註格式**：例如 `2 次（掉入第一次(09/01)、掉入第二次(09/07)）`。
- **⚠️ 注意事項**：
  - 若「已掉入河中次數」已達 **2 次以上**，系統會立即特別標註 ⚠️ 提醒，代表多頭/空頭動能可能趨緩竭盡，有變盤風險！

---

### 📊 條件 4：成交量指標（VOL / MA10）詳細說明

- **綠色柱狀圖（🟢 陽線買量）**：當日收盤價 ≥ 開盤價（`Close >= Open`），代表買盤主導上漲。
- **紅色柱狀圖（🔴 陰線賣量）**：當日收盤價 < 開盤價（`Close < Open`），代表賣盤主導下跌。
- **MA10（10日均線）**：過去 10 天日 K 成交量的平均值。
- **VOL > MA10**：成交量高於 MA10 均線，表示交易活躍度顯著放大。

---

### 🚦 進出場條件

- 🚀 **現貨做多進場**: RD多 + MACD多 + 突破 60 天高點 + 綠色量能柱 且 VOL > MA10
- 🛑 **現貨出場**: RD 剛轉為空頭的第一天（`trend_days == 1`）
- 📉 **1X 做空進場**: RD空 + MACD空 + 跌破 60 天低點 + 紅色量能柱 且 VOL > MA10
- 🔄 **做空出場**: RD 剛轉為多頭的第一天（`trend_days == 1`）

---

### 📱 Telegram 推播模組（總覽日報 + 個幣圖文卡片）

系統每日掃描後，會依序透過 Telegram Bot 推送：

#### 1. 總覽日報（文字訊息）
```text
加密貨幣趨勢日報
2026/09/12 08:00 (台北時區）
———————————————————————————————————
⚡️今日新訊號（第1天）:
🔴 BCH(現貨出場)
———————————————————————————————————
🟢 RD向上：共18幣種
 1. BTC    | $77,224.52 | 📈 +0.85% | RD🟢(25天|掉河2(09/01,09/07⚠️)) | MACD DEA線🟢 | VOL>MA10🟢
 2. ETH    | $2,516.60 | 📈 +3.22% | RD🟢(71天|掉河7(07/08,07/13,07/17⚠️)) | MACD DEA線🟢 | VOL>MA10🟢
 ...
———————————————————————————————————
🔴 RD向下：共2幣種
 1. BCH    | $228.1000 | 📈 +1.92% | RD🔴(1天|掉河0) | MACD DEA線🟢 | VOL>MA10🟢 | 訊號: 🛑現貨出場
 2. CC     | $0.097610 | 📉 -0.41% | RD🔴(7天|掉河1(09/06)) | MACD DEA線🔴 | VOL>MA10🔴
———————————————————————————————————
```

#### 2. 個幣圖文卡片（K 線指標圖 + 詳細分析）
由 Matplotlib 繪製暗黑風格（TradingView 質感）三子圖：
- **頂部子圖**：日 K 棒 + EMA10 (藍) + EMA20 (紅) + 60日阻力線 (紅虛線) + 60日支撐線 (綠虛線)
- **中部子圖**：成交量柱狀圖 (陽綠/陰紅) + 成交量 MA10 均線 (黃線)
- **底部子圖**：MACD 快慢線 + 柱狀圖 (正綠/負紅) + 0 軸虛線

**卡片文案範例**：
```text
市值排名1: BTC (Bitcoin)
9/11收盤價： $77,224.52
🟢 RD向上：
已過河拆橋天數：25天
操作建議：自8/19訊號出現“現貨做多進場訊號”後，目前趨勢尚未反轉向下，因此現貨可續抱。
已掉入河中次數：2次；掉入第一次(09/01)、掉入第二次(09/07)。
注意事項：⚠️已掉入河中達2次，且目前回測河中，注意趨勢轉折風險！

<a href="https://tw.tradingview.com/chart/?symbol=BITGET%3ABTCUSDT">🔗Tradingview</a>
```

---

## 🚀 從零開始完整設定指南

> 💡 以下步驟假設你是完全的新手，會一步一步帶你完成設定。

---

### 📱 第一步：安裝 Telegram 並建立帳號

如果你已經有 Telegram 帳號，可以跳到第二步。

1. **下載 Telegram**
   - iPhone：到 App Store 搜尋「Telegram」，點擊下載
   - Android：到 Google Play 搜尋「Telegram」，點擊安裝
   - 電腦：到 https://desktop.telegram.org 下載桌面版

2. **註冊帳號**
   - 打開 Telegram
   - 輸入你的手機號碼
   - 輸入收到的驗證碼
   - 設定你的名字
   - 完成！你現在有 Telegram 帳號了

---

### 🤖 第二步：建立 Telegram Bot

Bot（機器人）是 Telegram 上可以自動發送訊息的帳號，我們需要建立一個來推送策略通知。

1. **找到 BotFather**
   - 打開 Telegram
   - 點擊上方的搜尋框（放大鏡圖示）
   - 輸入 `@BotFather`
   - 點擊搜尋結果中有藍色勾勾 ✓ 的「BotFather」

2. **建立新 Bot**
   - 點擊「Start」或輸入 `/start`
   - 輸入 `/newbot` 並發送
   - BotFather 會問你 Bot 的名字，輸入一個名字，例如：`FT策略通知`
   - BotFather 會問你 Bot 的帳號名，必須以 `bot` 結尾，例如：`ft_strategy_notify_bot`
   - 如果帳號已被使用，換一個再試

3. **記下 Bot Token** ⚠️ 重要！
   - 建立成功後，BotFather 會回覆一串 Token，格式像這樣：
     ```
     123456789:ABCdefGhIjKlmNoPqRsTuVwXyZ
     ```
   - **複製並妥善保存這串 Token**，之後會用到
   - ⚠️ 不要分享給任何人，Token 等同於 Bot 的密碼

4. **啟動你的 Bot**
   - 在 Telegram 搜尋框搜尋你剛才設的帳號名（例如 `@ft_strategy_notify_bot`）
   - 點進去，按「Start」
   - 這一步很重要！不按 Start 的話 Bot 無法發訊息給你

---

### 🔑 第三步：取得你的 Chat ID

Chat ID 是你的個人 Telegram ID，Bot 需要知道要發訊息給誰。

**方法一（最簡單）：使用 @userinfobot**

1. 在 Telegram 搜尋 `@userinfobot`
2. 點擊 Start
3. 它會立刻回覆你的資訊，其中 `Id` 就是你的 Chat ID
4. 記下這個數字（例如：`123456789`）

**方法二：使用瀏覽器**

1. 先在 Telegram 對你剛建的 Bot 發送任意一條訊息（例如 "hello"）
2. 打開瀏覽器，在網址列輸入：
   ```
   https://api.telegram.org/bot你的TOKEN/getUpdates
   ```
   把「你的TOKEN」替換成第二步記下的 Token
3. 在回覆的 JSON 中找到 `"chat":{"id":123456789}`，那個數字就是 Chat ID

**如果要發送到群組：**

1. 把 Bot 加入群組（在群組中「新增成員」，搜尋你的 Bot 名稱）
2. 在群組中發一條訊息
3. 用方法二的瀏覽器方式，找到群組的 Chat ID（群組 ID 通常是負數，如 `-987654321`）

---

### 🖥️ 第四步：安裝 Git 和建立 GitHub 帳號

#### 4-1. 安裝 Git

**Mac 用戶：**
1. 打開「終端機」（在 Spotlight 搜尋「Terminal」或「終端機」）
2. 輸入以下指令並按 Enter：
   ```bash
   git --version
   ```
3. 如果顯示版本號（如 `git version 2.39.0`），表示已安裝
4. 如果跳出安裝提示，按照提示安裝 Xcode Command Line Tools

**Windows 用戶：**
1. 到 https://git-scm.com/download/win 下載 Git
2. 執行安裝程式，一路按 Next 即可
3. 安裝完成後，打開「命令提示字元」或「PowerShell」
4. 輸入 `git --version` 確認安裝成功

#### 4-2. 註冊 GitHub 帳號

1. 打開瀏覽器，前往 https://github.com
2. 點擊右上角的「Sign up」
3. 依序輸入：
   - Email 地址
   - 密碼
   - 使用者名稱（英文，例如 `mytrading123`）
4. 完成驗證後，你就有 GitHub 帳號了

#### 4-3. 設定 Git 基本資訊

在終端機輸入（把引號內替換成你的資訊）：

```bash
git config --global user.name "你的名字"
git config --global user.email "你的email@example.com"
```

---

### 📦 第五步：建立 GitHub Repository 並推上程式碼

#### 5-1. 在 GitHub 上建立新 Repository

1. 登入 GitHub（https://github.com）
2. 點擊右上角的「+」→「New repository」
3. 填寫：
   - **Repository name**: `FT_notify`
   - **Description**: `FT 波段策略自動通知系統`
   - **Public / Private**: 選 **Private**（私人，推薦）
   - ⚠️ **不要勾選** "Add a README file"（因為我們已經有了）
4. 點擊「Create repository」
5. 建立完成後，頁面會顯示你的 repo 網址，類似：
   ```
   https://github.com/你的帳號/FT_notify.git
   ```

#### 5-2. 把程式碼推上 GitHub

打開終端機，依序輸入以下指令：

```bash
# 1. 進入專案資料夾
cd ~/理財醫生學院/FT_notify

# 2. 初始化 Git
git init

# 3. 加入所有檔案
git add .

# 4. 建立第一個 commit
git commit -m "初始化 FT 波段策略通知系統"

# 5. 設定主分支名稱
git branch -M main

# 6. 連接到你的 GitHub repo（把 <你的帳號> 替換掉）
git remote add origin https://github.com/<你的帳號>/FT_notify.git

# 7. 推上去
git push -u origin main
```

> 💡 第一次推送時，可能會要求你登入 GitHub。按照提示操作即可。
>
> 如果出現認證問題，GitHub 現在建議使用 **Personal Access Token** 取代密碼：
> 1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
> 2. Generate new token → 勾選 `repo` 權限 → Generate token
> 3. 複製 Token，在終端機要求密碼時貼上

---

### 🔐 第六步：設定 GitHub Secrets

Secrets 是安全存放敏感資訊（如 Token）的地方，GitHub Actions 會自動讀取。

1. 打開你的 GitHub repo 頁面（`https://github.com/<你的帳號>/FT_notify`）
2. 點擊上方的 **Settings**（齒輪圖示）
3. 左側選單找到 **Secrets and variables** → **Actions**
4. 點擊 **New repository secret**
5. 新增兩個 Secret：

| Name | Value |
|------|-------|
| `TELEGRAM_BOT_TOKEN` | 你在第二步記下的 Bot Token（例：`123456789:ABCdef...`） |
| `TELEGRAM_CHAT_ID` | 你在第三步記下的 Chat ID（例：`987654321`） |

每個都要分別新增，新增方式：
- 在「Name」欄位輸入名稱（如 `TELEGRAM_BOT_TOKEN`）
- 在「Secret」欄位貼上對應的值
- 點擊「Add secret」

---

### ✅ 第七步：測試 GitHub Actions

1. 進入你的 GitHub repo 頁面
2. 點擊上方的 **Actions** 分頁
3. 如果看到提示「Workflows aren't being run on this repository」，點擊「I understand my workflows, go ahead and enable them」
4. 左側找到 **FT 波段策略每日通知**
5. 點擊右側的 **Run workflow** → **Run workflow**
6. 等待幾秒鐘，你應該會在 Telegram 收到策略通知！

如果測試成功，系統會在每天早上 08:00（台北時間）自動執行。

---

### ⏰ 第八步：設定 Cron-job.org 備援觸發（選做）

GitHub Actions 的 cron 排程有時會延遲。Cron-job.org 可以作為備援觸發器。

#### 8-1. 建立 GitHub Personal Access Token

1. 登入 GitHub
2. 點擊右上角的頭像 → **Settings**
3. 左側最下方 → **Developer settings**
4. **Personal access tokens** → **Fine-grained tokens** → **Generate new token**
5. 填寫：
   - **Token name**: `cron-job-trigger`
   - **Expiration**: 選 90 天或更長
   - **Repository access**: 選 **Only select repositories** → 勾選 `FT_notify`
   - **Permissions** → Repository permissions → **Contents**: Read and write
6. 點擊 **Generate token**
7. ⚠️ **立刻複製 Token**（只會顯示一次）

#### 8-2. 設定 Cron-job.org

1. 前往 https://cron-job.org 並註冊帳號（免費）
2. 登入後，點擊 **Create cronjob**
3. 填寫以下資訊：

   | 欄位 | 值 |
   |------|-----|
   | **Title** | FT Strategy Daily Scan |
   | **URL** | `https://api.github.com/repos/<你的帳號>/FT_notify/dispatches` |
   | **Schedule** | Custom → Minute: `0`, Hour: `0`, 其他全選 → 即每天 UTC 00:00 = 台北 08:00 |
   | **Request method** | POST |

4. 展開 **Advanced** 設定：
   - **Headers**（點擊 Add header，分別新增以下三個）：

     | Header | Value |
     |--------|-------|
     | `Accept` | `application/vnd.github.v3+json` |
     | `Authorization` | `Bearer <你的GitHub Token>` |
     | `Content-Type` | `application/json` |

   - **Request Body**：
     ```json
     {"event_type": "daily-scan"}
     ```

5. 點擊 **Create** 完成

---

### 🧪 本地測試（選做）

你也可以在自己的電腦上測試：

```bash
# 進入專案資料夾
cd ~/理財醫生學院/FT_notify

# 只印出分析結果，不發送通知（Dry-run 模式）
DRY_RUN=true python3 src/main.py

# 實際發送通知到 Telegram
export TELEGRAM_BOT_TOKEN="你的token"
export TELEGRAM_CHAT_ID="你的chat_id"
python3 src/main.py
```

---

## 📁 專案結構

```
FT_notify/
├── .github/
│   └── workflows/
│       └── daily_notify.yml    # GitHub Actions 排程
├── src/
│   ├── config.py               # 策略參數與推播設定
│   ├── scanner.py              # CoinGecko 市值篩選 + CCXT (Bitget) 日 K 棒抓取
│   ├── strategy.py             # FT 策略邏輯（4大條件、進出場、操作建議）
│   ├── chart_generator.py      # Matplotlib 暗黑風格 K 線指標圖表產生器
│   ├── notifier.py             # Telegram 總覽日報與圖文卡片推播
│   └── main.py                 # 主程式入口
├── script/
│   └── FT_pineScript_V1.rtf    # 原始 Pine Script
├── .env.example                # 環境變數範本
├── .gitignore                  # Git 忽略清單
├── requirements.txt            # Python 依賴 (requests, ccxt, matplotlib, pillow)
└── README.md                   # 本文件
```

## ⚙️ 技術細節

- **數據來源**: CoinGecko API (市值前20名篩選) + CCXT Bitget (現貨日 K 線數據)
- **指標計算**: 原生高精度計算 EMA10、EMA20、MACD DEA破零、60日突破與成交量 MA10
- **圖表繪製**: Matplotlib Headless (Agg) 繪製 TradingView 暗黑質感三子圖
- **通知平台**: Telegram Bot API (`sendMessage` + `sendPhoto`)
- **排程**: GitHub Actions cron (UTC 00:00) + Cron-job.org 備援
- **語言**: Python 3.11+

## ❓ 常見問題

**Q: 沒有收到 Telegram 通知？**
- 確認你有對 Bot 按過「Start」
- 確認 GitHub Secrets 的 Token 和 Chat ID 是否正確
- 到 GitHub → Actions 查看執行記錄是否有錯誤

**Q: GitHub Actions 沒有自動執行？**
- 確認 Actions 已啟用（repo → Actions → 檢查是否有啟用提示）
- GitHub cron 可能有 5-15 分鐘的延遲，屬正常現象
- 設定 Cron-job.org 備援可以解決這個問題

**Q: 想修改掃描的幣種數量？**
- 修改 `src/config.py` 中的 `TOP_N_COINS` 值即可

**Q: 想調整策略參數（EMA、MACD 長度）？**
- 修改 `src/config.py` 中對應的參數值
