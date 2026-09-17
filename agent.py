"""디자인코 고객응대 에이전트 — LangGraph 파이프라인

입력 → 카테고리 판정 → 근거 조립 → 답변(도구 호출) → 가드레일 검증
                                                       ↓ (위반 시)
                                           재시도 or 에스컬레이션
"""

import json
import operator
import os
import re
from typing import Annotated, List, Optional
from typing_extensions import TypedDict

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from context import build_context
from prompts import FIXED_NUMBERS, get_answer_prompt, get_router_prompt
from tools import ALL_TOOLS


# ── State 정의 ───────────────────────────────────────────

class AgentState(TypedDict, total=False):
    question: str
    history: List[str]
    route: str
    confidence: float
    action: str
    context: str
    tools_called: List[str]
    tool_results: dict
    answer: str
    guardrail_ok: Optional[bool]
    guardrail_violations: List[str]
    attempts: int


# ── 모델 초기화 ──────────────────────────────────────────

router_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
answer_llm = ChatOpenAI(model="gpt-4o", temperature=0)


# ── 1. 라우터 노드 ───────────────────────────────────────

def node_route(state: dict) -> dict:
    question = state["question"]
    prompt = get_router_prompt()

    response = router_llm.invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=question),
    ])

    try:
        text = response.content.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        result = json.loads(text)
        route = result.get("route", "OTHER")
        confidence = float(result.get("confidence", 0.0))
    except (json.JSONDecodeError, ValueError):
        route = "OTHER"
        confidence = 0.0

    if confidence < 0.6:
        route = "OTHER"

    action = "ESCALATE" if route == "OTHER" else "HANDLE"

    return {
        "route": route,
        "confidence": confidence,
        "action": action,
    }


# ── 2. 컨텍스트 조립 + 답변 노드 (도구 호출 포함) ──────

def node_answer(state: dict) -> dict:
    route = state["route"]
    question = state["question"]

    context = build_context(route)
    system_prompt = get_answer_prompt(context)

    llm_with_tools = answer_llm.bind_tools(ALL_TOOLS)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=question),
    ]

    tools_called = []
    tool_results = {}
    tool_map = {t.name: t for t in ALL_TOOLS}
    max_tool_rounds = 5

    for _ in range(max_tool_rounds):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            tools_called.append(tool_name)

            if tool_name in tool_map:
                result = tool_map[tool_name].invoke(tool_args)
            else:
                result = f"도구 '{tool_name}'을 찾을 수 없습니다."

            tool_results[tool_name] = str(result)

            from langchain_core.messages import ToolMessage
            messages.append(ToolMessage(
                content=str(result),
                tool_call_id=tc["id"],
            ))

    answer = response.content if response.content else ""

    if "escalate_to_agent" in tools_called:
        action = "ESCALATE"
    elif not answer.strip():
        action = "ASK"
    else:
        action = "ANSWER"

    return {
        "context": context,
        "tools_called": tools_called,
        "tool_results": tool_results,
        "answer": answer,
        "action": action,
    }


# ── 3. 가드레일 노드 ────────────────────────────────────

def _extract_numbers(text: str) -> set:
    nums = set()
    for m in re.finditer(r"[\d,]+(?:\.\d+)?", text):
        s = m.group().replace(",", "")
        try:
            if "." in s:
                nums.add(float(s))
            else:
                nums.add(int(s))
        except ValueError:
            continue
    return nums


def _build_allowed_set(tool_results: dict, fixed: set) -> set:
    allowed = set(fixed)
    for result_text in tool_results.values():
        allowed |= _extract_numbers(result_text)
    base = set(allowed)
    for a in base:
        for b in base:
            if a == 0 or b == 0:
                continue
            for op_result in [a + b, a - b, a * b]:
                if isinstance(op_result, float):
                    if op_result == int(op_result):
                        allowed.add(int(op_result))
                allowed.add(op_result)
            if b != 0:
                div = a / b
                if div == int(div):
                    allowed.add(int(div))
                allowed.add(div)
    return allowed


def node_guard(state: dict) -> dict:
    answer = state.get("answer", "")
    tool_results = state.get("tool_results", {})
    attempts = state.get("attempts", 0)

    answer_nums = _extract_numbers(answer)
    allowed = _build_allowed_set(tool_results, FIXED_NUMBERS)

    violations = []
    for num in answer_nums:
        if num < 1000:
            continue
        if num not in allowed:
            violations.append(f"출처 불명 숫자: {num:,}")

    if violations:
        return {
            "guardrail_ok": False,
            "guardrail_violations": violations,
            "attempts": attempts + 1,
            "action": "RETRY" if attempts < 1 else "ESCALATE",
        }

    return {
        "guardrail_ok": True,
        "guardrail_violations": [],
        "action": "ANSWER",
    }


# ── 4. 에스컬레이션 노드 ────────────────────────────────

def node_escalate(state: dict) -> dict:
    route = state.get("route", "OTHER")
    question = state.get("question", "")
    violations = state.get("guardrail_violations", [])

    if violations:
        reason = f"가드레일 위반: {', '.join(violations)}"
    elif route == "OTHER":
        reason = "문의 카테고리 분류 불가 — 범위 밖 문의"
    else:
        reason = "자동 응답 처리 불가"

    from tools import escalate_to_agent
    result = escalate_to_agent.invoke({"reason": reason, "context": question})

    prev_tools = list(state.get("tools_called", []))
    prev_tools.append("escalate_to_agent")

    prev_results = dict(state.get("tool_results", {}))
    prev_results["escalate_to_agent"] = str(result)

    return {
        "answer": (
            "해당 문의는 담당자에게 전달하여 정확한 안내를 드리겠습니다. "
            "영업일 기준 1일 이내에 연락드리겠습니다."
        ),
        "action": "ESCALATE",
        "tools_called": prev_tools,
        "tool_results": prev_results,
    }


# ── 라우팅 함수 ──────────────────────────────────────────

def after_route(state: dict) -> str:
    if state.get("action") == "ESCALATE":
        return "escalate"
    return "answer"


def after_answer(state: dict) -> str:
    action = state.get("action", "")
    if action == "ESCALATE":
        return "escalate"
    if action == "ASK":
        return END
    return "guard"


def after_guard(state: dict) -> str:
    action = state.get("action", "")
    if action == "ANSWER":
        return END
    if action == "RETRY":
        return "answer"
    return "escalate"


# ── 그래프 빌드 ──────────────────────────────────────────

def build_agent():
    g = StateGraph(AgentState)

    g.add_node("route", node_route)
    g.add_node("answer", node_answer)
    g.add_node("guard", node_guard)
    g.add_node("escalate", node_escalate)

    g.add_edge(START, "route")
    g.add_conditional_edges("route", after_route, {"answer": "answer", "escalate": "escalate"})
    g.add_conditional_edges("answer", after_answer, {"guard": "guard", "escalate": "escalate", END: END})
    g.add_conditional_edges("guard", after_guard, {"answer": "answer", "escalate": "escalate", END: END})
    g.add_edge("escalate", END)

    return g.compile()


agent = build_agent()


def run_agent(question: str) -> dict:
    """에이전트를 실행하고 전체 상태를 반환한다."""
    initial_state = {
        "question": question,
        "history": [],
        "route": "",
        "confidence": 0.0,
        "action": "",
        "context": "",
        "tools_called": [],
        "tool_results": {},
        "answer": "",
        "guardrail_ok": None,
        "guardrail_violations": [],
        "attempts": 0,
    }
    result = agent.invoke(initial_state)
    return result


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "로고 디자인 가격이 어떻게 되나요?"
    result = run_agent(q)
    print(f"\n[라우트] {result['route']} (확신도: {result['confidence']:.2f})")
    print(f"[호출 도구] {result['tools_called']}")
    print(f"[가드레일] {'통과' if result.get('guardrail_ok') else '위반'}")
    print(f"[답변]\n{result['answer']}")
