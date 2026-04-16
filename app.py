import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import datetime
from notion_client import Client

st.set_page_config(page_title="專業英語學習發射台 V3.0", layout="wide")

# ==========================================
# 🛑 金鑰讀取區
# ==========================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    NOTION_PAGE_ID = st.secrets["NOTION_DB_ID"] # 這裡請填入您的 Notion 頁面 ID
    
    genai.configure(api_key=GEMINI_API_KEY)
    notion = Client(auth=NOTION_TOKEN)
except Exception as e:
    st.error(f"🚨 金鑰讀取錯誤或未設定：{e}")
    st.stop()

# ==========================================
# 核心函式：語音生成
# ==========================================
async def get_audio_bytes(text, voice, rate):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

# ==========================================
# 側邊欄：進階控制區
# ==========================================
st.sidebar.title("🛠️ 學習設定")

# 1. 主題自訂功能
topic_choice = st.sidebar.selectbox("文章主題", ["再生能源", "精品咖啡", "無碳電力", "兜蟲飼育", "親子旅遊", "生活對話", "其他"])
if topic_choice == "其他":
    topic = st.sidebar.text_input("✍️ 請輸入自訂主題：", "例如：Wi-Fi 7 技術優勢")
else:
    topic = topic_choice

# 2. 字數彈性調整
word_count = st.sidebar.slider("文章字數 (約略)", 100, 600, 300, 50)

# 3. 語速與口音
speed_choice = st.sidebar.select_slider("語速設定", options=["慢速", "正常", "快速"], value="正常")
speed_map = {"慢速": "-20%", "正常": "+0%", "快速": "+20%"}
accent = st.sidebar.selectbox("口音選擇", ["美國腔 (US - Aria)", "英國腔 (UK - Sonia)"])
voice_map = {"美國腔 (US - Aria)": "en-US-AriaNeural", "英國腔 (UK - Sonia)": "en-GB-SoniaNeural"}

mode = st.sidebar.radio("內容模式", ["閱讀文章 (Reading)", "情境對話 (Dialogue)"])

# ==========================================
# 主顯示區
# ==========================================
st.title(f"📖 今日學習：{topic}")

if st.button("🔥 生成教材並開始練習"):
    if not topic.strip():
        st.warning("⚠️ 請輸入主題後再開始。")
        st.stop()

    with st.spinner("AI 老師正在調度知識庫與錄製語音..."):
        try:
            model = genai.GenerativeModel('gemini-2.5-flash-lite')
            # 調整 Prompt 以包含「重點片語」並移除括號
            prompt = f"""
            請針對主題『{topic}』，以『{mode}』模式撰寫一段約 {word_count} 字的高階英文。
            
            格式要求（嚴禁使用中括號 []）：
            1. 第一行直接給出一個吸引人的英文標題，不加 #。
            2. 接著是英文原文。
            3. 使用 ### 中文翻譯 作為分隔。
            4. 使用 ### 重點單字 分區。
            5. 使用 ### 重點片語 分區。
            6. 使用 ### 重要文法 分區。
            
            單字、片語、文法各提供三個，格式如下：
            項目 - 性質 - /發音/ - 翻譯：例句
            """
            response_text = model.generate_content(prompt).text
        except Exception as api_err:
            st.error(f"❌ Gemini API 失敗：{api_err}")
            st.stop()

        # 內容解析
        try:
            sections = response_text.split("###")
            header_and_eng = sections[0].strip().split('\n')
            article_title = header_and_eng[0].replace("#", "").strip()
            english_content = '\n'.join(header_and_eng[1:]).strip()
            
            chinese_trans = ""
            vocab_content = ""
            phrase_content = ""
            grammar_content = ""

            for sec in sections:
                if "中文翻譯" in sec: chinese_trans = sec.replace("中文翻譯", "").strip()
                if "重點單字" in sec: vocab_content = sec.replace("重點單字", "").strip()
                if "重點片語" in sec: phrase_content = sec.replace("重點片語", "").strip()
                if "重要文法" in sec: grammar_content = sec.replace("重要文法", "").strip()
        except:
            st.error("AI 格式解析異常，請重新生成。")
            st.stop()

        # --- 主要顯示區排版 ---
        st.markdown(f"# {article_title}")
        st.write(english_content)

        # 音檔與下載 (放在英文內容下方)
        try:
            audio_data = asyncio.run(get_audio_bytes(english_content, voice_map[accent], speed_map[speed_choice]))
            c1, c2 = st.columns([3, 1])
            with c1: st.audio(audio_data)
            with c2: st.download_button("📥 下載音檔", audio_data, f"{topic}.mp3")
        except: st.warning("語音服務暫時忙碌中。")

        st.divider()
        st.subheader("🇹🇼 中文翻譯")
        st.write(chinese_trans)

        # 學習重點區塊 (美編色塊區隔)
        st.divider()
        st.markdown("### 🎯 核心學習重點")
        col_v, col_p, col_g = st.columns(3)
        with col_v:
            st.info(f"**【重點單字】**\n\n{vocab_content}")
        with col_p:
            st.success(f"**【重點片語】**\n\n{phrase_content}")
        with col_g:
            st.warning(f"**【重要文法】**\n\n{grammar_content}")

        # ==========================================
        # Notion 累積式匯入：學習卡模式
        # ==========================================
        try:
            today_str = datetime.datetime.now().strftime("%Y/%m/%d")
            
            # 定義學習卡 (Callout 區塊) 函式
            def create_callout(title, content, emoji):
                return {
                    "callout": {
                        "rich_text": [{"text": {"content": f"【{title}】\n{content}"}}],
                        "icon": {"emoji": emoji},
                        "color": "blue_background"
                    }
                }

            # 準備匯入的區塊：先加上日期標題，再放三張卡片
            new_blocks = [
                {"divider": {}},
                {"heading_2": {"rich_text": [{"text": {"content": f"📅 {today_str}：{topic}"}}]}},
                create_callout("重點單字", vocab_content, "💡"),
                create_callout("重點片語", phrase_content, "🔗"),
                create_callout("重要文法", grammar_content, "📝")
            ]

            # 執行累積式匯入 (Append)
            notion.blocks.children.append(block_id=NOTION_PAGE_ID, children=new_blocks)
            
            st.success(f"✅ 學習卡已累積至 Notion 頁面底部！")
            st.balloons()
            
        except Exception as e:
            st.error(f"❌ Notion 累積失敗 (請檢查是否使用 Page ID): {e}")
