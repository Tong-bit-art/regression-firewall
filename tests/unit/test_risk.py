from regression_firewall.config.schema import ThresholdsConfig
from regression_firewall.models.change import Change
from regression_firewall.scoring.risk import score_changes
from regression_firewall.scoring.severity import confidence_for


def make_change(severity="high", classification="unexpected", category="status_changed",
                confidence=None):
    change = Change(surface="http", target="POST /login", category=category,
                    before=401, after=400, classification=classification,
                    severity=severity)
    change.confidence = confidence if confidence is not None else confidence_for(category)
    return change


TH = ThresholdsConfig()


def test_no_changes_pass():
    score, verdict, floored, contributions = score_changes([], TH)
    assert (score, verdict, floored) == (0, "PASS", False)


def test_critical_unexpected_blocks():
    score, verdict, floored, _ = score_changes([make_change("critical", category="symbol_removed")], TH)
    assert verdict == "BLOCK"
    assert floored and score == TH.block_score


def test_high_unexpected_blocks_by_default():
    score, verdict, floored, _ = score_changes([make_change("high")], TH)
    assert verdict == "BLOCK"
    assert floored and score == TH.block_score


def test_high_unexpected_review_when_block_on_high_false():
    th = ThresholdsConfig(block_on_high=False)
    score, verdict, floored, _ = score_changes([make_change("high")], th)
    # score 34 * 0.95 = 32 naturally exceeds review_score(30): REVIEW, no floor
    assert verdict == "REVIEW"
    assert not floored and score == 32


def test_medium_unexpected_reviews():
    score, verdict, floored, _ = score_changes(
        [make_change("medium", category="field_type_changed")], TH)
    assert verdict == "REVIEW"
    assert floored and score == TH.review_score


def test_uncertain_drives_review():
    change = make_change("low", classification="uncertain", category="stdout_changed")
    score, verdict, floored, _ = score_changes([change], TH)
    assert verdict == "REVIEW"
    assert floored and score == TH.review_score


def test_low_unexpected_passes():
    change = make_change("low", category="field_added")
    score, verdict, floored, _ = score_changes([change], TH)
    assert verdict == "PASS"
    assert not floored
    assert 0 < score < TH.review_score


def test_expected_changes_contribute_zero():
    expected = make_change("critical", classification="expected", category="symbol_removed")
    score, verdict, floored, contributions = score_changes([expected], TH)
    assert verdict == "PASS" and score == 0
    assert contributions[0].points == 0.0


def test_score_accumulates_without_floor():
    # 2 x medium unexpected structural (20 * 0.95 = 19 each) = 38 >= review 30, no block
    changes = [make_change("medium", category="field_type_changed"),
               make_change("medium", category="signature_changed")]
    score, verdict, floored, _ = score_changes(changes, TH)
    assert score == 38 and verdict == "REVIEW" and not floored


def test_score_blocks_at_threshold():
    # 3 x medium (19) = 57; add 2 low value_changed (4*0.75=3 each) = 63...
    # simpler: many mediums push past block threshold without any high
    changes = [make_change("medium", category="field_type_changed") for _ in range(4)]
    changes.append(make_change("medium", classification="uncertain", category="header_changed"))
    score, verdict, _, _ = score_changes(changes, TH)
    assert score >= TH.block_score
    assert verdict == "BLOCK"


def test_uncertain_discount():
    change = make_change("high", classification="uncertain", category="exit_code_changed")
    _, _, _, contributions = score_changes([change], TH)
    expected_points = round(34 * confidence_for("exit_code_changed") * 0.6, 2)
    assert contributions[0].points == expected_points
