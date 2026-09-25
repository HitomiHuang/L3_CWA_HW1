# 台灣天氣觀測地圖

這個專案有兩個入口，共用同一份中央氣象署資料：

- **Vercel 網站**：public/ 的純前端全版面地圖，讀取公開的 public/data/snapshot.json，沒有網站後端或 API Key。
- **課程資料流程**：Python 定時讀取 CWA API，解析 JSON，存入 SQLite，再匯出網站快照；app.py 另外提供 Streamlit / Pandas / Folium / SQL 展示。

資料流程：**CWA API → Python 爬蟲 → SQLite 批次與執行紀錄 → JSON 快照 → Vercel 靜態網站**。

## 網站功能

- 預設顯示**最新測站氣溫**。全台視角為各縣市有效測站的算術平均；放大地圖顯示測站實際位置與個別讀值。
- 切換測站**相對濕度、平均風速**，以及縣市**預報最高溫、降雨機率**五種圖層。
- 搜尋縣市或測站，點選地圖或縣市清單查看觀測時間、站名、濕度、風速、36 小時預報、一週預報與趨勢圖。
- 預報時段切換、全台定位、目前圖層 CSV 下載、來源與爬蟲紀錄查詢。
- 深色全版面地圖、淺色左右資料面板與手機版選單。
- 明確標示抓取時間；網站「重讀」只會重新載入已發布的 JSON，不能觸發雲端爬蟲。

測站觀測是實際量測；預報圖層使用縣市代表座標。縣市測站平均是此專案計算的摘要，不是中央氣象署發布的縣市官方氣溫。

## 本機抓取與預覽

需要 Python 3.11 以上和[中央氣象署開放資料平台](https://opendata.cwa.gov.tw/)授權碼。把 .env.example 複製為 .env，填入：

~~~text
CWA_API_KEY=你的授權碼
~~~

.env 已排除於 Git。從專案根目錄執行：

~~~powershell
python scripts/fetch_once.py --all
python scripts/dev_server.py
~~~

開啟 http://127.0.0.1:8765/。第一次抓取會建立 database/weather.db 與 public/data/snapshot.json。如果只需從現有 SQLite 重新產生網站快照，可執行 python scripts/fetch_once.py --export-only。

爬蟲只使用 Python 標準函式庫。它分別抓取 36 小時預報 F-C0032-001、一週預報 F-D0047-091 與測站觀測 O-A0001-001；每個資料集在 crawl_runs 留下成功或失敗、筆數及時間。成功批次完整寫入 SQLite；失敗不會覆蓋最近成功資料。

## 定時更新與 Vercel 部署

1. 將專案推送至 GitHub，在儲存庫 **Settings → Secrets and variables → Actions** 建立 CWA_API_KEY Repository secret。
2. 匯入同一個儲存庫到 Vercel；Framework Preset 選 **Other**，Root Directory 用專案根目錄。vercel.json 已設定 public 為輸出目錄。**Vercel 不需要 CWA_API_KEY**。
3. .github/workflows/refresh-weather.yml 每 6 小時執行一次，也可在 GitHub Actions 頁面手動執行。它抓取 CWA API，將 SQLite 資料庫與 JSON 快照提交回儲存庫。新提交由 Vercel 的 Git 整合重新部署。

GitHub Actions 排程可能延遲，或因儲存庫設定、分支保護、缺少 Secret 而失敗。網站會顯示最後一次成功發布的快照與時間；Vercel 靜態頁本身不會直接更新資料。若先只需展示網站，儲存庫內已包含一份可顯示的 public/data/snapshot.json。

database/weather.db 平常受 .gitignore 保護，不會因本機執行而意外加入提交；排程工作明確用 git add -f 保存資料庫。請不要把 .env 或 API Key 加入版本控制。

## Streamlit 課程展示

~~~powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
~~~

Streamlit 版保留 Pandas 表格、SQL 查詢、Folium 地圖、溫度與降雨趨勢、歷次預報版本比較，也能按鈕更新三種資料集。畫面中的「爬蟲執行紀錄（SQLite）」可檢查抓取結果。更新完成時同樣匯出 Vercel 使用的 JSON。

SQLite 資料表：

- crawl_runs：每次 API 抓取的資料集、開始／結束時間、成功或失敗、筆數及錯誤。
- forecast_runs / forecast_periods：36 小時預報批次和縣市時段。
- weekly_forecast_runs / weekly_forecast_periods：逐 12 小時的一週預報。
- observation_runs / station_observations：測站座標、觀測時間、實測值。

## 驗證

~~~powershell
python -m unittest discover -s tests -v
node --check public/app.js
~~~

測試使用離線範例，確認成功與失敗抓取會留下紀錄，JSON 包含最新資料且不含 API Key。

## 資料來源

- [中央氣象署開放資料平台](https://opendata.cwa.gov.tw/)
- [今明 36 小時天氣預報 F-C0032-001](https://opendata.cwa.gov.tw/dataset/forecast/F-C0032-001)
- [一週預報 F-D0047-091](https://opendata.cwa.gov.tw/dataset/forecast/F-D0047-091)
- [全測站逐時氣象資料 O-A0001-001](https://opendata.cwa.gov.tw/dataset/statisticDays/O-A0001-001)

底圖由 OpenStreetMap 提供，並在前端轉為深色樣式；網路無法載入地圖圖磚時，側邊縣市資料仍可查閱。
