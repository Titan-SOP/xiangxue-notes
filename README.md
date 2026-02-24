# 🏮 人相學書稿工作室 v2

> 郭證銂師資班筆記整理系統 — Streamlit + Supabase

## 功能

| 功能 | 說明 |
|------|------|
| 📂 動態偵測章節 | 上傳PDF自動找到所有章節，不需手動設定 |
| 🖼️ 圖片提取 | 自動提取PDF內嵌圖片（PyMuPDF） |
| ☁️ 雲端儲存 | 文字、圖片、進度全部存Supabase，手機也能查看 |
| ✏️ 補充筆記 | 新課程筆記附加到對應章節，自動加日期 |
| 📤 匯出書稿 | 一鍵下載完整Markdown書稿 |

---

## 設定步驟（約20分鐘）

### 第一步：建立 Supabase 資料庫（免費）

1. 前往 [supabase.com](https://supabase.com) 註冊
2. 點 **New Project**，填入名稱（如 `xiangxue`）與密碼
3. 等待建立完成（約1分鐘）
4. 進入專案後，點左側 **SQL Editor**
5. 把 `supabase_init.sql` 的內容全部貼上，點 **Run**
6. 左側點 **Settings > API**，複製：
   - `Project URL`（格式：`https://xxx.supabase.co`）
   - `anon public` key

### 第二步：設定 Secrets

複製 `.streamlit/secrets.toml.example`，另存為 `.streamlit/secrets.toml`：

```toml
SUPABASE_URL = "https://你的專案ID.supabase.co"
SUPABASE_KEY = "你的anon public key"
```

### 第三步：本地測試

```bash
pip install -r requirements.txt
streamlit run app.py
```

### 第四步：上傳 GitHub

```bash
git init
git add .
git commit -m "初始版本"
git remote add origin https://github.com/你的帳號/xiangxue-notes.git
git push -u origin main
```

### 第五步：部署到 Streamlit Cloud（免費）

1. 前往 [share.streamlit.io](https://share.streamlit.io)
2. 連接 GitHub，選擇此 repo，主檔案為 `app.py`
3. 點 **Advanced Settings > Secrets**，貼上 secrets.toml 內容
4. 點 **Deploy**，約2分鐘上線

---

## 技術架構

```
上傳PDF
  ↓ PyMuPDF
  ├─ 自動偵測章節標題
  ├─ 提取各章文字
  └─ 提取各章圖片（base64）
        ↓ Supabase
        ├─ chapters 表（章節基本資料）
        ├─ chapter_content 表（文字）
        └─ chapter_images 表（圖片）
              ↓ Streamlit
              └─ 顯示、整理、匯出
```

## 日常使用流程

1. **每次上課後** → 上傳新版PDF → 系統自動更新各章內容
2. **整理筆記** → 到「章節整理」頁更新狀態和完成度
3. **補充內容** → 到「補充筆記」頁貼新的課堂筆記
4. **匯出書稿** → 到「匯出書稿」頁下載完整Markdown

## 注意事項

- PDF圖片若超過5MB，Supabase free tier可能有限制，建議壓縮PDF後再上傳
- `secrets.toml` 已在 `.gitignore` 排除，不會上傳到GitHub
- 每次上傳新版PDF會覆蓋舊的文字和圖片，但補充筆記和狀態不會消失
