"""디자인코 고객응대 에이전트 — Chainlit 데모"""

import chainlit as cl
from agent import run_agent


WELCOME_MESSAGE = """## 🎨 디자인코(DesignCo) 고객응대 에이전트

로고·브랜딩 디자인 전문 에이전시 — AI 고객 상담

**처리 가능한 문의:**
- 🎯 서비스/견적 — 패키지, 가격, 작업 기간
- ✏️ 수정/피드백 — 수정 횟수, 추가 비용
- 💳 결제/환불 — 환불 조건, 취소 절차
- 📦 납품/저작권 — 파일 형식, 저작권 이전

**테스트 프로젝트 ID:**
`PRJ-2024-001`(완료) · `PRJ-2024-002`(수정 중) · `PRJ-2024-003`(제작 중/긴급) · `PRJ-2024-004`(검토 대기)
"""


@cl.on_chat_start
async def start():
    await cl.Message(content=WELCOME_MESSAGE).send()


@cl.on_message
async def main(message: cl.Message):
    msg = cl.Message(content="")
    await msg.send()

    result = await cl.make_async(run_agent)(message.content)
    answer = result.get("answer", "죄송합니다, 답변을 생성하지 못했습니다.")

    msg.content = answer
    await msg.update()

    # 라우팅 정보 Step
    route = result.get("route", "-")
    confidence = result.get("confidence", 0)
    action = result.get("action", "-")
    guard = result.get("guardrail_ok")
    guard_text = "✅ 통과" if guard else ("❌ 위반" if guard is False else "⏭️ 미검사")

    async with cl.Step(name="📋 라우팅 정보", parent_id=msg.id) as step:
        step.output = (
            f"**라우트:** `{route}`\n\n"
            f"**확신도:** `{confidence:.2f}`\n\n"
            f"**액션:** `{action}`\n\n"
            f"**가드레일:** {guard_text}"
        )
        if result.get("guardrail_violations"):
            step.output += f"\n\n**위반 사항:** {', '.join(result['guardrail_violations'])}"

    # 도구 호출 Step
    tools_called = result.get("tools_called", [])
    if tools_called:
        async with cl.Step(name=f"🔧 도구 호출 ({len(tools_called)}건)", parent_id=msg.id) as tools_step:
            tool_results = result.get("tool_results", {})
            tool_summary = []
            for tool_name in tools_called:
                tool_result = tool_results.get(tool_name, "결과 없음")
                tool_summary.append(f"### {tool_name}\n```\n{tool_result}\n```")
            tools_step.output = "\n\n".join(tool_summary)

    # 참조 문서 Step
    context = result.get("context", "")
    if context:
        async with cl.Step(name="📄 참조 근거 문서", parent_id=msg.id) as ctx_step:
            ctx_step.output = context[:3000] + ("..." if len(context) > 3000 else "")
