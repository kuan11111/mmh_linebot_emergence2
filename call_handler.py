import config
import requests
from linebot.models import (
    TextSendMessage,
    FlexSendMessage,
    QuickReply,
    QuickReplyButton,
    MessageAction,
    DatetimePickerAction,
)
from linebot import LineBotApi

line_bot_api = LineBotApi(config.LINE_CHANNEL_ACCESS_TOKEN)


def handle_333_message(event):
    hospid_text = "請點選院區(新竹/竹兒)"
    flex_content = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "此為333召集報到查詢\n請選擇您所屬院區\n(新竹院區/竹兒院區)",
                    "wrap": True,
                    "align": "center",
                    "contents": [
                        {
                            "type": "span",
                            "text": "此為333召集報到查詢\n",
                            "color": "#D70000",
                        },
                        {
                            "type": "span",
                            "text": "請選擇您所屬院區\n(新竹院區/竹兒院區)",
                        },
                    ],
                }
            ],
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "message",
                        "label": "新竹院區",
                        "text": "新竹院區",
                    },
                },
                {
                    "type": "button",
                    "action": {
                        "type": "message",
                        "label": "竹兒院區",
                        "text": "竹兒院區",
                    },
                },
            ],
        },
    }
    line_bot_api.reply_message(
        event.reply_token,
        [
            TextSendMessage(text="您已開始進行333大量傷患報到功能"),
            TextSendMessage(text=hospid_text),
            FlexSendMessage(alt_text="333_院區選擇", contents=flex_content),
        ],
    )


def handle_hospid_selection(text, event):
    hospid_map = {"新竹院區": 4, "竹兒院區": 5}
    if text in hospid_map:
        config.hospid = hospid_map[text]
        empno_text = "333大量傷患報到\n請輸入員工代號(英文須為大寫):"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=empno_text))


def handle_employee_search(text, event, call_user_id):
    config.empno = text

    # 檢查是否已經報到過
    if config.empno in config.call_employee_check_in:
        reply_text = f"員工代號 {config.empno} 已經報到過，請勿重複報到。"
        quick_reply_buttons = QuickReply(
            items=[
                QuickReplyButton(
                    action=MessageAction(
                        label="333重新報到其他員工",
                        text="333重新報到其他員工",
                    )
                ),
            ]
        )

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text, quick_reply=quick_reply_buttons),
        )
        return

    try:
        response = requests.get(
            f"http://10.8.41.142:5000/psn?HOSPID={config.hospid}&EMPNO={config.empno}"
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                employee = data[0]
                position = employee["DIVISION"]
                reply_text = f"您好，\n員工姓名: {employee['NAMEC']}\n職位類別: {position}\n已完成333大量傷患報到"

                # 記錄報到
                config.call_employee_check_in.add(config.empno)

                if position in config.call_position_counts:
                    config.call_position_counts[position] += 1

                if call_user_id not in config.call_user_reports:
                    config.call_user_reports[call_user_id] = {
                        "行政": 0,
                        "護理": 0,
                        "醫師": 0,
                        "醫技": 0,
                    }
                if position in config.call_user_reports[call_user_id]:
                    config.call_user_reports[call_user_id][position] += 1

                quick_reply_buttons = QuickReply(
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
                        QuickReplyButton(
                            action=MessageAction(
                                label="333報到計算歸零(手動)",
                                text="333報到計算歸零(手動)",
                            )
                        ),
                        QuickReplyButton(
                            action=MessageAction(
                                label="333報到計算歸零(自動)",
                                text="333報到計算歸零(自動)",
                            )
                        ),
                    ]
                )
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=reply_text, quick_reply=quick_reply_buttons),
                )
            else:
                reply_text = "找不到該員工的資料，請重新輸入。"
                quick_reply_buttons = QuickReply(
                    items=[
                        QuickReplyButton(
                            action=MessageAction(
                                label="333重新報到其他員工",
                                text="333重新報到其他員工",
                            )
                        ),
                    ]
                )
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=reply_text, quick_reply=quick_reply_buttons),
                )
        else:
            reply_text = "查詢API時發生錯誤。"
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text=reply_text)
            )
    except Exception as e:
        reply_text = f"發生錯誤: {str(e)}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
    config.hospid = None  # 重置hospid以便下一次查詢
    config.empno = None  # 重置empno以便下一次查詢


def handle_report_count_request(event):
    reply_text = (
        f"目前333召集報到統計人數\n醫師共: {config.call_position_counts['醫師']} 人\n"
        f"護理共: {config.call_position_counts['護理']} 人\n"
        f"行政共: {config.call_position_counts['行政']} 人\n"
        f"醫技共: {config.call_position_counts['醫技']} 人"
    )
    quick_reply_buttons = QuickReply(
        items=[
            QuickReplyButton(
                action=MessageAction(
                    label="333重新報到其他員工", text="333重新報到其他員工"
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="333目前回報總人數", text="333目前回報總人數"
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="333報到計算歸零(手動)", text="333報到計算歸零(手動)"
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="333報到計算歸零(自動)", text="333報到計算歸零(自動)"
                )
            ),
        ]
    )
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text, quick_reply=quick_reply_buttons),
    )


def handle_manual_reset_request(event, call_user_id):
    if call_user_id in config.ALLOWED_USERS:
        reply_text = (
            "此為特定管理者使用，一旦歸零則所有使用者必須重新報到並重新計算人數"
        )
        flex_content = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "此為333手動歸零功能\n確定要歸零嗎?",
                        "wrap": True,
                        "align": "center",
                        "contents": [
                            {
                                "type": "span",
                                "text": "此為333手動歸零功能\n",
                                "color": "#D70000",
                            },
                            {
                                "type": "span",
                                "text": "確定要歸零嗎?",
                            },
                        ],
                    }
                ],
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "確定",
                            "data": "confirm_manual_reset",
                        },
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "取消",
                            "data": "call_cancel_reset",
                        },
                    },
                ],
            },
        }
        line_bot_api.reply_message(
            event.reply_token,
            [
                TextSendMessage(text=reply_text),
                FlexSendMessage(alt_text="確認歸零", contents=flex_content),
            ],
        )
    else:
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text="您沒有權限使用此功能。")
        )


def handle_auto_reset_request(event, call_user_id):
    if call_user_id in config.ALLOWED_USERS:
        flex_content = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "此為自動歸零功能\n請選擇自動歸零的日期和時間",
                        "wrap": True,
                        "align": "center",
                        "contents": [
                            {
                                "type": "span",
                                "text": "此為自動歸零功能\n",
                                "color": "#D70000",
                            },
                            {
                                "type": "span",
                                "text": "請選擇自動歸零的日期和時間",
                            },
                        ],
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "button",
                                "action": DatetimePickerAction(
                                    label="選擇日期和時間",
                                    data="schedule_reset",
                                    mode="datetime",
                                ),
                            },
                        ],
                    },
                ],
            },
        }
        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(alt_text="選擇自動歸零時間", contents=flex_content),
        )
    else:
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text="您沒有權限使用此功能。")
        )
