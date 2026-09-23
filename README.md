# 台灣天氣預報儀表板

以中央氣象署（CWA）預報及測站觀測資料建立的單頁天氣儀表板。專案串接 **CWA API → JSON → Python / Pandas → SQLite / SQL → Streamlit**，並以 Folium 顯示全台縣市代表點。

## 功能

- 取得 22 縣市的 `Wx`、`MinT`、`MaxT`、`PoP`、`CI` 預報。
- 依預報有效時間區間對齊欄位，資料以台灣時區儲存。
- 使用 Pandas 做基本欄位與溫度範圍檢查。
- 每次成功更新建立一個 SQLite 預報批次；失敗時保留最近成功批次。
- 切換縣市查看主卡、時段卡、最高／最低溫圖、降雨機率圖與 SQL 查詢表格。
- Folium 地圖顯示同一預報時段的縣市代表點及最高溫圖例。
- 獨立儲存 F-D0047-091 逐 12 小時的一週預報，不與 36 小時資料混合。
- 顯示同縣市測站的整點實測氣溫、相對濕度、風速與觀測時間。
- 依相同資料批次和有效時段列出最高溫與降雨機率排行。
- 比較同一預報有效時段的歷次預報快照，辨識預報版本修訂。
- 提供手動更新按鈕與命令列單次抓取腳本。
- 可展開查看最近成功儲存的預報批次。

目前版本呈現的是**預報**，沒有把預報數值當作測站實測；地圖標記是縣市代表點，不是測站位置。預報快照只供查看歷次批次，沒有將其描述為歷史實測天氣。

## 環境需求

- Python 3.11 或 3.12
- 中央氣象署開放資料平台帳號與 API 授權碼

SQLite 使用 Python 內建的 `sqlite3`，不用另外安裝 SQLite Python 套件。

## 安裝

在專案根目錄執行：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

若 PowerShell 阻擋虛擬環境啟用，可在目前終端機使用：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

## 設定 API Key

1. 到[中央氣象署開放資料平台](https://opendata.cwa.gov.tw/)註冊並取得授權碼。
2. 將 `.env.example` 複製為 `.env`。
3. 在 `.env` 設定 `CWA_API_KEY=你的授權碼`。

`.env` 已列入 `.gitignore`。不要把授權碼貼到程式、README、GitHub 或畫面中。

### 部署到 Streamlit Community Cloud

在 `share.streamlit.io` 的 App 設定中開啟 **Secrets**，貼上 TOML 格式（請換成自己的授權碼）：

```toml
CWA_API_KEY = "你的中央氣象署授權碼"
```

若 App 已建立，從工作區 App 的選單進入 **Settings → Secrets**；儲存後重新啟動 App。Key 名稱需為根層的 `CWA_API_KEY`，不要使用 `.env` 的未加引號格式。程式也接受分組寫法 `[cwa]` 下的 `api_key`。本機仍可沿用 `.env`，也可在未提交的 `.streamlit/secrets.toml` 使用相同 TOML 格式。

## 執行

啟動儀表板：

```powershell
python -m streamlit run app.py
```

在側欄按「更新所有資料」後，各資料集的成功批次會分別寫入 `database/weather.db`；單一資料集失敗時，其他成功批次仍會保留。也可以從專案根目錄單次更新 36 小時預報：

```powershell
python scripts/fetch_once.py
```

補抓三種資料集可加 `--all`：

```powershell
python scripts/fetch_once.py --all
```

第一次啟動會自動建立資料庫和資料表。沒有 API Key 時，畫面仍會啟動並提示設定方式；若資料庫已有成功資料，API 暫時失敗時仍可查看最後一次儲存的預報。

## 專案結構

```text
app.py
config.py
services/
  cwa_client.py
  forecast_parser.py
  weekly_forecast_parser.py
  observation_parser.py
  parse_utils.py
  weather_service.py
database/
  schema.sql
  repository.py
components/
  charts.py
  map_view.py
assets/style.css
.streamlit/config.toml
scripts/fetch_once.py
tests/fixtures/sample_forecast.json
```

## 資料與來源

- 資料集：[一般天氣預報－今明 36 小時天氣預報 F-C0032-001](https://opendata.cwa.gov.tw/dataset/forecast/F-C0032-001)
- 一週預報：[臺灣各縣市鄉鎮未來 1 週逐 12 小時天氣預報 F-D0047-091](https://opendata.cwa.gov.tw/dataset/forecast/F-D0047-091)
- 測站觀測：[氣象觀測站－全測站逐時氣象資料 O-A0001-001](https://opendata.cwa.gov.tw/dataset/statisticDays/O-A0001-001)
- API 使用方式：[中央氣象署開發指南](https://opendata.cwa.gov.tw/devManual/insrtuction)
- 儀表板僅在使用者按下更新時呼叫三個資料集 API；切換縣市和圖表不會重新抓取。
- 天氣指標：`Wx` 天氣現象、`MinT` 最低溫、`MaxT` 最高溫、`PoP` 降雨機率、`CI` 舒適度。

`tests/fixtures/sample_forecast.json` 是用來說明 JSON 欄位階層的示意資料，不含 API Key，也不是即時資料集回應。

## 資料庫結構

- `forecast_runs` 保存資料集代碼、抓取時間、來源發布時間及批次列數。
- `forecast_periods` 保存縣市與預報有效區間的指標，以 `run_id + location + start_time + end_time` 唯一識別。
- `weekly_forecast_runs` / `weekly_forecast_periods` 獨立保存逐 12 小時的一週預報。
- `observation_runs` / `station_observations` 保存測站 ID、座標、觀測時間和實測氣象值。
- 每次成功抓取在單一 SQLite transaction 中寫入；空批次不會成為成功批次。
- `database/weather.db` 是本機執行後產生的資料檔，已排除於 Git。

## 已知限制

- 一週預報以 F-D0047-091 每 12 小時區間獨立呈現，不與 36 小時預報直接合併。
- 測站觀測以 O-A0001-001 整點資料顯示站名和實際觀測時間；同縣市沒有有效讀值時會提示暫無資料。
- 預報版本比較需要在同一有效時段仍存在時再次抓取；快照不代表歷史實測。
- 地圖使用人工整理的縣市代表座標，Popup 提供該縣市同一有效時段的預報。
- 地圖點擊不會切換縣市；請用縣市下拉選單切換圖表與資料表。
- 真正的資料更新需要有效 CWA API Key 和網路連線。
