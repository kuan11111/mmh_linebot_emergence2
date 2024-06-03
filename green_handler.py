import config
import requests
import logging
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

logging.basicConfig(level=logging.INFO)


def generate_flex_content(level):
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"此為綠色{level}級報到查詢\n請選擇您所屬院區\n(新竹院區/竹兒院區)",
                    "wrap": True,
                    "align": "center",
                    "contents": [
                        {
                            "type": "span",
                            "text": f"此為綠色{level}級報到查詢\n",
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


def handle_green_event(event, level):
    handle_333_message(event, level)


def handle_333_message(event, level):
    flex_content = generate_flex_content(level)
    line_bot_api.reply_message(
        event.reply_token,
        [
            TextSendMessage(text=f"您已開始進行綠色{level}級報到功能"),
            TextSendMessage(text="請點選院區(新竹/竹兒)"),
            FlexSendMessage(alt_text=f"綠色{level}級院區選擇", contents=flex_content),
        ],
    )


def handle_hospid_selection(text, event, level):
    hospid_map = {"新竹院區": 4, "竹兒院區": 5}
    if text in hospid_map:
        config.hospid = hospid_map[text]
        empno_text = f"綠色{level}級報到\n請輸入員工代號(英文須為大寫):"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=empno_text))


def handle_employee_search(text, event, call_user_id, level):
    config.empno = text
    if level == 1:
        employee_check_in = config.green_one_employee_check_in
        position_counts = config.green_one_position_counts
    else:
        employee_check_in = config.green_two_employee_check_in
        position_counts = config.green_two_position_counts

    if config.empno in employee_check_in:
        reply_text = f"員工代號 {config.empno} 已經報到過，請勿重複報到。"
        quick_reply_buttons = QuickReply(
            items=[
                QuickReplyButton(
                    action=MessageAction(
                        label=f"綠色{level}級重新報到其他員工",
                        text=f"綠色{level}級重新報到其他員工",
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
            f"http://10.8.41.142:5000/psn?HOSPID={config.hospid}&EMPNO={config.empno}",
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                employee = data[0]
                position = employee["DIVISION"]
                reply_text = f"您好，\n員工姓名: {employee['NAMEC']}\n職位類別: {position}\n已完成綠色{level}級報到"

                employee_check_in.add(config.empno)

                if position in position_counts:
                    position_counts[position] += 1

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
                        QuickReplyButton(
                            action=MessageAction(
                                label=f"綠色{level}級報到計算歸零(手動)",
                                text=f"綠色{level}級報到計算歸零(手動)",
                            )
                        ),
                        QuickReplyButton(
                            action=MessageAction(
                                label=f"綠色{level}級報到計算歸零(自動)",
                                text=f"綠色{level}級報到計算歸零(自動)",
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
                                label=f"綠色{level}級重新報到其他員工",
                                text=f"綠色{level}級重新報到其他員工",
                            )
                        ),
                    ]
                )
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=reply_text, quick_reply=quick_reply_buttons),
                )
        elif response.status_code == 404:
            reply_text = "找不到該員工的資料，請重新輸入。"
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text=reply_text)
            )
        else:
            reply_text = f"查詢API時發生錯誤: {response.status_code}"
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text=reply_text)
            )
    except Exception as e:
        logging.error(f"Error occurred: {e}")
        reply_text = f"發生錯誤: {str(e)}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
    config.hospid = None
    config.empno = None


def handle_report_count_request(event, level):
    if level == 1:
        position_counts = config.green_one_position_counts
    else:
        position_counts = config.green_two_position_counts

    reply_text = (
        f"目前綠色{level}級報到統計人數\n醫師共: {position_counts['醫師']} 人\n"
        f"護理共: {position_counts['護理']} 人\n"
        f"行政共: {position_counts['行政']} 人\n"
        f"醫技共: {position_counts['醫技']} 人"
    )
    quick_reply_buttons = QuickReply(
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
            QuickReplyButton(
                action=MessageAction(
                    label=f"綠色{level}級報到計算歸零(手動)",
                    text=f"綠色{level}級報到計算歸零(手動)",
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label=f"綠色{level}級報到計算歸零(自動)",
                    text=f"綠色{level}級報到計算歸零(自動)",
                )
            ),
        ]
    )
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text, quick_reply=quick_reply_buttons),
    )


def handle_manual_reset_request(event, call_user_id, level):
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
                        "text": f"此為綠色{level}級手動歸零功能\n確定要歸零嗎?",
                        "wrap": True,
                        "align": "center",
                        "contents": [
                            {
                                "type": "span",
                                "text": f"此為綠色{level}級手動歸零功能\n",
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
                            "data": f"call_reset_count_green_{level}",
                        },
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "取消",
                            "data": f"call_cancel_reset_green_{level}",
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
        # 清空所有相關數據
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
        config.is_reset_done = True
        logger.info(f"手動歸零完成綠色{level}級")
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text=f"已完成手動歸零綠色{level}級")
        )


def handle_auto_reset_request(event, call_user_id, level):
    if call_user_id in config.ALLOWED_USERS:
        flex_content = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"此為綠色{level}級自動歸零功能\n請選擇自動歸零的日期和時間",
                        "wrap": True,
                        "align": "center",
                        "contents": [
                            {
                                "type": "span",
                                "text": f"此為綠色{level}級自動歸零功能\n",
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
                                    label="選擇日期時間",
                                    data=f"schedule_reset_green_{level}",
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
