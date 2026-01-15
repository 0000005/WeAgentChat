from . import user_profile_topics
from .utils import pack_profiles_into_string
from ..models.response import AIUserProfiles
from ..env import CONFIG

ADD_KWARGS = {
    "prompt_id": "event_tagging",
}
FACT_RETRIEVAL_PROMPT = """You are a expert of tagging events.
You will be given a event summary, and you need to extract the specific tags' values for the event.
Only tag facts about the real user; ignore assistant/friend statements or roleplay content.
仅基于真实用户的事实打标签，忽略好友/助手的自述、推测或角色设定。

## Event Tags
Below are some event tags you need to extract:
<event_tags>
{event_tags}
</event_tags>
each line is the tag name and its description(if any), for example:
- emotion(the user's current emotion)
the tag name is `emotion`, and the description of this tag is `the user's current emotion`.
### Rules
- Strick to the exact tag name, don't change the tag name.
- Remember: if some tags are not mentioned in the summary, you should not include them in the result.

## Formatting
### Output
You need to extract the specific tags' values for the event:
- TAG{tab}VALUE
For example:
- emotion{tab}sad
- goals{tab}find a new home

For each line is a new event tag of this summary, containing:
1. TAG: the event tag name
2. VALUE: the value of the event tag
those elements should be separated by `{tab}` and each line should be separated by `\n` and started with "- ".

## Rules
- Return the new event tags in a list format as shown above.
- Strick to the exact tag name, don't change the tag name.
- If some tags are not mentioned in the summary, you should not include them in the result.
- Only tag facts about the real user; do not infer tags from assistant/friend content.

Now, please extract the event tags for the following event summary:
"""


def get_prompt(event_tags: str) -> str:
    return FACT_RETRIEVAL_PROMPT.format(
        tab=CONFIG.llm_tab_separator,
        event_tags=event_tags,
    )


def get_kwargs() -> dict:
    return ADD_KWARGS


def get_few_shot_messages() -> list[dict]:
    tab = CONFIG.llm_tab_separator
    return [
        {
            "role": "user",
            "content": """Event summary:
- 用户这两周加班到很晚，昨晚两点才睡。[提及于2024/06/02]
- 用户白天很困，靠黑咖啡提神。[提及于2024/06/02]
- 用户喜欢黑咖啡。[提及于2024/06/02]
- 用户计划周五去体检。[提及于2024/06/02]
""",
        },
        {
            "role": "assistant",
            "content": f"""- emotion{tab}tired
- goals{tab}attend medical checkup""",
        },
        {
            "role": "user",
            "content": """Event summary:
- 用户周末要带孩子去看牙。[提及于2024/06/05]
- 用户目前住在上海。[提及于2024/06/05]
""",
        },
        {
            "role": "assistant",
            "content": f"""- goals{tab}take child to dentist
- location{tab}Shanghai""",
        },
        {
            "role": "user",
            "content": """Event summary:
- 用户最近在健身，计划周三跑步。[提及于2024/06/08]
- 用户不太能吃辣。[提及于2024/06/08]
""",
        },
        {
            "role": "assistant",
            "content": f"""- goals{tab}go running on Wednesday
- emotion{tab}motivated""",
        },
        {
            "role": "user",
            "content": """Event summary:
- 用户上个月感冒了，现在好多了。[提及于2024/06/12]
- 用户下周准备去成都旅行。[提及于2024/06/12]
""",
        },
        {
            "role": "assistant",
            "content": f"""- emotion{tab}relieved
- goals{tab}travel to Chengdu""",
        },
    ]


if __name__ == "__main__":
    print(
        get_prompt(
            event_tags="""- 冒险
- 天气
- 休息
- 逃离
""",
        )
    )
