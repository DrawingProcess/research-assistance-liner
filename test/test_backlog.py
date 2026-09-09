import json

from src.backlog import add_curiosity_topics, load_backlog, mark_done, pop_pending_topics, save_backlog, slugify


def test_slugify_lowercases_and_hyphenates():
    assert slugify("3D Gaussian Splatting scene graph") == "3d-gaussian-splatting-scene-graph"


def test_load_backlog_returns_empty_when_missing(tmp_path):
    assert load_backlog(tmp_path / "backlog.json") == {"topics": []}


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "backlog.json"
    data = {"topics": [{"id": "a", "topic": "A", "status": "pending", "source": "seed", "added_date": "2026-08-03"}]}
    save_backlog(path, data)
    assert load_backlog(path) == data


def test_save_backlog_writes_atomically_leaving_no_tmp_file(tmp_path):
    path = tmp_path / "backlog.json"
    save_backlog(path, {"topics": []})
    assert path.exists()
    assert not path.with_suffix(".json.tmp").exists()


def test_pop_pending_topics_returns_only_pending_up_to_n():
    backlog = {"topics": [
        {"id": "a", "topic": "A", "status": "done", "source": "seed", "added_date": "d"},
        {"id": "b", "topic": "B", "status": "pending", "source": "seed", "added_date": "d"},
        {"id": "c", "topic": "C", "status": "pending", "source": "seed", "added_date": "d"},
        {"id": "d", "topic": "D", "status": "pending", "source": "seed", "added_date": "d"},
    ]}
    result = pop_pending_topics(backlog, n=2)
    assert [t["id"] for t in result] == ["b", "c"]


def test_mark_done_updates_status_by_id():
    backlog = {"topics": [{"id": "a", "topic": "A", "status": "pending", "source": "seed", "added_date": "d"}]}
    mark_done(backlog, "a")
    assert backlog["topics"][0]["status"] == "done"


def test_add_curiosity_topics_inserts_at_front_and_dedupes():
    backlog = {"topics": [{"id": "existing", "topic": "Existing Topic", "status": "pending", "source": "seed", "added_date": "d"}]}
    added = add_curiosity_topics(backlog, ["New Topic", "Existing Topic"], "2026-08-04")
    assert added == ["New Topic"]
    assert backlog["topics"][0]["id"] == slugify("New Topic")
    assert backlog["topics"][0]["source"] == "curiosity"
    assert backlog["topics"][1]["id"] == "existing"
    assert len(backlog["topics"]) == 2
