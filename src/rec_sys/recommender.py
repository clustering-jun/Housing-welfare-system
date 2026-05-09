from pathlib import Path
from typing import Optional
import hashlib
import json
import re

from openai import OpenAI

from rec_sys.community_retriever import format_for_prompt, get_example_programs
from rec_sys.config import CACHE_DIR
from rec_sys.program_catalog import COMPLEMENTARY_CANDIDATES, CORE_CANDIDATES, EXAMPLE_ACTIVITIES, PROGRAM_CATALOG, get_program_display_name, score_programs, select_programs


CACHE_DIR.mkdir(exist_ok=True)
CACHE_VERSION = "public_v1"
BANNED_TERMS = ["이동식", "이동형", "의료차", "셔틀", "경로당 설치", "복지관 설치", "신설", "건립", "대규모 공사"]
SYSTEM_PROMPT = "당신은 주택관리공단 임대주택 단지의 주거복지 프로그램 추천 전문가입니다. 추천은 반드시 제공된 P01~P12 공식 사업 카탈로그 안에서만 고르세요. 이동식, 이동형, 의료차, 셔틀, 설치, 신설, 건립, 대규모 공사 표현은 쓰지 마세요. JSON 객체만 응답하세요."


def cache_key(complex_id: str, model: str) -> str:
    return hashlib.md5(f"{complex_id}_{model}_{CACHE_VERSION}".encode("utf-8")).hexdigest()


def load_cache(key: str) -> Optional[dict]:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_cache(key: str, data: dict) -> None:
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_cache(complex_id: Optional[str] = None, model: str = "gpt-4o") -> None:
    if complex_id:
        path = CACHE_DIR / f"{cache_key(complex_id, model)}.json"
        if path.exists():
            path.unlink()
        return
    for path in CACHE_DIR.glob("*.json"):
        if path.name != ".gitkeep":
            path.unlink()


def parse_json(content: str) -> dict:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    return {"error": "LLM 응답을 JSON으로 해석하지 못했습니다.", "raw": text[:500]}


def sanitize_text(value: str) -> str:
    text = str(value or "")
    replacements = {"이동식": "찾아가는", "이동형": "방문형", "의료차": "보건소 연계 방문상담", "셔틀": "외부기관 연계", "경로당 설치": "경로당 이용 연계", "복지관 설치": "복지관 프로그램 연계", "신설": "운영", "건립": "연계", "대규모 공사": "서비스 연계"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.strip()


def pct(value):
    return "미상" if value is None else f"{float(value) * 100:.1f}%"


def num(value, digits=3):
    return "미상" if value is None else f"{float(value):.{digits}f}"


def format_programs(program_ids: list[str], title: str, reasons: dict[str, list[str]]) -> str:
    lines = [f"### {title}"]
    if not program_ids:
        return "\n".join(lines + ["- 없음"])
    for pid in program_ids:
        program = PROGRAM_CATALOG[pid]
        lines.append(f"- {pid} | {program['name']} | {program['category']}\n  설명: {program['description']}\n  선정 근거: {', '.join(reasons.get(pid, program['conditions'][:2]))}")
    return "\n".join(lines)


def format_candidates(program_ids: list[str], title: str) -> str:
    lines = [f"### {title}"]
    if not program_ids:
        return "\n".join(lines + ["- 없음"])
    for pid in program_ids:
        program = PROGRAM_CATALOG[pid]
        lines.append(f"- {pid} | {program['name']} | {program['category']} | 조건: {', '.join(program['conditions'])}")
    return "\n".join(lines)


def build_prompt(detail: dict, rule_core: list[str], rule_comp: list[str], llm_core: list[str], llm_comp: list[str], reasons: dict[str, list[str]]) -> str:
    vuln = detail.get("vulnerability_detail", {})
    acc = detail.get("accessibility", {})
    comm = detail.get("community", {})
    hd = detail.get("home_doctor", {})
    gov = detail.get("governance", {})
    examples = format_for_prompt(get_example_programs(detail))
    lines = [
        "단지 요약",
        f"- 단지명: {detail.get('name')} ({detail.get('village')})",
        f"- 위치: {detail.get('sido')} {detail.get('sigungu')} {detail.get('emd')}",
        f"- 공급유형: {detail.get('supply_type')}",
        f"- 건설호수: {detail.get('total_units')}호 / 총인구: {detail.get('total_population')}명",
        f"- 고령화율: {pct(detail.get('elderly_rate'))} / 초고령비율: {pct(detail.get('super_elderly_rate'))} / 아동청소년비율: {pct(detail.get('child_youth_rate'))}",
        f"- 종합 취약도: {num(vuln.get('total'))} / 순위: {detail.get('rank')} / 등급: {detail.get('risk_grade')}",
        f"- 주요 취약 원인: {detail.get('main_causes')}",
        f"- 시설 취약도: {num(vuln.get('facility'))} / 접근성 취약도: {num(vuln.get('accessibility'))} / 서비스 이용 취약도: {num(vuln.get('service'))}",
        f"- 거버넌스 취약도: {num(vuln.get('governance'))} / 이상탐지 점수: {num(vuln.get('anomaly'))}",
        f"- 의료 접근성: {num(acc.get('medical'))} / 복지 접근성: {num(acc.get('welfare'))} / 문화 접근성: {num(acc.get('culture'))} / 돌봄 접근성: {num(acc.get('care'))}",
        f"- 커뮤니티 활동횟수: {num(comm.get('total_activities'), 1)} / 세대당 참여인원: {num(comm.get('participants_per_household'))}",
        f"- 홈닥터 세대당 지원건수: {num(hd.get('supports_per_household'))} / 경제지원 비율: {pct(hd.get('economic_rate'))} / 서비스 이용률: {pct(hd.get('usage_rate'))}",
        f"- 거버넌스 평균 연간합계: {num(gov.get('avg_annual'), 1)} / 악화중 여부: {gov.get('worsening')}",
        "",
        "규칙 기반으로 이미 선정된 프로그램",
        format_programs(rule_core, "핵심 프로그램", reasons),
        format_programs(rule_comp, "보완 프로그램", reasons),
        "",
        "LLM이 추가 선택할 수 있는 후보",
        format_candidates(llm_core, "추가 핵심 후보"),
        format_candidates(llm_comp, "추가 보완 후보"),
        "",
        "운영 프로그램 참고",
        examples,
        "",
        "JSON 필드: overall_assessment, urgent_needs, rule_based_programs, llm_selected_programs, implementation_roadmap, monitoring_indicators.",
        "각 프로그램 항목은 catalog_id, program_title, target, description, rationale, implementation, expected_effect, priority를 포함하세요.",
    ]
    return "\n".join(lines)


def build_entry(pid: str, narrative: dict, is_core: bool, method: str, reasons: dict[str, list[str]], detail: dict) -> dict:
    program = PROGRAM_CATALOG[pid]
    entry = {
        "name": sanitize_text(narrative.get("program_title") or get_program_display_name(pid, detail)),
        "official_name": program["name"],
        "category": program["category"],
        "catalog_id": pid,
        "selection_method": method,
        "target": sanitize_text(narrative.get("target") or "취약 입주민"),
        "description": sanitize_text(narrative.get("description") or program["description"]),
        "rationale": sanitize_text(narrative.get("rationale") or "단지 취약도와 인구·서비스 이용 특성을 근거로 선정했습니다."),
        "implementation": sanitize_text(narrative.get("implementation") or "관리소, 주거복지 담당자, 지역 유관기관이 협력해 정기 운영합니다."),
        "expected_effect": sanitize_text(narrative.get("expected_effect") or "입주민의 생활 안정과 서비스 접근성 개선이 기대됩니다."),
        "fit_reasons": reasons.get(pid, program["conditions"][:2]),
        "example_activities": EXAMPLE_ACTIVITIES.get(pid, [])[:4],
    }
    if is_core:
        entry["priority"] = sanitize_text(narrative.get("priority") or "중")
    return entry


def postprocess(llm_result: dict, rule_core: list[str], rule_comp: list[str], reasons: dict[str, list[str]], score_order: list[str], detail: dict) -> dict:
    rule_ids = set(rule_core + rule_comp)
    narratives = {str(item.get("catalog_id", "")).strip(): item for item in llm_result.get("rule_based_programs", []) if str(item.get("catalog_id", "")).strip() in PROGRAM_CATALOG}
    llm_narratives = {str(item.get("catalog_id", "")).strip(): item for item in llm_result.get("llm_selected_programs", []) if str(item.get("catalog_id", "")).strip() in PROGRAM_CATALOG and str(item.get("catalog_id", "")).strip() not in rule_ids}
    core_ids = list(rule_core)
    comp_ids = list(rule_comp)
    for pid in llm_narratives:
        if pid in CORE_CANDIDATES and len(core_ids) < 4:
            core_ids.append(pid)
        elif pid in COMPLEMENTARY_CANDIDATES and len(comp_ids) < 2:
            comp_ids.append(pid)
    for pid in score_order:
        if len(core_ids) >= 3 and len(comp_ids) >= 1:
            break
        if pid in rule_ids or pid in core_ids or pid in comp_ids:
            continue
        if pid in CORE_CANDIDATES and len(core_ids) < 3:
            core_ids.append(pid)
        elif pid in COMPLEMENTARY_CANDIDATES and len(comp_ids) < 1:
            comp_ids.append(pid)
    return {
        "overall_assessment": sanitize_text(llm_result.get("overall_assessment", "")),
        "urgent_needs": sanitize_text(llm_result.get("urgent_needs", "")),
        "core_programs": [build_entry(pid, narratives.get(pid) or llm_narratives.get(pid, {}), True, "rule_based" if pid in rule_ids else "llm_selected", reasons, detail) for pid in core_ids],
        "complementary_programs": [build_entry(pid, narratives.get(pid) or llm_narratives.get(pid, {}), False, "rule_based" if pid in rule_ids else "llm_selected", reasons, detail) for pid in comp_ids],
        "implementation_roadmap": sanitize_text(llm_result.get("implementation_roadmap", "단기에는 대상 세대 발굴과 협력기관 연결을 시작하고, 중기에는 정기 프로그램을 운영하며, 장기에는 참여율과 지원 실적을 점검해 조정합니다.")),
        "monitoring_indicators": [sanitize_text(x) for x in llm_result.get("monitoring_indicators", [])[:5]] or ["대상 세대 발굴 수", "프로그램 참여율", "사례관리 연계 건수"],
    }


def fallback_result(detail: dict, rule_core: list[str], rule_comp: list[str], reasons: dict[str, list[str]], model: str, complex_id: str) -> dict:
    selected = {"overall_assessment": f"{detail.get('name')}은 취약도와 인구구조를 기준으로 단지 맞춤형 복지 프로그램 운영이 필요한 단지입니다.", "urgent_needs": "고위험 세대 발굴, 정기 안부 확인, 지역자원 연계를 우선 추진해야 합니다.", "rule_based_programs": [{"catalog_id": pid} for pid in rule_core + rule_comp], "llm_selected_programs": []}
    score_order = [pid for pid, _, _ in score_programs(detail)]
    result = postprocess(selected, rule_core, rule_comp, reasons, score_order, detail)
    result.update({"from_cache": False, "model_used": model, "complex_id": complex_id, "llm_fallback": True})
    return result


def generate_recommendation(detail: dict, api_key: str, model: str = "gpt-4o", max_tokens: int = 3500, temperature: float = 0.2, use_cache: bool = True) -> dict:
    complex_id = str(detail.get("id", "unknown"))
    key = cache_key(complex_id, model)
    if use_cache:
        cached = load_cache(key)
        if cached:
            cached["from_cache"] = True
            return cached
    core_ids, comp_ids, reasons = select_programs(detail)
    rule_core = core_ids[:2]
    rule_comp = comp_ids[:1]
    rule_set = set(rule_core + rule_comp)
    scored = score_programs(detail)
    score_order = [pid for pid, _, _ in scored]
    llm_core = [pid for pid in score_order if pid in CORE_CANDIDATES and pid not in rule_set][:5]
    llm_comp = [pid for pid in score_order if pid in COMPLEMENTARY_CANDIDATES and pid not in rule_set][:3]
    if not api_key:
        return fallback_result(detail, rule_core, rule_comp, reasons, model, complex_id)
    prompt = build_prompt(detail, rule_core, rule_comp, llm_core, llm_comp, reasons)
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(model=model, messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}], max_tokens=max_tokens, temperature=temperature, response_format={"type": "json_object"})
        raw = parse_json(response.choices[0].message.content)
        if "error" in raw:
            raise ValueError(raw["error"])
        result = postprocess(raw, rule_core, rule_comp, reasons, score_order, detail)
        result.update({"from_cache": False, "model_used": model, "complex_id": complex_id})
    except Exception as exc:
        result = fallback_result(detail, rule_core, rule_comp, reasons, model, complex_id)
        result["llm_error"] = str(exc)
    save_cache(key, result)
    return result
