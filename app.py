{\rtf1\ansi\ansicpg950\cocoartf2868
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import streamlit as st\
import google.generativeai as genai\
import edge_tts\
import asyncio\
import datetime\
from notion_client import Client\
\
# \uc0\u38913 \u38754 \u37197 \u32622 \
st.set_page_config(page_title="\uc0\u23560 \u26989 \u33521 \u35486 \u23416 \u32722 \u31449 ", layout="wide")\
\
# \uc0\u23433 \u20840 \u35712 \u21462 \u37329 \u38000 \
try:\
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]\
    NOTION_DB_ID = st.secrets["NOTION_DB_ID"]\
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]\
    genai.configure(api_key=GEMINI_API_KEY)\
    notion = Client(auth=NOTION_TOKEN)\
except:\
    st.error("\uc0\u35531 \u22312  Secrets \u38913 \u38754 \u35373 \u23450 \u37329 \u38000 \u12290 ")\
\
async def get_audio_bytes(text, voice):\
    communicate = edge_tts.Communicate(text, voice)\
    audio_data = b""\
    async for chunk in communicate.stream():\
        if chunk["type"] == "audio":\
            audio_data += chunk["data"]\
    return audio_data\
\
# \uc0\u24037 \u20316 \u21015 \u35373 \u23450 \
st.sidebar.title("\uc0\u55357 \u57056 \u65039  \u23416 \u32722 \u38754 \u26495 ")\
topic = st.sidebar.selectbox("\uc0\u20027 \u38988 ", ["\u20877 \u29983 \u33021 \u28304 \u24977 \u35657 (T-REC)\u21046 \u24230 ", "\u31934 \u21697 \u21654 \u21857 \u33795 \u21462 \u33287 \u28888 \u28953 ", "\u20225 \u26989 \u32026 \u32178 \u36890 \u33287 Mesh\u26550 \u27083 ", "\u30002 \u34802 (CBF1)\u39164 \u32946 \u25216 \u34899 ", "\u26085 \u26412 \u23478 \u24237 \u33258 \u39381 \u26053 \u36938 "])\
mode = st.sidebar.radio("\uc0\u27169 \u24335 ", ["\u28145 \u24230 \u38321 \u35712  (Article)", "\u24773 \u22659 \u23565 \u35441  (Dialogue)"])\
accent = st.sidebar.selectbox("\uc0\u21475 \u38899 ", ["\u32654 \u22283 \u33108  (US - Aria)", "\u33521 \u22283 \u33108  (UK - Sonia)"])\
voice_map = \{"\uc0\u32654 \u22283 \u33108  (US - Aria)": "en-US-AriaNeural", "\u33521 \u22283 \u33108  (UK - Sonia)": "en-GB-SoniaNeural"\}\
\
st.title(f"\uc0\u55357 \u56534  \{topic\}")\
\
if st.button("\uc0\u55357 \u56613  \u29983 \u25104 \u25945 \u26448 "):\
    with st.spinner("AI \uc0\u32769 \u24107 \u25776 \u23531 \u20013 ..."):\
        model = genai.GenerativeModel('gemini-1.5-flash')\
        prompt = f"""\
        \uc0\u35531 \u37341 \u23565 \u20027 \u38988 \u12302 \{topic\}\u12303 \u20197 \u12302 \{mode\}\u12303 \u27169 \u24335 \u25776 \u23531  150 \u23383 \u36914 \u38542 \u33521 \u25991 \u12290 \u26684 \u24335 \u22914 \u19979 \u65306 \
        ### [English Text]\
        (\uc0\u25991 \u31456 \u20839 \u23481 )\
        ### [\uc0\u20013 \u25991 \u32763 \u35695 ]\
        (\uc0\u32763 \u35695 \u20839 \u23481 )\
        ### [\uc0\u37325 \u40670 \u21934 \u23383 ]\
        1. \uc0\u21934 \u23383  - [\u35422 \u24615 ] - /IPA\u30332 \u38899 (\u21152 \u31895 \u37325 \u38899 \u31526 \u34399 )/ - \u32763 \u35695 \u65306 \u20363 \u21477 \
        (\uc0\u20849 \u19977 \u20491 )\
        ### [\uc0\u37325 \u35201 \u25991 \u27861 ]\
        1. \uc0\u29992 \u27861 \u35498 \u26126 \u65306 \u20363 \u21477 \
        (\uc0\u20849 \u19977 \u20491 )\
        """\
        response = model.generate_content(prompt).text\
        st.markdown(response)\
        \
        # \uc0\u38899 \u27284 \u34389 \u29702 \
        eng_text = response.split("### [\uc0\u20013 \u25991 \u32763 \u35695 ]")[0].replace("### [English Text]", "")\
        audio_data = asyncio.run(get_audio_bytes(eng_text, voice_map[accent]))\
        \
        st.divider()\
        col1, col2 = st.columns([3, 1])\
        with col1: st.audio(audio_data, format="audio/mp3")\
        with col2: st.download_button("\uc0\u55357 \u56549  \u19979 \u36617 \u35486 \u38899 ", data=audio_data, file_name=f"\{topic\}.mp3")\
        \
        # \uc0\u21516 \u27493  Notion\
        notion.pages.create(\
            parent=\{"database_id": NOTION_DB_ID\},\
            properties=\{\
                "\uc0\u21517 \u31281 ": \{"title": [\{"text": \{"content": f"\{topic\} \u31558 \u35352 "\}\}]\},\
                "\uc0\u26085 \u26399 ": \{"date": \{"start": datetime.datetime.now().strftime("%Y-%m-%d")\}\},\
                "\uc0\u20027 \u38988 ": \{"select": \{"name": topic\}\}\
            \},\
            children=[\{"paragraph": \{"rich_text": [\{"text": \{"content": response\}\}]\}\}]\
        )\
        st.balloons()}