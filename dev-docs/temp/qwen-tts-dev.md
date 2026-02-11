语音合成-千问提供多种拟人音色，支持多语言及方言，并可在同一音色下输出多语言内容。系统可自适应语气，流畅处理复杂文本。

## **核心功能**

-   支持流式输出，可以边合成边播放
    
-   覆盖多种语言，包含中文方言
    
-   提供丰富音色，满足场景需求
    
-   提供[声音复刻](/help/zh/model-studio/qwen-tts-voice-cloning)与[声音设计](/help/zh/model-studio/qwen-tts-voice-design)两种音色定制方式
    
-   支持[指令控制](#12884a10929p9)，可通过自然语言指令控制语音表现力
    

## **适用范围**

**支持的模型：**

## 国际

在[国际部署模式](/help/zh/model-studio/regions/#080da663a75xh)下，接入点与数据存储均位于**新加坡地域**，模型推理计算资源在全球范围内动态调度（不含中国内地）。

调用以下模型时，请选择新加坡地域的[API Key](https://modelstudio.console.alibabacloud.com/?tab=dashboard#/api-key)：

-   **千问3-TTS-Instruct-Flash**：qwen3-tts-instruct-flash（稳定版，当前等同qwen3-tts-instruct-flash-2026-01-26）、qwen3-tts-instruct-flash-2026-01-26（最新快照版）
    
-   **千问3-TTS-VD****：**qwen3-tts-vd-2026-01-26（最新快照版）
    
-   **千问3-TTS-VC****：**qwen3-tts-vc-2026-01-22（最新快照版）
    
-   **千问3-TTS-Flash**：qwen3-tts-flash（稳定版，当前等同qwen3-tts-flash-2025-11-27）、qwen3-tts-flash-2025-11-27、qwen3-tts-flash-2025-09-18
    

## 中国内地

在[中国内地部署模式](/help/zh/model-studio/regions/#080da663a75xh)下，接入点与数据存储均位于**北京地域**，模型推理计算资源仅限于中国内地。

调用以下模型时，请选择北京地域的[API Key](https://bailian.console.alibabacloud.com/?tab=model#/api-key)：

-   **千问3-TTS-Instruct-Flash**：qwen3-tts-instruct-flash（稳定版，当前等同qwen3-tts-instruct-flash-2026-01-26）、qwen3-tts-instruct-flash-2026-01-26（最新快照版）
    
-   **千问3-TTS-VD****：**qwen3-tts-vd-2026-01-26（最新快照版）
    
-   **千问3-TTS-VC****：**qwen3-tts-vc-2026-01-22（最新快照版）
    
-   **千问3-TTS-Flash**：qwen3-tts-flash（稳定版，当前等同qwen3-tts-flash-2025-11-27）、qwen3-tts-flash-2025-11-27、qwen3-tts-flash-2025-09-18
    
-   **千问-TTS**：qwen-tts（稳定版，当前等同qwen-tts-2025-04-10）、qwen-tts-latest（最新版，当前等同qwen-tts-2025-05-22）、qwen-tts-2025-05-22（快照版）、qwen-tts-2025-04-10（快照版）
    

更多信息请参见[模型列表](/help/zh/model-studio/models)

## **模型选型**

| **场景** | **推荐模型** | **推荐理由** |
| --- | --- | --- |
| **品牌形象、专属声音、扩展系统音色等语音定制（基于文本描述）** | qwen3-tts-vd-2026-01-26 | 支持声音设计，无需音频样本，通过文本描述创建定制化音色，适合从零开始设计品牌专属声音 |
| **品牌形象、专属声音、扩展系统音色等语音定制（基于音频样本）** | qwen3-tts-vc-2026-01-22 | 支持声音复刻，基于真实音频样本快速复刻音色，打造拟人化品牌声纹，确保音色高度还原与一致性 |
| **情感化内容生产（有声书、广播剧、游戏/动画配音）** | qwen3-tts-instruct-flash | 支持指令控制，通过自然语言描述精确控制音调、语速、情感、角色性格，适合需要丰富表现力和角色塑造的场景 |
| **移动端导航/通知播报** | qwen3-tts-flash | 按字符计费简单透明，适合短文本高频调用场景 |
| **在线教育课件配音** | qwen3-tts-flash | 支持多语种与方言，满足地域化教学需求 |
| **有声读物批量生产** | qwen3-tts-flash | 成本可控，多音色选择丰富内容表现力 |

更多说明请参见[模型功能特性对比](#6e3883d028fqq)

## **快速开始**

**准备工作**

-   已[配置 API Key](/help/zh/model-studio/get-api-key)并[配置API Key到环境变量](/help/zh/model-studio/configure-api-key-through-environment-variables)。
    
-   如果通过 DashScope SDK 进行调用，需要[安装最新版SDK](/help/zh/model-studio/install-sdk)。DashScope Java SDK 版本需要不低于 2.21.9，DashScope Python SDK 版本需要不低于 1.24.6。
    
    **说明**
    
    DashScope Python SDK中的`SpeechSynthesizer`接口已统一为`MultiModalConversation`，使用新接口只需替换接口名称即可，其他参数完全兼容。
    

## 使用系统音色进行语音合成

以下示例演示如何使用[系统音色](#bac280ddf5a1u)进行语音合成。

## 非流式输出

通过返回的`url`来获取合成的语音。URL 有效期为24 小时。

## Python

```
import os
import dashscope

# 以下为新加坡地域url，若使用北京地域的模型，需将url替换为：https://dashscope.aliyuncs.com/api/v1
dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'

text = "Today is a wonderful day to build something people love!"
# SpeechSynthesizer接口使用方法：dashscope.audio.qwen_tts.SpeechSynthesizer.call(...)
response = dashscope.MultiModalConversation.call(
    # 如需使用指令控制功能，请将model替换为qwen3-tts-instruct-flash
    model="qwen3-tts-flash",
    # 新加坡地域和北京地域的API Key不同。获取API Key：https://www.alibabacloud.com/help/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx"
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    text=text,
    voice="Cherry",
    language_type="English", # 建议与文本语种一致，以获得正确的发音和自然的语调。
    # 如需使用指令控制功能，请取消下方注释，并将model替换为qwen3-tts-instruct-flash
    # instructions='语速较快，带有明显的上扬语调，适合介绍时尚产品。',
    # optimize_instructions=True,
    stream=False
)
print(response)
```


## cURL

```
# ======= 重要提示 =======
# 以下为新加坡地域url，若使用北京地域的模型，需将url替换为：https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
# 新加坡地域和北京地域的API Key不同。获取API Key：https://www.alibabacloud.com/help/zh/model-studio/get-api-key
# === 执行时请删除该注释 ===

curl -X POST 'https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation' \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H 'Content-Type: application/json' \
-d '{
    "model": "qwen3-tts-flash",
    "input": {
        "text": "Today is a wonderful day to build something people love!",
        "voice": "Cherry",
        "language_type": "English"
    }
}'
```

## 流式输出

可以流式地将音频数据以 Base64 格式进行输出，此时最后一个数据包中包含完整音频的 URL。

## Python

```
# coding=utf-8
#
# Installation instructions for pyaudio:
# APPLE Mac OS X
#   brew install portaudio
#   pip install pyaudio
# Debian/Ubuntu
#   sudo apt-get install python-pyaudio python3-pyaudio
#   or
#   pip install pyaudio
# CentOS
#   sudo yum install -y portaudio portaudio-devel && pip install pyaudio
# Microsoft Windows
#   python -m pip install pyaudio

import os
import dashscope
import pyaudio
import time
import base64
import numpy as np

# 以下为新加坡地域url，若使用北京地域的模型，需将url替换为：https://dashscope.aliyuncs.com/api/v1
dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'

p = pyaudio.PyAudio()
# 创建音频流
stream = p.open(format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True)


text = "Today is a wonderful day to build something people love!"
response = dashscope.MultiModalConversation.call(
    # 新加坡地域和北京地域的API Key不同。获取API Key：https://www.alibabacloud.com/help/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx"
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    # 如需使用指令控制功能，请将model替换为qwen3-tts-instruct-flash
    model="qwen3-tts-flash",
    text=text,
    voice="Cherry",
    language_type="English", # 建议与文本语种一致，以获得正确的发音和自然的语调。
    # 如需使用指令控制功能，请取消下方注释，并将model替换为qwen3-tts-instruct-flash
    # instructions='语速较快，带有明显的上扬语调，适合介绍时尚产品。',
    # optimize_instructions=True,
    stream=True
)

for chunk in response:
    if chunk.output is not None:
      audio = chunk.output.audio
      if audio.data is not None:
          wav_bytes = base64.b64decode(audio.data)
          audio_np = np.frombuffer(wav_bytes, dtype=np.int16)
          # 直接播放音频数据
          stream.write(audio_np.tobytes())
      if chunk.output.finish_reason == "stop":
          print("finish at: {} ", chunk.output.audio.expires_at)
time.sleep(0.8)
# 清理资源
stream.stop_stream()
stream.close()
p.terminate()
```


## cURL

```
# ======= 重要提示 =======
# 以下为新加坡地域url，若使用北京地域的模型，需将url替换为：https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
# 新加坡地域和北京地域的API Key不同。获取API Key：https://www.alibabacloud.com/help/zh/model-studio/get-api-key
# === 执行时请删除该注释 ===

curl -X POST 'https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation' \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H 'Content-Type: application/json' \
-H 'X-DashScope-SSE: enable' \
-d '{
    "model": "qwen3-tts-flash",
    "input": {
        "text": "Today is a wonderful day to build something people love!",
        "voice": "Cherry",
        "language_type": "Chinese"
    }
}'
```

## 使用声音复刻音色进行语音合成

声音复刻服务不提供预览音频。需将复刻生成的音色应用于语音合成后，才能试听并评估效果。

以下示例演示了如何在语音合成中使用声音复刻生成的专属音色，实现与原音高度相似的输出效果。这里参考了使用系统音色进行语音合成DashScope SDK的“非流式输出”示例代码，将`voice`参数替换为复刻生成的专属音色进行语音合成。

-   **关键原则**：声音复刻时使用的模型 (`target_model`) 必须与后续进行语音合成时使用的模型 (`model`) 保持一致，否则会导致合成失败。
    
-   示例使用本地音频文件 `voice.mp3` 进行声音复刻，运行代码时，请注意替换。
    

### Python

```
import os
import requests
import base64
import pathlib
import dashscope

# ======= 常量配置 =======
DEFAULT_TARGET_MODEL = "qwen3-tts-vc-2026-01-22"  # 声音复刻、语音合成要使用相同的模型
DEFAULT_PREFERRED_NAME = "guanyu"
DEFAULT_AUDIO_MIME_TYPE = "audio/mpeg"
VOICE_FILE_PATH = "voice.mp3"  # 用于声音复刻的本地音频文件的相对路径


def create_voice(file_path: str,
                 target_model: str = DEFAULT_TARGET_MODEL,
                 preferred_name: str = DEFAULT_PREFERRED_NAME,
                 audio_mime_type: str = DEFAULT_AUDIO_MIME_TYPE) -> str:
    """
    创建音色，并返回 voice 参数
    """
    # 新加坡地域和北京地域的API Key不同。获取API Key：https://www.alibabacloud.com/help/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx"
    api_key = os.getenv("DASHSCOPE_API_KEY")

    file_path_obj = pathlib.Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"音频文件不存在: {file_path}")

    base64_str = base64.b64encode(file_path_obj.read_bytes()).decode()
    data_uri = f"data:{audio_mime_type};base64,{base64_str}"

    # 以下为新加坡地域url，若使用北京地域的模型，需将url替换为：https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization
    url = "https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization"
    payload = {
        "model": "qwen-voice-enrollment", # 不要修改该值
        "input": {
            "action": "create",
            "target_model": target_model,
            "preferred_name": preferred_name,
            "audio": {"data": data_uri}
        }
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    resp = requests.post(url, json=payload, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"创建 voice 失败: {resp.status_code}, {resp.text}")

    try:
        return resp.json()["output"]["voice"]
    except (KeyError, ValueError) as e:
        raise RuntimeError(f"解析 voice 响应失败: {e}")


if __name__ == '__main__':
    # 以下为新加坡地域url，若使用北京地域的模型，需将url替换为：https://dashscope.aliyuncs.com/api/v1
    dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'

    text = "今天天气怎么样？"
    # SpeechSynthesizer接口使用方法：dashscope.audio.qwen_tts.SpeechSynthesizer.call(...)
    response = dashscope.MultiModalConversation.call(
        model=DEFAULT_TARGET_MODEL,
        # 新加坡地域和北京地域的API Key不同。获取API Key：https://www.alibabacloud.com/help/zh/model-studio/get-api-key
        # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx"
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        text=text,
        voice=create_voice(VOICE_FILE_PATH), # 将voice参数替换为复刻生成的专属音色
        stream=False
    )
    print(response)
```

## 使用声音设计音色进行语音合成

使用声音设计功能时，服务会返回预览音频数据。建议先试听该预览音频，确认效果符合预期后再用于语音合成，降低调用成本。

1.  生成专属音色并试听效果，若对效果满意，进行下一步；否则重新生成。
    
    ### Python
    
    ```
    import requests
    import base64
    import os
    
    def create_voice_and_play():
        # 新加坡和北京地域的API Key不同。获取API Key：https://www.alibabacloud.com/help/zh/model-studio/get-api-key
        # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx"
        api_key = os.getenv("DASHSCOPE_API_KEY")
        
        if not api_key:
            print("错误: 未找到DASHSCOPE_API_KEY环境变量，请先设置API Key")
            return None, None, None
        
        # 准备请求数据
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "qwen-voice-design",
            "input": {
                "action": "create",
                "target_model": "qwen3-tts-vd-2026-01-26",
                "voice_prompt": "A composed middle-aged male announcer with a deep, rich and magnetic voice, a steady speaking speed and clear articulation, is suitable for news broadcasting or documentary commentary.",
                "preview_text": "Dear listeners, hello everyone. Welcome to the evening news.",
                "preferred_name": "announcer",
                "language": "en"
            },
            "parameters": {
                "sample_rate": 24000,
                "response_format": "wav"
            }
        }
        
        # 以下为新加坡地域url，若使用北京地域的模型，需将url替换为：https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization
        url = "https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization"
        
        try:
            # 发送请求
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=60  # 添加超时设置
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 获取音色名称
                voice_name = result["output"]["voice"]
                print(f"音色名称: {voice_name}")
                
                # 获取预览音频数据
                base64_audio = result["output"]["preview_audio"]["data"]
                
                # 解码Base64音频数据
                audio_bytes = base64.b64decode(base64_audio)
                
                # 保存音频文件到本地
                filename = f"{voice_name}_preview.wav"
                
                # 将音频数据写入本地文件
                with open(filename, 'wb') as f:
                    f.write(audio_bytes)
                
                print(f"音频已保存到本地文件: {filename}")
                print(f"文件路径: {os.path.abspath(filename)}")
                
                return voice_name, audio_bytes, filename
            else:
                print(f"请求失败，状态码: {response.status_code}")
                print(f"响应内容: {response.text}")
                return None, None, None
                
        except requests.exceptions.RequestException as e:
            print(f"网络请求发生错误: {e}")
            return None, None, None
        except KeyError as e:
            print(f"响应数据格式错误，缺少必要的字段: {e}")
            print(f"响应内容: {response.text if 'response' in locals() else 'No response'}")
            return None, None, None
        except Exception as e:
            print(f"发生未知错误: {e}")
            return None, None, None
    
    if __name__ == "__main__":
        print("开始创建语音...")
        voice_name, audio_data, saved_filename = create_voice_and_play()
        
        if voice_name:
            print(f"\n成功创建音色 '{voice_name}'")
            print(f"音频文件已保存: '{saved_filename}'")
            print(f"文件大小: {os.path.getsize(saved_filename)} 字节")
        else:
            print("\n音色创建失败")
    ```
    
    
2.  使用上一步生成的专属音色进行语音合成（非流式合成）。
    
    这里参考了使用系统音色进行语音合成DashScope SDK的“非流式输出”示例代码，将`voice`参数替换为声音设计生成的专属音色进行语音合成。单向流式合成请参见[语音合成-千问](/help/zh/model-studio/qwen-tts#c204937c02gsb)。
    
    **关键原则**：声音设计时使用的模型 (`target_model`) 必须与后续进行语音合成时使用的模型 (`model`) 保持一致，否则会导致合成失败。
    
    ### Python
    
    ```
    import os
    import dashscope
    
    
    if __name__ == '__main__':
        # 以下为新加坡地域url，若使用北京地域的模型，需将url替换为：https://dashscope.aliyuncs.com/api/v1
        dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'
    
        text = "今天天气怎么样？"
        # SpeechSynthesizer接口使用方法：dashscope.audio.qwen_tts.SpeechSynthesizer.call(...)
        response = dashscope.MultiModalConversation.call(
            model="qwen3-tts-vd-2026-01-26",
            # 新加坡和北京地域的API Key不同。获取API Key：https://www.alibabacloud.com/help/zh/model-studio/get-api-key
            # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx"
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            text=text,
            voice="myvoice", # 将voice参数替换为声音设计生成的专属音色
            stream=False
        )
        print(response)
    ```
    

## **指令控制**

指令控制是一项高级语音合成功能，通过自然语言描述的方式精确控制语音的表达效果。您可以使用简单的文字描述，让合成语音呈现出特定的音调、语速、情感、音色特点，无需调整复杂的音频参数。

**支持的模型**：仅支持千问3-TTS-Instruct-Flash系列模型。

**使用方式**：通过`instructions`参数指定指令内容，例如“语速较快，带有明显的上扬语调，适合介绍时尚产品”。

**支持语言**：描述文本仅支持中文和英文。

**长度限制**：长度不得超过 1600 Token。

**适用场景**：

-   有声书和广播剧配音
    
-   广告和宣传片配音
    
-   游戏角色和动画配音
    
-   情感化的智能语音助手
    
-   纪录片和新闻播报
    

**如何编写高质量的声音描述：**

-   核心原则：
    
    1.  具体而非模糊：使用能够描绘具体声音特质的词语，如“低沉”、“清脆”、“语速偏快”。避免使用“好听”、“普通”等主观且缺乏信息量的词汇。
        
    2.  多维而非单一：优秀的描述通常结合多个维度（如下文所述的音调、语速、情感等）。单一维度的描述（如仅“高音”）过于宽泛，难以生成特色鲜明的效果。
        
    3.  客观而非主观：专注于声音本身的物理和感知特征，而不是个人的喜好。例如，用“音调偏高，带有活力”代替“我最喜欢的声音”。
        
    4.  原创而非模仿：请描述声音的特质，而不是要求模仿特定人物（如名人、演员）。此类请求涉及版权风险且模型不支持直接模仿。
        
    5.  简洁而非冗余：确保每个词都有其意义。避免重复使用同义词或无意义的强调词（如“非常非常棒的声音”）。
        
-   描述维度参考：可以组合多个维度，创造更丰富的表达效果。
    
    | **维度** | **描述示例** |
    | --- | --- |
    | 音调  | 高音、中音、低音、偏高、偏低 |
    | 语速  | 快速、中速、缓慢、偏快、偏慢 |
    | 情感  | 开朗、沉稳、温柔、严肃、活泼、冷静、治愈 |
    | 特点  | 有磁性、清脆、沙哑、圆润、甜美、浑厚、有力 |
    | 用途  | 新闻播报、广告配音、有声书、动画角色、语音助手、纪录片解说 |
    
-   示例：
    
    -   标准播音风格：吐字清晰精准，字正腔圆
        
    -   情绪递进效果：音量由正常对话迅速增强至高喊，性格直率，情绪易激动且外露
        
    -   特殊情感状态：哭腔导致发音略微含糊，略显沙哑，带有明显哭腔的紧张感
        
    -   广告配音风格：音调偏高，语速中等，充满活力和感染力，适合广告配音
        
    -   温柔治愈风格：语速偏慢，音调温柔甜美，语气治愈温暖，像贴心朋友般关怀
        

## **API 参考**

## **模型功能特性对比**

| **功能/特性** | **千问3-TTS-Instruct-Flash** | **千问3-TTS-VD** | **千问3-TTS-VC** | **千问3-TTS-Flash** | **千问-TTS** |
| --- | --- | --- | --- | --- | --- |
| **支持语言** | 因[音色](#bac280ddf5a1u)而异：中文（普通话）、英文、西班牙语、俄语、意大利语、法语、韩语、日语、德语、葡萄牙语 | 中文（普通话）、英文、西班牙语、俄语、意大利语、法语、韩语、日语、德语、葡萄牙语 |   | 因[音色](#bac280ddf5a1u)而异：中文（普通话、上海话、北京话、四川话、南京话、陕西话、闽南语、天津话）、粤语、英文、法语、德语、俄语、意大利语、西班牙语、葡萄牙语、日语、韩语 | 因[音色](#bac280ddf5a1u)而异：中文（普通话、上海话、北京话、四川话）、英文 |
| **音频格式** | - wav：非流式输出时 - pcm：流式输出时，Base64编码 |   |   |   |   |
| **音频采样率** | 24kHz |   |   |   |   |
| **声音复刻** | 不支持 |   | 支持  | 不支持 |   |
| **声音设计** | 不支持 | 支持  | 不支持 |   |   |
| **SSML** | 不支持 |   |   |   |   |
| **LaTeX** | 不支持 |   |   |   |   |
| **音量调节** | 支持 > 可通过[指令控制](#12884a10929p9)调节 | 不支持 |   |   |   |
| **语速调节** | 支持 > 可通过[指令控制](#12884a10929p9)调节 | 不支持 |   |   |   |
| **语调（音高）调节** | 支持 > 可通过[指令控制](#12884a10929p9)调节 | 不支持 |   |   |   |
| **码率调节** | 不支持 |   |   |   |   |
| **时间戳** | 不支持 |   |   |   |   |
| **指令控制（Instruct）** | 支持  | 不支持 |   |   |   |
| **流式输入** | 不支持 |   |   |   |   |
| **流式输出** | 支持  |   |   |   |   |
| **限流** | 每分钟调用次数（RPM）：180 | 每分钟调用次数（RPM）：180 | 每分钟调用次数（RPM）：180 | 每分钟调用次数（RPM）因模型而异： - qwen3-tts-flash、qwen3-tts-flash-2025-11-27：180 - qwen3-tts-flash-2025-09-18：10 | 每分钟调用次数（RPM）：10 每分钟消耗Token数（TPM，含输入与输出Token）：100,000 |
| **接入方式** | Java/Python SDK、WebSocket API |   |   |   |   |
| **价格** | 国际：$0.115/万字符 中国内地：$0.115/万字符 | 国际：$0.115/万字符 中国内地：$0.115/万字符 | 国际：$0.115/万字符 中国内地：$0.115/万字符 | 国际：$0.1/万字符 中国内地：$0.114682/万字符 | 中国内地： - 输入成本：$0.230/千Token - 输出成本：$1.434/千Token 音频转换为 Token 的规则：每1秒的音频对应 50个 Token ;若音频时长不足1秒，则按 50个 Token 计算 |

## **支持的系统音色**

不同模型支持的音色有所差异，使用时将请求参数`voice`设置为音色列表中**voice参数**列对应的值。
具体音色列表请查看本地文件 `dev-docs\temp\tts-sample.html`。里面有每个音色的代码和对应的声音效果mp3文件。

## **常见问题**

### **Q：音频文件链接的有效期是多久？**

A：24小时后音频文件链接将失效。
