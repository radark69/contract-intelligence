"""Load and validate the DBS Contract Playbook from YAML files.

The playbook is static knowledge loaded once at startup. Rules are
validated strictly — an invalid playbook must fail fast rather than
silently produce wrong risk findings (plan section 6: the AI must
never invent DBS policy).
"""

import logging
from pathlib import Path

import yaml

from app.playbook.schema import PlaybookRule

logger = logging.getLogger(__name__)

PLAYBOOK_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "playbook"


class PlaybookError(Exception):
    """Raised when the playbook fails validation."""


class Playbook:
    """Validated, indexed collection of playbook rules."""

    def __init__(self, rules: list[PlaybookRule]):
        by_id: dict[str, PlaybookRule] = {}
        for rule in rules:
            if rule.id in by_id:
                raise PlaybookError(f"duplicate rule id: {rule.id}")
            by_id[rule.id] = rule
        self._rules = rules
        self._by_id = by_id

    @property
    def rules(self) -> list[PlaybookRule]:
        return list(self._rules)

    def get(self, rule_id: str) -> PlaybookRule | None:
        return self._by_id.get(rule_id)

    def by_category(self, category: str) -> list[PlaybookRule]:
        return [r for r in self._rules if r.category == category]

    def by_severity(self, severity: str) -> list[PlaybookRule]:
        return [r for r in self._rules if r.severity == severity]

    def approval_required(self) -> list[PlaybookRule]:
        return [r for r in self._rules if r.requires_management_approval]

    def __len__(self) -> int:
        return len(self._rules)


def load_playbook(directory: Path | None = None) -> Playbook:
    """Load every YAML file in the playbook directory into a Playbook."""
    directory = directory or PLAYBOOK_DIR
    if not directory.is_dir():
        raise PlaybookError(f"playbook directory not found: {directory}")

    rules: list[PlaybookRule] = []
    errors: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            errors.append(f"{path.name}: invalid YAML: {e}")
            continue
        if data is None:
            continue
        if not isinstance(data, dict) or "rules" not in data:
            errors.append(f"{path.name}: expected top-level 'rules' key")
            continue
        for i, raw in enumerate(data["rules"]):
            try:
                rules.append(PlaybookRule.model_validate(raw))
            except Exception as e:
                errors.append(f"{path.name} rules[{i}]: {e}")

    if errors:
        raise PlaybookError("playbook validation failed:\n" + "\n".join(errors))

    if not rules:
        raise PlaybookError(f"no rules found in {directory}")

    logger.info("loaded %d playbook rules from %s", len(rules), directory)
    return Playbook(rules)


_cached: Playbook | None = None


def get_playbook() -> Playbook:
    """Return the process-wide playbook, loading it on first use."""
    global _cached
    if _cached is None:
        _cached = load_playbook()
    return _cached


def reset_playbook_cache() -> None:
    """Clear the cache (tests reloading the playbook)."""
    global _cached
    _cached = None
