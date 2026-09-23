# 台灣天氣預報儀表板

以中央氣象署（CWA）今明 36 小時預報資料建立的單頁天氣儀表板。專案串接 **CWA API → JSON → Python / Pandas → SQLite / SQL → Streamlit**，並以 Folium 顯示全台縣市代表點。

## 功能

- 取得 22 縣市的 `Wx`、`MinT`、`MaxT`、`PoP`、`CI` 預報。
- 依預報有效時間區間對齊欄位，資料以台灣時區儲存。
- 使用 Pandas 做基本欄位與溫度範圍檢查。
- 每次成功更新建立一個 SQLite 預報批次；失敗時保留最近成功批次。
- 切換縣市查看主卡、時段卡、最高／最低溫圖、降雨機率圖與 SQL 查詢表格。
- Folium 地圖顯示同一預報時段的縣市代表點及最高溫圖例。
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

`.env` 已列入 `.gitignore`。不要把授權碼貼到程式、README、GitHub 或畫面中。部署時請使用部署平台的 Secrets。

## 執行

啟動儀表板：

```powershell
python -m streamlit run app.py
```

在側欄按「更新預報資料」後，成功批次會寫入 `database/weather.db`。也可以從專案根目錄單次更新：

```powershell
python scripts/fetch_once.py
```

第一次啟動會自動建立資料庫和資料表。沒有 API Key 時，畫面仍會啟動並提示設定方式；若資料庫已有成功資料，API 暫時失敗時仍可查看最後一次儲存的預報。

## 專案結構

```text
app.py
config.py
services/
  cwa_client.py
  forecast_parser.py
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
- API 使用方式：[中央氣象署開發指南](https://opendata.cwa.gov.tw/devManual/insrtuction)
- 更新頻率：資料集頁面標示每 6 小時更新；儀表板僅在使用者按下更新時呼叫 API。
- 天氣指標：`Wx` 天氣現象、`MinT` 最低溫、`MaxT` 最高溫、`PoP` 降雨機率、`CI` 舒適度。

`tests/fixtures/sample_forecast.json` 是用來說明 JSON 欄位階層的示意資料，不含 API Key，也不是即時資料集回應。

## 資料庫結構

- `forecast_runs` 保存資料集代碼、抓取時間、來源發布時間及批次列數。
- `forecast_periods` 保存縣市與預報有效區間的指標，以 `run_id + location + start_time + end_time` 唯一識別。
- 每次成功抓取在單一 SQLite transaction 中寫入；空批次不會成為成功批次。
- `database/weather.db` 是本機執行後產生的資料檔，已排除於 Git。

## 已知限制

- 首版只接今明 36 小時預報；沒有提供一週預報或即時測站觀測。
- 地圖使用人工整理的縣市代表座標，Popup 提供該縣市同一有效時段的預報。
- 地圖點擊不會切換縣市；請用縣市下拉選單切換圖表與資料表。
- 真正的資料更新需要有效 CWA API Key 和網路連線。
