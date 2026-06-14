# 血壓提醒 LINE Bot — 設計文件

日期：2026-06-14
狀態：已確認，進入實作

## 目標

在現有 LINE Bot（FastAPI + Google ADK/Gemini，部署於 GCP Cloud Run）基底上，打造提醒長輩量血壓的功能：

1. 每天早上 11:00 推播個人訊息提醒長輩量血壓；若當日已輸入資料則跳過。
2. 血壓可用聊天文字輸入，或直接拍血壓計照片由 Bot 辨識。
3. 若當日未量測，於 14:00 主動通知綁定的親屬「長輩今天還沒量血壓」。
4. 每次輸入血壓即自動給予分級建議；過高時提醒長輩小心行動。

## 已確認的關鍵決策

| 主題 | 決定 |
|------|------|
| 使用者範圍 | 多家庭，需註冊綁定流程 |
| 資料儲存 | Firestore |
| 通知時間 | 早上 11:00 提醒長輩；14:00 單次判定未量則通知親屬 |
| 綁定流程 | 親屬產生配對碼、長輩輸入 |
| 血壓建議 | 規則分級 + LLM 潤飾 |
| 時區 | Asia/Taipei |
| 配對碼 | 6 位數，30 分鐘失效 |

## 架構

Webhook 進來後先經過「指令路由器」處理明確意圖（註冊綁定、血壓文字、血壓圖片），
無法判定的文字才 fall through 給原本的 Gemini 對話 agent。排程用 Cloud Scheduler
定時打受保護的 task endpoint。資料全部走 Firestore。

模組（小而專一，各自可獨立測試）：

```
main.py             FastAPI：webhook + task endpoints + 組裝
firestore_store.py  Firestore 資料存取（users/families/pairing/records）
registration.py     配對碼產生與綁定邏輯
bp_parser.py        文字血壓解析
bp_image.py         Gemini 圖片 OCR
bp_advice.py        規則分級 + LLM 潤飾
line_messaging.py   push/reply 輔助
multi_tool_agent/agent.py  對話 agent（改成血壓查詢工具）
tests/              pytest，mock Firestore/LINE/Gemini
```

## 資料模型（Firestore）

```
users/{lineUserId}
  role: "elder" | "relative"
  displayName: str
  familyId: str | null
  createdAt

families/{familyId}
  elderId: str | null
  relativeIds: [str]
  createdAt

pairingCodes/{code}     # 6 位數，親屬產生
  relativeId: str
  expiresAt
  used: bool

records/{recordId}      # 一筆血壓量測
  familyId, elderId
  date: "YYYY-MM-DD"    # Asia/Taipei
  systolic, diastolic, pulse
  category: str
  source: "text" | "image"
  createdAt
```

「今天是否已量」= 查 records 中該 elder + 今日 date 是否存在。

## 訊息路由

依序判斷：

1. **註冊/綁定指令**（文字）
   - 「我是親屬」/「成為照護者」→ 建立 relative、產生 6 位數配對碼回傳
   - 「我是長輩」→ 標記為 elder，提示輸入配對碼
   - 6 位數碼 → 驗證、把長輩與親屬綁進同一個 family
2. **血壓文字輸入** — 正則解析 `120/80`、`120 80 70`、「收縮壓120 舒張壓80 脈搏70」；成功則存檔 + 回建議
3. **圖片訊息** — 下載圖片 → Gemini OCR 讀收縮壓/舒張壓/脈搏 → 存檔 + 回建議；讀不到請重拍或改文字
4. **其他文字** — fall through 給 Gemini 對話 agent（血壓查詢工具，如「查我這週血壓」）

## 排程（Cloud Scheduler → 受保護 endpoint）

用共享密鑰 header `X-Tasks-Token`（存 Secret Manager）驗證：

- `POST /tasks/morning-reminder`（每日 11:00）：對每位 elder，若今日尚無紀錄則推播提醒；已量跳過。
- `POST /tasks/escalation-check`（每日 14:00）：對每位 elder，若今日仍無紀錄，推播通知其綁定的所有親屬。

## 血壓分級 + 建議

規則先分級（居家量測常見標準），再由 Gemini 用溫暖口吻潤飾：

| 分級 | 收縮壓 | | 舒張壓 |
|------|--------|---|--------|
| 正常 | <120 | 且 | <80 |
| 偏高 Elevated | 120–129 | 且 | <80 |
| 高血壓一期 | 130–139 | 或 | 80–89 |
| 高血壓二期 | ≥140 | 或 | ≥90 |
| 高血壓危象 | ≥180 | 或 | ≥120 |

「高血壓危象」觸發明確警告：請長輩立即休息、勿激烈活動、必要時就醫，並通知親屬。

## 錯誤處理

- Firestore/LINE/Gemini 呼叫失敗 → log 並回友善訊息，不讓 webhook 噴 500。
- 圖片 OCR 失敗 → 請使用者重拍或改文字輸入。
- 血壓數值超出合理範圍（如收縮壓 < 50 或 > 300）→ 視為解析失敗，請重新確認。
- task endpoint 缺/錯 token → 回 401。

## 測試

pytest，mock 掉 Firestore、LINE、Gemini 外部相依：

- bp_parser：各種文字格式、邊界值、非血壓文字
- bp_advice：每個分級邊界、危象觸發
- registration：產碼、綁定、過期碼、重複用碼
- firestore_store：用 fake/in-memory client
- 路由與 task endpoint：用 FastAPI TestClient + mock

## 部署

- 新增相依 `google-cloud-firestore`。
- 沿用 Dockerfile + Cloud Run。
- 新增 Secret `TasksToken`、Cloud Scheduler 兩個 job（11:00、14:00 Asia/Taipei）。
- Cloud Run 服務帳號需 Firestore 存取權限。
