from __future__ import annotations

from pathlib import Path

import pytest

from xspacekit.har.publisher_offer_trickle_extractor import extract_publisher_offer_and_trickle_from_har


def _fixture_har_path() -> Path:
    # tests live at: <repo>/src/xspacekit/tests/...
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "full_order_xspaces.har"


def test_extract_publisher_offer_and_trickle_from_har_default() -> None:
    har_path = _fixture_har_path()

    offer_sdp, trickle_candidates = extract_publisher_offer_and_trickle_from_har(
        har_file=har_path,
        janus_publisher_handle_id=None,
    )

    assert isinstance(offer_sdp, str)
    assert offer_sdp.strip() != ""

    assert isinstance(trickle_candidates, list)
    assert trickle_candidates

    # For the bundled HAR, we observed 7 trickle candidate objects
    # associated with the publisher offer.
    assert len(trickle_candidates) == 7

    for cand in trickle_candidates:
        assert isinstance(cand, dict)
        assert "candidate" in cand
        assert "sdpMid" in cand
        assert "sdpMLineIndex" in cand


def test_extract_publisher_offer_and_trickle_from_har_with_handle_filter() -> None:
    har_path = _fixture_har_path()

    # Handle id observed in the bundled HAR for the publisher offer.
    offer_sdp, trickle_candidates = extract_publisher_offer_and_trickle_from_har(
        har_file=har_path,
        janus_publisher_handle_id="7392863721276664",
    )

    assert offer_sdp.strip() != ""
    assert len(trickle_candidates) == 7


def test_extract_publisher_offer_and_trickle_from_har_invalid_handle_raises() -> None:
    har_path = _fixture_har_path()

    with pytest.raises(SystemExit) as exc:
        extract_publisher_offer_and_trickle_from_har(
            har_file=har_path,
            janus_publisher_handle_id="does-not-exist",
        )

    assert "janus_publisher_handle_id" in str(exc.value)
