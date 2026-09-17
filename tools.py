"""디자인코 고객응대 에이전트 — 조회 도구 함수"""

import json
import re
from pathlib import Path
from langchain_core.tools import tool

DATA_PATH = Path(__file__).parent / "data" / "mockdata.json"

def _load_data():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


@tool
def search_service(query: str) -> str:
    """디자인 서비스/패키지를 이름이나 카테고리로 검색합니다.
    query: 검색어 (예: '로고', 'BI', '명함', '패키지')
    """
    data = _load_data()
    query_lower = query.lower()
    matches = []
    for svc in data["services"]:
        searchable = f"{svc['name']} {svc['category']}".lower()
        if query_lower in searchable:
            rev = "무제한" if svc.get("revisions_unlimited") else f"{svc.get('revisions', '-')}회"
            info = (
                f"[{svc['service_id']}] {svc['name']} ({svc['category']})\n"
                f"  가격: {svc['price']:,}원(VAT 별도) | "
                f"작업일: {svc['working_days']}영업일 | "
                f"수정: {rev}"
            )
            matches.append(info)
    if not matches:
        return f"'{query}'에 해당하는 서비스를 찾지 못했습니다."
    return "\n\n".join(matches)


@tool
def get_service_detail(service_id: str) -> str:
    """서비스 ID로 상세 정보(포함 항목, 납품 파일, 옵션 등)를 조회합니다.
    service_id: 서비스 ID (예: 'SVC-001')
    """
    data = _load_data()
    for svc in data["services"]:
        if svc["service_id"] == service_id:
            rev = "무제한" if svc.get("revisions_unlimited") else f"{svc.get('revisions', '-')}회"
            lines = [
                f"서비스: {svc['name']} ({svc['category']})",
                f"가격: {svc['price']:,}원 (VAT 별도)",
                f"시안 수: {svc.get('drafts', '-')}개",
                f"수정 횟수: {rev}",
                f"작업일: {svc['working_days']}영업일",
                f"납품 파일: {', '.join(svc['deliverables'])}",
                f"원본 소스 포함: {'예' if svc['includes_source'] else '아니오'}",
            ]
            if "includes" in svc:
                lines.append(f"포함 항목: {', '.join(svc['includes'])}")
            return "\n".join(lines)
    return f"서비스 ID '{service_id}'를 찾을 수 없습니다. 올바른 서비스 ID를 확인해 주세요."


@tool
def get_project_status(project_id: str) -> str:
    """프로젝트 ID로 현재 진행 상태를 조회합니다.
    project_id: 프로젝트 ID (예: 'PRJ-2024-001')
    """
    data = _load_data()
    for prj in data["projects"]:
        if prj["project_id"] == project_id:
            status_map = {
                "PENDING": "결제 대기",
                "BRIEFING": "브리핑 대기/확인 중",
                "IN_PROGRESS": "시안 제작 중",
                "REVIEW": "시안 검토 대기 (고객 피드백 대기)",
                "REVISION": "수정 작업 중",
                "FINAL_CHECK": "최종 확인 대기",
                "COMPLETED": "납품 완료",
                "CANCELLED": "취소됨",
            }
            lines = [
                f"프로젝트: {prj['project_id']}",
                f"서비스: {prj['service_name']}",
                f"상태: {status_map.get(prj['status'], prj['status'])}",
                f"담당 디자이너: {prj['designer'] or '미배정'}",
                f"주문일: {prj['order_date']}",
            ]
            if prj["briefing_date"]:
                lines.append(f"브리핑 제출일: {prj['briefing_date']}")
            if prj["draft_delivered_date"]:
                lines.append(f"초안 시안 전달일: {prj['draft_delivered_date']}")
            if prj["selected_draft"] is not None:
                lines.append(f"선택 시안: {prj['selected_draft']}번")
            rev_total = prj.get("revisions_total")
            if rev_total is not None:
                lines.append(f"수정 횟수: {prj['revisions_used']}/{rev_total}회 사용")
            elif prj["revisions_used"] > 0:
                lines.append(f"수정 횟수: {prj['revisions_used']}회 사용 (무제한)")
            if prj["completion_date"]:
                lines.append(f"완료일: {prj['completion_date']}")
            if prj["delivery_date"]:
                lines.append(f"납품일: {prj['delivery_date']}")
            if prj["is_urgent"]:
                lines.append(f"긴급 작업: 예 (추가 요금 {prj.get('urgent_surcharge', 0):,}원)")
            if prj["status"] == "CANCELLED":
                lines.append(f"취소일: {prj.get('cancel_date', '-')}")
                lines.append(f"취소 사유: {prj.get('cancel_reason', '-')}")
            return "\n".join(lines)
    return f"프로젝트 ID '{project_id}'를 찾을 수 없습니다. 올바른 프로젝트 ID를 확인해 주세요."


@tool
def get_revision_info(project_id: str) -> str:
    """프로젝트의 수정 현황(남은 수정 횟수, 추가 수정 비용)을 조회합니다.
    project_id: 프로젝트 ID (예: 'PRJ-2024-002')
    """
    data = _load_data()
    for prj in data["projects"]:
        if prj["project_id"] == project_id:
            svc = next((s for s in data["services"] if s["service_id"] == prj["service_id"]), None)
            is_unlimited = svc and svc.get("revisions_unlimited", False)

            lines = [
                f"프로젝트: {prj['project_id']} ({prj['service_name']})",
                f"사용한 수정 횟수: {prj['revisions_used']}회",
            ]
            if is_unlimited:
                lines.append("수정 한도: 무제한")
                lines.append("추가 수정 비용: 해당 없음")
            else:
                total = prj.get("revisions_total", 0)
                remaining = max(0, total - prj["revisions_used"])
                lines.append(f"총 수정 횟수: {total}회")
                lines.append(f"남은 수정 횟수: {remaining}회")
                if remaining == 0:
                    category = svc["category"] if svc else ""
                    if "로고" in category:
                        extra_cost = 55000
                    elif "브랜드" in category or "BI" in category:
                        extra_cost = 88000
                    else:
                        extra_cost = 33000
                    lines.append(f"추가 수정 비용: 1회당 {extra_cost:,}원")
                else:
                    lines.append("추가 수정 비용: 남은 횟수 내 무료")
            return "\n".join(lines)
    return f"프로젝트 ID '{project_id}'를 찾을 수 없습니다."


@tool
def get_refund_info(project_id: str) -> str:
    """프로젝트의 환불 가능 여부 및 환불율을 조회합니다.
    project_id: 프로젝트 ID (예: 'PRJ-2024-004')
    """
    data = _load_data()
    for prj in data["projects"]:
        if prj["project_id"] == project_id:
            status = prj["status"]

            if status == "CANCELLED":
                return (
                    f"프로젝트 {project_id}는 이미 취소되었습니다.\n"
                    f"취소일: {prj.get('cancel_date', '-')}\n"
                    f"환불율: {int(prj.get('refund_rate', 0) * 100)}%\n"
                    f"환불 금액: {prj.get('refund_amount', 0):,}원"
                )
            if status == "COMPLETED":
                return (
                    f"프로젝트 {project_id}는 납품 완료 상태입니다.\n"
                    f"납품 완료 후에는 환불이 불가합니다.\n"
                    f"단, 디자인코 귀책 사유 시 협의 후 부분 환불 가능합니다."
                )

            if prj["is_urgent"]:
                return (
                    f"프로젝트 {project_id}는 긴급 작업으로 접수되었습니다.\n"
                    f"긴급 작업은 접수 후 취소가 불가합니다."
                )

            refund_map = {
                "PENDING": (1.0, "결제 대기 중 — 전액 환불 가능"),
                "BRIEFING": (0.9, "브리핑 단계 — 기획 착수 비용 10% 공제"),
                "IN_PROGRESS": (0.7, "시안 제작 중 — 작업 진행분 30% 공제"),
                "REVIEW": (0.5, "시안 전달 후 — 50% 환불"),
                "REVISION": (0.3, "수정 단계 — 30% 환불"),
                "FINAL_CHECK": (0.0, "최종 확인 단계 — 환불 불가"),
            }

            rate, desc = refund_map.get(status, (0.0, "환불 불가"))
            paid = prj["paid_amount"]
            refund_amount = int(paid * rate)

            lines = [
                f"프로젝트: {prj['project_id']} ({prj['service_name']})",
                f"현재 상태: {status}",
                f"환불 규정: {desc}",
                f"결제 금액: {paid:,}원",
                f"환불 가능 금액: {refund_amount:,}원",
            ]
            return "\n".join(lines)
    return f"프로젝트 ID '{project_id}'를 찾을 수 없습니다."


@tool
def get_payment_info(project_id: str) -> str:
    """프로젝트의 결제 현황(착수금, 잔금, 결제 수단)을 조회합니다.
    project_id: 프로젝트 ID (예: 'PRJ-2024-002')
    """
    data = _load_data()
    for prj in data["projects"]:
        if prj["project_id"] == project_id:
            lines = [
                f"프로젝트: {prj['project_id']} ({prj['service_name']})",
                f"총 금액: {prj['total_price']:,}원 (VAT 포함)",
                f"착수금: {prj['deposit']:,}원",
                f"잔금: {prj['balance']:,}원",
                f"잔금 결제 여부: {'완료' if prj['balance_paid'] else '미결제'}",
                f"결제 수단: {prj['payment_method'] or '미선택'}",
                f"결제 완료 금액: {prj['paid_amount']:,}원",
            ]
            remaining = prj["total_price"] - prj["paid_amount"]
            if remaining > 0:
                lines.append(f"미결제 잔액: {remaining:,}원")
            return "\n".join(lines)
    return f"프로젝트 ID '{project_id}'를 찾을 수 없습니다."


@tool
def get_delivery_info(project_id: str) -> str:
    """프로젝트의 납품 상태(파일 형식, 저작권 이전 여부, 다운로드 링크 만료일)를 조회합니다.
    project_id: 프로젝트 ID (예: 'PRJ-2024-001')
    """
    data = _load_data()
    for prj in data["projects"]:
        if prj["project_id"] == project_id:
            svc = next((s for s in data["services"] if s["service_id"] == prj["service_id"]), None)

            if prj["status"] != "COMPLETED":
                status_msg = {
                    "PENDING": "아직 결제가 완료되지 않았습니다.",
                    "BRIEFING": "브리핑 단계입니다. 아직 납품 전입니다.",
                    "IN_PROGRESS": "시안 제작 중입니다. 아직 납품 전입니다.",
                    "REVIEW": "시안 검토 대기 중입니다. 아직 납품 전입니다.",
                    "REVISION": "수정 작업 중입니다. 아직 납품 전입니다.",
                    "FINAL_CHECK": "최종 확인 대기 중입니다. 승인 후 납품됩니다.",
                    "CANCELLED": "취소된 프로젝트입니다.",
                }
                return (
                    f"프로젝트 {project_id} — {status_msg.get(prj['status'], '납품 전')}\n"
                    f"현재 상태: {prj['status']}"
                )

            lines = [
                f"프로젝트: {prj['project_id']} ({prj['service_name']})",
                f"납품일: {prj['delivery_date']}",
                f"다운로드 링크 만료일: {prj['delivery_link_expires']}",
                f"저작권 이전: {'완료' if prj['copyright_transferred'] else '미완료 (잔금 결제 필요)'}",
            ]
            if svc:
                lines.append(f"납품 파일 형식: {', '.join(svc['deliverables'])}")
                lines.append(f"원본 소스 포함: {'예' if svc['includes_source'] else '아니오'}")
            return "\n".join(lines)
    return f"프로젝트 ID '{project_id}'를 찾을 수 없습니다."


@tool
def get_copyright_info(project_id: str) -> str:
    """프로젝트의 저작권 이전 상태 및 원본 소스 구매 가능 여부를 조회합니다.
    project_id: 프로젝트 ID (예: 'PRJ-2024-001')
    """
    data = _load_data()
    for prj in data["projects"]:
        if prj["project_id"] == project_id:
            svc = next((s for s in data["services"] if s["service_id"] == prj["service_id"]), None)

            lines = [
                f"프로젝트: {prj['project_id']} ({prj['service_name']})",
                f"저작권 이전 여부: {'완료' if prj['copyright_transferred'] else '미완료'}",
            ]

            if not prj["copyright_transferred"]:
                if prj["status"] == "COMPLETED":
                    lines.append("사유: 잔금 결제 확인 필요")
                else:
                    lines.append("사유: 프로젝트 완료 및 잔금 결제 후 이전됩니다.")

            if svc:
                if svc["includes_source"]:
                    lines.append("원본 소스 파일: 패키지에 포함 (추가 비용 없음)")
                else:
                    category = svc["category"]
                    if "로고" in category:
                        source_price = 110000
                    elif "브랜드" in category or "BI" in category:
                        source_price = 220000
                    else:
                        source_price = 110000
                    lines.append(f"원본 소스 파일: 별도 구매 필요 ({source_price:,}원)")

            lines.append("포트폴리오 사용: 기본 허용 (비공개 원하시면 별도 요청, 추가 비용 없음)")
            return "\n".join(lines)
    return f"프로젝트 ID '{project_id}'를 찾을 수 없습니다."


@tool
def escalate_to_agent(reason: str, context: str) -> str:
    """고객 문의를 담당자에게 에스컬레이션합니다. 자동 응답으로 해결할 수 없는 경우 사용합니다.
    reason: 에스컬레이션 사유
    context: 고객 문의 내용 요약
    """
    return (
        f"담당자에게 문의가 전달되었습니다.\n"
        f"사유: {reason}\n"
        f"내용: {context}\n"
        f"담당자가 영업일 기준 1일 이내에 연락드리겠습니다."
    )


ALL_TOOLS = [
    search_service,
    get_service_detail,
    get_project_status,
    get_revision_info,
    get_refund_info,
    get_payment_info,
    get_delivery_info,
    get_copyright_info,
    escalate_to_agent,
]
