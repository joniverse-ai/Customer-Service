"""디자인코 고객응대 에이전트 — Streamlit 데모"""

import streamlit as st
from agent import run_agent

st.set_page_config(
    page_title="디자인코 고객응대",
    page_icon="🎨",
    layout="wide",
)

st.title("🎨 디자인코(DesignCo) 고객응대 에이전트")
st.caption("로고·브랜딩 디자인 전문 에이전시 — AI 고객 상담")

# 사이드바
with st.sidebar:
    st.header("ℹ️ 안내")
    st.markdown("""
    **디자인코** 고객응대 에이전트입니다.

    다음과 같은 문의를 처리할 수 있습니다:
    - 🎯 **서비스/견적** — 패키지, 가격, 작업 기간
    - ✏️ **수정/피드백** — 수정 횟수, 추가 비용
    - 💳 **결제/환불** — 환불 조건, 취소 절차
    - 📦 **납품/저작권** — 파일 형식, 저작권 이전
    """)

    st.divider()
    st.markdown("**테스트 프로젝트 ID**")
    st.code("""
PRJ-2024-001 (완료)
PRJ-2024-002 (수정 중)
PRJ-2024-003 (제작 중/긴급)
PRJ-2024-004 (검토 대기)
PRJ-2024-005 (브리핑 대기)
PRJ-2024-006 (최종 확인)
    """)

# 채팅 히스토리
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and "metadata" in msg:
            meta = msg["metadata"]
            with st.expander("🔍 상세 정보", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**라우트:** `{meta.get('route', '-')}`")
                    st.markdown(f"**확신도:** `{meta.get('confidence', 0):.2f}`")
                    st.markdown(f"**액션:** `{meta.get('action', '-')}`")
                with col2:
                    guard = meta.get('guardrail_ok')
                    guard_text = "✅ 통과" if guard else ("❌ 위반" if guard is False else "⏭️ 미검사")
                    st.markdown(f"**가드레일:** {guard_text}")
                    if meta.get('guardrail_violations'):
                        st.error(f"위반: {meta['guardrail_violations']}")

                if meta.get("tools_called"):
                    st.markdown("**호출한 도구:**")
                    for tool_name in meta["tools_called"]:
                        st.code(tool_name)

                if meta.get("tool_results"):
                    st.markdown("**도구 조회 결과:**")
                    for name, result in meta["tool_results"].items():
                        st.text_area(name, result, height=120, disabled=True, key=f"tool_{name}_{msg.get('idx', 0)}")

                if meta.get("context"):
                    st.markdown("**참조한 근거 문서:**")
                    with st.container(height=200):
                        st.markdown(meta["context"][:2000] + ("..." if len(meta["context"]) > 2000 else ""))

# 입력
if prompt := st.chat_input("문의사항을 입력하세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("답변 생성 중..."):
            try:
                result = run_agent(prompt)
                answer = result.get("answer", "죄송합니다, 답변을 생성하지 못했습니다.")

                metadata = {
                    "route": result.get("route", ""),
                    "confidence": result.get("confidence", 0),
                    "action": result.get("action", ""),
                    "tools_called": result.get("tools_called", []),
                    "tool_results": result.get("tool_results", {}),
                    "context": result.get("context", ""),
                    "guardrail_ok": result.get("guardrail_ok"),
                    "guardrail_violations": result.get("guardrail_violations", []),
                }

                st.markdown(answer)

                with st.expander("🔍 상세 정보", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**라우트:** `{metadata['route']}`")
                        st.markdown(f"**확신도:** `{metadata['confidence']:.2f}`")
                        st.markdown(f"**액션:** `{metadata['action']}`")
                    with col2:
                        guard = metadata['guardrail_ok']
                        guard_text = "✅ 통과" if guard else ("❌ 위반" if guard is False else "⏭️ 미검사")
                        st.markdown(f"**가드레일:** {guard_text}")
                        if metadata['guardrail_violations']:
                            st.error(f"위반: {metadata['guardrail_violations']}")

                    if metadata["tools_called"]:
                        st.markdown("**호출한 도구:**")
                        for tool_name in metadata["tools_called"]:
                            st.code(tool_name)

                    if metadata["tool_results"]:
                        st.markdown("**도구 조회 결과:**")
                        for name, res in metadata["tool_results"].items():
                            st.text_area(name, res, height=120, disabled=True, key=f"tool_{name}_latest")

                    if metadata["context"]:
                        st.markdown("**참조한 근거 문서:**")
                        with st.container(height=200):
                            st.markdown(metadata["context"][:2000] + ("..." if len(metadata["context"]) > 2000 else ""))

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "metadata": metadata,
                    "idx": len(st.session_state.messages),
                })

            except Exception as e:
                error_msg = f"오류가 발생했습니다: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                })
