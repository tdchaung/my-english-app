import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import re
from notion_client import Client

st.set_page_config(page_title="專業英語學習發射台 V4.4", layout="wide")

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
# 核心功能：自動查找或建立分類區塊
# ==========================================
def get_section_id(page_id, title, emoji):
    try:
        results = notion.blocks.children.list(block_id=page_id).get("results", [])
        for block in results:
            if block.get("type") == "callout":
                rich_text = block["callout"]["rich_text"]
                if rich_text and title in rich_text[0]["plain_text"]:
                    return block["id"]
        
        # 建立新的 Callout 容器
        new_block = notion.blocks.children.append(
            block_id=page_id,
            children=[{
                "callout": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": f"{title}\n"},
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

# ==========================================
# 文字格式清洗濾波器 (拔除數字、消滅空白行)
# ==========================================
def format_to_bullet(text):
    if not text: return ""
    text = text.strip()
    # 1. 把所有開頭的 "數字." (例如 1. 2. 3.) 強制換成 "• "
    text = re.sub(r'^\s*\d+\.\s*', '• ', text, flags=re.MULTILINE)
    # 2. 如果 AI 偷用 "-" 或 "*" 列點，也統一洗成 "• "
    text = re.sub(r'^\s*[-*]\s+', '• ', text, flags=re.MULTILINE)
    # 3. 壓縮空白行：把多個連續換行符號壓縮成一個換行符號 (消滅大間距)
    text = re.sub(r'\n\s*\n', '\n', text)
    # 4. 確保結尾只帶有一個換行，讓下次匯入完美銜接
    return text + "\n"

# ==========================================
# 側邊欄：控制區
# ==========================================
st.sidebar.title("🛠️ 學習設定")

topic_list = ["再生能源", "精品咖啡", "無碳電力", "甲蟲飼育", "親子旅遊", "AI技術", "其他"]
topic_choice = st.sidebar.selectbox("文章主題", topic_list)
if topic_choice == "其他":
    topic = st.sidebar.text_input("✍️ 請輸入自訂主題：")
else:
    topic = topic_choice

word_count = st.sidebar.slider("文章字數 (約略)", 100, 600, 300, 50)
speed_choice = st.sidebar.select_slider("語速設定", options=["慢速", "正常", "快速"], value="正常")
speed_map = {"慢速": "-20%", "正常": "+0%", "快速": "+20%"}
accent = st.sidebar.selectbox("口音選擇", ["美國腔 (US - Aria)", "英國腔 (UK - Sonia)"])
voice_map = {"美國腔 (US - Aria)": "en-US-AriaNeural", "英國腔 (UK - Sonia)": "en-GB-SoniaNeural"}

mode = st.sidebar.radio("內容模式", ["閱讀文章 (Reading)", "情境對話 (Dialogue)"])

# ==========================================
# 主顯示區
# ==========================================
st.title(f"📖 今日學習：{topic}")

if st.button("🔥 生成教材並同步知識庫"):
    if not topic:
        st.warning("⚠️ 請輸入主題。")
        st.stop()

    with st.spinner("AI 老師正在組織知識結構..."):
        try:
            model = genai.GenerativeModel('gemini-2.5-flash-lite')
            # 調整 Prompt：明令禁止使用數字編號
            prompt = f"""
            請針對主題『{topic}』，以『{mode}』模式撰寫一段約 {word_count} 字的高階英文。
            要求：
            1. 第一行為英文標題 (不含任何符號)。
            2. 接著是英文原文。
            3. 使用 ### 中文翻譯 分隔。
            4. 使用 ### 重點單字 分區。
            5. 使用 ### 重點片語 分區。
            6. 使用 ### 重要文法 分區。
            
            ⚠️ 極度嚴格限制：
            單字、片語、文法【每一項絕對只能提供剛好 3 個】。
            【絕對禁止使用數字編號 (1. 2. 3.)】，每一項請一律以 bullet point「•」開頭！
            條列格式：• 項目 - 性質 - /發音/ - 翻譯：精簡例句 (嚴禁使用 [])
            """
            response_text = model.generate_content(prompt).text
        except Exception as api_err:
            st.error(f"❌ API 失敗：{api_err}"); st.stop()

        # 解析內容
        try:
            sections = response_text.split("###")
            eng_part = sections[0].strip().split('\n')
            title = eng_part[0].strip()
            english_text = '\n'.join(eng_part[1:]).strip()
            
            trans, vocab, phrase, grammar = "", "", "", ""
            for s in sections:
                if "中文翻譯" in s: trans = s.replace("中文翻譯", "").strip()
                if "重點單字" in s: vocab = s.replace("重點單字", "").strip()
                if "重點片語" in s: phrase = s.replace("重點片語", "").strip()
                if "重要文法" in s: grammar = s.replace("重要文法", "").strip()
        except:
            st.error("格式解析異常，請重新嘗試。"); st.stop()

        # ==========================================
        # 套用文字格式清洗
        # ==========================================
        vocab = format_to_bullet(vocab)
        phrase = format_to_bullet(phrase)
        grammar = format_to_bullet(grammar)

        # --- 顯示介面 ---
        st.markdown(f"# {title}")
        st.write(english_text)

        try:
            audio_data = asyncio.run(get_audio_bytes(english_text, voice_map[accent], speed_map[speed_choice]))
            c1, c2 = st.columns([3, 1])
            with c1: st.audio(audio_data)
            with c2: st.download_button("📥 下載音檔", audio_data, f"{topic}.mp3")
        except: st.warning("語音合成暫時停用。")

        st.divider()
        st.subheader("🇹🇼 中文翻譯")
        st.write(trans)

        st.divider()
        st.markdown("### 🎯 核心學習重點")
        col_v, col_p, col_g = st.columns(3)
        with col_v: st.info(f"**【單字庫】**\n\n{vocab}")
        with col_p: st.success(f"**【片語庫】**\n\n{phrase}")
        with col_g: st.warning(f"**【文法庫】**\n\n{grammar}")

        # ==========================================
        # Notion 累積合併邏輯
        # ==========================================
        try:
            v_id = get_section_id(NOTION_PAGE_ID, "重點單字", "💡")
            p_id = get_section_id(NOTION_PAGE_ID, "重點片語", "🔗")
            g_id = get_section_id(NOTION_PAGE_ID, "重要文法", "📝")
            
            def append_to_notion(block_id, content):
                if not content.strip(): return
                
                rich_text_list = []
                
                # 內容切割防護 (維持純淨，已無多餘空行)
                chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
                
                for chunk in chunks:
                    rich_text_list.append({
                        "type": "text",
                        "text": {"content": chunk}
                    })

                notion.blocks.children.append(
                    block_id=block_id,
                    children=[{
                        "paragraph": {
                            "rich_text": rich_text_list
                        }
                    }]
                )

            append_to_notion(v_id, vocab)
            append_to_notion(p_id, phrase)
            append_to_notion(g_id, grammar)
            
            st.success("✅ 知識已自動純淨合併至 Notion 對應庫中！無縫排版完成！")
            st.balloons()
            
        except Exception as e:
            st.error(f"❌ Notion 同步失敗: {e}")
