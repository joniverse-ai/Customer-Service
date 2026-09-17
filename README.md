# 🎨 디자인코(DesignCo) 고객응대 라우팅 에이전트

LangGraph + GPT-4o 기반 고객 문의 자동 분류 및 응대 시스템

## 빠른 시작

### 1. 레포 클론

```bash
git clone https://github.com/joniverse-ai/Customer-Service.git
cd Customer-Service
```

### 2. 가상환경 생성 및 의존성 설치

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install scikit-learn    # 평가 실행 시 필요
```

### 3. API 키 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 OpenAI API 키를 입력합니다:

```
OPENAI_API_KEY=sk-your-actual-api-key
```

### 4. 데모 실행

**Chainlit (권장)**
```bash
chainlit run app_chainlit.py -w
```
브라우저에서 `http://localhost:8000`으로 접속합니다.

**Streamlit**
```bash
streamlit run app.py
```
브라우저에서 `http://localhost:8501`이 자동으로 열립니다.

### 5. 평가 실행

```bash
python evaluate.py
```

15건의 Golden Set으로 라우팅 정확도, 도구 호출 적절성, 답변 적절성, macro F1을 측정합니다.

### 6. 단일 질문 테스트

```bash
python agent.py "로고 디자인 가격이 어떻게 되나요?"
```

## 테스트 질문 예시

| 질문 | 카테고리 |
|------|---------|
| 로고 디자인 가격이 어떻게 되나요? | SERVICE_INFO |
| PRJ-2024-004 수정 몇 번 남았나요? | REVISION |
| PRJ-2024-004 지금 취소하면 얼마나 돌려받을 수 있어요? | PAYMENT_REFUND |
| PRJ-2024-001 저작권이 제 것인가요? | DELIVERY_COPYRIGHT |
| 디자인 작업을 AI로 하시나요? | OTHER (에스컬레이션) |

## 프로젝트 구조

```
├── agent.py          # LangGraph 파이프라인 (핵심)
├── tools.py          # 9종 도구 함수
├── context.py        # 카테고리-문서 매핑
├── prompts.py        # 프롬프트 + 가드레일 고정값
├── evaluate.py       # 평가 모듈
├── app.py            # Streamlit 데모
├── app_chainlit.py   # Chainlit 데모
├── data/
│   ├── goldenset.json  # 평가셋 (15건 + 예시 3건)
│   └── mockdata.json   # 서비스·프로젝트·디자이너 데이터
├── docs/
│   ├── service_guide.md       # 서비스 가이드
│   ├── refund_policy.md       # 환불 정책
│   ├── delivery_copyright.md  # 납품·저작권 가이드
│   └── terms_of_service.md    # 이용약관
├── REPORT.md         # 프로젝트 리포트
└── requirements.txt
```

## 파이프라인 흐름

```
고객 문의 → [Route] → [Context] → [Answer + Tools] → [Guardrail] → 답변
              │                                            │
              └─ OTHER ──→ [Escalate] ←── 위반 시 ─────────┘
```

## 요구사항

- Python 3.9+
- OpenAI API 키 (gpt-4o, gpt-4o-mini 사용)
