import math
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from build import parse_cell, parse_farside  # noqa: E402
from fetch import quarterly_expiries  # noqa: E402


def test_parse_cell():
    assert parse_cell("(95.1)") == -95.1
    assert parse_cell("1,234.5") == 1234.5
    assert math.isnan(parse_cell("-"))


def test_holiday_rows_dropped():
    html = """<table><tr><th>Date</th><th>IBIT</th><th>GBTC</th><th>Total</th></tr>
    <tr><td>11 Jan 2024</td><td>111.7</td><td>(95.1)</td><td>16.6</td></tr>
    <tr><td>15 Jan 2024</td><td>-</td><td>-</td><td>0.0</td></tr>
    <tr><td>16 Jan 2024</td><td>-</td><td>(10.0)</td><td>(10.0)</td></tr></table>"""
    s = parse_farside(html)
    assert list(s.index.strftime("%Y-%m-%d")) == ["2024-01-11", "2024-01-16"]
    assert round(s.iloc[0], 1) == 16.6 and s.iloc[1] == -10.0


def test_quarterly_expiries_are_last_fridays():
    e = quarterly_expiries(date(2024, 1, 1), date(2025, 12, 31))
    assert e[:4] == [date(2024, 3, 29), date(2024, 6, 28), date(2024, 9, 27), date(2024, 12, 27)]
    assert date(2025, 3, 28) in e and all(d.weekday() == 4 for d in e)
