"""The review workflow must never fabricate human review."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mfpi import editorial

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def drafts(tmp_path):
    current = editorial.load_week(DATA, 2026, 4)
    previous = editorial.load_week(DATA, 2026, 3)
    articles = [
        editorial.weekly_analysis(current, previous, DATA),
        editorial.risers_and_fallers(current, previous),
        editorial.performance_review(DATA, 2026, 4),
    ]
    for article in articles:
        editorial.save_draft(article, tmp_path)
    return tmp_path, articles, current


def test_generated_articles_are_drafts_without_reviewer(drafts) -> None:
    _, articles, current = drafts
    for article in articles:
        assert article["status"] == "draft"
        assert article["reviewed_by"] is None and article["published_at"] is None
        assert article["author"] == editorial.DRAFT_AUTHOR
        assert editorial.validate_article(article, set(current.by_id)) == []
        assert article["sources"]


def test_publish_requires_named_reviewer_and_confirmation(drafts) -> None:
    content, articles, _ = drafts
    slug = articles[0]["slug"]
    with pytest.raises(SystemExit):
        editorial.publish(slug, "Jane Editor", confirm=False, content_dir=content)
    with pytest.raises(SystemExit):
        editorial.publish(slug, "   ", confirm=True, content_dir=content)
    with pytest.raises(SystemExit):
        editorial.publish(slug, editorial.DRAFT_AUTHOR, confirm=True, content_dir=content)
    stored = json.loads((content / f"{slug}.json").read_text())
    assert stored["status"] == "draft"

    now = datetime(2026, 9, 25, 15, tzinfo=timezone.utc)
    published = editorial.publish(slug, "Jane Editor", confirm=True, content_dir=content, now=now)
    assert published["status"] == "published" and published["reviewed_by"] == "Jane Editor"
    assert published["published_at"] == published["reviewed_at"]


def test_backdated_or_unreviewed_publication_is_rejected(drafts) -> None:
    _, articles, _ = drafts
    article = dict(articles[0], status="published", reviewed_by=None, reviewed_at=None, published_at=None)
    assert "published without a named human reviewer" in editorial.validate_article(article)
    snapshot_time = datetime.fromisoformat(articles[0]["snapshot_generated_at"])
    backdated = dict(articles[0], status="published", reviewed_by="Jane Editor",
                     reviewed_at=(snapshot_time - timedelta(days=2)).isoformat(),
                     published_at=(snapshot_time - timedelta(days=1)).isoformat())
    assert any("backdated" in problem for problem in editorial.validate_article(backdated))
    draft_with_reviewer = dict(articles[0], reviewed_by="Someone")
    assert editorial.validate_article(draft_with_reviewer)


def test_regenerating_never_overwrites_a_published_article(drafts) -> None:
    content, articles, _ = drafts
    slug = articles[1]["slug"]
    editorial.publish(slug, "Jane Editor", confirm=True, content_dir=content,
                      now=datetime(2026, 9, 25, 15, tzinfo=timezone.utc))
    _, outcome = editorial.save_draft(dict(articles[1]), content)
    assert outcome.startswith("kept")
    assert json.loads((content / f"{slug}.json").read_text())["status"] == "published"


def test_performance_review_uses_only_pregame_snapshots(drafts) -> None:
    _, articles, _ = drafts
    review = articles[2]
    table = next(section["table"] for section in review["sections"] if section["heading"] == "Results by ranking week")
    for row in table["rows"]:
        assert int(row[3]) <= int(row[2])
    # Each window's ranking must have been generated before any game it evaluates.
    for week in (1, 2, 3):
        snapshot = editorial.load_week(DATA, 2026, week)
        assert snapshot.generated_at.astimezone(editorial.CENTRAL).date() <= snapshot.cutoff_date


def test_articles_do_not_mention_unsupported_narratives(drafts) -> None:
    _, articles, _ = drafts
    text = json.dumps(articles).lower()
    for word in ("quarterback", "touchdown", "coach said", "told reporters", "sources say"):
        assert word not in text


def test_automated_publication_is_labelled_and_idempotent(tmp_path) -> None:
    articles, _ = editorial.build_articles(DATA, 2026, 4)
    first = datetime(2026, 9, 25, 16, tzinfo=timezone.utc)
    for article in articles:
        path, outcome = editorial.auto_publish(dict(article), tmp_path, now=first)
        assert outcome == "published"
        stored = json.loads(path.read_text())
        assert stored["publication_mode"] == "automated" and stored["approved_by"] == editorial.STANDING_APPROVER
        assert stored["reviewed_by"] is None and stored["reviewed_at"] is None
        assert editorial.validate_article(stored, now=first) == []
    # Same snapshot again: nothing changes.
    assert editorial.auto_publish(dict(articles[0]), tmp_path, now=first + timedelta(days=1))[1] == "unchanged"
    # A corrected snapshot refreshes the article but keeps its publication date.
    corrected = dict(articles[0], snapshot_run_id="2026-week-04-correction")
    path, outcome = editorial.auto_publish(corrected, tmp_path, now=first + timedelta(days=1))
    stored = json.loads(path.read_text())
    assert outcome.startswith("updated") and stored["published_at"] == first.astimezone(editorial.CENTRAL).isoformat(timespec="seconds")
    assert stored["updated_at"]


def test_automation_never_replaces_a_human_reviewed_article(tmp_path) -> None:
    articles, _ = editorial.build_articles(DATA, 2026, 4)
    editorial.save_draft(dict(articles[0]), tmp_path)
    editorial.publish(articles[0]["slug"], "Jane Editor", confirm=True, content_dir=tmp_path,
                      now=datetime(2026, 9, 25, 15, tzinfo=timezone.utc))
    _, outcome = editorial.auto_publish(dict(articles[0], snapshot_run_id="new"), tmp_path)
    assert outcome == "kept (human-reviewed)"


def test_automated_article_cannot_claim_a_reviewer() -> None:
    articles, _ = editorial.build_articles(DATA, 2026, 4)
    fake = dict(articles[0], status="published", publication_mode="automated", approved_by="Jon Ross Myers",
                reviewed_by="Jon Ross Myers", published_at="2026-09-25T10:00:00-05:00")
    assert "an automated article must not claim a human reviewer" in editorial.validate_article(fake)
