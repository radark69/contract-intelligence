from app.facts.patterns import (
    DURATION_RE,
    MONEY_RE,
    duration_to_months,
    parse_date,
    parse_money,
    word_to_int,
)


def money(text: str) -> tuple[float, str | None] | None:
    m = MONEY_RE.match(text)
    return parse_money(m) if m else None


class TestParseMoney:
    def test_currency_before(self):
        assert money("USD 20,000,000") == (20_000_000.0, "USD")

    def test_dollar_sign(self):
        assert money("$25,000 per day") == (25_000.0, "USD")

    def test_currency_after(self):
        assert money("5,000,000 NGN") == (5_000_000.0, "NGN")

    def test_million_suffix(self):
        assert money("USD 20 million") == (20_000_000.0, "USD")

    def test_m_suffix(self):
        assert money("$12.5M") == (12_500_000.0, "USD")

    def test_thousands_suffix(self):
        assert money("USD 25k") == (25_000.0, "USD")

    def test_plain_small_number_rejected(self):
        assert money("36 months") is None

    def test_unmarked_ok_param(self):
        m = MONEY_RE.match("20000000 total")
        assert parse_money(m, unmarked_ok=True) == (20_000_000.0, None)

    def test_unmarked_small_allowed_when_flagged(self):
        m = MONEY_RE.match("50")
        assert parse_money(m, unmarked_ok=True) == (50.0, None)

    def test_euro(self):
        assert money("€1,500") == (1500.0, "EUR")

    def test_commaless_large_with_currency(self):
        assert money("USD 5000000") == (5_000_000.0, "USD")


class TestParseDate:
    def test_iso(self):
        assert parse_date("2026-01-01") == "2026-01-01"

    def test_day_month_year(self):
        assert parse_date("1 January 2026") == "2026-01-01"

    def test_ordinal_day(self):
        assert parse_date("1st January 2026") == "2026-01-01"

    def test_month_day_year(self):
        assert parse_date("January 1, 2026") == "2026-01-01"

    def test_slash_dayfirst(self):
        assert parse_date("01/02/2026") == "2026-02-01"

    def test_invalid(self):
        assert parse_date("not a date") is None

    def test_short_month(self):
        assert parse_date("1 Jan 2026") == "2026-01-01"


class TestWordToInt:
    def test_simple(self):
        assert word_to_int("three") == 3

    def test_compound(self):
        assert word_to_int("thirty-six") == 36

    def test_compound_space(self):
        assert word_to_int("twenty four") == 24

    def test_digits(self):
        assert word_to_int("90") == 90

    def test_unknown(self):
        assert word_to_int("banana") is None


class TestDuration:
    def test_months(self):
        m = DURATION_RE.search("36 months")
        assert duration_to_months(36, m.group("unit")) == 36

    def test_years_to_months(self):
        m = DURATION_RE.search("3 years")
        assert duration_to_months(3, m.group("unit")) == 36

    def test_weeks(self):
        m = DURATION_RE.search("4 weeks")
        assert duration_to_months(4, m.group("unit")) == 1

    def test_word_number(self):
        m = DURATION_RE.search("thirty six months")
        assert m is not None
        assert m.group("w") == "thirty six"

    def test_parenthesized_digits(self):
        m = DURATION_RE.search("three (3) years")
        assert m is not None
        assert m.group("wp") == "3"
