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
    """
    尋找帶有語言前綴的區塊，例如 "🇬🇧 英文單字庫"
    """
    full_title = f"{lang_prefix} {title}"
    try:
        results = notion.blocks.children.list(block_id=page_id).get("results", [])
        for block in results:
            if block.get("type") == "callout":
                rich_text = block["callout"]["rich_text"]
                if rich_text and full_title in rich_text[0]["plain_text"]:
                    return block["id"]
        
        # 建立新的語言專屬容器
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
# 側邊欄：控制區 (強化主題與語言分流)
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

# 整合個人興趣與專業領域的主題清單
topic_list = [
    "再生能源", 
    "精品咖啡", 
    "無碳電力", 
    "甲蟲飼育", 
    "AI技術",
    "親子旅遊",
    "其他"
]
topic_choice = st.sidebar.selectbox("📚 文章主題", topic_list)
topic = st.sidebar.text_input("✍️ 自訂主題：") if topic_choice == "其他" else topic_choice

word_count = st.sidebar.slider("文章字數", 100, 600, 300, 50)
speed_choice = st.sidebar.select_slider("語速", options=["慢速", "正常", "快速"], value="正常")
speed_map = {"慢速": "-20%", "正常": "+0%", "快速": "+20%"}
mode = st.sidebar.radio("內容模式", ["閱讀文章 (Reading)", "情境對話 (Dialogue)"])

# =
