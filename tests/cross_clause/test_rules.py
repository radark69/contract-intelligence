from uuid import uuid4

from app.cross_clause.rules import (
    check_approval_without_deemed,
    check_availability_broad_downtime,
    check_broad_scope_fixed_price,
    check_client_equipment_guarantee,
    check_conflicting_definitions,
    check_ld_with_uncapped,
    check_maintenance_without_exclusions,
    check_termination_without_mob_recovery,
    run_cross_clause_rules,
)
from app.storage.models import Clause, FindingSeverity


def clause(category: str, text: str, number: str = "1", page: int | None = 1) -> Clause:
    return Clause(
        id=uuid4(),
        document_id=uuid4(),
        raw_text=text,
        category=category,
        clause_number=number,
        source_page=page,
    )


class TestLDWithUncapped:
    def test_detects_stack(self):
        ld = clause("liquidated_damages", "Liquidated damages of USD 10,000 per day apply.")
        liab = clause("liability", "Contractor accepts unlimited liability for all claims.")
        findings = check_ld_with_uncapped([ld, liab])
        assert len(findings) == 1
        f = findings[0]
        assert f.rule_id == "XC-LD-UNCAPPED"
        assert f.severity == FindingSeverity.CRITICAL
        assert f.secondary_refs  # links the liability clause

    def test_capped_liability_ok(self):
        ld = clause("liquidated_damages", "Liquidated damages apply per day.")
        liab = clause("liability", "Liability is capped at USD 5,000,000.")
        assert check_ld_with_uncapped([ld, liab]) == []

    def test_no_ld_clause_ok(self):
        liab = clause("liability", "unlimited liability")
        assert check_ld_with_uncapped([liab]) == []


class TestAvailabilityDowntime:
    def test_detects_broad_downtime_without_exclusions(self):
        c = clause(
            "availability",
            "Contractor is responsible for all downtime and NPT against the 98% availability target.",
        )
        findings = check_availability_broad_downtime([c])
        assert findings[0].rule_id == "XC-AVAIL-DOWNTIME"

    def test_exclusions_present_ok(self):
        c = clause(
            "availability",
            "Contractor is responsible for all downtime except force majeure and client delay.",
        )
        assert check_availability_broad_downtime([c]) == []


class TestApprovalDeemed:
    def test_detects_missing_deemed_approval(self):
        c = clause("payment", "Invoices require prior written approval by the Client.")
        findings = check_approval_without_deemed([c])
        assert findings[0].rule_id == "XC-APPROVAL-NODEEM"

    def test_deemed_approval_present_ok(self):
        c = clause("payment", "Invoices are deemed approved after 10 business days.")
        assert check_approval_without_deemed([c]) == []


class TestTerminationMobRecovery:
    def test_detects_tfc_without_recovery(self):
        c = clause(
            "termination", "Client may terminate this Agreement for convenience on 30 days notice."
        )
        findings = check_termination_without_mob_recovery([c])
        assert findings[0].rule_id == "XC-TERM-NOMOB"

    def test_recovery_clause_present_ok(self):
        c = clause(
            "termination",
            "Client may terminate for convenience upon reimbursement of demobilisation costs.",
        )
        assert check_termination_without_mob_recovery([c]) == []

    def test_no_tfc_ok(self):
        c = clause("termination", "Termination only for material breach after cure period.")
        assert check_termination_without_mob_recovery([c]) == []


class TestBroadScopeFixedPrice:
    def test_detects_combination(self):
        scope = clause(
            "scope", "Contractor shall perform any and all work requested by the Client."
        )
        pricing = clause("pricing", "The Contract Price is a fixed lump-sum price.")
        findings = check_broad_scope_fixed_price([scope, pricing])
        assert findings[0].rule_id == "XC-SCOPE-FIXED"
        assert findings[0].secondary_refs

    def test_variation_mechanism_ok(self):
        scope = clause("scope", "any and all work")
        pricing = clause("pricing", "fixed lump-sum price")
        adj = clause("change_control", "Rates shall be equitably adjusted for variations.")
        assert check_broad_scope_fixed_price([scope, pricing, adj]) == []


class TestClientEquipment:
    def test_detects_guarantee_over_client_equipment(self):
        equip = clause("procurement", "Client-supplied equipment shall be provided at site.")
        kpi = clause(
            "availability", "Contractor guarantees performance of the equipment at all times."
        )
        findings = check_client_equipment_guarantee([equip, kpi])
        assert findings[0].rule_id == "XC-CLIENT-EQUIP"
        assert findings[0].secondary_refs == ["Page 1 → Clause 1"]

    def test_no_client_equipment_ok(self):
        kpi = clause("availability", "Contractor guarantees performance of its own equipment.")
        assert check_client_equipment_guarantee([kpi]) == []


class TestMaintenance:
    def test_detects_unexcluded_maintenance(self):
        c = clause("maintenance", "Contractor shall keep the Client's plant in good working order.")
        findings = check_maintenance_without_exclusions([c])
        assert findings[0].rule_id == "XC-MAINT-NOEXCL"
        assert findings[0].severity == FindingSeverity.MEDIUM

    def test_exclusions_ok(self):
        c = clause(
            "maintenance",
            "Contractor shall keep the plant in good order, excluding pre-existing defects and latent defects.",
        )
        assert check_maintenance_without_exclusions([c]) == []


class TestConflictingDefinitions:
    def test_detects_separate_definitions(self):
        avail = clause(
            "availability", "Availability means the percentage of time the rig is operational."
        )
        down = clause("downtime_npt", "Downtime means any period the unit is not operational.")
        findings = check_conflicting_definitions([avail, down])
        assert findings[0].rule_id == "XC-DEFINITION-CONFLICT"
        assert findings[0].secondary_refs

    def test_single_definition_ok(self):
        avail = clause("availability", "Availability means operational time.")
        assert check_conflicting_definitions([avail]) == []


class TestRunAll:
    def test_empty_clauses(self):
        assert run_cross_clause_rules([]) == []

    def test_finds_multiple_interactions(self):
        ld = clause("liquidated_damages", "Liquidated damages per day apply for delay.", "4")
        liab = clause("liability", "unlimited liability", "3")
        pay = clause("payment", "Invoices require approval by the Client.", "1")
        findings = run_cross_clause_rules([ld, liab, pay])
        ids = {f.rule_id for f in findings}
        assert "XC-LD-UNCAPPED" in ids
        assert "XC-APPROVAL-NODEEM" in ids

    def test_all_findings_have_evidence(self):
        clauses = [
            clause("liquidated_damages", "Liquidated damages per day apply for delay."),
            clause("liability", "unlimited liability"),
        ]
        for f in run_cross_clause_rules(clauses):
            assert f.source_text
            assert f.primary_clause is not None
            assert f.risk and f.recommendation
