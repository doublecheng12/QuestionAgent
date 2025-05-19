import numpy as np
import openai
from openai import OpenAI
from zhipuai import ZhipuAI

class LLMModel:
    def __init__(self, model_type: str = "gpt", model_name: str = "gpt-4o-mini", temperature: float = 0.7):
        """
        初始化大语言模型
        
        Args:
            model_type: 模型类型,支持 gpt/deepseek/glm
            model_name: 具体的模型名称
            temperature: 采样温度
        """
        self.model_type = model_type
        self.model_name = model_name
        self.temperature = temperature
        
        # 初始化不同类型的模型客户端
        if model_type == "gpt":
            openai.api_key = ""
            self.client = OpenAI(
                api_key=openai.api_key,
                base_url=""
            )
        elif model_type == "deepseek":
            base_url = "https://api.deepseek.com/v1"
            openai.api_key = ""
            self.client = OpenAI(
                api_key=openai.api_key,
                base_url=base_url
            )
        elif model_type == "glm":
            api_key = ""
            self.client = ZhipuAI(api_key=api_key)
        elif model_type == "qwen2.5-7b":
            api_key = ""
            self.client = OpenAI(api_key=api_key,base_url="http://127.0.0.1:10086/v1")
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")

    def generate(self, prompt: str) -> str:
        """
        获取模型响应
        
        Args:
            prompt: 输入的提示文本
            
        Returns:
            str: 模型生成的响应文本
        """
        if self.model_type == "gpt":
            messages = [
                {
                    "role": "system",
                    "content": "你是一名专业的高中数学老师，根据要求，完成命题相关的任务"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        else:
            messages = [{"role": "user", "content": prompt}]
            
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature
        )
        
        return response.choices[0].message.content

