from http import HTTPStatus
from urllib.parse import urlparse, unquote
from pathlib import PurePosixPath
import requests
from dashscope import ImageSynthesis
import os
import dashscope

# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1
dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'

prompt = "一副典雅庄重的对联悬挂于厅堂之中，房间是个安静古典的中式布置，桌子上放着一些青花瓷，对联上左书“义本生知人机同道善思新”，右书“通云赋智乾坤启数高志远”， 横批“智启通义”，字体飘逸，在中间挂着一幅中国风的画作，内容是岳阳楼。"

# 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx"
api_key = os.getenv("DASHSCOPE_API_KEY")

print('----同步调用，请等待任务执行----')
rsp = ImageSynthesis.call(api_key=api_key,
                          model="qwen-image-plus", # 当前仅qwen-image-plus、qwen-image模型支持异步接口
                          prompt=prompt,
                          negative_prompt=" ",
                          n=1,
                          size='1024*1024',
                          prompt_extend=True,
                          watermark=False)
print(f'response: {rsp}')
if rsp.status_code == HTTPStatus.OK:
    # 在当前目录下保存图像
    for result in rsp.output.results:
        file_name = PurePosixPath(unquote(urlparse(result.url).path)).parts[-1]
        with open('./%s' % file_name, 'wb+') as f:
            f.write(requests.get(result.url).content)
else:
    print(f'同步调用失败, status_code: {rsp.status_code}, code: {rsp.code}, message: {rsp.message}')