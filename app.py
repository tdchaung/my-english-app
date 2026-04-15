import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="引擎掃描模式", layout="wide")

# 讀取金鑰
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error(f"🚨 金鑰讀取錯誤: {e}")
    st.stop()

st.title("🔍 Google AI 引擎掃描器")
st.write("正在連線至 Google 伺服器，查詢您的金鑰目前擁有權限的模型清單...")

try:
    models = []
    # 呼叫 Google 系統，列出所有支援文字生成的模型
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            models.append(m.name)
    
    st.success("✅ 掃描完成！您的金鑰確實支援以下模型：")
    
    # 將清單印在網頁上
    for model_name in models:
        st.code(model_name.replace("models/", "")) # 幫您過濾掉多餘的前綴
        
    st.info("👉 破案關鍵：請看一下畫面上的清單，把帶有 `gemini-1.5` 或 `gemini-pro` 字眼的那個「精確名稱」貼給我（例如它可能會寫 `gemini-1.5-flash-002` 或 `gemini-1.5-flash-8b`）！")
    
except Exception as e:
    st.error(f"❌ 掃描失敗: {e}")
