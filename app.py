import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import re
from notion_client import Client

st.set_page_config(page_title="專業雙語學習發射台 V5.2", layout="wide")

# ==========================================
# 🛑 金鑰讀取區
# ==========================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    NOTION_PAGE_ID = st.secrets["NOTION_DB_ID"] 
    
    genai.configure(api_key=GEMINI_API_KEY)
    notion = Client(auth=NOTION_TOKEN)
except Exception as e:
    st.error(f"🚨 金鑰讀取錯誤或未設定：{e}")
    st.stop()

# ==========================================
# 核心功能：自動查找或建立分類區塊 (支援語言隔離)
# ==========================================
def get_section_id(page_id, lang_prefix, title, emoji):
    full_title = f"{lang_prefix} {title}"
    try:
        results = notion.blocks.children.list(block_id=page_id).get("results", [])
        for block in results:
            if block.get("type") == "callout":
                rich_text = block["callout"]["rich_text"]
                if rich_text and full_title in rich_text[0]["plain_text"]:
                    return block["id"]
        
        new_block = notion.blocks.children.append(
            block_id=page_id,
            children=[{
                "callout": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": f"{full_title}\n"},
                            "annotations": {"bold": True}
                        }
                    ],
                    "icon": {"emoji": emoji},
                    "color": "blue_background"
                }
            }]
        )
        return new_block["results"][0]["id"]
    except Exception as e:
        st.error(f"Notion 區塊檢索失敗: {e}")
        return None

async def get_audio_bytes(text, voice, rate):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

def format_to_bullet(text):
    if not text: return ""
    text = text.strip()
    text = re.sub(r'^\s*\d+\.\s*', '• ', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-*]\s+', '• ', text, flags=re.MULTILINE)
    text = re.sub(r'\n\s*\n', '\n', text)
    return text + "\n"

# ==========================================
# 側邊欄：控制區
# ==========================================
st.sidebar.title("🛠️ 學習設定")

learning_lang = st.sidebar.radio("🌐 學習語言", ["英文 (English)", "日文 (日本語)"])

if learning_lang == "英文 (English)":
    lang_prefix = "🇬🇧 英文"
    difficulty = st.sidebar.selectbox("📈 難易度", ["基礎 (A1-A2)", "中階 (B1-B2)", "高階 (C1-C2 專業)"])
    accent = st.sidebar.selectbox("🗣️ 口音", ["美國腔 (US - Aria)", "英國腔 (UK - Sonia)"])
    voice_map = {"美國腔 (US - Aria)": "en-US-AriaNeural", "英國腔 (UK - Sonia)": "en-GB-SoniaNeural"}
    lang_prompt_target = f"{difficulty} 程度的英文"
    pronunciation_desc = "/發音與重音/"
else:
    lang_prefix = "🇯🇵 日文"
    difficulty = st.sidebar.selectbox("📈 難易度", ["基礎 (JLPT N5-N4)", "中階 (JLPT N3)", "高階 (JLPT N2-N1)"])
    accent = st.sidebar.selectbox("🗣️ 語音", ["標準日語 (女聲)", "標準日語 (男聲)"])
    voice_map = {"標準日語 (女聲)": "ja-JP-NanamiNeural", "標準日語 (男聲)": "ja-JP-KeitaNeural"}
    lang_prompt_target = f"{difficulty} 程度的日文"
    pronunciation_desc = "/平假名讀音/"

# 整合了您的 AI 技術與個人專屬主題清單
topic_list = [
    "AI 技術", 
    "再生能源", 
    "精品咖啡", 
    "無碳電力", 
    "甲蟲飼育", 
    "親子旅遊",
    "美食",
    "其他"
]
topic_choice = st.sidebar.selectbox("📚 文章主題", topic_list)
topic = st.sidebar.text_input("✍️ 自訂主題：") if topic_choice == "其他" else topic_choice

word_count = st.sidebar.slider("文章字數", 100, 600, 300, 50)
speed_choice = st.sidebar.select_slider("語速", options=["慢速", "正常", "快速"], value="正常")
speed_map = {"慢速": "-20%", "正常": "+0%", "快速": "+20%"}
mode = st.sidebar.radio("內容模式", ["閱讀文章 (Reading)", "情境對話 (Dialogue)"])

# ==========================================
# 主顯示區 (這一段就是剛剛遺失的靈魂)
# ==========================================
st.title(f"📖 今日學習：{topic}")

if st.button("🔥 生成教材並同步知識庫"):
    if not topic:
        st.warning("⚠️ 請輸入主題。")
        st.stop()

    with st.spinner(f"AI 老師正在組織 {lang_prefix} 的學習重點..."):
        try:
            model = genai.GenerativeModel('gemini-2.5-flash-lite')
            target_lang_name = "英文" if "英文" in learning_lang else "日文"
            
            prompt = f"""
            請針對主題『{topic}』，以『{mode}』模式撰寫一段約 {word_count} 字的【{lang_prompt_target}】。
            要求：符合 {difficulty} 難度，第一行為{target_lang_name}標題，接著原文，其後使用 ### 分隔中文翻譯、重點單字、重點片語、重要文法。
            ⚠️ 每項嚴格限制剛好 3 個，禁止數字編號，統一使用 • 開頭。
            格式：• 項目 - 性質 - {pronunciation_desc} - 翻譯：精簡例句
            """
            response_text = model.generate_content(prompt).text
        except Exception as api_err:
            st.error(f"❌ API 失敗：{api_err}"); st.stop()

        # 解析與清洗
        try:
            sections = response_text.split("###")
            eng_part = sections[0].strip().split('\n')
            title = eng_part[0].strip()
            article_text = '\n'.join(eng_part[1:]).strip()
            trans, vocab, phrase, grammar = "", "", "", ""
            for s in sections:
                if "中文翻譯" in s: trans = s.replace("中文翻譯", "").strip()
                if "重點單字" in s: vocab = format_to_bullet(s.replace("重點單字", "").strip())
                if "重點片語" in s: phrase = format_to_bullet(s.replace("重點片語", "").strip())
                if "重要文法" in s: grammar = format_to_bullet(s.replace("重要文法", "").strip())
        except:
            st.error("解析異常，請稍後再試。"); st.stop()

        # --- UI 呈現 ---
        st.markdown(f"# {title}")
        st.write(article_text)

        try:
            audio_data = asyncio.run(get_audio_bytes(article_text, voice_map[accent], speed_map[speed_choice]))
            c1, c2 = st.columns([3, 1])
            with c1: st.audio(audio_data)
            with c2: st.download_button("📥 下載音檔", audio_data, f"{topic}.mp3")
        except: st.warning("語音合成暫時停用。")

        st.divider()
        st.subheader("🇹🇼 中文翻譯")
        st.write(trans)

        st.divider()
        st.markdown(f"### 🎯 {lang_prefix} 核心學習重點")
        col_v, col_p, col_g = st.columns(3)
        with col_v: st.info(f"**【單字庫】**\n\n{vocab}")
        with col_p: st.success(f"**【片語庫】**\n\n{phrase}")
        with col_g: st.warning(f"**【文法庫】**\n\n{grammar}")

        # ==========================================
        # Notion 隔離式累積合併
        # ==========================================
        try:
            v_id = get_section_id(NOTION_PAGE_ID, lang_prefix, "單字庫", "💡")
            p_id = get_section_id(NOTION_PAGE_ID, lang_prefix, "片語庫", "🔗")
            g_id = get_section_id(NOTION_PAGE_ID, lang_prefix, "文法庫", "📝")
            
            def append_to_notion(block_id, content):
                if not content.strip(): return
                rich_text_list = []
                chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
                for chunk in chunks:
                    rich_text_list.append({"type": "text", "text": {"content": chunk}})

                notion.blocks.children.append(
                    block_id=block_id,
                    children=[{"paragraph": {"rich_text": rich_text_list}}]
                )

            append_to_notion(v_id, vocab)
            append_to_notion(p_id, phrase)
            append_to_notion(g_id, grammar)
            
            st.success(f"✅ 知識已自動歸類至 Notion {lang_prefix} 專區！")
            st.balloons()
            
        except Exception as e:
            st.error(f"❌ Notion 同步失敗: {e}")
