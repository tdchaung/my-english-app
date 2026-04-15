import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import datetime
from notion_client import Client

# --- 介面設定 ---
st.set_page_config(page_title="專業英語學習發射台", layout="wide")

# --- 金鑰讀取 (只需兩組) ---
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    NOTION_DB_ID = st.secrets["NOTION_DB_ID"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
    notion = Client(auth=NOTION_TOKEN)
except:
    st.warning("請在 Secrets 中設定 GEMINI_API_KEY, NOTION_TOKEN, NOTION_DB_ID")

# --- 核心函式：語音生成與讀取 ---
async def get_audio_bytes(text, voice):
    communicate = edge_tts.Communicate(text, voice)
    # 將音檔存為 bytes 以供下載
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

# --- 側邊欄：工作列 ---
st.sidebar.title("🛠️ 學習設定")
topic = st.sidebar.selectbox("文章主題", ["再生能源憑證制度", "精品咖啡萃取理論", "企業級網通架構", "大象大兜蟲飼育(CBF1)", "日本親子旅遊對話"])
mode = st.sidebar.radio("內容模式", ["閱讀文章 (Reading)", "情境對話 (Dialogue)"])
accent = st.sidebar.selectbox("口音選擇", ["美國腔 (US - Aria)", "英國腔 (UK - Sonia)"])
voice_map = {"美國腔 (US - Aria)": "en-US-AriaNeural", "英國腔 (UK - Sonia)": "en-GB-SoniaNeural"}

# --- 主畫面 ---
st.title(f"📖 今日學習：{topic}")

if st.button("🔥 生成教材並開始練習"):
    with st.spinner("AI 老師正在準備內容..."):
        # 1. AI 生成內容
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"""
        請針對主題『{topic}』，以『{mode}』模式撰寫一段約 150 字的高階英文。
        格式必須精確如下：
        ### [原文]
        (英文原文)
        ### [翻譯]
        (中文翻譯)
        ### [重點單字]
        1. 單字 - [詞性] - /發音與重音/ - 翻譯：例句
        2. ... (共三個)
        ### [重要文法]
        1. 用法說明：例句
        2. ... (共三個)
        """
        response_text = model.generate_content(prompt).text
        
        # 2. 生成語音 bytes
        english_text = response_text.split("### [翻譯]")[0].replace("### [原文]", "")
        audio_data = asyncio.run(get_audio_bytes(english_text, voice_map[accent]))
        
        # 3. 畫面呈現
        st.markdown(response_text)
        
        # --- 音檔操作區 ---
        st.divider()
        col1, col2 = st.columns([2, 1])
        with col1:
            st.audio(audio_data, format="audio/mp3")
        with col2:
            st.download_button(
                label="📥 下載本篇語音 (MP3)",
                data=audio_data,
                file_name=f"{topic}_{datetime.date.today()}.mp3",
                mime="audio/mp3"
            )
        
        # 4. 同步至 Notion (僅同步文字資訊)
        try:
            notion.pages.create(
                parent={"database_id": NOTION_DB_ID},
                properties={
                    "名稱": {"title": [{"text": {"content": f"{topic} 學習筆記"}}]},
                    "日期": {"date": {"start": datetime.datetime.now().strftime("%Y-%m-%d")}},
                    "主題": {"select": {"name": topic}}
                },
                children=[
                    {"heading_2": {"rich_text": [{"text": {"content": "📄 教材全文與解析"}}]}},
                    {"paragraph": {"rich_text": [{"text": {"content": response_text}}]}}
                ]
            )
            st.success("✅ 解析已同步至 Notion 資料庫！")
        except Exception as e:
            st.error(f"Notion 同步失敗: {e}")

# --- 複習提示 ---
st.sidebar.divider()
st.sidebar.info("💡 產出的單字與文法會自動彙整至 Notion，您可以在手機上隨時複習。")
