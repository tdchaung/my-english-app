import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import datetime
from notion_client import Client

st.set_page_config(page_title="專業英語學習發射台", layout="wide")

# ==========================================
# 🛑 嚴格金鑰安檢站 (偵錯專用)
# ==========================================
if "GEMINI_API_KEY" not in st.secrets:
    st.error("🚨 系統找不到『GEMINI_API_KEY』！請至 Advanced Settings -> Secrets 檢查。")
    st.stop()
if "NOTION_TOKEN" not in st.secrets:
    st.error("🚨 系統找不到『NOTION_TOKEN』！請至 Advanced Settings -> Secrets 檢查。")
    st.stop()

# 讀取金鑰並初始化
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
# 核心函式與介面
# ==========================================
async def get_audio_bytes(text, voice):
    communicate = edge_tts.Communicate(text, voice)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

st.sidebar.title("🛠️ 學習設定")
topic = st.sidebar.selectbox("文章主題", ["再生能源", "精品咖啡", "無碳電力", "兜蟲飼育", "親子旅遊", "生活對話"])
mode = st.sidebar.radio("內容模式", ["閱讀文章 (Reading)", "情境對話 (Dialogue)"])
accent = st.sidebar.selectbox("口音選擇", ["美國腔 (US - Aria)", "英國腔 (UK - Sonia)"])
voice_map = {"美國腔 (US - Aria)": "en-US-AriaNeural", "英國腔 (UK - Sonia)": "en-GB-SoniaNeural"}

st.title(f"📖 今日學習：{topic}")

if st.button("🔥 生成教材並開始練習"):
    with st.spinner("AI 老師正在準備內容 ..."):
        try:
            # 使用絕對路徑呼叫最新 Flash 模型
            model = genai.GenerativeModel('gemini-2.5-flash-lite')
            prompt = f"""
            請針對主題『{topic}』，以『{mode}』模式撰寫一段約 300 字的高階英文。
            格式必須精確如下：
            ### [原文]
            (英文原文)
            ### [翻譯]
            (中文翻譯)
            ### [重點單字]
            1. 單字 - [詞性] - /發音與重音/ - 翻譯：例句
            (共三個)
            ### [重要文法]
            1. 用法說明：例句
            (共三個)
            """
            # 若這裡出錯，會在網頁上直接印出紅色錯誤，不再是黑盒子！
            response_text = model.generate_content(prompt).text
        except Exception as api_err:
            st.error(f"❌ Gemini API 呼叫失敗！詳細原因：{api_err}")
            st.stop()
        
        # 語音與畫面呈現
        english_text = response_text.split("### [翻譯]")[0].replace("### [原文]", "")
        audio_data = asyncio.run(get_audio_bytes(english_text, voice_map[accent]))
        
        st.markdown(response_text)
        
        st.divider()
        col1, col2 = st.columns([2, 1])
        with col1:
            st.audio(audio_data, format="audio/mp3")
        with col2:
            st.download_button("📥 下載本篇語音", data=audio_data, file_name=f"{topic}.mp3", mime="audio/mp3")
        
        # 同步至 Notion (含自動分段防護機制)
        # ==========================================
        try:
            # 1. 建立基礎標題
            notion_blocks = [
                {"heading_2": {"rich_text": [{"text": {"content": "📄 教材全文與解析"}}]}}
            ]
            
            # 2. 將長文章依「換行符號」切開，變成多個小段落
            for line in response_text.split('\n'):
                if line.strip():  # 忽略完全空白的行
                    # 預防萬一單行依然超過 2000 字，再進行 1900 字的安全切割
                    chunks = [line[i:i+1900] for i in range(0, len(line), 1900)]
                    for chunk in chunks:
                        notion_blocks.append({
                            "paragraph": {"rich_text": [{"text": {"content": chunk}}]}
                        })

            # 3. 將切好的小段落送進 Notion
            notion.pages.create(
                parent={"database_id": NOTION_DB_ID},
                properties={
                    "名稱": {"title": [{"text": {"content": f"{topic} 學習筆記"}}]},
                    "日期": {"date": {"start": datetime.datetime.now().strftime("%Y-%m-%d")}},
                    "主題": {"select": {"name": topic}}
                },
                children=notion_blocks
            )
            st.success("✅ 解析已成功同步至 Notion！您可以前往手機 App 複習了。")
            st.balloons() # 加上慶祝小動畫
            
        except Exception as e:
            st.error(f"❌ Notion 同步失敗: {e}")
