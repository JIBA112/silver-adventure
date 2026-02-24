from openai import AsyncOpenAI
from config import AI_API_KEY, AI_BASE_URL, AI_MODEL
from database import get_setting

# ================================
# 中转站配置
# 只需在 .env 里改这两项：
# AI_API_KEY=中转站给你的密钥
# AI_BASE_URL=中转站地址（例如 https://api.xxx.com/v1）
# ================================
client = AsyncOpenAI(
    api_key=AI_API_KEY,
    base_url=AI_BASE_URL,  # 中转站地址，OpenAI格式兼容
)


async def get_ai_response(user_message: str, user_name: str = "用户") -> str:
    try:
        preset = await get_setting("preset", "")
        persona = await get_setting(
            "persona", "你是一个友好的AI助理，请用简体中文回答。"
        )

        # 构建系统提示词（预设优先级最高）
        system_parts = []
        if preset:
            system_parts.append(f"[最高指令 - 必须遵守]\n{preset}")
        if persona:
            system_parts.append(f"[人设]\n{persona}")

        system_prompt = "\n\n".join(system_parts) if system_parts else "你是一个友好的AI助理。"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{user_name}: {user_message}"},
        ]

        response = await client.chat.completions.create(
            model=AI_MODEL,
            messages=messages,
            max_tokens=1000,
            temperature=0.8,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"⚠️ AI 服务出现错误：{str(e)}"
