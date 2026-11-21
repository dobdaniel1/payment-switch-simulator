"""RRNs must be unique. A random 6-digit suffix collided after a few thousand
transactions in one hour and the switch answered with a 500 (found by load testing)."""

from datetime import timedelta

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.models import RrnCounter


def set_counter(client, value):
    with client.app.state.db.sessions() as s:
        s.execute(update(RrnCounter).values(value=value))
        s.commit()


def test_rrn_is_hour_stamp_plus_sequence(send):
    # 2026-11-11 09:30 UTC: year digit 6, day 315, hour 09
    assert [send().json()["rrn"] for _ in range(3)] == [
        "631509000001",
        "631509000002",
        "631509000003",
    ]


def test_hour_stamp_changes_and_sequence_continues(send, clock):
    send()
    clock.now += timedelta(hours=1)
    assert send().json()["rrn"] == "631510000002"


def test_declines_and_refunds_take_a_number_too(send):
    rrns = [send(amount=10051).json()["rrn"], send(type="refund").json()["rrn"]]
    assert rrns == ["631509000001", "631509000002"]


def test_duplicate_does_not_consume_a_number(send):
    send(stan="000777")
    send(stan="000777")
    assert send().json()["rrn"] == "631509000002"


def test_suffix_wraps_after_a_million(client, send):
    send()
    set_counter(client, 999_999)
    assert send().json()["rrn"] == "631509000000"


def test_other_integrity_errors_are_not_reported_as_duplicates(client, send):
    send()
    set_counter(client, 0)  # the next RRN repeats the first one
    with pytest.raises(IntegrityError):
        send()
