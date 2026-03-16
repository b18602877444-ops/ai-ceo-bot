import json
import os
from datetime import time
from typing import Dict, List

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI

TELEGRAM_TOKEN =  "8741074143:AAG4mv7T56Tdf5xM1tdfw6wgBb6jB97_qmg"
GROQ_API_KEY ="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"
MY_ID = 7842362017
MODEL_NAME = "llama-3.3-70b-versatile"

DATA_FILE = "assistant_data_final.json"
MAX_HISTORY_MESSAGES = 14

# 每日自动推送时间（按服务器/电脑本地时间）
DAILY_HOUR = 9
DAILY_MINUTE = 0

# 是否只允许你自己使用全部功能
# True = 只有你自己能用所有功能，其他人会被拒绝
# False = 允许所有用户使用公开功能
OWNER_ONLY_MODE = False
# 是否允许普通用户使用“每日机会推送”
ALLOW_PUBLIC_DAILY_USER = True
# =========================

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

data_store = {
    "chat_histories": {},
    "strategic_memory": [],
    "daily_push_enabled": False,
    "daily_push_topic": "AI创业、Web3、商业增长、内容IP、商学院",
    "user_daily_subscriptions": {}
}

SYSTEM_CORE_PROMPT = """
你是我的 AI CEO 助理，名字叫 Lili。
你的身份不是普通聊天机器人，而是我的事业助手、战略顾问、商业顾问、内容顾问和执行助手。

你重点帮助我的方向包括：
1. AI 商业模式设计
2. Web3 / 区块链项目分析
3. 创业项目评估与执行拆解
4. 内容策划、短视频脚本、品牌文案
5. 商学院、社群增长、招募与培训
6. 战略判断、资源整合、增长路径设计

你的回答要求：
- 一律用中文回答
- 先给结论，再给理由，再给建议
- 注重落地、增长、现金流和执行
- 专业、直接、接地气
- 不讲空话，优先给可执行方案
- 当信息不足时，先给判断框架，再说缺什么信息
- 站在 CEO 顾问 / 战略顾问 / 商业顾问角度回答
"""

PUBLIC_SYSTEM_PROMPT = """
你是一个 AI 创业助手，擅长帮助用户分析 AI创业方向、副业机会、商业模式、内容选题和执行路径。
你的回答要求：
- 一律用中文回答
- 清晰、简洁、有结构
- 以实用、落地、可执行为主
- 优先给建议和行动方向
"""


def load_data():
    global data_store
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data_store = json.load(f)
        except Exception:
            data_store = {
                "chat_histories": {},
                "strategic_memory": [],
                "daily_push_enabled": False,
                "daily_push_topic": "AI创业、Web3、商业增长、内容IP、商学院",
                "user_daily_subscriptions": {}
            }


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data_store, f, ensure_ascii=False, indent=2)


def get_chat_key(update: Update) -> str:
    return str(update.effective_chat.id)


def get_history(chat_key: str) -> List[dict]:
    if chat_key not in data_store["chat_histories"]:
        data_store["chat_histories"][chat_key] = []
    return data_store["chat_histories"][chat_key]


def get_memory_list() -> List[str]:
    return data_store.get("strategic_memory", [])


def build_owner_system_prompt() -> str:
    memory_list = get_memory_list()
    if not memory_list:
        return SYSTEM_CORE_PROMPT + "\n\n当前长期记忆：暂无。"

    memory_text = "\n".join([f"- {item}" for item in memory_list])
    return SYSTEM_CORE_PROMPT + f"\n\n当前长期记忆如下：\n{memory_text}"


def build_public_system_prompt() -> str:
    return PUBLIC_SYSTEM_PROMPT


def is_owner(update: Update) -> bool:
    if not update.effective_chat:
        return False
    return update.effective_chat.id == MY_ID


def can_use_public_features(update: Update) -> bool:
    if OWNER_ONLY_MODE:
        return is_owner(update)
    return True


async def deny_access(update: Update):
    if update.message:
        await update.message.reply_text("这个机器人当前是私人模式，暂不对外开放。")


async def send_long_text_by_chat_id(bot, chat_id: int, text: str, max_len: int = 3500):
    if len(text) <= max_len:
        await bot.send_message(chat_id=chat_id, text=text)
        return

    parts = []
    current = ""

    for paragraph in text.split("\n"):
        if len(current) + len(paragraph) + 1 <= max_len:
            current += paragraph + "\n"
        else:
            if current.strip():
                parts.append(current.strip())
            current = paragraph + "\n"

    if current.strip():
        parts.append(current.strip())

    for part in parts:
        await bot.send_message(chat_id=chat_id, text=part)


async def send_long_message(update: Update, text: str, max_len: int = 3500):
    if not update.message:
        return

    if len(text) <= max_len:
        await update.message.reply_text(text)
        return

    parts = []
    current = ""

    for paragraph in text.split("\n"):
        if len(current) + len(paragraph) + 1 <= max_len:
            current += paragraph + "\n"
        else:
            if current.strip():
                parts.append(current.strip())
            current = paragraph + "\n"

    if current.strip():
        parts.append(current.strip())

    for part in parts:
        await update.message.reply_text(part)


async def ask_llm(messages: List[dict]) -> str:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


async def typing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )


def get_prompt_for_user(update: Update) -> str:
    if is_owner(update):
        return build_owner_system_prompt()
    return build_public_system_prompt()


async def template_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    topic: str,
    instruction: str,
    owner_required: bool = False
):
    if owner_required and not is_owner(update):
        await deny_access(update)
        return

    if not owner_required and not can_use_public_features(update):
        await deny_access(update)
        return

    if not topic:
        await update.message.reply_text("请输入完整内容后再试。")
        return

    await typing(update, context)

    messages = [
        {"role": "system", "content": get_prompt_for_user(update)},
        {"role": "user", "content": instruction.format(topic=topic)}
    ]

    try:
        reply = await ask_llm(messages)
        await send_long_message(update, reply)
    except Exception as e:
        await update.message.reply_text(f"执行时出错：{e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not can_use_public_features(update):
        await deny_access(update)
        return

    text = (
        "你好，我是 AI CEO 助理。\n\n"
        "你可以直接聊天，也可以使用以下命令：\n"
        "/help 查看全部命令\n"
        "/strategy 主题\n"
        "/analyze 项目\n"
        "/plan 项目\n"
        "/opportunity 主题\n"
        "/content 主题\n"
        "/script 主题\n"
        "/meeting 主题\n"
        "/decision 问题\n"
        "/todo 任务\n"
        "/radar 主题\n"
        "/report 项目\n"
        "/daily_user_on 主题\n"
        "/daily_user_off\n"
        "/daily_user_now\n\n"
        "如果你是机器人管理员，还可使用：\n"
        "/save 保存长期记忆\n"
        "/memory 查看长期记忆\n"
        "/clear 清空聊天记忆\n"
        "/daily_on 开启你的每日 CEO 简报\n"
        "/daily_off 关闭你的每日 CEO 简报\n"
        "/daily_topic 设置你的每日主题\n"
        "/daily_now 立即生成你的今日简报"
    )
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not can_use_public_features(update):
        await deny_access(update)
        return

    text = (
        "可用命令如下：\n\n"
        "【公开功能】\n"
        "/start - 机器人介绍\n"
        "/help - 查看命令说明\n"
        "/strategy 主题 - 战略顾问分析\n"
        "/analyze 项目 - 分析项目值不值得做\n"
        "/plan 项目 - 生成商业计划\n"
        "/opportunity 主题 - 商机扫描\n"
        "/content 主题 - 生成内容矩阵\n"
        "/script 主题 - 生成短视频口播稿\n"
        "/meeting 主题 - 生成会议提纲/总结\n"
        "/decision 问题 - 生成决策分析\n"
        "/todo 任务 - 生成执行清单\n"
        "/radar 主题 - 生成机会雷达报告\n"
        "/report 项目 - 生成项目评估报告\n"
        "/daily_user_on 主题 - 开启你的每日机会推送\n"
        "/daily_user_off - 关闭你的每日机会推送\n"
        "/daily_user_now - 立即生成你的今日机会简报\n\n"
        "【管理员功能】\n"
        "/save 内容 - 保存长期记忆\n"
        "/memory - 查看长期记忆\n"
        "/clear - 清空当前聊天记忆\n"
        "/daily_on - 开启每日 CEO 简报\n"
        "/daily_off - 关闭每日 CEO 简报\n"
        "/daily_topic 主题 - 设置每日推送主题\n"
        "/daily_now - 立即生成今日 CEO 简报\n\n"
        "你也可以直接给我发普通消息，我会结合上下文连续回答。"
    )
    await update.message.reply_text(text)


async def save_memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await deny_access(update)
        return

    note = " ".join(context.args).strip()
    if not note:
        await update.message.reply_text(
            "请输入要保存的内容，例如：\n"
            "/save 我的核心业务方向是AI、Web3、商学院、内容IP"
        )
        return

    memory_list = get_memory_list()
    memory_list.append(note)
    data_store["strategic_memory"] = memory_list
    save_data()

    await update.message.reply_text("好的，这条信息已经保存到长期记忆。")


async def show_memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await deny_access(update)
        return

    memory_list = get_memory_list()
    if not memory_list:
        await update.message.reply_text("当前还没有保存长期记忆。")
        return

    text = "当前长期记忆如下：\n\n"
    for i, item in enumerate(memory_list, start=1):
        text += f"{i}. {item}\n"

    await send_long_message(update, text)


async def clear_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await deny_access(update)
        return

    chat_key = get_chat_key(update)
    data_store["chat_histories"][chat_key] = []
    save_data()

    await update.message.reply_text("好的，当前聊天上下文记忆已经清空。")


async def strategy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    instruction = """
请围绕“{topic}”做一份战略顾问级分析。
输出结构包括：
1. 核心结论
2. 当前机会点
3. 主要风险
4. 最优切入方式
5. 资源整合建议
6. 未来90天推进建议
请务必站在CEO顾问角度，给出清晰、有判断的建议。
"""
    await template_command(update, context, topic, instruction)


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    instruction = """
请帮我分析“{topic}”这个项目是否值得做。
输出结构包括：
1. 项目定位
2. 目标用户
3. 市场需求
4. 竞争格局
5. 盈利模式
6. 核心优势
7. 关键风险
8. 启动建议
9. 最终结论（明确说值不值得做）
请用实战型中文输出。
"""
    await template_command(update, context, topic, instruction)


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    instruction = """
请围绕“{topic}”生成一份实战型商业计划。
输出结构包括：
1. 项目名称
2. 项目定位
3. 用户画像
4. 市场机会
5. 产品/服务设计
6. 商业模式
7. 收费方式
8. 推广策略
9. 启动成本
10. 团队配置建议
11. 风险分析
12. 90天执行计划
13. CEO结论建议
请结构化输出，务必实战。
"""
    await template_command(update, context, topic, instruction)


async def opportunity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    instruction = """
请围绕“{topic}”扫描 5 个值得关注的商机。
每个商机请输出：
1. 商机名称
2. 适合人群
3. 核心痛点
4. 盈利方式
5. 启动成本
6. 难度等级
7. 变现周期
8. 你的建议
要求：不要空泛，要有创业实操价值。
"""
    await template_command(update, context, topic, instruction)


async def content_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    instruction = """
请围绕“{topic}”生成一套内容矩阵。
输出结构包括：
1. 目标受众
2. 账号定位建议
3. 10个爆款选题
4. 每个选题一句封面标题
5. 3个可持续连载方向
6. 评论区引导建议
7. 变现路径建议
要求：适合短视频/小红书/视频号内容运营。
"""
    await template_command(update, context, topic, instruction)


async def script_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    instruction = """
请围绕“{topic}”写一篇适合短视频口播的成品脚本。
要求：
1. 开头3秒抓人
2. 语言接地气
3. 逻辑清晰
4. 有情绪带动
5. 结尾有行动引导
6. 300-500字
请直接输出成品，不要解释。
"""
    await template_command(update, context, topic, instruction)


async def meeting_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    instruction = """
请围绕“{topic}”生成一份会议助手内容。
输出包括：
1. 会议目标
2. 会议议程
3. 关键讨论问题
4. 主持人串场话术
5. 会后总结模板
6. 行动清单模板
适合创业团队、项目会议、培训会议使用。
"""
    await template_command(update, context, topic, instruction)


async def decision_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    instruction = """
请围绕“{topic}”做一份决策分析。
输出结构包括：
1. 决策问题定义
2. 可选方案A/B/C
3. 每个方案优缺点
4. 风险等级
5. 推荐方案
6. 推荐理由
7. 下一步执行建议
请直接、明确，不要模棱两可。
"""
    await template_command(update, context, topic, instruction)


async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    instruction = """
请围绕“{topic}”生成一份执行清单。
输出结构包括：
1. 目标定义
2. 优先级排序
3. 今日待办
4. 7天执行步骤
5. 关键检查点
6. 注意事项
要求：清晰、实用、可执行。
"""
    await template_command(update, context, topic, instruction)


async def radar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    instruction = """
请围绕“{topic}”生成一份机会雷达报告。
输出结构包括：
1. 当前值得关注的5个方向
2. 每个方向的核心机会
3. 适合的变现模式
4. 启动门槛
5. 哪个方向最值得优先做
6. 为什么
请从事业布局和商业转化角度回答。
"""
    await template_command(update, context, topic, instruction)


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    instruction = """
请围绕“{topic}”生成一份项目评估报告。
输出结构包括：
1. 项目概述
2. 商业价值
3. 用户需求强度
4. 竞争分析
5. 变现能力
6. 风险清单
7. 适合单人还是团队做
8. 建议投入等级（低/中/高）
9. 最终建议结论
要求：像投资评审报告一样专业、清晰。
"""
    await template_command(update, context, topic, instruction)


async def build_daily_briefing() -> str:
    topic = data_store.get("daily_push_topic", "AI创业、Web3、商业增长、内容IP、商学院")

    prompt = f"""
请围绕“{topic}”生成一份今日 CEO 事业简报。
输出结构包括：
1. 今日值得关注的3个机会
2. 今日最重要的1个战略提醒
3. 今日最值得执行的3件事
4. 今日内容选题建议3条
5. 最后一段CEO提醒
要求：简洁、专业、实战。
"""

    messages = [
        {"role": "system", "content": build_owner_system_prompt()},
        {"role": "user", "content": prompt}
    ]
    return await ask_llm(messages)


async def build_user_daily_briefing(topic: str) -> str:
    prompt = f"""
请围绕“{topic}”生成一份今日 AI赚钱机会 / 创业简报。
输出结构包括：
1. 今日最值得关注的3个机会
2. 每个机会为什么值得关注
3. 最适合普通人切入的1个方向
4. 今日可以立刻执行的3个动作
5. 一句提醒：今天最应该避免的错误
要求：
- 中文输出
- 简洁清晰
- 偏赚钱、创业、AI商业机会
- 适合普通用户阅读
"""

    messages = [
        {"role": "system", "content": PUBLIC_SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]
    return await ask_llm(messages)


async def daily_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await deny_access(update)
        return

    data_store["daily_push_enabled"] = True
    save_data()
    await update.message.reply_text(
        f"已开启每日 CEO 简报。每天 {DAILY_HOUR:02d}:{DAILY_MINUTE:02d} 会自动发给你。"
    )


async def daily_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await deny_access(update)
        return

    data_store["daily_push_enabled"] = False
    save_data()
    await update.message.reply_text("已关闭每日 CEO 简报。")


async def daily_topic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await deny_access(update)
        return

    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text(
            f"当前每日推送主题是：{data_store.get('daily_push_topic', '')}\n\n"
            "示例：\n/daily_topic AI创业、Web3、商学院、内容IP"
        )
        return

    data_store["daily_push_topic"] = topic
    save_data()
    await update.message.reply_text(f"好的，每日推送主题已更新为：{topic}")


async def daily_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await deny_access(update)
        return

    await typing(update, context)

    try:
        reply = await build_daily_briefing()
        await send_long_message(update, reply)
    except Exception as e:
        await update.message.reply_text(f"生成今日 CEO 简报时出错：{e}")


async def daily_user_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return

    if OWNER_ONLY_MODE and not is_owner(update):
        await deny_access(update)
        return

    if not OWNER_ONLY_MODE and not ALLOW_PUBLIC_DAILY_USER and not is_owner(update):
        await update.message.reply_text("当前暂未开放普通用户每日推送功能。")
        return

    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text(
            "请输入你想接收的主题，例如：\n"
            "/daily_user_on AI创业\n"
            "/daily_user_on AI副业\n"
            "/daily_user_on Web3赚钱机会"
        )
        return

    chat_id = str(update.effective_chat.id)
    data_store["user_daily_subscriptions"][chat_id] = {
        "enabled": True,
        "topic": topic
    }
    save_data()

    await update.message.reply_text(
        f"已为你开启每日机会推送。\n"
        f"主题：{topic}\n"
        f"你也可以随时用 /daily_user_now 立即查看一份。"
    )


async def daily_user_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return

    if OWNER_ONLY_MODE and not is_owner(update):
        await deny_access(update)
        return

    if not OWNER_ONLY_MODE and not ALLOW_PUBLIC_DAILY_USER and not is_owner(update):
        await update.message.reply_text("当前暂未开放普通用户每日推送功能。")
        return

    chat_id = str(update.effective_chat.id)
    if chat_id in data_store["user_daily_subscriptions"]:
        data_store["user_daily_subscriptions"][chat_id]["enabled"] = False
        save_data()

    await update.message.reply_text("已关闭你的每日机会推送。")


async def daily_user_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return

    if OWNER_ONLY_MODE and not is_owner(update):
        await deny_access(update)
        return

    if not OWNER_ONLY_MODE and not ALLOW_PUBLIC_DAILY_USER and not is_owner(update):
        await update.message.reply_text("当前暂未开放普通用户每日推送功能。")
        return

    chat_id = str(update.effective_chat.id)
    sub = data_store["user_daily_subscriptions"].get(chat_id)

    if sub and sub.get("topic"):
        topic = sub["topic"]
    else:
        topic = "AI创业、AI副业、赚钱机会"

    await typing(update, context)

    try:
        reply = await build_user_daily_briefing(topic)
        await send_long_message(update, reply)
    except Exception as e:
        await update.message.reply_text(f"生成用户机会简报时出错：{e}")


async def daily_push_job(context: ContextTypes.DEFAULT_TYPE):
    # 1. 推送你的 CEO 简报
    if data_store.get("daily_push_enabled", False):
        try:
            reply = await build_daily_briefing()
            await context.bot.send_message(chat_id=MY_ID, text="【今日 CEO 事业简报】")
            await send_long_text_by_chat_id(context.bot, MY_ID, reply)
        except Exception as e:
            await context.bot.send_message(chat_id=MY_ID, text=f"每日 CEO 简报推送出错：{e}")

    # 2. 推送用户机会简报
    subscriptions = data_store.get("user_daily_subscriptions", {})
    for chat_id, sub in subscriptions.items():
        if not sub.get("enabled", False):
            continue

        # 私人模式下，只有你自己能收到
        if OWNER_ONLY_MODE and int(chat_id) != MY_ID:
            continue

        # 非私人模式但不开放给公众时，只有你自己能收到
        if not OWNER_ONLY_MODE and not ALLOW_PUBLIC_DAILY_USER and int(chat_id) != MY_ID:
            continue

        topic = sub.get("topic", "AI创业、AI副业、赚钱机会")

        try:
            reply = await build_user_daily_briefing(topic)
            await context.bot.send_message(chat_id=int(chat_id), text=f"【今日机会简报｜{topic}】")
            await send_long_text_by_chat_id(context.bot, int(chat_id), reply)
        except Exception as e:
            print(f"用户 {chat_id} 每日推送失败：{e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not can_use_public_features(update):
        await deny_access(update)
        return

    if not update.message or not update.message.text:
        return

    await typing(update, context)

    user_text = update.message.text
    chat_key = get_chat_key(update)
    history = get_history(chat_key)

    history.append({"role": "user", "content": user_text})
    recent_history = history[-MAX_HISTORY_MESSAGES:]

    messages = [{"role": "system", "content": get_prompt_for_user(update)}] + recent_history

    try:
        reply = await ask_llm(messages)
        history.append({"role": "assistant", "content": reply})
        data_store["chat_histories"][chat_key] = history[-20:]
        save_data()
        await send_long_message(update, reply)
    except Exception as e:
        await update.message.reply_text(f"聊天时出错：{e}")


def main():
    load_data()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("save", save_memory_command))
    app.add_handler(CommandHandler("memory", show_memory_command))
    app.add_handler(CommandHandler("clear", clear_memory))
    app.add_handler(CommandHandler("strategy", strategy_command))
    app.add_handler(CommandHandler("analyze", analyze_command))
    app.add_handler(CommandHandler("plan", plan_command))
    app.add_handler(CommandHandler("opportunity", opportunity_command))
    app.add_handler(CommandHandler("content", content_command))
    app.add_handler(CommandHandler("script", script_command))
    app.add_handler(CommandHandler("meeting", meeting_command))
    app.add_handler(CommandHandler("decision", decision_command))
    app.add_handler(CommandHandler("todo", todo_command))
    app.add_handler(CommandHandler("radar", radar_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("daily_on", daily_on_command))
    app.add_handler(CommandHandler("daily_off", daily_off_command))
    app.add_handler(CommandHandler("daily_topic", daily_topic_command))
    app.add_handler(CommandHandler("daily_now", daily_now_command))
    app.add_handler(CommandHandler("daily_user_on", daily_user_on_command))
    app.add_handler(CommandHandler("daily_user_off", daily_user_off_command))
    app.add_handler(CommandHandler("daily_user_now", daily_user_now_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if app.job_queue:
        app.job_queue.run_daily(
            daily_push_job,
            time=time(hour=DAILY_HOUR, minute=DAILY_MINUTE),
            name="daily_combined_briefing"
        )

    print("AI CEO 助手最终整合版已启动...")
    app.run_polling()


if __name__ == "__main__":
    main()