"""TC-06 … TC-08: маршрутизация и порог уверенности."""

from __future__ import annotations

import pytest

from core.config import STATUS_NEW, STATUS_REVIEW
from core.routing import category_groups, load_categories, route

GROUPS = category_groups(load_categories())


def test_tc06_category_to_group():
    group, _, _ = route("billing", 0.9, GROUPS, 0.6)
    assert group == "Биллинг"


def test_tc07_threshold_boundary_is_auto():
    _, status, auto = route("tech", 0.6, GROUPS, 0.6)
    assert auto is True and status == STATUS_NEW


def test_tc08_below_threshold_goes_to_review():
    _, status, auto = route("tech", 0.59, GROUPS, 0.6)
    assert auto is False and status == STATUS_REVIEW


def test_unknown_category():
    with pytest.raises(ValueError):
        route("unknown", 0.9, GROUPS, 0.6)
