import pytest
from funds_agentic.parsing import ExtractionError, header_map, number, performance, ranking
from funds_agentic.models import FUND_PERIODS, InputFund
from funds_agentic.collection import parse_fund_tables

HEADERS = ["Key", "3 m", "6 m", "1 y", "3 y", "5 y"]

def test_missing_value_keeps_its_period():
    values = performance(["Fund", "-", "2.0", "3.0", "4.0", "5.0"], header_map(HEADERS, FUND_PERIODS))
    assert values == {"3m": None, "6m": 2, "1y": 3, "3y": 4, "5y": 5}

def test_periods_follow_headers_and_whitespace():
    mapping = header_map(["Key", "5\ny", "1 y (%)", "3 m", "6 m", "3 y"], FUND_PERIODS)
    values = performance(["Fund", "50", "10", "3", "6", "30"], mapping)
    assert values == {"3m": 3, "6m": 6, "1y": 10, "3y": 30, "5y": 50}

@pytest.mark.parametrize("value", ["nan", "inf", "unexpected", "1/5"])
def test_invalid_numbers_are_failures(value):
    with pytest.raises(ExtractionError): number(value)

@pytest.mark.parametrize("value", ["-", "N/A", "—", ""])
def test_explicit_unavailable_cells(value):
    assert number(value) is None

def test_short_row_is_failure():
    with pytest.raises(ExtractionError): performance(["Fund", "1"], header_map(HEADERS, FUND_PERIODS))

def test_quartile_domain():
    assert ranking("3") == 3
    with pytest.raises(ExtractionError): ranking("12/56")

def test_real_table_shape_and_named_price_field():
    tables = [[HEADERS, ["Test Fund", "-", "2", "3", "4", "5"],
               ["IA Global", "8", "9", "10", "11", "12"], ["Quartile Ranking", "2", "3", "1", "1", "1"]],
              [["Pricing Times:", "12.00 Daily"], ["Mid price:", "122.0200p (06/11/2026)"],
               ["FE fundinfo Risk Score:", "141"]]]
    fund = parse_fund_tables("Test Fund", tables, InputFund(url="test"), "IA Global", "https://www.trustnet.com/fund/sectors?sector=O:G")
    assert fund.price == "122.0200"
    assert fund.price_date == "06/11/2026"
    assert fund.source_date is None
    assert fund.quartile == 2
    assert fund.fe_risk == 141
    assert fund.performance["3m"] is None
    assert "Source return unavailable: 3m" in fund.warnings

def test_conflicting_duplicate_tables_are_rejected():
    with pytest.raises(ExtractionError, match="Conflicting cumulative"):
        parse_fund_tables("Fund", [[HEADERS, ["Fund", "1", "2", "3", "4", "5"]],
                                  [HEADERS, ["Fund", "9", "2", "3", "4", "5"]]],
                          InputFund(url="test"), "IA Global", None)


def test_cent_price_retains_unit():
    tables = [[HEADERS, ["Fund", "1", "2", "3", "4", "5"]], [["Mid price:", "3622.6700c (06/11/2026)"]]]
    record = parse_fund_tables("Fund", tables, InputFund(url="test"), "IA Global", None)
    assert record.price == "3622.6700c" and record.price_unit == "c"


def test_corrupt_source_price_unit_is_unavailable_with_explanation():
    tables = [[HEADERS, ["Fund", "1", "2", "3", "4", "5"]], [["Mid price:", "9114.6000\ufffd (06/11/2026)"]]]
    record = parse_fund_tables("Fund", tables, InputFund(url="test"), "IA Global", None)
    assert record.price is None and record.price_date == "06/11/2026"
    assert record.performance["1y"] == 3
    assert any("undecodable" in warning for warning in record.warnings)


@pytest.mark.parametrize("values", [{}, {"3m": float("nan"), "6m": 1, "1y": 1, "3y": 1, "5y": 1}])
def test_invalid_performance_cannot_enter_a_fund_record(values):
    from funds_agentic.models import FundRecord
    with pytest.raises(ValueError):
        FundRecord(name="Fund", url="test", performance=values)


def test_unicode_minus_and_missing_dash_are_parsed():
    assert number("\u22121.5") == -1.5
    assert number("\u2014") is None


def test_alternate_unit_grid_uses_exact_share_class_and_header_positions():
    tables = [[HEADERS, ["Fund I", "1", "2", "3", "4", "5"]],
              [["", "Unit Details", "Unit Details", "Prices", "Prices", "Prices"],
               ["Name", "Currency", "Bid", "Offer", "Date", "Yields"],
               ["Fund R", "GBX", "50.0100p", "50.0100p", "06/11/2026", "4.00"],
               ["Fund I", "GBX", "118.1700p", "118.1700p", "06/11/2026", "3.80"]]]
    record = parse_fund_tables("Fund I", tables, InputFund(url="test"), "IA Global", None)
    assert record.price == "118.1700" and record.price_unit == "p"
    assert record.price_date == "06/11/2026"


def test_misaligned_unit_grid_is_not_guessed():
    tables = [[HEADERS, ["Fund", "1", "2", "3", "4", "5"]],
              [["Name", "Currency", "Bid", "Offer", "Date"], ["Fund", "GBX", "10p", "06/11/2026"]]]
    with pytest.raises(ExtractionError, match="align"):
        parse_fund_tables("Fund", tables, InputFund(url="test"), "IA Global", None)


def test_explicit_bid_label_is_a_price_field():
    tables = [[HEADERS, ["Fund", "1", "2", "3", "4", "5"]], [["Bid:", "194.1000p (06/11/2026)"]]]
    record = parse_fund_tables("Fund", tables, InputFund(url="test"), "IA Global", None)
    assert record.price == "194.1000"
