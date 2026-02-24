-- ============================================================
-- 人相學書稿工作室 — Supabase 資料庫初始化
-- 在 Supabase > SQL Editor 執行此檔案
-- ============================================================

-- 1. 章節基本資料表
CREATE TABLE IF NOT EXISTS chapters (
    id            BIGSERIAL PRIMARY KEY,
    num           TEXT NOT NULL,          -- 章節編號（一、二、三...）
    name          TEXT NOT NULL,          -- 章節名稱（形局、聲相...）
    start_page    INTEGER,                -- PDF起始頁
    end_page      INTEGER,                -- PDF結束頁
    status        TEXT DEFAULT '待整理',  -- 待整理/整理中/初稿完成/修訂中/定稿
    completeness  INTEGER DEFAULT 0,      -- 完成度 0-100
    notes         TEXT DEFAULT '',        -- 備忘錄（不進書稿）
    extra_notes   TEXT DEFAULT '',        -- 補充課堂筆記（進書稿）
    last_edit     TEXT DEFAULT '',        -- 最後編輯日期
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (num, name)                    -- 同章節編號+名稱不重複
);

-- 2. 章節文字內容表
CREATE TABLE IF NOT EXISTS chapter_content (
    id            BIGSERIAL PRIMARY KEY,
    chapter_num   TEXT NOT NULL,
    chapter_name  TEXT NOT NULL,
    text_content  TEXT DEFAULT '',        -- 從PDF提取的文字
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (chapter_num, chapter_name)
);

-- 3. 章節圖片表
CREATE TABLE IF NOT EXISTS chapter_images (
    id            BIGSERIAL PRIMARY KEY,
    chapter_num   TEXT NOT NULL,
    chapter_name  TEXT NOT NULL,
    page_num      INTEGER,               -- 來自PDF哪一頁
    img_index     INTEGER,               -- 該頁第幾張圖
    data_b64      TEXT,                  -- base64編碼圖片
    ext           TEXT DEFAULT 'png',    -- 圖片格式
    width         INTEGER,
    height        INTEGER,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 建立索引加速查詢
CREATE INDEX IF NOT EXISTS idx_chapters_num      ON chapters (num);
CREATE INDEX IF NOT EXISTS idx_content_ch        ON chapter_content (chapter_num, chapter_name);
CREATE INDEX IF NOT EXISTS idx_images_ch         ON chapter_images (chapter_num, chapter_name);

-- ============================================================
-- Row Level Security（讓App可讀寫，但外部無法隨意存取）
-- ============================================================
ALTER TABLE chapters        ENABLE ROW LEVEL SECURITY;
ALTER TABLE chapter_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE chapter_images  ENABLE ROW LEVEL SECURITY;

-- 允許 anon key 讀寫（Streamlit App使用）
CREATE POLICY "allow_all_chapters"
    ON chapters FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "allow_all_content"
    ON chapter_content FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "allow_all_images"
    ON chapter_images FOR ALL USING (true) WITH CHECK (true);
