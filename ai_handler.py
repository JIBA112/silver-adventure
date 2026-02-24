from openai import AsyncOpenAI
from config import AI_API_KEY, AI_BASE_URL, AI_MODEL
from database import get_setting

client = AsyncOpenAI(
    api_key=AI_API_KEY,
    base_url=AI_BASE_URL,
)

async def get_ai_response(user_message: str, user_name: str = "用户") -> str:
    try:
        preset = await get_setting("preset", "")
        persona = await get_setting("persona", "你是一个友好的AI助理，请用简体中文回答。")

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

        # 检查响应有效性，防止 'NoneType' object is not subscriptable
        if not response or not response.choices:
            return "对不起拉~有点小错误,没听清,能再说一遍吗?"

        return response.choices[0].message.content.strip()

    except Exception as e:
        # 捕获所有错误（包括网络、API、代码逻辑错误），统一返回要求的内容
        return "对不起拉~有点小错误,没听清,能再说一遍吗?"
