# 台灣天氣預報儀表板｜專案實作計畫

> 目標：完成老師指定的「中央氣象署 API → JSON → Python → SQLite／SQL → Streamlit」流程，並以 AirBox 的地圖探索概念，做出清爽、可操作的單頁天氣儀表板。本文是實作藍圖，尚未代表功能已完成。

## 1. 作業要求與成品範圍

老師圖片的 24 個步驟，核心是：申請 CWA API Key、取得 JSON、分析 `MinT`／`MaxT`、用 Pandas 整理、寫入 SQLite、SQL 查詢驗證、以 Streamlit 做地區選擇／折線圖／資料表、再以 Folium 做地圖、上傳 GitHub。建議按此順序完成，最後才加強 UI。

**第一版（必做）**：22 縣市今明 36 小時預報、選擇縣市、最高／最低溫圖與表、SQLite 持久化、全台地圖及資料時間標示。

**第二版（加分）**：未來一週預報卡、降雨圖、觀測站目前溫濕度、排行榜、歷次「預報快照」分析。先確認資料集提供哪些欄位再顯示，缺值顯示「暫無資料」。

### 資料語意要分清楚

| 畫面資訊 | 建議來源 | 標示方式 |
| --- | --- | --- |
| 今明 36 小時 `Wx`、`MinT`、`MaxT`、`PoP`、`CI` | CWA `F-C0032-001` | 「預報」，每筆對應時間區間 |
| 未來一週 | CWA 一週預報資料集，例如 `F-D0047-091`，實作前檢查回傳結構 | 「預報」，不可用 36 小時資料假裝一週 |
| 當前溫度、濕度、風速 | CWA 觀測資料，先確認測站種類、欄位及有效時間 | 「測站觀測」，附測站名稱和觀測時間 |
| 地圖縣市點 | 首版用人工確認的縣市代表座標，搭配縣市預報 | 「縣市代表點」，不可暗示它是測站座標 |
| 歷史趨勢 | 自己定期保存的觀測記錄或預報快照 | 前者可稱歷史天氣；後者應稱「歷次預報」 |

**關鍵修正**：先前構想中的「目前天氣 30°C、濕度 68%、體感 32°C」不能直接從 36 小時預報當作實測值；也不能把不同抓取時間的同一預報畫成「過去七天實際氣溫」。

## 2. 使用者介面與互動

單頁由上而下：頂部標題與更新時間 → 左側縣市預報主卡／右側台灣地圖 → 指標卡（預報最高、最低、降雨機率、舒適度）→ 時段預報卡 → 溫度及降雨趨勢圖 → SQL 資料表 → 可折疊的歷次預報紀錄。若增加觀測 API，再獨立加入「現在觀測」卡。

- 桌面：主卡與地圖並列；手機：垂直排列，圖表不固定寬度。
- 預設縣市可設臺中市；下拉選縣市後同步更新圖、表與主卡。Folium 點位先顯示 popup；如要「點地圖連動選單」，需另處理 `streamlit-folium` 回傳的點擊事件，不能假設原生 Folium 自動連動。
- 預報時間採 `Asia/Taipei`，標示「預報有效期間」與「資料取得時間」。降雨機率是時段的預報值。
- 配色：背景 `#F5F7FB`、卡片 `#FFFFFF`、主藍 `#4A90E2`、文字 `#1E293B`，晴天黃 `#FBBF24`、雨天藍 `#60A5FA`；卡片圓角約 16px。控制 CSS 範圍，避免 Streamlit 升版後選擇器失效。
- 指標卡只顯示有來源的資料；圖表與地圖要有空資料、API 失敗、資料過期的狀態。

## 3. 專案結構

```text
taiwan-weather-dashboard/
├── app.py                    # 單頁 UI：選單、卡片、圖表、地圖
├── config.py                 # 非機密常數、資料集代碼、座標
├── services/
│   ├── cwa_client.py         # requests：呼叫 API、timeout、錯誤處理
│   ├── forecast_parser.py    # JSON → 標準化預報列
│   └── weather_service.py    # 刷新、查詢、資料時間與組裝畫面
├── database/
│   ├── schema.sql            # 建表及索引
│   └── repository.py         # SQLite 寫入及參數化查詢
├── components/
│   ├── charts.py             # Plotly 折線圖
│   └── map_view.py           # Folium Marker／Popup
├── assets/
│   └── style.css             # 輕量化視覺樣式
├── .streamlit/
│   └── config.toml           # Streamlit 主題；不要放 API Key
├── scripts/
│   └── fetch_once.py         # 手動抓取並寫入資料庫
├── tests/
│   └── fixtures/             # 移除金鑰的 JSON 範例
├── .env.example              # CWA_API_KEY=請填自己的金鑰
├── .gitignore
├── requirements.txt
└── README.md
```

由 `app.py` 先呼叫 service，service 再使用 client、parser 與 repository；UI 不直接解析原始 JSON 或組 SQL。`database/weather.db` 是執行後產生的本機檔案，放入 `.gitignore`，不要提交 GitHub。

## 4. 安裝與啟動

建議 Python 3.11 或 3.12、Git、編輯器（例如 VS Code）、瀏覽器。SQLite 由 Python 標準函式庫 `sqlite3` 提供，**不用另裝 SQLite Python 套件**；若想手動看資料，可選裝 DB Browser for SQLite。

```bash
mkdir taiwan-weather-dashboard
cd taiwan-weather-dashboard
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install requests pandas streamlit plotly folium streamlit-folium python-dotenv
```

macOS／Linux：

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install requests pandas streamlit plotly folium streamlit-folium python-dotenv
```

將直接依賴列入 `requirements.txt`（成功執行後可依環境鎖定版本）：

```text
requests
pandas
streamlit
plotly
folium
streamlit-folium
python-dotenv
```

| 套件／模組 | 用途 | 必要性 |
| --- | --- | --- |
| `requests` | 向 CWA 取 JSON | 必要 |
| `pandas` | 標準化表格與查詢結果 | 必要（對應課堂） |
| `streamlit` | Web 畫面及互動 | 必要 |
| `plotly` | 可滑鼠查看的趨勢圖 | 建議 |
| `folium`、`streamlit-folium` | 互動地圖及放入 Streamlit | 地圖階段必要 |
| `python-dotenv` | 本機讀取 `.env` 中的 Key | 建議 |
| 標準模組 `sqlite3`、`json`、`datetime`、`zoneinfo` | 資料庫與時間處理 | Python 內建 |

於中央氣象署[開放資料平台](https://opendata.cwa.gov.tw/)註冊並取得授權碼，在專案根目錄新增 `.env`：

```text
CWA_API_KEY=你的授權碼
```

`.gitignore` 至少加入 `.env`、`.venv/`、`__pycache__/`、`*.db`。部署時將授權碼設在部署平台的 Secrets，不要寫在程式、README、GitHub 或畫面中。

跑完程式後啟動：

```bash
python -m streamlit run app.py
```

## 5. 分階段實作（每一階段的完成標準）

### 階段 A｜確定資料與 API

1. 先選 `F-C0032-001` 作第一版。到[資料集頁](https://opendata.cwa.gov.tw/dataset/forecast/F-C0032-001)確認欄位與時間粒度。
2. 在 `cwa_client.py` 用 `requests.get` 呼叫 `https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001`，以 `params={"Authorization": api_key, "format": "JSON"}` 帶入參數，設 `timeout`，檢查 HTTP 狀態和回傳是否成功。官方[開發指南](https://opendata.cwa.gov.tw/devManual/insrtuction)有 API 路徑與參數範例。
3. 將一份去除敏感資訊的回傳 JSON 存作 fixture，觀察 `records`、`location`、`weatherElement`、`time` 的實際階層；**先看真實 JSON 再寫 parser**。
4. 完成標準：可列印縣市名稱與每段有效起訖時間；API 壞掉時呈現可理解的錯誤。

### 階段 B｜解析與資料庫

1. 把每個縣市、每個時段的 `Wx`、`MinT`、`MaxT`、`PoP`、`CI` 合成一筆；以有效時間對齊元素，解析數字、缺值與時間，不靠陣列索引假設所有欄位必定等長。
2. 用 Pandas 檢查列數、唯一縣市數、缺值和 `min_temp <= max_temp`，顯示一小段資料表。
3. 建 SQLite 資料表及索引，存入每次抓取時間 `fetched_at`（台灣時區）與預報有效期間。建議至少設 `forecast_runs(id, dataset_id, fetched_at)`、`forecast_periods(run_id, location, start_time, end_time, wx, min_temp, max_temp, pop, comfort)`；預報列用 `(run_id, location, start_time, end_time)` 唯一鍵避免同次重複。
4. `repository.py` 用 `?` 參數化查詢和 transaction；抓取失敗不可產生空的成功批次。查最新預報時先挑一個成功的 `run_id`，再依縣市及開始時間查詢，不要混合不同批次。
5. 完成標準：同次資料重跑不重複、SQL 能查某縣市依時間排序的 MinT／MaxT、關閉 API 仍能讀上次成功的資料。

### 階段 C｜先完成符合老師要求的 Web App

1. `app.py` 設頁面標題、縣市下拉選單與最新抓取時間。
2. 用 SQL 從 SQLite 讀所選縣市資料，顯示表格與 Plotly 雙折線圖（最高與最低溫）；X 軸是預報有效時段，不是抓取日期。
3. 加「更新資料」按鈕；用 Streamlit 快取減少重跑，不在每次 widget 變動都呼叫 CWA。按鈕刷新資料庫後清除相關快取。
4. 完成標準：換縣市時圖表和表格同步；沒有網路時顯示最後成功資料及其時間。

### 階段 D｜地圖與設計

1. `config.py` 定義縣市代表點座標，`map_view.py` 以 Folium 呈現各縣市 Marker；顏色說明需固定且顯示圖例。
2. Marker popup 放縣市、**該時段預報**最高／最低溫與降雨機率；篩選時段時所有點使用同一有效時間，不混用不同時段。
3. `streamlit-folium` 內嵌地圖。若要點 Marker 更新選取縣市，先驗證點擊事件的回傳值，再用 `st.session_state` 實作；否則以 popup + 下拉選單完成基本互動。
4. 主卡、四張指標卡、地圖、預報時段卡與折線圖依序加入。先用 Streamlit columns/container/theme，再少量 CSS 修飾。檢查 1366px 桌面和手機窄畫面不重疊、字體能讀。
5. 完成標準：單頁可展示全台概況，也能查看某縣市的圖、表與地圖資訊。

### 階段 E｜加分功能及交付

1. 若想做一週卡，另接 CWA 一週預報資料集，確認它與 36 小時資料格式不同時，寫**獨立 parser 和資料表**；不要把不同時間粒度直接 join 成同一列。
2. 若想做目前天氣卡與歷史觀測，另接觀測資料；每筆保存測站 ID、座標、觀測時間與抓取時間。歷次預報快照可展示「同一預報時段的版本變化」，不得稱為實測溫度歷史。
3. 排行榜須限定同一批次與同一預報時段，再依最高溫或降雨機率排序，避免比較不同時間的數值。
4. 驗收：空值、離島、API 逾時、無金鑰、時區、長地名、手機版、圖表單位及資料來源說明。
5. README 寫專案功能、環境建置、金鑰設定、執行指令、資料集來源、功能截圖和已知限制；再 `git init`、提交程式與 README、推到 GitHub，確認 `.env` 和 `.db` 沒被提交。

## 6. 建議進度與驗收清單

| 里程碑 | 交付成果 | 預估投入（供排程，不是保證） |
| --- | --- | --- |
| 1 | Key、成功 API 請求、原始 JSON 結構筆記 | 2–4 小時 |
| 2 | Parser、Pandas 表、SQLite 建表與 SQL 查詢 | 4–7 小時 |
| 3 | Streamlit 選單、折線圖、資料表 | 3–5 小時 |
| 4 | Folium 地圖、卡片與手機排版 | 5–9 小時 |
| 5 | 空值／失敗狀態、README、截圖與 GitHub | 3–5 小時 |

**最小可交版本**：一個有效 API Key、22 縣市 36 小時資料、能查 SQLite、縣市切換、最高／最低溫圖與表、可用地圖、資料時間與 README。若時間不足，先不做一週預報、實測觀測與歷史曲線。

## 7. 參考來源

- 老師提供的「AI 創新微課程 Taiwan Weather Forecast」24 步圖片（本計畫依其流程整理）。
- [中央氣象署 36 小時資料集 F-C0032-001](https://opendata.cwa.gov.tw/dataset/forecast/F-C0032-001)
- [中央氣象署一週預報資料集 F-D0047-091](https://opendata.cwa.gov.tw/dataset/forecast/F-D0047-091)
- [中央氣象署 API 使用說明](https://opendata.cwa.gov.tw/devManual/insrtuction)
- [Streamlit 安裝說明](https://docs.streamlit.io/get-started/installation)與[Plotly 圖表說明](https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart)
- [AirBox](https://airbox.edimaxcloud.com/)：僅參考地圖探索的資訊架構，版面與品牌視覺自行設計。
