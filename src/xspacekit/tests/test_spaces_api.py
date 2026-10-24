from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from xspacekit.spaces.spaces_api import AudioSpaceMetadata, SpacesApi


@dataclass
class _DummyXSession:
    def graphql(self, query_id: str, operation: str, *, variables: dict[str, Any], features=None):
        _ = (query_id, operation, features)
        # Minimal shape matching `SpacesApi.audio_space_by_id`.
        return {
            "data": {
                "audioSpace": {
                    "metadata": {
                        "rest_id": variables["id"],
                        "state": "Running",
                        "title": "Test Space",
                        "participants": {"admins": [], "speakers": [], "listeners": [], "total": 0},
                    }
                }
            }
        }


def test_audio_space_by_id_parses_metadata() -> None:
    dummy = _DummyXSession()
    api = SpacesApi(x_session=dummy)

    meta = api.audio_space_by_id(
        query_id="bpQedjCUnMgs3yXNi8fZlA",
        broadcast_id="br-1",
        with_replays=True,
        with_listeners=True,
        is_metatags_query=False,
        features=None,
    )

    assert isinstance(meta, AudioSpaceMetadata)
    assert meta.broadcast_id == "br-1"
    assert meta.state == "Running"
    assert meta.title == "Test Space"
    assert meta.participants["total"] == 0
