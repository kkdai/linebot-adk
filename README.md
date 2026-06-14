# 血壓提醒 LINE Bot（Blood Pressure Reminder）

提醒長輩每天量血壓的 LINE Bot，基於 FastAPI + Google ADK/Gemini，部署於 GCP Cloud Run，資料存於 Firestore。

## 功能

1. **每日提醒**：每天早上 11:00（Asia/Taipei）提醒長輩量血壓；若當日已輸入則跳過。
2. **血壓輸入**：可用文字（例如 `120/80`、`收縮壓120 舒張壓80 脈搏70`）或直接拍血壓計照片，由 Gemini 辨識數字。
3. **未量測通知**：每天 14:00 檢查，若長輩當日仍無紀錄，主動通知綁定的家屬。
4. **自動建議**：每次輸入血壓會依規則分級（正常／偏高／一期／二期／危象）並由 Gemini 用溫暖口吻給建議；達高血壓危象會提醒立即休息並就醫。
5. **家庭綁定**：家屬輸入「我是親屬」取得 6 位數配對碼，長輩輸入該碼即完成綁定（一位長輩可對應多位家屬）。
6. **查詢紀錄**：輸入「查血壓」查看最近 7 天紀錄。

## 使用方式（LINE 對話）

| 角色 | 指令 | 說明 |
|------|------|------|
| 家屬 | `我是親屬` | 取得 6 位數配對碼（30 分鐘有效） |
| 長輩 | `我是長輩` | 標記為長輩並提示輸入配對碼 |
| 長輩 | `123456` | 輸入家屬給的配對碼完成綁定 |
| 長輩 | `120/80` 或傳照片 | 記錄血壓並取得建議 |
| 任一 | `查血壓` | 查看最近紀錄 |
| 任一 | `說明` | 顯示使用說明 |

## 架構

```
main.py             FastAPI：webhook + 排程 endpoint + 組裝
router.py           訊息路由（註冊綁定／血壓文字／查詢／對話 fallthrough）
firestore_store.py  Firestore 資料存取
registration.py     配對碼產生與綁定
bp_parser.py        文字血壓解析
bp_image.py         Gemini 圖片 OCR
bp_advice.py        規則分級 + LLM 潤飾
tasks.py            每日提醒／未量測通知邏輯
tests/              pytest（mock Firestore/LINE/Gemini）
```

設計文件：`docs/superpowers/specs/2026-06-14-blood-pressure-reminder-design.md`

## 環境變數

| 變數 | 說明 |
|------|------|
| `ChannelSecret` | LINE channel secret |
| `ChannelAccessToken` | LINE channel access token |
| `GOOGLE_API_KEY` | Gemini API key（或改用 Vertex，見下） |
| `TasksToken` | 保護排程 endpoint 的共享密鑰 |
| `GOOGLE_GENAI_USE_VERTEXAI` | 設為 `True` 改用 Vertex AI（需 `GOOGLE_CLOUD_PROJECT`、`GOOGLE_CLOUD_LOCATION`） |

## 本機測試

```bash
pip install -r requirements.txt
pytest -q
```

## 部署到 Cloud Run

### 1. 啟用 API 與 Firestore

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  firestore.googleapis.com cloudscheduler.googleapis.com secretmanager.googleapis.com

# 建立 Firestore（Native 模式，亞洲區）
gcloud firestore databases create --location=asia-east1
```

### 2. 建立 Secret

```bash
echo -n "YOUR_LINE_SECRET"  | gcloud secrets create line-channel-secret --data-file=-
echo -n "YOUR_LINE_TOKEN"   | gcloud secrets create line-channel-token  --data-file=-
echo -n "YOUR_GEMINI_KEY"   | gcloud secrets create gemini-api-key      --data-file=-
echo -n "$(openssl rand -hex 16)" | gcloud secrets create tasks-token   --data-file=-
```

### 3. 建置與部署

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/linebot-bp

gcloud run deploy linebot-bp \
  --image gcr.io/YOUR_PROJECT_ID/linebot-bp \
  --platform managed --region asia-east1 --allow-unauthenticated \
  --update-secrets=ChannelSecret=line-channel-secret:latest,ChannelAccessToken=line-channel-token:latest,GOOGLE_API_KEY=gemini-api-key:latest,TasksToken=tasks-token:latest
```

Cloud Run 的服務帳號需有 Firestore 權限：

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member=serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --role=roles/datastore.user
```

取得服務網址並設為 LINE webhook（指向 `/`）：

```bash
gcloud run services describe linebot-bp --region asia-east1 --format 'value(status.url)'
```

### 4. 建立 Cloud Scheduler 排程

把 `SERVICE_URL` 換成上一步的網址，`TASKS_TOKEN` 換成你存進 secret 的值：

```bash
# 每天 11:00 提醒長輩
gcloud scheduler jobs create http bp-morning-reminder \
  --schedule="0 11 * * *" --time-zone="Asia/Taipei" \
  --uri="SERVICE_URL/tasks/morning-reminder" --http-method=POST \
  --headers="X-Tasks-Token=TASKS_TOKEN" --location=asia-east1

# 每天 14:00 檢查未量測並通知家屬
gcloud scheduler jobs create http bp-escalation-check \
  --schedule="0 14 * * *" --time-zone="Asia/Taipei" \
  --uri="SERVICE_URL/tasks/escalation-check" --http-method=POST \
  --headers="X-Tasks-Token=TASKS_TOKEN" --location=asia-east1
```

## 健康檢查

`GET /healthz` 回傳 `{"status":"ok"}`。

## 注意事項

血壓分級與建議僅供一般健康參考，不構成醫療診斷；如有不適請就醫。
