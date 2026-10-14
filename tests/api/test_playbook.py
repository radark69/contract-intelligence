class TestPlaybookList:
    async def test_list_all(self, client):
        rules = (await client.get("/api/v1/playbook")).json()
        assert len(rules) >= 20

    async def test_filter_by_category(self, client):
        rules = (await client.get("/api/v1/playbook?category=liability")).json()
        assert rules
        assert all(r["category"] == "liability" for r in rules)

    async def test_filter_by_severity(self, client):
        rules = (await client.get("/api/v1/playbook?severity=critical")).json()
        assert rules
        assert all(r["severity"] == "critical" for r in rules)

    async def test_filter_approval_required(self, client):
        rules = (await client.get("/api/v1/playbook?approval_required=true")).json()
        assert rules
        assert all(r["requires_management_approval"] for r in rules)

    async def test_invalid_category_422(self, client):
        resp = await client.get("/api/v1/playbook?category=not_a_category")
        assert resp.status_code == 422

    async def test_rule_shape(self, client):
        rules = (await client.get("/api/v1/playbook")).json()
        r = rules[0]
        for field in (
            "id",
            "category",
            "topic",
            "severity",
            "requires_management_approval",
            "preferred",
            "acceptable",
            "escalate",
            "reject",
            "clause_categories",
            "rationale",
        ):
            assert field in r


class TestPlaybookGet:
    async def test_get_by_id(self, client):
        r = (await client.get("/api/v1/playbook/LIABILITY-001")).json()
        assert r["severity"] == "critical"
        assert r["requires_management_approval"] is True

    async def test_get_is_case_insensitive(self, client):
        r = (await client.get("/api/v1/playbook/liability-001")).json()
        assert r["id"] == "LIABILITY-001"

    async def test_get_missing_404(self, client):
        resp = await client.get("/api/v1/playbook/NOPE-001")
        assert resp.status_code == 404
