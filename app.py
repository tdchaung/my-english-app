import streamlit as st
import google.generativeai as genai
from gtts import gTTS
from io import BytesIO
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
# 核心函式：Google 語音生成 (極度穩定版)
# ==========================================
def get_audio_bytes(text, accent_tld):
    # 使用 Google TTS，tld 控制口音 (us=美國, co.uk=英國)
    tts = gTTS(text=text, lang='en', tld=accent_tld)
    fp = BytesIO()
    tts.write_to_fp(fp)
    return fp.getvalue()

# ==========================================
# 側邊欄與介面
# ==========================================
st.sidebar.title("🛠️ 學習設定")
topic = st.sidebar.selectbox("文章主題", ["再生能源", "精品咖啡", "無碳電力", "兜蟲飼育", "親子旅遊", "生活對話"])
mode = st.sidebar.radio("內容模式", ["閱讀文章 (Reading)", "情境對話 (Dialogue)"])
# 改用 Google TTS 支援的口音代碼
accent = st.sidebar.selectbox("口音選擇", ["美國腔 (US)", "英國腔 (UK)"])
voice_map = {"美國腔 (US)": "us", "英國腔 (UK)": "co.uk"}

st.title(f"📖 今日學習：{topic}")

if st.button("🔥 生成教材並開始練習"):
    with st.spinner("AI 老師正在準備內容 ..."):
        try:
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
            response_text = model.generate_content(prompt).text
        except Exception as api_err:
            st.error(f"❌ Gemini API 呼叫失敗！詳細原因：{api_err}")
            st.stop()
        
        # 畫面呈現 (先印出文字)
        st.markdown(response_text)
        
        # ==========================================
        # 語音萃取與播放防護機制
        # ==========================================
        st.divider()
        try:
            # 嚴格過濾：只抓取第一段的英文，並清除 Markdown 符號避免引擎當機
            english_text = response_text.split("### [翻譯]")[0].replace("### [原文]", "").replace("*", "").replace("#", "").strip()
            
            # 生成語音
            audio_data = get_audio_bytes(english_text, voice_map[accent])
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.audio(audio_data, format="audio/mp3")
            with col2:
                st.download_button("📥 下載本篇語音", data=audio_data, file_name=f"{topic}.mp3", mime="audio/mp3")
        except Exception as e:
            st.warning("⚠️ 語音生成暫時無法使用，但文字教材已順利產出。")
        
        # ==========================================
        # 同步至 Notion 
        # ==========================================
        try:
            notion_blocks = [
                {"heading_2": {"rich_text": [{"text": {"content": "📄 教材全文與解析"}}]}}
            ]
            
            for line in response_text.split('\n'):
                if line.strip():  
                    chunks = [line[i:i+1900] for i in range(0, len(line), 1900)]
                    for chunk in chunks:
                        notion_blocks.append({
                            "paragraph": {"rich_text": [{"text": {"content": chunk}}]}
                        })

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
            
        except Exception as e:
            st.error(f"❌ Notion 同步失敗: {e}")
