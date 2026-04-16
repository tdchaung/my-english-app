import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import re
import time
from notion_client import Client

st.set_page_config(page_title="專業雙語學習發射台 V5.11", layout="wide")

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
                    "rich_text": [{"type": "text", "text": {"content": f"{full_title}\n"}, "annotations": {"bold": True}}],
                    "icon": {"emoji": emoji},
                    "color": "blue_background"
                }
            }]
        )
        return new_block["results"][0]["id"]
    except Exception as e:
        st.error(f"Notion 區塊檢索失敗: {e}")
        return None

# ==========================================
# 語音引擎 (包含智慧分軌器)
# ==========================================
async def get_audio_bytes(text, voice, rate):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

async def get_dialogue_audio_bytes(text, voice_pair, rate):
    """智慧語音分軌器：自動切換男女聲，並過濾人名"""
    lines = text.strip().split('\n')
    speakers = {}
    audio_data = b""
    voice_index = 0
    current_voice = voice_pair[0] 
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        match = re.match(r'^([^:：]+)[:：]\s*(.*)$', line)
        if match:
            speaker = match.group(1).strip()
            spoken_text = match.group(2).strip()
            
            if speaker not in speakers:
                speakers[speaker] = voice_pair[voice_index % 2]
                voice_index += 1
                
            current_voice = speakers[speaker]
            chunk = await get_audio_bytes(spoken_text, current_voice, rate)
            audio_data += chunk
        else:
            chunk = await get_audio_bytes(line, current_voice, rate)
            audio_data += chunk
            
    return audio_data

# ==========================================
# 文字清洗濾波器
# ==========================================
def format_to_bullet(text, max_items=3):
    if not text: return ""
    text = text.strip()
    text = re.sub(r'^\s*\d+\.\s*', '• ', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-*]\s+', '• ', text, flags=re.MULTILINE)
    text = re.sub(r'(?<!^)\s*•\s*', '\n\n• ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    lines = text.split('\n\n')
    bullets = [line.strip() for line in lines if line.strip().startswith('•')]
    return '\n\n'.join(bullets[:max_items]) + '\n\n'

def extract_section(text, section_name):
    pattern = rf"### {section_name}\s*(.*?)(?=###|$)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""

# ==========================================
# 側邊欄：控制區
# ==========================================
st.sidebar.title("🛠️ 學習設定")

learning_lang = st.sidebar.radio("🌐 學習語言", ["英文 (English)", "日文 (日本語)"])
mode = st.sidebar.radio("內容模式", ["閱讀文章 (Reading)", "情境對話 (Dialogue)"])

# 🌟 核心修改區：動態配置英文與日文的選單邏輯
if learning_lang == "英文 (English)":
    lang_prefix = "🇬🇧 英文"
    difficulty = st.sidebar.selectbox("📈 難易度", ["基礎 (A1-A2)", "中階 (B1-B2)", "高階 (C1-C2 專業)"])
    
    # 根據閱讀或對話模式，顯示不同的介面與選項
    if mode == "情境對話 (Dialogue)":
        st.sidebar.info("🗣️ 英文對話已自動啟用【男女雙聲道】")
        accent = st.sidebar.selectbox("🗣️ 口音搭配", ["🇺🇸 美國腔 (女+男)", "🇬🇧 英國腔 (女+男)"])
        if "美國腔" in accent:
            voice_pair = ("en-US-AriaNeural", "en-US-GuyNeural")
        else:
            voice_pair = ("en-GB-SoniaNeural", "en-GB-RyanNeural")
        voice_single = None
    else:
        accent = st.sidebar.selectbox("🗣️ 語音", [
            "🇺🇸 美國腔 (女聲 - Aria)", "🇺🇸 美國腔 (男聲 - Guy)",
            "🇬🇧 英國腔 (女聲 - Sonia)", "🇬🇧 英國腔 (男聲 - Ryan)"
        ])
        if "Aria" in accent: voice_single = "en-US-AriaNeural"
        elif "Guy" in accent: voice_single = "en-US-GuyNeural"
        elif "Sonia" in accent: voice_single = "en-GB-SoniaNeural"
        else: voice_single = "en-GB-RyanNeural"
        voice_pair = None
        
    lang_prompt_target = f"{difficulty} 程度的英文"
    pronunciation_desc = "/發音與重音/"
    romaji_template = ""
else:
    lang_prefix = "🇯🇵 日文"
    difficulty = st.sidebar.selectbox("📈 難易度", ["基礎 (JLPT N5-N4)", "中階 (JLPT N3)", "高階 (JLPT N2-N1)"])
    
    if mode == "情境對話 (Dialogue)":
        st.sidebar.info("🗣️ 日文對話已自動啟用【男女雙聲道】")
        voice_pair = ("ja-JP-NanamiNeural", "ja-JP-KeitaNeural")
        voice_single = None
    else:
        accent = st.sidebar.selectbox("🗣️ 語音", ["標準日語 (女聲)", "標準日語 (男聲)"])
        voice_single = "ja-JP-NanamiNeural" if "女聲" in accent else "ja-JP-KeitaNeural"
        voice_pair = None
        
    lang_prompt_target = f"{difficulty} 程度的日文"
    pronunciation_desc = "/羅馬拼音 (Romaji)/"
    romaji_template = "### 羅馬拼音\n(此處寫出整段原文的羅馬拼音，如果是對話請務必一人一行，並保留角色名字)\n"

topic_list = [
    "AI 技術", "美食", "假期",
    "再生能源", "精品咖啡", 
    "無碳電力", "甲蟲飼育", 
    "親子旅遊", "其他"
]
topic_choice = st.sidebar.selectbox("📚 文章主題", topic_list)
topic = st.sidebar.text_input("✍️ 自訂主題：") if topic_choice == "其他" else topic_choice

word_count = st.sidebar.slider("文章字數", 100, 600, 300, 50)
speed_choice = st.sidebar.select_slider("語速", options=["慢速", "正常", "快速"], value="正常")
speed_map = {"慢速": "-20%", "正常": "+0%", "快速": "+20%"}

dialogue_rule = "【⚠️ 排版警告：這是情境對話，請務必嚴格遵守「一人一句」，且每句話必須嚴格以「角色名字: 」開頭 (例如 Tom: Hello!)】" if mode == "情境對話 (Dialogue)" else ""

# ==========================================
# 主顯示區
# ==========================================
st.title(f"📖 今日學習：{topic}")

if st.button("🔥 生成教材並同步知識庫"):
    if not topic:
        st.warning("⚠️ 請輸入主題。")
        st.stop()

    with st.spinner(f"AI 老師正在組織 {lang_prefix} 的學習重點..."):
        model = genai.GenerativeModel('gemini-2.5-flash')
        target_lang_name = "英文" if "英文" in learning_lang else "日文"
        
        prompt = f"""
        請針對主題『{topic}』，撰寫一篇 {word_count} 字的【{lang_prompt_target}】{mode}。
        {dialogue_rule}
        
        ⚠️ 嚴格指令：你必須 100% 複製以下結構輸出，不可遺漏任何一個 ### 標籤！

        ### 標題
        (此處寫出{target_lang_name}標題)
        ### 原文
        (此處寫出{target_lang_name}原文)
        {romaji_template}### 中文翻譯
        (此處寫出完整的中文翻譯)
        ### 重點單字
        • 單字1 - 性質 - {pronunciation_desc} - 翻譯：精簡例句
        • 單字2 - 性質 - {pronunciation_desc} - 翻譯：精簡例句
        • 單字3 - 性質 - {pronunciation_desc} - 翻譯：精簡例句
        ### 重點片語
        • 片語1 - 性質 - {pronunciation_desc} - 翻譯：精簡例句
        • 片語2 - 性質 - {pronunciation_desc} - 翻譯：精簡例句
        • 片語3 - 性質 - {pronunciation_desc} - 翻譯：精簡例句
        ### 重要文法
        • 文法1 - 性質 - {pronunciation_desc} - 翻譯：精簡例句
        • 文法2 - 性質 - {pronunciation_desc} - 翻譯：精簡例句
        • 文法3 - 性質 - {pronunciation_desc} - 翻譯：精簡例句
        """
        
        max_retries = 2
        response_text = ""
        for attempt in range(max_retries):
            try:
                response_text = model.generate_content(prompt).text
                break 
            except Exception as api_err:
                err_msg = str(api_err)
                if "429" in err_msg or "Quota" in err_msg or "exceeded" in err_msg.lower():
                    if attempt < max_retries - 1:
                        st.warning("⏳ 觸發 Google API 流量保護機制！系統將在 30 秒後自動為您重試，請勿關閉網頁...")
                        time.sleep(30) 
                    else:
                        st.error("❌ API 流量限制極限，請稍後幾分鐘再試。或考慮至 Google AI Studio 升級為 Pay-as-you-go 計畫。")
                        st.stop()
                else:
                    st.error(f"❌ API 發生未知的錯誤：{api_err}")
                    st.stop()

        try:
            title = extract_section(response_text, "標題")
            article_text = extract_section(response_text, "原文")
            if mode == "情境對話 (Dialogue)":
                article_text = re.sub(r'([^\n])\n([^\n])', r'\1\n\n\2', article_text)

            romaji = extract_section(response_text, "羅馬拼音")
            if mode == "情境對話 (Dialogue)" and romaji:
                romaji = re.sub(r'([^\n])\n([^\n])', r'\1\n\n\2', romaji)

            trans = extract_section(response_text, "中文翻譯")
            vocab = format_to_bullet(extract_section(response_text, "重點單字"), max_items=3)
            phrase = format_to_bullet(extract_section(response_text, "重點片語"), max_items=3)
            grammar = format_to_bullet(extract_section(response_text, "重要文法"), max_items=3)
        except Exception as e:
            st.error("解析異常，AI 生成的格式有誤，請稍後再試。"); st.stop()

        st.markdown(f"# {title}")
        st.write(article_text)
        
        if romaji:
            st.caption(f"🗣️ **Romaji**：\n{romaji}")

        try:
            clean_audio_text = article_text.replace("*", "")
            if mode == "情境對話 (Dialogue)":
                audio_data = asyncio.run(get_dialogue_audio_bytes(clean_audio_text, voice_pair, speed_map[speed_choice]))
            else:
                audio_data = asyncio.run(get_audio_bytes(clean_audio_text, voice_single, speed_map[speed_choice]))
                
            c1, c2 = st.columns([3, 1])
            with c1: st.audio(audio_data)
            with c2: st.download_button("📥 下載音檔", audio_data, f"{topic}.mp3")
        except Exception as e: 
            st.warning(f"語音合成暫時停用：{e}")

        st.divider()
        st.subheader("🇹🇼 中文翻譯")
        st.write(trans)

        st.divider()
        st.markdown(f"### 🎯 {lang_prefix} 核心學習重點")
        col_v, col_p, col_g = st.columns(3)
        with col_v: st.info(f"**【單字庫】**\n\n{vocab}")
        with col_p: st.success(f"**【片語庫】**\n\n{phrase}")
        with col_g: st.warning(f"**【文法庫】**\n\n{grammar}")

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
