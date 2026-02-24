"""tests/test_srs.py — Unit tests for the SM-2 algorithm (pure logic, no DB)."""
import pytest
from core.srs import sm2_review


def test_sm2_easy_increases_interval():
    interval, ease, reps = sm2_review(interval=1, ease=2.5, reps=1, score=5)
    assert interval > 1
    assert ease >= 2.5
    assert reps == 2


def test_sm2_again_resets_interval():
    interval, ease, reps = sm2_review(interval=10, ease=2.5, reps=5, score=0)
    assert interval == 1
    assert reps == 0


def test_sm2_hard_decreases_ease():
    _, ease_after, _ = sm2_review(interval=3, ease=2.5, reps=2, score=2)
    assert ease_after < 2.5


def test_sm2_ease_floor():
    """Ease factor must never drop below 1.3."""
    ease = 2.5
    for _ in range(20):
        _, ease, _ = sm2_review(1, ease, 0, score=0)
    assert ease >= 1.3


def test_sm2_first_review_day_1():
    interval, _, reps = sm2_review(interval=0, ease=2.5, reps=0, score=3)
    assert interval == 1
    assert reps == 1


def test_sm2_second_review_day_6():
    _, _, reps1 = sm2_review(interval=0, ease=2.5, reps=0, score=3)
    interval2, _, reps2 = sm2_review(interval=1, ease=2.5, reps=1, score=3)
    assert interval2 == 6
    assert reps2 == 2


def test_sm2_good_grade_correct_reps():
    interval, ease, reps = sm2_review(interval=6, ease=2.5, reps=2, score=3)
    assert reps == 3
    assert round(interval) == round(6 * 2.5)


def test_sm2_easy_grade_boosts_ease():
    _, ease, _ = sm2_review(interval=6, ease=2.5, reps=2, score=5)
    assert ease > 2.5
