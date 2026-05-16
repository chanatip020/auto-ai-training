"""Tests for the deterministic seeded train/val/test split."""
from __future__ import annotations

import uuid

import pytest

from app.services.datasets.split import (
    DEFAULT_RATIOS,
    split_items,
    validate_ratios,
)


def test_default_ratios_sum_to_one():
    assert sum(DEFAULT_RATIOS.values()) == pytest.approx(1.0)


def test_validate_ratios_accepts_default():
    validate_ratios(DEFAULT_RATIOS)


def test_validate_ratios_rejects_non_unit_sum():
    with pytest.raises(ValueError, match="sum to 1.0"):
        validate_ratios({"train": 0.5, "val": 0.2, "test": 0.1})


def test_validate_ratios_rejects_negatives():
    with pytest.raises(ValueError, match="negative"):
        validate_ratios({"train": 1.2, "val": -0.1, "test": -0.1})


def test_validate_ratios_rejects_extra_keys():
    with pytest.raises(ValueError, match="exactly the keys"):
        validate_ratios({"train": 1.0, "val": 0.0})  # missing 'test'


def test_split_empty():
    s = split_items([], seed=uuid.uuid4())
    assert s.train == []
    assert s.val == []
    assert s.test == []


def test_split_70_20_10_on_10_items():
    items = [f"item-{i}" for i in range(10)]
    s = split_items(items, seed=uuid.UUID(int=42))
    assert len(s.train) == 7
    assert len(s.val) == 2
    assert len(s.test) == 1
    # No leakage
    all_split = set(s.train) | set(s.val) | set(s.test)
    assert all_split == set(items)


def test_split_is_deterministic_with_uuid_seed():
    items = [f"i-{i}" for i in range(20)]
    seed = uuid.UUID("00000000-0000-0000-0000-000000000001")
    s1 = split_items(items, seed=seed)
    s2 = split_items(items, seed=seed)
    assert s1.train == s2.train
    assert s1.val == s2.val
    assert s1.test == s2.test


def test_split_is_deterministic_with_int_seed():
    items = list(range(50))
    s1 = split_items(items, seed=12345)
    s2 = split_items(items, seed=12345)
    assert s1.train == s2.train


def test_split_changes_with_different_seed():
    items = [f"i-{i}" for i in range(50)]
    s1 = split_items(items, seed=uuid.UUID(int=1))
    s2 = split_items(items, seed=uuid.UUID(int=2))
    assert s1.train != s2.train  # near-impossible to collide


def test_split_input_order_doesnt_matter():
    """Sort-then-shuffle makes the split independent of input order."""
    items = [f"i-{i}" for i in range(30)]
    seed = uuid.UUID(int=99)
    s1 = split_items(items, seed=seed)
    s2 = split_items(list(reversed(items)), seed=seed)
    assert s1.train == s2.train
    assert s1.val == s2.val
    assert s1.test == s2.test


def test_split_custom_ratios():
    items = list(range(100))
    s = split_items(items, ratios={"train": 0.5, "val": 0.3, "test": 0.2}, seed=1)
    assert len(s.train) == 50
    assert len(s.val) == 30
    assert len(s.test) == 20


def test_split_uses_floor_then_leftovers_go_to_test():
    # 7 items at 70/20/10 = 4.9 / 1.4 / 0.7 → 4 / 1 / 2 (test gets the remainder)
    items = list(range(7))
    s = split_items(items, seed=1)
    assert len(s.train) == 4
    assert len(s.val) == 1
    assert len(s.test) == 2
    assert len(s.train) + len(s.val) + len(s.test) == 7
