import os
import warnings
import json
import logging
import threading
from datetime import datetime, timezone, timedelta
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    PostbackEvent,
    QuickReply,
    QuickReplyButton,
    MessageAction,
    PostbackAction,
)
import pytz
import requests

import config  # 引入配置文件
import call_handler as my_handler  # 引入處理函數模塊並改名為 my_handler
import green_handler

# 檢查環境變量是否已設置
if not all([config.LINE_CHANNEL_ACCESS_TOKEN, config.LINE_CHANNEL_SECRET]):
    raise ValueError("One或more LINE Channel environment variables are not set.")

# 創建 Flask 應用
app = Flask(__name__)

# 設置日誌記錄
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 創建 LineBotApi 和 WebhookHandler 實例
line_bot_api = LineBotApi(config.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(config.LINE_CHANNEL_SECRET)


# 保存重置時間到文件
def save_reset_time(reset_time):
    with open(config.RESET_TIME_FILE, "w") as f:
        f.write(reset_time)


# 從文件加載重置時間
def load_reset_time():
    if os.path.exists(config.RESET_TIME_FILE):
        with open(config.RESET_TIME_FILE, "r") as f:
            return f.read().strip()
    return None


# 設置重置計劃
def schedule_reset(datetime_str, level=None):
    try:
        taiwan_tz = pytz.timezone("Asia/Taipei")
        local_reset_time = taiwan_tz.localize(datetime.fromisoformat(datetime_str))
        reset_time = local_reset_time.astimezone(timezone.utc)
        save_reset_time(reset_time.isoformat())
        delay = (reset_time - datetime.now(timezone.utc)).total_seconds()
        if delay > 0:
            logger.info(
                f"Scheduling a reset at {reset_time} UTC, which is in {delay} seconds."
            )
            if level:
                config.scheduled_reset_timer = threading.Timer(
                    delay,
                    lambda: line_bot_api.push_message(
                        config.ALLOWED_USERS[0], reset_counts(level)
                    ),
                )
            else:
                config.scheduled_reset_timer = threading.Timer(
                    delay,
                    lambda: line_bot_api.push_message(
                        config.ALLOWED_USERS[0], reset_counts()
                    ),
                )
            config.scheduled_reset_timer.start()
        else:
            logger.warning(
                f"Scheduled time {reset_time} is in the past. No action taken."
            )
    except Exception as e:
        logger.error(f"Error scheduling reset: {str(e)}")


# 重置計數
def reset_counts(level=None):
    now = datetime.now(timezone.utc)
    reset_time_str = load_reset_time()
    if reset_time_str:
        reset_time = datetime.fromisoformat(reset_time_str)
        if now >= reset_time:
            # 確保清空統計數據並重置標志位
            if level == 1:
                config.green_one_position_counts = {
                    "行政": 0,
                    "護理": 0,
                    "醫師": 0,
                    "醫技": 0,
                }
                config.green_one_employee_check_in.clear()
            elif level == 2:
                config.green_two_position_counts = {
                    "行政": 0,
                    "護理": 0,
                    "醫師": 0,
                    "醫技": 0,
                }
                config.green_two_employee_check_in.clear()
            else:
                config.call_position_counts = {
                    "行政": 0,
                    "護理": 0,
                    "醫師": 0,
                    "醫技": 0,
                }
                config.call_employee_check_in.clear()  # 清空已報到的員工代號記錄

            config.is_reset_done = True  # 設置歸零完成標志
            logger.info("自動歸零完成")

            save_reset_time("")  # 清空已完成的自動歸零時間
            config.is_reset_done = False  # 重置標志位，允許新的歸零操作

            # 返回用於確定歸零的文本消息
            if level:
                return TextSendMessage(text=f"已完成綠色{level}級自動歸零")
            else:
                return TextSendMessage(text="已完成自動歸零")
    else:
        logger.warning("沒有設置重置時間或時間未到")
        return None


# 取消已設置的重置計劃
def cancel_scheduled_reset():
    if config.scheduled_reset_timer is not None:
        config.scheduled_reset_timer.cancel()
        config.scheduled_reset_timer = None
        save_reset_time("")  # 清空已設定的自動歸零時間
        logger.info("已取消自動歸零")


# 處理 LINE Webhook 回調
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    if signature is None:
        logger.error("Missing X-Line-Signature")
        abort(400, "Missing X-Line-Signature")

    body = request.get_data(as_text=True)
    logger.info("Request body: " + body)
    logger.info("X-Line-Signature: " + signature)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        abort(400, "Invalid signature")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        abort(400, "Error handling request")

    return "OK"


# 處理收到的消息
def process_message(text, event, call_user_id):
    # 333相關消息處理
    if text in ["333大量傷患召回報到", "333重新報到其他員工"]:
        config.current_mode = "333"
        my_handler.handle_333_message(event)
    elif text == "333目前回報總人數":
        my_handler.handle_report_count_request(event)
    elif text == "333報到計算歸零(手動)":
        my_handler.handle_manual_reset_request(event, call_user_id)
    elif text == "333報到計算歸零(自動)":
        my_handler.handle_auto_reset_request(event, call_user_id)

    # 綠色級別相關消息處理
    if text in ["綠色一級回覆", "綠色1級重新報到其他員工"]:
        config.current_mode = "green_1"
        green_handler.handle_green_event(event, 1)
    elif text in ["綠色二級回覆", "綠色2級重新報到其他員工"]:
        config.current_mode = "green_2"
        green_handler.handle_green_event(event, 2)
    elif text == "綠色1級目前回報總人數":
        green_handler.handle_report_count_request(event, 1)
    elif text == "綠色2級目前回報總人數":
        green_handler.handle_report_count_request(event, 2)
    elif text == "綠色1級報到計算歸零(手動)":
        green_handler.handle_manual_reset_request(event, call_user_id, 1)
    elif text == "綠色2級報到計算歸零(手動)":
        green_handler.handle_manual_reset_request(event, call_user_id, 2)
    elif text == "綠色1級報到計算歸零(自動)":
        green_handler.handle_auto_reset_request(event, call_user_id, 1)
    elif text == "綠色2級報到計算歸零(自動)":
        green_handler.handle_auto_reset_request(event, call_user_id, 2)

    # 處理醫院選擇
    if text in ["新竹院區", "竹兒院區"]:
        if config.current_mode == "333":
            my_handler.handle_hospid_selection(text, event)
        elif config.current_mode == "green_1":
            green_handler.handle_hospid_selection(text, event, 1)
        elif config.current_mode == "green_2":
            green_handler.handle_hospid_selection(text, event, 2)
    elif text.isalnum() and config.hospid is not None:
        if config.current_mode == "333":
            my_handler.handle_employee_search(text, event, call_user_id)
        elif config.current_mode == "green_1":
            green_handler.handle_employee_search(text, event, call_user_id, 1)
        elif config.current_mode == "green_2":
            green_handler.handle_employee_search(text, event, call_user_id, 2)


# 處理收到的 TextMessage 事件
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text
    call_user_id = event.source.user_id

    logger.info(f"Received message from user_id: {call_user_id}, message: {text}")

    process_message(text, event, call_user_id)


# 處理 postback 數據
def process_postback(data, event, call_user_id):
    # 333_quick_reply
    quick_reply_buttons_call = QuickReply(
        items=[
            QuickReplyButton(
                action=MessageAction(
                    label="333重新報到其他員工",
                    text="333重新報到其他員工",
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="333目前回報總人數", text="333目前回報總人數"
                )
            ),
        ]
    )

    # 333手動歸零
    if data == "confirm_manual_reset" and call_user_id in config.ALLOWED_USERS:
        # 清空所有相關數據
        if len(config.call_employee_check_in) == 0:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="已經歸零，請勿重複點選。"),
            )
        else:
            config.call_position_counts = {"行政": 0, "護理": 0, "醫師": 0, "醫技": 0}
            config.call_employee_check_in.clear()
            config.is_reset_done = True  # 設置歸零完成標志

            line_bot_api.reply_message(
                event.reply_token,
                [
                    TextSendMessage(text="確定歸零"),
                    TextSendMessage(text="已完成歸零。"),
                ],
            )
            logger.info("手動歸零已完成")

    elif data == "call_cancel_reset" and call_user_id in config.ALLOWED_USERS:
        if len(config.call_employee_check_in) == 0:
            # 處理空值情況
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="已經歸零，無法取消。", quick_reply=quick_reply_buttons_call
                ),
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="已取消333歸零", quick_reply=quick_reply_buttons_call
                ),
            )

    elif data == "schedule_reset" and call_user_id in config.ALLOWED_USERS:
        reset_time = event.postback.params["datetime"]
        logger.info(f"Received schedule reset request for {reset_time}")
        schedule_reset(reset_time)
        cancel_quick_reply = QuickReply(
            items=[
                QuickReplyButton(
                    action=PostbackAction(
                        label="取消自動歸零",
                        data="cancel_schedule_reset",
                    )
                ),
            ]
        )
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f"已設定自動歸零時間為 {reset_time}",
                quick_reply=cancel_quick_reply,
            ),
        )
    elif data == "cancel_schedule_reset":
        cancel_scheduled_reset()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="已取消自動歸零設定", quick_reply=quick_reply_buttons_call
            ),
        )

    # 定義一個函數來生成 quick reply 按鈕
    def generate_quick_reply_buttons(level):
        return QuickReply(
            items=[
                QuickReplyButton(
                    action=MessageAction(
                        label=f"綠色{level}級重新報到其他員工",
                        text=f"綠色{level}級重新報到其他員工",
                    )
                ),
                QuickReplyButton(
                    action=MessageAction(
                        label=f"綠色{level}級目前回報總人數",
                        text=f"綠色{level}級目前回報總人數",
                    )
                ),
            ]
        )

    # 在處理綠色級別歸零的地方使用這個函數
    if (
        data.startswith("call_reset_count_green_")
        and call_user_id in config.ALLOWED_USERS
    ):
        level = int(data.split("_")[-1])
        if len(config.green_one_employee_check_in) == 0:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="已經歸零，請勿重複點選。")
            )
        else:
            # 確保清空統計數據並重置標志位
            if level == 1:
                config.green_one_position_counts = {
                    "行政": 0,
                    "護理": 0,
                    "醫師": 0,
                    "醫技": 0,
                }
                config.green_one_employee_check_in.clear()
                line_bot_api.reply_message(
                    event.reply_token,
                    [
                        TextSendMessage(text="確定歸零"),
                        TextSendMessage(text="已完成歸零。"),
                    ],
                )
            elif level == 2:
                config.green_two_position_counts = {
                    "行政": 0,
                    "護理": 0,
                    "醫師": 0,
                    "醫技": 0,
                }
                config.green_two_employee_check_in.clear()
                line_bot_api.reply_message(
                    event.reply_token,
                    [
                        TextSendMessage(text="確定歸零"),
                        TextSendMessage(text="已完成歸零。"),
                    ],
                )
            config.is_reset_done = True  # 設置歸零完成標志

            reply_message = reset_counts(level)
            line_bot_api.reply_message(event.reply_token, reply_message)
            logger.info(f"自動歸零已完成: 綠色{level}級")

    elif data.startswith("call_cancel_reset_green_"):
        level = int(data.split("_")[-1])
        if len(config.green_one_employee_check_in) == 0:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="已經歸零，無法取消。")
            )
        else:
            cancel_scheduled_reset()
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"已取消綠色{level}級歸零",
                    quick_reply=generate_quick_reply_buttons(level),
                ),
            )
    elif (
        data.startswith("schedule_reset_green_")
        and call_user_id in config.ALLOWED_USERS
    ):
        level = int(data.split("_")[-1])
        reset_time = event.postback.params["datetime"]
        logger.info(
            f"Received schedule reset request for green level {level} at {reset_time}"
        )
        schedule_reset(reset_time, level)
        cancel_quick_reply = QuickReply(
            items=[
                QuickReplyButton(
                    action=PostbackAction(
                        label="取消自動歸零",
                        data=f"cancel_schedule_reset_green_{level}",
                    )
                ),
            ]
        )
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f"已設定綠色{level}級自動歸零時間為 {reset_time}",
                quick_reply=cancel_quick_reply,
            ),
        )
    elif data.startswith("cancel_schedule_reset_green_"):
        level = int(data.split("_")[-1])
        if config.is_reset_done:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="已經歸零，無法取消。")
            )
        elif data == f"cancel_schedule_reset_green_{level}":
            cancel_scheduled_reset()
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"已取消綠色{level}級自動歸零設定",
                    quick_reply=generate_quick_reply_buttons(level),
                ),
            )


# 處理收到的 Postback 事件
@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    call_user_id = event.source.user_id

    process_postback(data, event, call_user_id)


# 主程序入口
if __name__ == "__main__":
    reset_time_str = load_reset_time()
    if reset_time_str:
        schedule_reset(reset_time_str)
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
