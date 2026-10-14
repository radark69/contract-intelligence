import pytest

from app.playbook.loader import Playbook, PlaybookError, load_playbook


@pytest.fixture(scope="module")
def playbook() -> Playbook:
    return load_playbook()


class TestLoadPlaybook:
    def test_loads_rules(self, playbook):
        assert len(playbook) >= 20

    def test_rules_unique_ids(self, playbook):
        ids = [r.id for r in playbook.rules]
        assert len(ids) == len(set(ids))

    def test_get(self, playbook):
        rule = playbook.get("LIABILITY-001")
        assert rule is not None
        assert rule.severity == "critical"

    def test_get_missing_returns_none(self, playbook):
        assert playbook.get("NOPE-999") is None

    def test_by_category(self, playbook):
        liability = playbook.by_category("liability")
        assert liability
        assert all(r.category == "liability" for r in liability)

    def test_by_severity(self, playbook):
        critical = playbook.by_severity("critical")
        assert critical
        assert all(r.severity == "critical" for r in critical)

    def test_approval_required(self, playbook):
        flagged = playbook.approval_required()
        assert flagged
        assert all(r.requires_management_approval for r in flagged)


class TestMissingDirectory:
    def test_raises(self, tmp_path):
        with pytest.raises(PlaybookError, match="not found"):
            load_playbook(tmp_path / "nope")

    def test_empty_directory_raises(self, tmp_path):
        with pytest.raises(PlaybookError, match="no rules"):
            load_playbook(tmp_path)


class TestInvalidContent:
    def _write(self, tmp_path, text: str):
        (tmp_path / "x.yaml").write_text(text)
        return tmp_path

    def test_missing_rules_key(self, tmp_path):
        self._write(tmp_path, "foo: 1")
        with pytest.raises(PlaybookError, match="expected top-level"):
            load_playbook(tmp_path)

    def test_invalid_yaml(self, tmp_path):
        self._write(tmp_path, "rules: [::")
        with pytest.raises(PlaybookError, match="invalid YAML"):
            load_playbook(tmp_path)

    def test_invalid_rule_reports_location(self, tmp_path):
        self._write(tmp_path, "rules:\n  - id: bad-id\n")
        with pytest.raises(PlaybookError, match=r"x\.yaml rules\[0\]"):
            load_playbook(tmp_path)

    def test_duplicate_ids_across_files(self, tmp_path):
        rule = """
  - id: PAYMENT-001
    category: payment
    topic: payment terms
    severity: low
    preferred: a
    acceptable: a
    escalate: a
    reject: a
    clause_categories: [payment]
"""
        (tmp_path / "a.yaml").write_text(f"rules:\n{rule}")
        (tmp_path / "b.yaml").write_text(f"rules:\n{rule}")
        with pytest.raises(PlaybookError, match="duplicate rule id"):
            load_playbook(tmp_path)
