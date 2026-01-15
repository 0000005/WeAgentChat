from ..env import CONFIG

ADD_KWARGS = {
    "prompt_id": "zh_summary_entry_chats",
}
SUMMARY_PROMPT = """你是一位从聊天记录中记录个人信息、日程安排和事件的专家。
你将获得用户和助手之间的对话内容。对话可能包含好友/助手的发言，你只记录真实用户(ROLE=user)相关的事实与事件。好友/助手的自述、推测、设定不要写入用户记录，只能用于理解用户语境。

## 要求
- 你需要列出用户信息和日程安排
- {additional_requirements}
- 如果用户事件/日程有具体的提及时间或者事件发生的时间。根据消息中的[TIME]在你提取的事件和日程中补充相关的时间信息。例如：
    输入: `[2024/04/30] user: 我昨天买了一辆新车！`
    输出: `用户买了一辆新车[提及于 2024/04/30, 买车在2024/04/29]。`
    输入: `[2024/04/30] user: 我4年前买了一辆车！`
    输出: `用户买了一辆车[提及于 2024/04/30, 买车在2020]。`
    说明: 因为你只知道年份而不知道具体日期，所以 2024-4=2020。或者你可以记录为 [2024/04/30之前4年]
    输入: `[2024/04/30] user: 我上周买了一辆新车！`
    输出: `用户买了一辆新车[提及于 2024/04/30, 买车在2024/04/30之前一周]。`
    说明: 因为你不知道具体日期。
    输入: `[...] user: 我上周买了一辆新车！`
    输出: `用户买了一辆新车。`
    说明: 因为你不知道具体日期，所以不要附加任何日期是错误的答案。

### 重要信息
以下是你应该从聊天中记录的主题/子主题。
<topics>
{topics}
</topics>
以下是你应该从聊天中记录的重要属性。
<attributes>
{attributes}
</attributes>

## 输入格式
### 已记录
你会收到一系列的已记录信息，你留意需要记录可能和已记录信息相关的信息。
已记录信息的组织形式如下:
- TOPIC{separator}SUBTOPIC{separator}CONTENT... // maybe truncated

### 输入对话
你将收到用户和助手之间的对话。对话格式为：
- [TIME] NAME: MESSAGE
其中NAME是ALIAS(ROLE)或仅ROLE，当ALIAS可用时，使用ALIAS来指代用户/助手。
MESSAGE是对话内容。
TIME是此消息发生的时间，因此你需要根据TIME转换消息中的日期信息（如有必要）。

## 输出格式
请使用Markdown无序列表格式输出你的记录结果。
例如：
```
- Jack画了一幅关于他孩子们的画。[提及于 2023/1/23] // event
- 用户的昵称是Jack，助手是Melinda。[提及于 2023/1/23] // info
- Jack提到他在Memobase工作，是一名软件工程师。[提及于 2023/1/23] // info
- Jack计划去健身房。[提及于 2023/1/23，计划定在 2023/1/24] // schedule
...
```
始终添加你记录的具体提及时间，如果可能的话也要添加事件发生时间。
记住，确保你的记录是纯正和简洁的，任何时间信息都应该移动到[TIME INFO]块中。

## 内容要求
- 你需要列出用户信息和日程安排
- {additional_requirements}
- 只记录真实用户(ROLE=user)的事实，不要记录好友/助手的个人信息、情绪或偏好

现在请执行你的任务。
"""


def pack_input(already_logged_str: str, chat_strs: str):
    return f"""### 已记录
{already_logged_str}

### 输入对话
{chat_strs}
"""


def get_prompt(
    topic_examples: str, attribute_examples: str, additional_requirements: str = ""
) -> str:
    return SUMMARY_PROMPT.format(
        topics=topic_examples,
        attributes=attribute_examples,
        additional_requirements=additional_requirements,
        separator=CONFIG.llm_tab_separator,
    )


def get_kwargs() -> dict:
    return ADD_KWARGS


def get_few_shot_messages() -> list[dict]:
    sep = CONFIG.llm_tab_separator
    return [
        {
            "role": "user",
            "content": f"""### 已记录
- 工作{sep}状态{sep}最近在找新工作

### 输入对话
- [2024/06/02 20:01] user: 这两周加班到很晚，昨晚两点才睡。
- [2024/06/02 20:02] assistant: 我昨晚也没睡好。
- [2024/06/02 20:03] user: 白天很困，靠黑咖啡提神。
- [2024/06/02 20:04] assistant: 我更喜欢奶茶。
- [2024/06/02 20:05] user: 周五要去体检。
- [2024/06/02 20:06] assistant: 祝你体检顺利。
""",
        },
        {
            "role": "assistant",
            "content": """- 用户这两周加班到很晚，昨晚两点才睡。[提及于 2024/06/02]
- 用户白天很困，靠黑咖啡提神。[提及于 2024/06/02]
- 用户喜欢黑咖啡。[提及于 2024/06/02]
- 用户计划周五去体检。[提及于 2024/06/02]""",
        },
        {
            "role": "user",
            "content": f"""### 已记录

### 输入对话
- [2024/06/05 19:10] user: 周末要带孩子去看牙。
- [2024/06/05 19:11] assistant: 我周末打算去看展。
- [2024/06/05 19:12] user: 我现在住在上海。
- [2024/06/05 19:13] assistant: 我住北京。
""",
        },
        {
            "role": "assistant",
            "content": """- 用户周末要带孩子去看牙。[提及于 2024/06/05]
- 用户目前住在上海。[提及于 2024/06/05]""",
        },
        {
            "role": "user",
            "content": f"""### 已记录

### 输入对话
- [2024/06/08 08:20] user: 最近在健身，计划周三跑步。
- [2024/06/08 08:21] assistant: 我更喜欢游泳。
- [2024/06/08 08:22] user: 我不太能吃辣。
- [2024/06/08 08:23] assistant: 我超爱吃辣。
""",
        },
        {
            "role": "assistant",
            "content": """- 用户最近在健身，计划周三跑步。[提及于 2024/06/08]
- 用户不太能吃辣。[提及于 2024/06/08]""",
        },
        {
            "role": "user",
            "content": f"""### 已记录

### 输入对话
- [2024/06/12 22:05] user: 上个月感冒了，现在好多了。
- [2024/06/12 22:06] assistant: 我最近也感冒。
- [2024/06/12 22:07] user: 下周准备去成都旅行。
- [2024/06/12 22:08] assistant: 祝你旅途愉快。
""",
        },
        {
            "role": "assistant",
            "content": """- 用户上个月感冒了，现在好多了。[提及于 2024/06/12]
- 用户下周准备去成都旅行。[提及于 2024/06/12]""",
        },
    ]


if __name__ == "__main__":
    print(get_prompt())
