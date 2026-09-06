"""Module 1 endpoints: surgical prompt generation and history."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import db, llm, prompt_service, remediation, schemas
from ..errors import FixGuardError
from .audits import require_key

router = APIRouter(prefix="/api/v1", tags=["prompts"])


@router.post("/prompts/surgify", dependencies=[Depends(require_key)])
async def surgify(payload: schemas.SurgifyRequest) -> dict:
    return await prompt_service.generate(
        intent=payload.intent,
        page_url=payload.page_url,
        code_context=payload.code_context,
        target_selector=payload.target_selector,
        use_model=payload.use_model,
    )


@router.post("/prompts/from-audit", dependencies=[Depends(require_key)])
async def from_audit(payload: schemas.FromAuditRequest) -> dict:
    """Turn a completed audit's findings into ready-to-paste fix prompts."""
    run = db.get_run(payload.audit_id)
    if not run:
        # Accept a share token too, so a link can be pasted straight in.
        link = db.get_share_link(payload.audit_id)
        run = db.get_run(link["audit_id"]) if link else None
    if not run:
        raise FixGuardError(
            "AUDIT_NOT_FOUND",
            "No audit found with that id or share token.",
            payload.audit_id,
        )
    if run["status"] != "complete":
        raise FixGuardError(
            "AUDIT_NOT_COMPLETE",
            "That audit has not finished yet.",
            run["id"],
        )

    result = remediation.build(run)

    # Persist each fix prompt so it appears in history alongside CSS prompts.
    for fix in result["fixes"]:
        if not fix.get("prompt"):
            continue
        db.insert_prompt(
            {
                "id": fix["id"],
                "original_intent": f"Fix: {fix['title']}",
                "guarded_prompt": fix["prompt"],
                "scope_boundary": {"category": fix["category"],
                                   "severity": fix["severity"]},
                "target_selector": None,
                "css_property": None,
                "css_value": None,
                "source_url": run["target_url"],
                "confidence": 1.0,
                "tokens_saved_estimate": max(0, 900 - len(fix["prompt"]) // 4),
                "engine": "rules",
                "created_at": fix["created_at"],
            }
        )
    return result


@router.get("/prompts/history", dependencies=[Depends(require_key)])
async def history(limit: int = 50) -> dict:
    return {
        "prompts": db.list_prompts(min(max(limit, 1), 200)),
        "totals": db.prompt_totals(),
    }


@router.get("/agents/status", dependencies=[Depends(require_key)])
async def agent_status() -> dict:
    """Which agents are model-backed right now, and recent call telemetry."""
    configured = llm.is_configured()
    return {
        "llm_configured": configured,
        "provider": llm.provider_name(),
        "agents": {
            "agent1_log_parser": {
                "role": "Turns console errors into plain English",
                "mode": "model + rules" if configured else "rules",
            },
            "agent2_prompt_generator": {
                "role": "Maps intent to a target element and CSS property",
                "mode": "model + rules" if configured else "rules",
            },
            "agent3_summary": {
                "role": "Writes the client-facing executive summary",
                "mode": "model" if configured else "template",
            },
        },
        "recent_calls": db.list_agent_calls(25),
    }
