"""Tests for the query fingerprint helper."""

from __future__ import annotations

from epip.cache import QueryFingerprint


def test_query_fingerprint_normalizes_and_hashes() -> None:
    fingerprint = QueryFingerprint()

    hash_one = fingerprint.compute("SELECT *  FROM Policies", {"limit": 10})
    hash_two = fingerprint.compute(" select * from  policies ", {"limit": 10})
    hash_three = fingerprint.compute("select * from policies", {"limit": 5})

    assert hash_one == hash_two
    assert hash_one != hash_three


def test_query_fingerprint_equivalence_check() -> None:
    fingerprint = QueryFingerprint()

    assert fingerprint.are_equivalent("MATCH (n)", " match  (N) ")
    assert not fingerprint.are_equivalent("MATCH (a)", "MATCH (b)")
