import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import datetime
from notion_client import Client

st.set_page_config(page_title="專業英語學習發射台", layout="wide")

# ==========================================
# 🛑 金鑰讀取區
# ==========================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    NOTION_DB_ID = st.secrets["NOTION_DB_ID"]
    
    genai.configure(api_key=GEMINI_API_KEY)
    notion = Client(auth=NOTION_TOKEN)
except Exception as e:
    st.error(f"🚨 金鑰格式讀取錯誤: {e}")
    st.stop()

# ==========================================
# 核心函式：微軟語音生成 (支援語速控制)
# ==========================================
async def get_audio_bytes(text, voice, rate):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

# ==========================================
# 側邊欄：控制區設定
# ==========================================
st.sidebar.title("🛠️ 學習設定")

# 1. 支援「其他」自訂主題
topic_choice = st.sidebar.selectbox(
    "文章主題", 
    ["再生能源", "精品咖啡", "無碳電力", "兜蟲飼育", "親子旅遊", "生活對話", "其他"]
)
if topic_choice == "其他":
    topic = st.sidebar.text_input("✍️ 請輸入自訂主題：", "例如：人工智慧的未來")
else:
    topic = topic_choice

# 2. 文章字數調整
word_count = st.sidebar.slider("文章字數 (約略)", min_value=100, max_value=600, value=300, step=50)

mode = st.sidebar.radio("內容模式", ["閱讀文章 (Reading)", "情境對話 (Dialogue)"])
accent = st.sidebar.selectbox("口音選擇", ["美國腔 (US - Aria)", "英國腔 (UK - Sonia)"])
voice_map = {"美國腔 (US - Aria)": "en-US-AriaNeural", "英國腔 (UK - Sonia)": "en-GB-SoniaNeural"}

# 3. 語速設定
speed_choice = st.sidebar.select_slider("語速設定", options=["慢速", "正常", "快速"], value="正常")
speed_map = {"慢速": "-20%", "正常": "+0%", "快速": "+20%"}

# ==========================================
# 主顯示區
# ==========================================
st.title(f"📖 今日學習：{topic}")

if st.button("🔥 生成教材並開始練習"):
    if not topic.strip():
        st.warning("⚠️ 請輸入您想學習的主題！")
        st.stop()

    with st.spinner("AI 老師正在撰寫內容與錄製語音..."):
        try:
            model = genai.GenerativeModel('gemini-2.5-flash-lite')
            # 嚴格要求 AI 輸出的格式，移除所有括號
            prompt = f"""
            請針對主題『{topic}』，以『{mode}』模式撰寫一段約 {word_count} 字的高階英文。
            格式必須精確如下，請不要使用任何中括號 []，標題直接寫：

            # (此處填入適合的英文標題)
            (此處填入英文原文內容)
            ### 中文翻譯
            (此處填入中文翻譯內容)
            ### 重點單字
            1. 單字 - 詞性 - /發音與重音/ - 翻譯：例句
            (共三個)
            ### 重點片語
            1. 片語 - 翻譯：例句
            (共三個)
            ### 重要文法
            1. 用法說明：例句
            (共三個)
            """
            response_text = model.generate_content(prompt).text
        except Exception as api_err:
            st.error(f"❌ Gemini API 呼叫失敗！詳細原因：{api_err}")
            st.stop()
        
        # ==========================================
        # 內容拆解與排版邏輯
        # ==========================================
        try:
            # 切割出：英文原文區塊 vs 中文與教學區塊
            parts = response_text.split("### 中文翻譯")
            eng_part = parts[0].strip()
            rest_part = parts[1].strip() if len(parts) > 1 else ""

            # 切割出：中文翻譯區塊 vs 學習重點區塊 (單字/片語/文法)
            if "### 重點單字" in rest_part:
                trans_part, learning_part = rest_part.split("### 重點單字", 1)
                learning_part = "### 重點單字\n" + learning_part # 把標題補回來
            else:
                trans_part = rest_part
                learning_part = ""

            # 萃取英文標題與內文
            eng_lines = eng_part.split('\n')
            title = eng_lines[0].replace("#", "").strip()
            english_text = '\n'.join(eng_lines[1:]).strip()

        except Exception as e:
            # 容錯處理：如果 AI 格式跑掉，就整包顯示
            title = f"{topic} (解析格式異常)"
            english_text = response_text
            trans_part = ""
            learning_part = ""

        # 1. 顯示短文標題與英文原文
        st.markdown(f"## ✨ {title}")
        st.write(english_text)

        # 2. 音檔位置移到英文內容下方
        try:
            # 去除 Markdown 符號以確保 TTS 朗讀順暢
            clean_text_for_audio = english_text.replace("*", "").replace("#", "")
            audio_data = asyncio.run(get_audio_bytes(clean_text_for_audio, voice_map[accent], speed_map[speed_choice]))
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.audio(audio_data, format="audio/mp3")
            with col2:
                st.download_button("📥 下載本篇語音", data=audio_data, file_name=f"{topic}.mp3", mime="audio/mp3")
        except Exception as e:
            st.warning("⚠️ 語音生成失敗 (可能遭微軟伺服器阻擋)，請稍後再試。")
        
        # 3. 顯示中文翻譯
        st.divider()
        st.markdown("### 🇹🇼 中文翻譯")
        st.write(trans_part.strip())

        # 4 & 5. 顯示學習重點 (用 Info 藍色色塊包覆區隔)
        if learning_part:
            st.divider()
            with st.container():
                st.info(learning_part) # 這會產生一個漂亮的藍底色塊
        
        # ==========================================
        # 專屬 Notion 同步：只匯入單字、片語、文法
        # ==========================================
        if learning_part:
            try:
                notion_blocks = []
                
                # 將學習區塊的純文字依據行數與標題轉換為 Notion 原生格式 (不帶超連結)
                for line in learning_part.split('\n'):
                    line = line.strip()
                    if not line: continue
                    
                    if line.startswith("### "):
                        # 把 "### 重點單字" 轉成 Notion 的漂亮小標題
                        heading_text = line.replace("### ", "")
                        notion_blocks.append({
                            "heading_3": {"rich_text": [{"text": {"content": heading_text}}]}
                        })
                    else:
                        # 一般內文處理，超過 1900 字元自動切斷防當機
                        chunks = [line[i:i+1900] for i in range(0, len(line), 1900)]
                        for chunk in chunks:
                            notion_blocks.append({
                                "paragraph": {"rich_text": [{"text": {"content": chunk}}]}
                            })

                notion.pages.create(
                    parent={"database_id": NOTION_DB_ID},
                    properties={
                        "名稱": {"title": [{"text": {"content": f"📝 學習筆記：{topic}"}}]},
                        "日期": {"date": {"start": datetime.datetime.now().strftime("%Y-%m-%d")}},
                        "主題": {"select": {"name": topic}}
                    },
                    children=notion_blocks
                )
                st.success("✅ 重點單字、片語與文法已純淨匯入 Notion！")
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Notion 同步失敗: {e}")
