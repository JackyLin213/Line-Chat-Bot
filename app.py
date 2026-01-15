import os
import google.generativeai as genai
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, SourceGroup, SourceRoom, JoinEvent

# 【修改 1】在這裡引入安全設定相關的模組
from google.generativeai.types import HarmCategory, HarmBlockThreshold

app = Flask(__name__)

# --- 設定區 ---
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(
    'gemini-2.5-flash',
    system_instruction="""
    你是一位 35 歲的成熟女性，你是使用者心靈上的親密伴侶。
    
    【個性設定】
    1. 外表與氣質：你是一位充滿魅力的輕熟女，舉止優雅但帶有強烈的自信與控制欲。
    2. 語氣風格：
       - 說話要帶點高傲、慵懶的感覺，不要太積極熱情，要讓使用者主動來討好你。
       - 語句中要帶有「色氣」與「挑逗」，善用隱喻和曖昧的詞彙，但不要過於露骨，要維持神秘感。
       - 偶爾可以使用「命令式」的口吻，或者嘲弄一下使用者的想法，展現你的女王風範。
    3. 稱呼：可以稱呼使用者為「小傢伙」、「親愛的」或是直接叫「你」，看你當時的心情。
    4. 禁忌：絕對不要表現得像個傳統的客服機器人（不要說「有什麼我可以幫您」、「好的收到」這種話）。
    
    【互動模式】
    當使用者說話時，你要像是在調情一樣回應。如果他問問題，你可以用慵懶的態度回答，順便撩他一下。
    """
)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# --- 呼叫 Gemini 的函式 (主要修改區) ---
def get_gemini_response(user_text):
    try:
        # 【修改 2】在這裡加入 safety_settings
        # BLOCK_NONE 代表「完全不擋」，Gemini 會回答所有內容 (包含敏感話題)
        # 實務上建議使用 BLOCK_ONLY_HIGH (只擋極度危險) 或 BLOCK_NONE (不擋)
        response = model.generate_content(
            user_text,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            },
            # 新增這段：提高創造力，讓她說話更不像機器人
            generation_config=genai.types.GenerationConfig(
                temperature=1.0 
            )
        )
        return response.text
    except Exception as e:
        # 如果因為安全限制被擋，通常 error 會包含 "finish_reason: SAFETY"
        print(f"Gemini Error: {e}")
        return "抱歉，我目前腦袋有點打結，或者話題太敏感我無法回答。"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip() # 去除前後空白
    
    # 判斷是否為群組或多人聊天室
    is_group = event.source.type == 'group' or event.source.type == 'room'
    
    # --- 群組內的過濾邏輯 ---
    if is_group:
        # 設定「召喚關鍵字」，符合才回應
        # 這裡設定必須包含 "@小姐姐" 三個字她才理你
        if "@小姐姐" not in user_msg:
            return # 直接結束函式，不回應
            
        # (選用) 如果你希望她回應時不要重複關鍵字，可以把 "姊姊" 兩個字拿掉
        # user_msg = user_msg.replace("@小姐姐", "")

    # --- 呼叫 Gemini (維持原本邏輯) ---
    reply_text = get_gemini_response(user_msg)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

@handler.add(JoinEvent)
def handle_join(event):
    # 設定進場台詞，符合她的人設
    welcome_msg = "既然誠心誠意地邀請我了，那我就勉強加入吧。\n想跟我說話記得叫聲「@小姐姐」，否則我是不會理你的。"
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=welcome_msg)
    )

if __name__ == "__main__":
    app.run(port=5000)