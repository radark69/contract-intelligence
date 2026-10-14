from fastapi import APIRouter, HTTPException, Query

from app.playbook.loader import PlaybookError, get_playbook
from app.playbook.schema import (
    PlaybookCategory,
    PlaybookRule,
    PlaybookRuleOut,
)
from app.storage.models import FindingSeverity

router = APIRouter(prefix="/playbook", tags=["playbook"])


def _to_out(rule: PlaybookRule) -> PlaybookRuleOut:
    return PlaybookRuleOut(
        id=rule.id,
        category=rule.category,
        topic=rule.topic,
        severity=rule.severity,
        requires_management_approval=rule.requires_management_approval,
        preferred=rule.preferred,
        acceptable=rule.acceptable,
        escalate=rule.escalate,
        reject=rule.reject,
        clause_categories=rule.clause_categories,
        rationale=rule.rationale,
    )


@router.get("", response_model=list[PlaybookRuleOut])
def list_rules(
    category: PlaybookCategory | None = None,
    severity: FindingSeverity | None = None,
    approval_required: bool | None = Query(default=None, alias="approval_required"),
) -> list[PlaybookRuleOut]:
    try:
        playbook = get_playbook()
    except PlaybookError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    rules = playbook.rules
    if category is not None:
        rules = [r for r in rules if r.category == category]
    if severity is not None:
        rules = [r for r in rules if r.severity == severity]
    if approval_required is not None:
        rules = [r for r in rules if r.requires_management_approval is approval_required]
    return [_to_out(r) for r in rules]


@router.get("/{rule_id}", response_model=PlaybookRuleOut)
def get_rule(rule_id: str) -> PlaybookRuleOut:
    try:
        playbook = get_playbook()
    except PlaybookError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    rule = playbook.get(rule_id.upper())
    if rule is None:
        raise HTTPException(
            status_code=404,
            detail=f"rule not found: {rule_id}",
        )
    return _to_out(rule)
