"""
人相學書稿工作室 v2
- 動態偵測章節（不寫死）
- 提取PDF內嵌圖片
- Supabase 雲端儲存（文字、圖片、進度）
"""

import streamlit as st
import fitz  # PyMuPDF
import json
import os
import re
import base64
import datetime
from io import BytesIO
from PIL import Image
from supabase import create_client, Client

# ── 頁面設定 ──────────────────────────────────────────────
st.set_page_config(
    page_title="人相學書稿工作室",
    page_icon="🏮",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;700;900&family=Noto+Sans+TC:wght@300;400;500&display=swap');

html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; }
h1, h2, h3 { font-family: 'Noto Serif TC', serif; }

.title-banner {
    background: linear-gradient(135deg, #8B1A1A 0%, #5C1010 60%, #3A0A0A 100%);
    color: #F5E6C8;
    padding: 1.8rem 2.5rem;
    border-radius: 4px;
    margin-bottom: 1.5rem;
    border-bottom: 4px solid #C9A84C;
}
.title-banner h1 { color: #F5E6C8; font-size: 1.9rem; margin: 0; letter-spacing: 0.12em; }
.title-banner p  { color: #C9A84C; margin: 0.3rem 0 0; font-size: 0.85rem; letter-spacing: 0.06em; }

.chapter-card {
    background: white;
    border-left: 5px solid #8B1A1A;
    border-radius: 0 6px 6px 0;
    padding: 1rem 1.4rem;
    margin-bottom: 0.8rem;
    box-shadow: 2px 2px 8px rgba(0,0,0,0.07);
}
.chapter-card h4 { margin: 0 0 0.25rem 0; color: #3A0A0A; font-family: 'Noto Serif TC', serif; }
.chapter-card p  { margin: 0; color: #7A6A5A; font-size: 0.83rem; }

.status-badge {
    display: inline-block; padding: 2px 10px;
    border-radius: 20px; font-size: 0.76rem; font-weight: 500; margin-left: 8px;
}
.s-待整理  { background:#F0E8D0; color:#8B6A2A; }
.s-整理中  { background:#D0E8F0; color:#2A5A8B; }
.s-初稿完成 { background:#D0F0DC; color:#2A8B4A; }
.s-修訂中  { background:#F0D8C0; color:#8B4A1A; }
.s-定稿   { background:#3A0A0A; color:#F5E6C8; }

.metric-box {
    background: white; border: 1px solid #E0D5C0;
    border-top: 3px solid #C9A84C; border-radius: 4px;
    padding: 1rem; text-align: center;
}
.metric-box .num   { font-size: 2rem; font-weight: 700; color: #8B1A1A; font-family:'Noto Serif TC',serif; }
.metric-box .label { font-size: 0.78rem; color: #7A6A5A; margin-top: 0.2rem; }

.progress-bg   { background:#E0D5C0; border-radius:4px; height:8px; width:100%; margin-top:4px; }
.progress-fill { height:8px; border-radius:4px; background:linear-gradient(90deg,#8B1A1A,#C9A84C); }

.note-block {
    background:#FFFBF0; border:1px solid #E8D8A0; border-radius:4px;
    padding:1rem 1.2rem; font-size:0.87rem; line-height:1.9;
    white-space:pre-wrap; max-height:480px; overflow-y:auto; color:#2C2010;
}
.img-grid { display:flex; flex-wrap:wrap; gap:10px; margin-top:8px; }
.img-grid img { max-height:200px; border-radius:4px; border:1px solid #DDD; }
</style>
""", unsafe_allow_html=True)

# ── Supabase 連線 ─────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

# ── 常數 ─────────────────────────────────────────────────
STATUSES = ['待整理', '整理中', '初稿完成', '修訂中', '定稿']
STATUS_ICON = {'待整理':'⬜', '整理中':'🔄', '初稿完成':'📝', '修訂中':'✏️', '定稿':'✅'}

# 用來自動偵測章節的標題Pattern（可擴充）
CHAPTER_PATTERNS = [
    r'^([一二三四五六七八九十百千萬]+)[、，。\s]?【(.+?)】',
    r'^第([一二三四五六七八九十百千萬\d]+)[章節、][\s　]*(.+)',
    r'^([一二三四五六七八九十百千萬]+)、(.+)',
]

# ── PDF解析核心 ───────────────────────────────────────────
def detect_chapters_from_pdf(doc: fitz.Document) -> list[dict]:
    """
    動態偵測PDF中的章節標題，回傳章節列表。
    每個章節格式：{num, name, start_page, end_page}
    """
    chapters = []
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        text = page.get_text("text")
        first_lines = text.strip().split('\n')[:5]  # 只看前5行
        for line in first_lines:
            line = line.strip()
            for pattern in CHAPTER_PATTERNS:
                m = re.match(pattern, line)
                if m:
                    num = m.group(1).strip()
                    name = m.group(2).strip()
                    # 避免重複偵測同一章節
                    if chapters and chapters[-1]['name'] == name:
                        continue
                    chapters.append({
                        'num': num,
                        'name': name,
                        'start_page': page_idx + 1,
                        'end_page': None,
                    })
                    break

    # 填入 end_page
    for i in range(len(chapters)):
        if i + 1 < len(chapters):
            chapters[i]['end_page'] = chapters[i + 1]['start_page'] - 1
        else:
            chapters[i]['end_page'] = len(doc)

    return chapters


def extract_chapter_text(doc: fitz.Document, start: int, end: int) -> str:
    """提取章節的純文字（含頁碼標記）"""
    lines = []
    for pg in range(start - 1, min(end, len(doc))):
        text = doc[pg].get_text("text").strip()
        if text:
            lines.append(f"【第{pg+1}頁】\n{text}")
    return '\n\n'.join(lines)


def extract_chapter_images(doc: fitz.Document, start: int, end: int) -> list[dict]:
    """
    提取章節內所有嵌入圖片，回傳 base64 列表。
    格式：[{page, index, data_b64, ext}, ...]
    """
    images = []
    for pg in range(start - 1, min(end, len(doc))):
        page = doc[pg]
        img_list = page.get_images(full=True)
        for img_idx, img_info in enumerate(img_list):
            xref = img_info[0]
            try:
                base_img = doc.extract_image(xref)
                img_bytes = base_img["image"]
                ext = base_img["ext"]  # png / jpeg / etc.

                # 用PIL檢查，過濾太小的icon（<50px）
                pil_img = Image.open(BytesIO(img_bytes))
                w, h = pil_img.size
                if w < 50 or h < 50:
                    continue

                b64 = base64.b64encode(img_bytes).decode('utf-8')
                images.append({
                    'page': pg + 1,
                    'index': img_idx,
                    'data_b64': b64,
                    'ext': ext,
                    'width': w,
                    'height': h,
                })
            except Exception:
                continue
    return images


# ── Supabase 資料操作 ─────────────────────────────────────
def db_upsert_chapter(ch: dict):
    """新增或更新章節基本資料"""
    supabase.table("chapters").upsert({
        "num": ch["num"],
        "name": ch["name"],
        "start_page": ch["start_page"],
        "end_page": ch["end_page"],
        "status": ch.get("status", "待整理"),
        "completeness": ch.get("completeness", 0),
        "notes": ch.get("notes", ""),
        "extra_notes": ch.get("extra_notes", ""),
        "last_edit": str(datetime.date.today()),
    }, on_conflict="num,name").execute()


def db_upsert_content(chapter_num: str, chapter_name: str, text: str):
    """儲存章節文字內容"""
    supabase.table("chapter_content").upsert({
        "chapter_num": chapter_num,
        "chapter_name": chapter_name,
        "text_content": text,
        "updated_at": datetime.datetime.utcnow().isoformat(),
    }, on_conflict="chapter_num,chapter_name").execute()


def db_upsert_images(chapter_num: str, chapter_name: str, images: list[dict]):
    """儲存章節圖片（base64存DB，也可改用Storage bucket）"""
    if not images:
        return
    # 先刪舊圖片再重寫（避免重複）
    supabase.table("chapter_images").delete().eq("chapter_num", chapter_num).eq("chapter_name", chapter_name).execute()
    for img in images:
        supabase.table("chapter_images").insert({
            "chapter_num": chapter_num,
            "chapter_name": chapter_name,
            "page_num": img["page"],
            "img_index": img["index"],
            "data_b64": img["data_b64"],
            "ext": img["ext"],
            "width": img["width"],
            "height": img["height"],
        }).execute()


def db_load_chapters() -> list[dict]:
    res = supabase.table("chapters").select("*").order("num").execute()
    return res.data or []


def db_load_content(chapter_num: str, chapter_name: str) -> str:
    res = supabase.table("chapter_content") \
        .select("text_content") \
        .eq("chapter_num", chapter_num) \
        .eq("chapter_name", chapter_name) \
        .execute()
    if res.data:
        return res.data[0]["text_content"]
    return ""


def db_load_images(chapter_num: str, chapter_name: str) -> list[dict]:
    res = supabase.table("chapter_images") \
        .select("*") \
        .eq("chapter_num", chapter_num) \
        .eq("chapter_name", chapter_name) \
        .order("page_num") \
        .execute()
    return res.data or []


def db_update_chapter_status(chapter_num: str, chapter_name: str,
                              status: str, completeness: int,
                              notes: str, extra_notes: str):
    supabase.table("chapters").update({
        "status": status,
        "completeness": completeness,
        "notes": notes,
        "extra_notes": extra_notes,
        "last_edit": str(datetime.date.today()),
    }).eq("num", chapter_num).eq("name", chapter_name).execute()


# ── UI 輔助 ───────────────────────────────────────────────
def render_images(images: list[dict]):
    if not images:
        st.caption("此章節無圖片")
        return
    cols = st.columns(min(len(images), 4))
    for i, img in enumerate(images):
        with cols[i % 4]:
            img_bytes = base64.b64decode(img["data_b64"])
            st.image(img_bytes, caption=f"第{img['page_num']}頁 ({img['width']}×{img['height']})")


def progress_bar_html(pct: int) -> str:
    return f'<div class="progress-bg"><div class="progress-fill" style="width:{pct}%"></div></div>'


# ══════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 🏮 人相學書稿工作室")

    # ── PDF上傳 ──
    st.markdown("**📂 上傳新版筆記PDF**")
    uploaded = st.file_uploader("選擇PDF", type=["pdf"], label_visibility="collapsed")

    if uploaded:
        with st.spinner("解析PDF中（含圖片提取，請稍候）..."):
            pdf_bytes = uploaded.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(doc)

            detected = detect_chapters_from_pdf(doc)

            if not detected:
                st.error("找不到章節標題，請確認PDF格式")
            else:
                progress_bar = st.progress(0)
                for i, ch in enumerate(detected):
                    # 提取文字
                    text = extract_chapter_text(doc, ch["start_page"], ch["end_page"])
                    # 提取圖片
                    images = extract_chapter_images(doc, ch["start_page"], ch["end_page"])

                    # 存到Supabase
                    db_upsert_chapter(ch)
                    db_upsert_content(ch["num"], ch["name"], text)
                    db_upsert_images(ch["num"], ch["name"], images)

                    progress_bar.progress((i + 1) / len(detected))

                doc.close()
                st.success(f"✅ 完成！偵測到 {len(detected)} 個章節，共 {total_pages} 頁")
                st.rerun()

    st.divider()

    # ── 整體進度 ──
    all_chapters = db_load_chapters()
    if all_chapters:
        overall = sum(c["completeness"] for c in all_chapters) // len(all_chapters)
        st.markdown(f"""
        <div class="metric-box">
            <div class="num">{overall}%</div>
            <div class="label">整體完成度</div>
            {progress_bar_html(overall)}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("尚無資料，請先上傳PDF")

    st.divider()
    st.markdown("**📖 功能選單**")
    page = st.radio("", ["🏠 總覽", "📚 章節整理", "✏️ 補充筆記", "📤 匯出書稿"],
                    label_visibility="collapsed")


# ── Banner ───────────────────────────────────────────────
st.markdown("""
<div class="title-banner">
    <h1>🏮 人相學相理精要</h1>
    <p>郭證銂師資班課程筆記 · 書稿整理工作室</p>
</div>
""", unsafe_allow_html=True)

all_chapters = db_load_chapters()

# ══════════════════════════════════════════════════════════
# 頁面一：總覽
# ══════════════════════════════════════════════════════════
if page == "🏠 總覽":

    if not all_chapters:
        st.info("👈 請先在左側上傳PDF筆記，系統會自動偵測章節")
    else:
        done  = sum(1 for c in all_chapters if c["status"] == "定稿")
        draft = sum(1 for c in all_chapters if c["status"] in ["初稿完成","修訂中"])
        ing   = sum(1 for c in all_chapters if c["status"] == "整理中")
        total = len(all_chapters)

        c1, c2, c3, c4 = st.columns(4)
        for col, num, label in zip(
            [c1, c2, c3, c4],
            [total, done, draft, ing],
            ["總章節數", "已定稿", "草稿階段", "整理中"]
        ):
            with col:
                st.markdown(f'<div class="metric-box"><div class="num">{num}</div><div class="label">{label}</div></div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📋 各章節狀態")

        for ch in all_chapters:
            pct    = ch["completeness"]
            status = ch["status"]
            icon   = STATUS_ICON.get(status, "❓")
            col_l, col_r = st.columns([6, 1])
            with col_l:
                st.markdown(f"""
                <div class="chapter-card">
                    <h4>{icon} 第{ch['num']}章　{ch['name']}
                        <span class="status-badge s-{status}">{status}</span>
                    </h4>
                    <p>頁碼範圍：PDF 第{ch['start_page']}–{ch['end_page']}頁　｜　最後編輯：{ch.get('last_edit','—')}</p>
                    {progress_bar_html(pct)}
                </div>
                """, unsafe_allow_html=True)
            with col_r:
                st.markdown(f"<div style='text-align:center;padding-top:1.2rem;font-size:1.1rem;color:#8B1A1A;font-weight:700'>{pct}%</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# 頁面二：章節整理
# ══════════════════════════════════════════════════════════
elif page == "📚 章節整理":

    st.markdown("### 📚 章節整理")

    if not all_chapters:
        st.info("👈 請先上傳PDF")
    else:
        options = [f"第{c['num']}章：{c['name']}" for c in all_chapters]
        sel_idx = st.selectbox("選擇章節", range(len(all_chapters)),
                               format_func=lambda i: options[i])
        ch = all_chapters[sel_idx]

        st.markdown(f"#### 第{ch['num']}章《{ch['name']}》")
        st.caption(f"PDF 第{ch['start_page']}–{ch['end_page']}頁")

        col_s, col_p = st.columns(2)
        with col_s:
            new_status = st.selectbox("整理狀態", STATUSES,
                                      index=STATUSES.index(ch.get("status","待整理")))
        with col_p:
            new_pct = st.slider("完成度", 0, 100, ch.get("completeness", 0), 5)

        new_notes = st.text_area("備忘錄（不進書稿）", value=ch.get("notes",""), height=70)

        if st.button("💾 儲存狀態", type="primary"):
            db_update_chapter_status(
                ch["num"], ch["name"],
                new_status, new_pct, new_notes,
                ch.get("extra_notes","")
            )
            st.success("✅ 已更新")
            st.rerun()

        st.divider()

        # 分頁顯示文字 / 圖片
        tab_text, tab_img = st.tabs(["📄 原始文字", "🖼️ 圖片"])

        with tab_text:
            text = db_load_content(ch["num"], ch["name"])
            if text:
                st.markdown(f'<div class="note-block">{text}</div>', unsafe_allow_html=True)
            else:
                st.caption("尚無文字內容")

        with tab_img:
            images = db_load_images(ch["num"], ch["name"])
            if images:
                st.caption(f"共 {len(images)} 張圖片")
                render_images(images)
            else:
                st.caption("此章節無嵌入圖片")


# ══════════════════════════════════════════════════════════
# 頁面三：補充筆記
# ══════════════════════════════════════════════════════════
elif page == "✏️ 補充筆記":

    st.markdown("### ✏️ 補充新課堂筆記")
    st.caption("上完課後，把新筆記附加到對應章節")

    if not all_chapters:
        st.info("請先上傳PDF")
    else:
        options = [f"第{c['num']}章：{c['name']}" for c in all_chapters]
        sel_idx = st.selectbox("選擇章節", range(len(all_chapters)),
                               format_func=lambda i: options[i], key="extra_sel")
        ch = all_chapters[sel_idx]

        existing = ch.get("extra_notes", "")

        new_content = st.text_area(
            f"輸入《{ch['name']}》的新筆記",
            placeholder="貼上或輸入新的課堂筆記...",
            height=280
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ 附加到此章節", type="primary", use_container_width=True):
                if new_content.strip():
                    today = str(datetime.date.today())
                    appended = existing + f"\n\n---\n【{today} 補充】\n{new_content.strip()}"
                    db_update_chapter_status(
                        ch["num"], ch["name"],
                        ch.get("status","待整理"),
                        ch.get("completeness",0),
                        ch.get("notes",""),
                        appended
                    )
                    st.success(f"✅ 已附加到《{ch['name']}》")
                    st.rerun()
                else:
                    st.warning("請輸入內容")

        with col2:
            if st.button("🔄 覆蓋舊內容", use_container_width=True):
                if new_content.strip():
                    db_update_chapter_status(
                        ch["num"], ch["name"],
                        ch.get("status","待整理"),
                        ch.get("completeness",0),
                        ch.get("notes",""),
                        new_content.strip()
                    )
                    st.success("✅ 已覆蓋")
                    st.rerun()

        if existing:
            st.divider()
            st.markdown(f"**《{ch['name']}》已有的補充筆記：**")
            st.markdown(f'<div class="note-block">{existing}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# 頁面四：匯出書稿
# ══════════════════════════════════════════════════════════
elif page == "📤 匯出書稿":

    st.markdown("### 📤 匯出書稿")

    if not all_chapters:
        st.info("請先上傳PDF")
    else:
        overall = sum(c["completeness"] for c in all_chapters) // len(all_chapters)
        done = sum(1 for c in all_chapters if c["status"] == "定稿")

        st.markdown(f"""
        <div class="metric-box" style="text-align:left;padding:1.2rem 2rem">
            整體完成度：{overall}%　｜　已定稿：{done} / {len(all_chapters)} 章
            {progress_bar_html(overall)}
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("#### 📄 完整書稿（Markdown）")
            st.caption("含所有章節文字與補充筆記，可用 Typora / Notion 繼續編輯")
            if st.button("生成書稿", type="primary", use_container_width=True):
                today = datetime.date.today().strftime('%Y年%m月%d日')
                lines = [f"# 人相學相理精要\n\n整理日期：{today}\n\n---\n\n## 目錄\n"]
                for c in all_chapters:
                    lines.append(f"- 第{c['num']}章　{c['name']}　（{c['status']} {c['completeness']}%）")
                lines.append("\n---\n")
                for c in all_chapters:
                    text = db_load_content(c["num"], c["name"])
                    extra = c.get("extra_notes","")
                    lines.append(f"\n## 第{c['num']}章　【{c['name']}】\n")
                    if text:
                        lines.append("### 原始筆記\n" + text)
                    if extra:
                        lines.append("\n### 補充整理\n" + extra)
                    lines.append("\n---")

                manuscript = '\n'.join(lines)
                fname = f"人相學精要_{datetime.date.today().strftime('%Y%m%d')}.md"
                st.download_button("⬇️ 下載書稿 .md", manuscript.encode("utf-8"),
                                   file_name=fname, mime="text/markdown", use_container_width=True)

        with col_b:
            st.markdown("#### 📊 進度報告")
            st.caption("各章節狀態總表")
            if st.button("生成進度報告", use_container_width=True):
                lines = [f"# 整理進度報告\n生成：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"]
                lines.append("| 章節 | 名稱 | 狀態 | 完成度 | 最後編輯 |")
                lines.append("|------|------|------|--------|----------|")
                for c in all_chapters:
                    lines.append(f"| 第{c['num']}章 | {c['name']} | {c['status']} | {c['completeness']}% | {c.get('last_edit','—')} |")
                report = '\n'.join(lines)
                st.download_button("⬇️ 下載進度報告 .md", report.encode("utf-8"),
                                   file_name=f"進度報告_{datetime.date.today()}.md",
                                   mime="text/markdown", use_container_width=True)
