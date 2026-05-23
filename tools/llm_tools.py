import json
import time
from typing import Any
from langchain_cohere import ChatCohere
from langchain_core.messages import HumanMessage, SystemMessage
from config.settings import get_settings
from core.logging import get_logger
from core.exceptions import LLMError
from tools.base import tool_call, with_retry

logger = get_logger("tools.llm")
_settings = get_settings()

_llm: ChatCohere | None = None


def get_llm() -> ChatCohere:
    global _llm
    if _llm is None:
        _llm = ChatCohere(
            cohere_api_key=_settings.cohere_api_key,
            model=_settings.cohere_model,
            temperature=0.3,
        )
        logger.info("cohere_llm_initialized", model=_settings.cohere_model)
    return _llm


@tool_call("llm_chat")
@with_retry()
def llm_chat(system_prompt: str, user_prompt: str) -> dict:
    """
    Call Cohere LLM and return {content, tokens_in, tokens_out, latency_ms}.
    """
    start = time.perf_counter()
    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = get_llm().invoke(messages)
        latency_ms = (time.perf_counter() - start) * 1000

        usage = response.usage_metadata or {}
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)

        logger.info(
            "llm_response",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=round(latency_ms, 2),
        )
        return {
            "content": response.content,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": round(latency_ms, 2),
        }
    except Exception as exc:
        raise LLMError(f"Cohere LLM call failed: {exc}") from exc


@tool_call("llm_extract_json")
@with_retry()
def llm_extract_json(system_prompt: str, user_prompt: str) -> dict:
    """Call LLM and parse JSON from response. Returns {data, tokens_in, tokens_out, latency_ms}."""
    result = llm_chat(system_prompt, user_prompt)
    content: str = result["content"]

    # Strip markdown code fences if present
    clean = content.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        # Try to extract JSON object/array from the content
        import re
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", clean)
        if match:
            data = json.loads(match.group(0))
        else:
            raise LLMError(
                "LLM did not return valid JSON",
                details={"raw_response": content[:500]},
            )

    return {
        "data": data,
        "tokens_in": result["tokens_in"],
        "tokens_out": result["tokens_out"],
        "latency_ms": result["latency_ms"],
    }


@tool_call("llm_parse_resume")
@with_retry()
def llm_parse_resume(resume_text: str) -> dict:
    """Extract structured candidate info from raw resume text."""
    system = (
        "You are an expert HR resume parser. Extract structured information from the resume text. "
        "Return ONLY valid JSON with these exact keys: "
        "name, email, phone, skills (array of strings), "
        "current_role, education, summary. "
        "If a field is missing, use empty string. Do not add any explanation."
    )
    user = f"Parse this resume:\n\n{resume_text[:4000]}"
    result = llm_extract_json(system, user)
    return result


@tool_call("llm_shortlist_candidates")
@with_retry()
def llm_shortlist_candidates(job_description: str, resumes: list[dict], top_n: int = 5) -> dict:
    """Rank resumes against JD and return top_n with reasons."""
    resumes_text = json.dumps(
        [{"id": i, **{k: v for k, v in r.items() if k != "raw_text"}} for i, r in enumerate(resumes)],
        indent=2,
    )[:6000]

    system = (
        "You are a senior technical recruiter. Analyze the resumes against the job description. "
        f"Select the top {top_n} best-fit candidates. "
        "Return ONLY valid JSON with this structure: "
        '{"candidates": [{"index": <int>, "name": <str>, "selection_reason": <str>, "match_score": <float 0-10>}], '
        '"overall_rationale": <str>}. '
        "Be specific about why each candidate was selected."
    )
    user = (
        f"Job Description:\n{job_description[:2000]}\n\n"
        f"Resumes:\n{resumes_text}"
    )
    return llm_extract_json(system, user)


@tool_call("llm_generate_call_response")
@with_retry()
def llm_generate_call_response(
    candidate_name: str,
    conversation_history: list[dict],
    screening_data: dict,
    company_name: str = "our company",
) -> dict:
    """
    Generate the next conversational response in a pre-screening call.
    Returns {reply, is_complete, updated_screening_data, tokens_in, tokens_out}.
    """
    import datetime
    today = datetime.date.today()
    # Build this week's remaining days (Mon–Fri)
    week_days = []
    for i in range(7):
        d = today + datetime.timedelta(days=i)
        if d.weekday() < 5:  # Monday=0 … Friday=4
            week_days.append(d.strftime("%A, %B %-d"))
    week_days_str = ", ".join(week_days) if week_days else "this week"

    history_text = "\n".join(
        f"{turn['role'].upper()}: {turn['text']}" for turn in conversation_history[-10:]
    )
    collected = json.dumps(screening_data, indent=2)

    system = (
        f"You are an AI HR recruiter calling {candidate_name} on behalf of {company_name} "
        "for a job pre-screening. Your goal is to naturally gather: "
        "(1) Are they open to a job change, (2) Reason for change, "
        "(3) Current CTC, (4) Expected CTC, (5) Total years of professional experience, "
        "(6) Which days this week they are available for an interview and the preferred time slot on each of those days. "
        f"This week's available weekdays are: {week_days_str}. "
        "When asking about interview availability, ask which days this week work for them AND what time slot they prefer on each day. "
        "After the candidate answers, confirm each slot back to them in this exact format: "
        "'Available on <Day>, <Month> <Date> from <start time> to <end time>.' "
        "For example: 'Available on Monday, May 25 from 8 AM to 12 PM.' "
        "Collect ALL their available slots before marking is_complete. "
        "Be professional, warm, and concise. Keep responses under 3 sentences. "
        "Return ONLY valid JSON: "
        '{"reply": <str>, "is_complete": <bool>, '
        '"screening_data": {"looking_for_change": <bool|null>, '
        '"reason_for_change": <str|null>, "current_ctc": <str|null>, '
        '"expected_ctc": <str|null>, "experience_years": <str|null>, '
        '"interview_slots": <list of strings like "Available on Monday, May 25 from 8 AM to 12 PM" | null>}}. '
        "Set is_complete to true only when all 6 fields are collected or candidate declines."
    )
    user = (
        f"Conversation so far:\n{history_text}\n\n"
        f"Already collected:\n{collected}\n\n"
        "Generate the next response."
    )
    result = llm_extract_json(system, user)
    result["data"]["tokens_in"] = result["tokens_in"]
    result["data"]["tokens_out"] = result["tokens_out"]
    result["data"]["latency_ms"] = result["latency_ms"]
    return result["data"]
