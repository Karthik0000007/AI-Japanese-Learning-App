"""tests/test_srs.py — Unit tests for the SM-2 algorithm (pure logic, no DB)."""
from datetime import date, datetime, timedelta

import pytest

from core.srs import EASE_FLOOR, sm2_review
from models.srs import ItemType, SRSCard


def make_card(interval: int = 1, ease: float = 2.5, reps: int = 0) -> SRSCard:
    """Build an in-memory card; sm2_review never touches the database."""
    return SRSCard(
        item_type=ItemType.vocab,
        item_id=1,
        ease_factor=ease,
        interval_days=interval,
        reps=reps,
        due_date=date.today(),
    )


def test_sm2_easy_increases_interval():
    """An 'easy' second review jumps the interval from 1 to 6 days."""
    card = sm2_review(make_card(interval=1, ease=2.5, reps=1), grade=5)
    assert card.interval_days > 1
    assert card.ease_factor >= 2.5
    assert card.reps == 2


def test_sm2_again_resets_interval():
    """A failed review (grade 0) sends even a well-known card back to 0 reps and a 1-day interval."""
    card = sm2_review(make_card(interval=30, ease=2.5, reps=5), grade=0)
    assert card.interval_days == 1
    assert card.reps == 0


def test_sm2_hard_decreases_ease():
    """A 'hard' answer lowers the ease factor."""
    card = sm2_review(make_card(interval=3, ease=2.5, reps=2), grade=2)
    assert card.ease_factor < 2.5


def test_sm2_ease_floor():
    """Ease factor must never drop below 1.3."""
    card = make_card(ease=2.5)
    for _ in range(20):
        card = sm2_review(card, grade=0)
    assert card.ease_factor >= EASE_FLOOR


def test_sm2_first_review_day_1():
    """The first successful review schedules the card for tomorrow."""
    card = sm2_review(make_card(interval=1, ease=2.5, reps=0), grade=3)
    assert card.interval_days == 1
    assert card.reps == 1


def test_sm2_second_review_day_6():
    """The second successful review schedules the card 6 days out."""
    card = sm2_review(make_card(interval=1, ease=2.5, reps=1), grade=3)
    assert card.interval_days == 6
    assert card.reps == 2


def test_sm2_good_grade_correct_reps():
    """From the third review on, interval = previous interval x new ease, rounded up."""
    card = sm2_review(make_card(interval=6, ease=2.5, reps=2), grade=3)
    assert card.reps == 3
    # 'good' moves ease 2.5 -> 2.36, so 6 x 2.36 = 14.16 -> 15 days
    assert card.ease_factor == 2.36
    assert card.interval_days == 15


def test_sm2_easy_grade_boosts_ease():
    """An 'easy' answer raises the ease factor."""
    card = sm2_review(make_card(interval=6, ease=2.5, reps=2), grade=5)
    assert card.ease_factor > 2.5


# ─── Edge cases worth explaining ──────────────────────────────────────────────

GOOD, EASY, HARD, AGAIN = 3, 5, 2, 0


def review_n_times(grade: int, times: int) -> list[int]:
    """Review a brand-new card `times` times with the same grade; return each new interval."""
    card, intervals = make_card(), []
    for _ in range(times):
        card = sm2_review(card, grade)
        intervals.append(card.interval_days)
    return intervals


def test_ease_floor_is_exactly_1_3_and_stays_there():
    """Repeated failures pin the ease at exactly 1.3, and one more failure cannot push it lower."""
    card = make_card(ease=2.5)
    for _ in range(5):
        card = sm2_review(card, AGAIN)
    assert card.ease_factor == EASE_FLOOR

    card = sm2_review(card, AGAIN)
    assert card.ease_factor == EASE_FLOOR


def test_good_reviews_give_1_then_6_then_interval_times_ease():
    """Three 'good' reviews of a new card give 1 day, 6 days, then 6 x ease (2.08) rounded up = 13 days."""
    card = make_card()
    expected = [(1, 2.36), (6, 2.22), (13, 2.08)]  # (interval, ease) after reviews 1, 2, 3
    for interval, ease in expected:
        card = sm2_review(card, GOOD)
        assert card.interval_days == interval
        assert card.ease_factor == pytest.approx(ease)
    assert card.reps == 3


def test_easy_grows_the_interval_faster_than_good():
    """From the third review on, 'easy' gives longer intervals than 'good', and the gap keeps widening."""
    good = review_n_times(GOOD, 4)
    easy = review_n_times(EASY, 4)

    assert good == [1, 6, 13, 26]
    assert easy == [1, 6, 17, 50]
    assert easy[2] > good[2] and easy[3] > good[3]


def test_hard_counts_as_a_failure():
    """'Hard' (grade 2) is below the SM-2 pass mark of 3, so it restarts the card like 'again' does."""
    card = sm2_review(make_card(interval=15, ease=2.5, reps=3), HARD)
    assert card.reps == 0
    assert card.interval_days == 1


@pytest.mark.parametrize("grade", [AGAIN, HARD, GOOD, EASY])
def test_due_date_is_review_date_plus_interval(grade):
    """Whatever the grade, the card is due exactly `interval_days` after the day it was reviewed."""
    card = make_card(interval=6, reps=2)
    before = date.today()
    card = sm2_review(card, grade)
    after = date.today()  # guards against the test running across midnight

    assert card.due_date in {before + timedelta(days=card.interval_days),
                             after + timedelta(days=card.interval_days)}


def test_review_records_when_it_happened():
    """Each review stamps last_reviewed with the current time."""
    start = datetime.utcnow()
    card = sm2_review(make_card(), GOOD)
    assert card.last_reviewed is not None
    assert start <= card.last_reviewed <= datetime.utcnow()
