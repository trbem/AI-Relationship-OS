from app.graph.relationship_graph import RelationshipGraphService


def test_timeline_includes_snapshot_metadata(monkeypatch) -> None:
    service = RelationshipGraphService()
    snapshot = {
        "nodes": [
            {"id": "user", "type": "center"},
            {"id": "person-1", "type": "person", "name": "Alice"},
        ],
        "links": [],
        "insights": {
            "top_changes": [],
            "active_count": 1,
            "strongest_tie": "Alice",
            "stress_count": 0,
        },
    }
    monkeypatch.setattr(service, "build_snapshot", lambda *_args, **_kwargs: snapshot)

    result = service.build_timeline(db=None, user_id="user-1", checkpoints=[30])
    node = result["series"][0]["nodes"][0]

    assert node["days_ago"] == 30
    assert node["snapshot_key"] == "person-1@30"
