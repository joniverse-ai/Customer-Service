"""카테고리별 근거 문서 조립 — 카테고리에 따라 필요한 부분만 프롬프트에 넣는다."""

from pathlib import Path

DOCS_DIR = Path(__file__).parent / "docs"

def _read(filename: str) -> str:
    return (DOCS_DIR / filename).read_text(encoding="utf-8")


from typing import Dict, List, Tuple

SECTION_MAP: Dict[str, List[Tuple[str, List[str]]]] = {
    "SERVICE_INFO": [
        ("service_guide.md", [
            "## 1. 회사 소개",
            "## 2. 서비스 종류 및 가격",
            "## 3. 작업 프로세스",
            "## 5. 작업 기간 안내",
        ]),
        ("terms_of_service.md", [
            "## 제2조 (서비스 범위)",
            "## 제3조 (계약의 성립)",
        ]),
    ],
    "REVISION": [
        ("service_guide.md", [
            "## 4. 수정 정책",
            "## 5. 작업 기간 안내",
        ]),
    ],
    "PAYMENT_REFUND": [
        ("refund_policy.md", [
            "## 1. 취소 및 환불 기본 원칙",
            "## 2. 단계별 환불 규정",
            "## 3. 환불 불가 항목",
            "## 4. 환불 절차",
            "## 5. 결제 방법별 환불 안내",
            "## 6. 프로젝트 일시 중단",
        ]),
        ("terms_of_service.md", [
            "## 제4조 (결제)",
            "## 제8조 (취소 및 환불)",
        ]),
    ],
    "DELIVERY_COPYRIGHT": [
        ("delivery_copyright.md", [
            "## 1. 납품 파일 형식",
            "## 2. 납품 방식",
            "## 3. 저작권 규정",
            "## 4. 상표 등록 관련 안내",
            "## 5. 데이터 보관 정책",
        ]),
        ("terms_of_service.md", [
            "## 제7조 (지식재산권)",
        ]),
    ],
    "OTHER": [],
}


def _extract_section(full_text: str, heading: str) -> str:
    """마크다운 문서에서 특정 ## 섹션을 추출한다."""
    idx = full_text.find(heading)
    if idx == -1:
        return ""
    end = len(full_text)
    search_start = idx + len(heading)
    level = heading.count("#", 0, heading.index(" "))
    prefix = "#" * level + " "
    next_heading = full_text.find(f"\n{prefix}", search_start)
    if next_heading != -1:
        end = next_heading
    higher_prefix = "#" * (level - 1) + " " if level > 1 else None
    if higher_prefix:
        next_higher = full_text.find(f"\n{higher_prefix}", search_start)
        if next_higher != -1:
            end = min(end, next_higher)
    return full_text[idx:end].strip()


def build_context(route: str) -> str:
    """라우트에 해당하는 근거 문서 조각들을 조립해서 반환한다."""
    if route not in SECTION_MAP or not SECTION_MAP[route]:
        return ""

    parts: list[str] = []
    file_cache: Dict[str, str] = {}

    for filename, headings in SECTION_MAP[route]:
        if filename not in file_cache:
            file_cache[filename] = _read(filename)
        full_text = file_cache[filename]
        for heading in headings:
            section = _extract_section(full_text, heading)
            if section:
                parts.append(section)

    return "\n\n---\n\n".join(parts)


ROUTE_DESCRIPTIONS = {
    "SERVICE_INFO": "서비스 종류, 가격, 견적, 작업 기간, 패키지 비교, 포함 항목, 긴급 작업 추가 비용, 프로젝트 진행 상황, 담당 디자이너 등 서비스 및 프로젝트 일반 정보 문의",
    "REVISION": "시안 수정 횟수, 추가 수정 비용, 수정 범위, 피드백 방법, 피드백 기한, 컨셉 변경 비용 등 수정(리비전) 관련 문의. 긴급 작업 비용은 SERVICE_INFO에 해당",
    "PAYMENT_REFUND": "결제 방법, 착수금/잔금, 환불 조건, 취소 절차, 세금계산서, 프로젝트 중단 등 결제/환불 문의",
    "DELIVERY_COPYRIGHT": "납품 파일 형식, 저작권 이전, 원본 소스 파일, 상표 등록, 데이터 보관, 다운로드 링크 등 납품/저작권 문의",
    "OTHER": "위 카테고리에 해당하지 않는 문의 — 담당자에게 전달 필요",
}
