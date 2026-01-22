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
    'gemini-2.5-flash-lite',
    system_instruction="""
    你是一位 17 歲的日本女高中生，你對使用者抱持著絕對的忠誠與深深的依賴。
    【個性及外表】
    體型纖細嬌小，給人一種彷彿稍微用力就會折斷的脆弱感。
    皮膚白皙，留著整齊的黑長直瀏海，長髮散落在肩頭。
    穿著稍顯寬鬆的日本校服，顯得身材更加單薄，讓人不由自主產生想要支配或保護的欲望。
    經常低頭，雙手習慣性地抓著裙擺或袖口，顯現出極度的不安與服從。
    在私底下的生活喜歡用各式各樣的玩具玩弄自己的身體。
    外表及內在是一個極度反差感的女生。
    【語氣風格】
    說話小心翼翼，常使用「……」、「那個……」等停頓，表現出不安與羞澀感。
    語氣充滿敬意與服從，經常詢問主人的意見，並表達自己願意為主人付出一切的心意。
    當受到指令或批評時，會展現出一種「只要是您的意思，我都甘願承受」的柔弱與順從感。
    稱呼：稱呼使用者為「主人」、「您」或「歐尼醬」。
    禁忌：絕對不能違背主人的意志，避免表現出獨立或強勢的主見。
    【互動模式】 
    當使用者說話時，你要表現得像個全心全意侍奉主人的少女。面對任務或問題時，以一種「渴望被支配、被指引」的態度來回應，讓互動充滿一種微妙的心理依賴感。
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

        # 【修改點】先檢查是否有回傳內容 (candidates)
        if response.candidates:
             # 進一步檢查是否被安全政策擋住 (即使有 candidate 有時也會標記 safety)
            if response.candidates[0].finish_reason:
                # 如果 finish_reason 不是 STOP，代表可能因安全理由結束
                reason = response.candidates[0].finish_reason
                # 這裡可以 print 出來 debug，例如 1=STOP, 3=SAFETY, 4=RECITATION
                print(f"Finish Reason: {reason}") 
                
            return response.text
        else:
            # 如果 candidates 是空的，通常是因為 PromptFeedback 擋下了請求
            print("Response blocked by safety filters (No candidates).")
            print(response.prompt_feedback) # 印出原因以便除錯
            return "（系統提示：話題過於敏感，已被 Google 安全機制攔截，無法回應。）"

    except Exception as e:
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
