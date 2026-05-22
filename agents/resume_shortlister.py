import uuid
import asyncio
from agents.base import BaseAgent
from tools.file_tools import extract_text_from_file
from tools.llm_tools import llm_parse_resume, llm_shortlist_candidates
from tools.storage_tools import load_file_bytes
from config.settings import get_settings
from core.logging import get_logger

logger = get_logger("agents.resume_shortlister")
_settings = get_settings()


class ResumeShortlisterAgent(BaseAgent):
    """
    Parses all uploaded resumes, scores them against the JD, and
    returns the top-N shortlisted candidates with selection reasons.
    """
    name = "resume_shortlister"

    async def _arun(
        self,
        job_description: str,
        resume_file_ids: list[str],
        resume_filenames: list[str],
        top_n: int | None = None,
    ) -> dict:
        n = top_n or _settings.max_shortlisted_candidates
        logger.info(
            "shortlister_start",
            num_resumes=len(resume_file_ids),
            top_n=n,
        )

        # ── Step 1: Parse all resumes in parallel ─────────────────────────
        tasks = [
            self._parse_single(file_id, filename)
            for file_id, filename in zip(resume_file_ids, resume_filenames)
        ]
        parsed_results = await asyncio.gather(*tasks, return_exceptions=True)

        parsed_resumes: list[dict] = []
        total_tokens_in = 0
        total_tokens_out = 0

        for i, res in enumerate(parsed_results):
            if isinstance(res, Exception):
                logger.warning(
                    "resume_parse_failed",
                    file_id=resume_file_ids[i],
                    error=str(res),
                )
                continue
            parsed_resumes.append(res["resume"])
            total_tokens_in += res.get("tokens_in", 0)
            total_tokens_out += res.get("tokens_out", 0)

        if not parsed_resumes:
            raise ValueError("No resumes could be parsed successfully")

        logger.info("resumes_parsed", count=len(parsed_resumes))

        # ── Step 2: Shortlist via LLM ──────────────────────────────────────
        shortlist_result = llm_shortlist_candidates(job_description, parsed_resumes, top_n=n)
        total_tokens_in += shortlist_result.get("tokens_in", 0)
        total_tokens_out += shortlist_result.get("tokens_out", 0)

        raw_data = shortlist_result["data"]
        selected_indexes: list[dict] = raw_data.get("candidates", [])
        overall_rationale: str = raw_data.get("overall_rationale", "")

        # ── Step 3: Build enriched candidate records ───────────────────────
        shortlisted: list[dict] = []
        for entry in selected_indexes:
            idx = entry.get("index", -1)
            if idx < 0 or idx >= len(parsed_resumes):
                logger.warning("invalid_candidate_index", index=idx)
                continue
            resume = parsed_resumes[idx]
            shortlisted.append({
                "candidate_id": str(uuid.uuid4()),
                "name": resume.get("name", "Unknown"),
                "email": resume.get("email", ""),
                "phone": resume.get("phone", ""),
                "skills": resume.get("skills", []),
                "current_role": resume.get("current_role", ""),
                "education": resume.get("education", ""),
                "selection_reason": entry.get("selection_reason", ""),
                "match_score": float(entry.get("match_score", 0.0)),
            })

        logger.info(
            "shortlisting_complete",
            shortlisted_count=len(shortlisted),
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
        )

        return {
            "parsed_resumes": parsed_resumes,
            "shortlisted_candidates": shortlisted,
            "shortlisting_rationale": overall_rationale,
            "tokens_in": total_tokens_in,
            "tokens_out": total_tokens_out,
        }

    async def _parse_single(self, file_id: str, filename: str) -> dict:
        """Load, extract text, and parse a single resume."""
        content = await load_file_bytes(file_id)
        raw_text = extract_text_from_file(filename, content)
        parse_result = llm_parse_resume(raw_text)
        resume = parse_result["data"]
        resume["raw_text"] = raw_text[:2000]
        resume["file_id"] = file_id
        return {
            "resume": resume,
            "tokens_in": parse_result.get("tokens_in", 0),
            "tokens_out": parse_result.get("tokens_out", 0),
        }


resume_shortlister_agent = ResumeShortlisterAgent()
