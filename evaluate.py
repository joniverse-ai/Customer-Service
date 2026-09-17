"""평가 모듈 — 도구 호출 적절성 + 답변 적절성 측정"""

import json
import re
from pathlib import Path
from collections import Counter
from typing import Dict, List, Tuple

from sklearn.metrics import classification_report, confusion_matrix

from agent import run_agent

GOLDEN_PATH = Path(__file__).parent / "data" / "goldenset.json"


def load_goldenset(use_filter: str = "eval") -> List[Dict]:
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if use_filter:
        data = [d for d in data if d.get("use") == use_filter]
    return data


def norm_num(s: str) -> str:
    return s.replace(",", "").strip()


def score_tool_call(expected_tools: List[str], actual_tools: List[str]) -> Tuple[bool, List[str]]:
    """도구 호출 적절성: 기대 도구와 실제 도구가 정확히 일치하면 1점"""
    expected_set = set(expected_tools)
    actual_set = set(actual_tools)

    fails = []
    missing = expected_set - actual_set
    extra = actual_set - expected_set

    if missing:
        fails.append(f"미호출: {missing}")
    if extra:
        fails.append(f"불필요 호출: {extra}")

    return (not fails), fails


def score_answer(must: List[str], forbid: List[str], answer: str) -> Tuple[bool, List[str]]:
    """답변 적절성: 필수 사실 전부 포함 + 금지 표현 없으면 1점"""
    fails = []
    answer_norm = norm_num(answer)

    for m in must:
        if norm_num(m) not in answer_norm:
            fails.append(f"필수 누락: '{m}'")

    for f in forbid:
        if norm_num(f) in answer_norm:
            fails.append(f"금지 위반: '{f}'")

    return (not fails), fails


def verify_scorer(goldenset: List[Dict]) -> bool:
    """채점기 자체를 모범 답안으로 검증한다."""
    all_pass = True
    for item in goldenset:
        ref = item.get("reference", "")
        ok, fails = score_answer(item["must"], item["forbid"], ref)
        if not ok:
            print(f"[채점기 검증 실패] ID {item['id']}: {fails}")
            all_pass = False
    return all_pass


def evaluate(goldenset=None, verbose: bool = True) -> dict:
    """전체 평가 실행"""
    if goldenset is None:
        goldenset = load_goldenset("eval")

    print(f"\n{'='*60}")
    print(f"평가 시작: {len(goldenset)}건")
    print(f"{'='*60}\n")

    # 채점기 검증
    if not verify_scorer(goldenset):
        print("[경고] 채점기 검증 실패 — 모범 답안과 채점 기준이 불일치합니다.")
        print("평가를 중단합니다. goldenset을 수정해 주세요.\n")
        return {}

    print("[채점기 검증 통과] 모범 답안 전체가 채점 기준을 만족합니다.\n")

    results = []
    route_true = []
    route_pred = []

    for item in goldenset:
        qid = item["id"]
        question = item["question"]

        if verbose:
            print(f"--- [{qid}] {question}")

        try:
            state = run_agent(question)
        except Exception as e:
            if verbose:
                print(f"  [오류] {e}")
            results.append({
                "id": qid,
                "question": question,
                "error": str(e),
                "tool_ok": False,
                "answer_ok": False,
            })
            continue

        # 라우팅 정확도
        route_true.append(item["expected_route"])
        route_pred.append(state.get("route", "OTHER"))

        # 도구 호출 적절성
        tool_ok, tool_fails = score_tool_call(
            item["expected_tools"],
            state.get("tools_called", [])
        )

        # 답변 적절성
        answer_ok, answer_fails = score_answer(
            item["must"],
            item["forbid"],
            state.get("answer", "")
        )

        results.append({
            "id": qid,
            "question": question,
            "expected_route": item["expected_route"],
            "actual_route": state.get("route"),
            "route_correct": item["expected_route"] == state.get("route"),
            "tool_ok": tool_ok,
            "tool_fails": tool_fails,
            "answer_ok": answer_ok,
            "answer_fails": answer_fails,
            "answer": state.get("answer", ""),
            "guardrail_ok": state.get("guardrail_ok"),
        })

        if verbose:
            route_mark = "O" if item["expected_route"] == state.get("route") else "X"
            tool_mark = "O" if tool_ok else "X"
            ans_mark = "O" if answer_ok else "X"
            print(f"  라우트: {route_mark} ({state.get('route')})")
            print(f"  도구:   {tool_mark} {tool_fails if tool_fails else ''}")
            print(f"  답변:   {ans_mark} {answer_fails if answer_fails else ''}")
            print()

    # 집계
    total = len(results)
    tool_acc = sum(1 for r in results if r["tool_ok"]) / total if total else 0
    answer_acc = sum(1 for r in results if r["answer_ok"]) / total if total else 0
    route_acc = sum(1 for r in results if r.get("route_correct")) / total if total else 0

    # 카테고리별 라우팅 정확도
    route_detail = {}
    for item, result in zip(goldenset, results):
        cat = item["expected_route"]
        if cat not in route_detail:
            route_detail[cat] = {"total": 0, "correct": 0}
        route_detail[cat]["total"] += 1
        if result.get("route_correct"):
            route_detail[cat]["correct"] += 1

    summary = {
        "total": total,
        "route_accuracy": route_acc,
        "tool_call_accuracy": tool_acc,
        "answer_accuracy": answer_acc,
        "route_detail": route_detail,
        "results": results,
    }

    print(f"\n{'='*60}")
    print(f"평가 결과 요약")
    print(f"{'='*60}")
    print(f"총 문항: {total}건")
    print(f"라우팅 정확도:      {route_acc:.1%}")
    print(f"도구 호출 적절성:   {tool_acc:.1%}")
    print(f"답변 적절성:        {answer_acc:.1%}")
    print(f"\n카테고리별 라우팅:")
    for cat, detail in route_detail.items():
        print(f"  {cat}: {detail['correct']}/{detail['total']}")

    # macro F1 및 혼동행렬
    if route_true and route_pred:
        labels = sorted(set(route_true + route_pred))
        print(f"\n{'='*60}")
        print("라우팅 분류 리포트 (precision / recall / F1)")
        print(f"{'='*60}")
        print(classification_report(route_true, route_pred, labels=labels, zero_division=0))

        print("혼동행렬:")
        cm = confusion_matrix(route_true, route_pred, labels=labels)
        header = "예측→  " + "  ".join(f"{l[:8]:>8}" for l in labels)
        print(header)
        for i, label in enumerate(labels):
            row = "  ".join(f"{cm[i][j]:>8}" for j in range(len(labels)))
            print(f"{label[:8]:>8}  {row}")
        print()

        summary["classification_report"] = classification_report(
            route_true, route_pred, labels=labels, zero_division=0, output_dict=True
        )
        summary["confusion_matrix"] = cm.tolist()

    # 실패 사례 분석
    failures = [r for r in results if not r["tool_ok"] or not r["answer_ok"]]
    if failures:
        print(f"\n실패 사례 분석 ({len(failures)}건):")
        for f in failures:
            print(f"  [{f['id']}] {f['question']}")
            if not f["tool_ok"]:
                print(f"    도구 실패: {f.get('tool_fails', [])}")
            if not f["answer_ok"]:
                print(f"    답변 실패: {f.get('answer_fails', [])}")

    return summary


if __name__ == "__main__":
    evaluate()
