from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_GATEWAY_URL_RE = re.compile(r"/v1/gateway/([^/?#]+)/([^/?#]+)")


def extract_publisher_offer_and_trickle_from_har(
    *,
    har_file: str | Path,
    janus_publisher_handle_id: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Extract videoroom publisher offer SDP + trickle candidates from a HAR.

    This is based on the observed Janus videoroom sequence in the repo's captured HARs:
    - POST .../v1/gateway/<session_id>/<handle_id> with body.request=configure
      and jsep.type=offer => contains jsep.sdp (offer)
    - POST .../v1/gateway/<session_id>/<handle_id> with janus=trickle
      => contains candidate objects

    The returned trickle candidates preserve the candidate objects exactly as they
    appear in the HAR.
    """

    return _extract_publisher_offer_and_trickle_from_har(
        har_file=har_file,
        janus_publisher_handle_id=janus_publisher_handle_id,
    )


def _extract_publisher_offer_and_trickle_from_har(
    *,
    har_file: str | Path,
    janus_publisher_handle_id: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    har_path = Path(har_file).expanduser().resolve()
    har = json.loads(har_path.read_text(encoding="utf-8", errors="replace"))

    entries = har.get("log", {}).get("entries")
    if not isinstance(entries, list):
        raise SystemExit(f"har extraction: unexpected HAR format (entries missing): {har_path}")

    # Keyed by (session_id, handle_id)
    state: dict[tuple[str, str], dict[str, Any]] = {}

    def _ensure(key: tuple[str, str]) -> dict[str, Any]:
        if key not in state:
            state[key] = {"offer_sdp": None, "trickle_candidates": []}
        return state[key]

    for entry in entries:
        req = entry.get("request") or {}
        if not isinstance(req, dict):
            continue

        url = req.get("url") or ""
        if not isinstance(url, str):
            continue

        m = _GATEWAY_URL_RE.search(url)
        if not m:
            continue

        session_id, handle_id = m.group(1), m.group(2)
        if janus_publisher_handle_id is not None and handle_id != janus_publisher_handle_id:
            continue

        post_data = req.get("postData") or {}
        if not isinstance(post_data, dict):
            continue
        post_text = post_data.get("text")
        if not isinstance(post_text, str) or not post_text.strip():
            continue

        try:
            post_json = json.loads(post_text)
        except Exception:
            continue

        if not isinstance(post_json, dict):
            continue

        janus = post_json.get("janus")
        if janus not in {"message", "trickle"}:
            continue

        key = (session_id, handle_id)
        slot = _ensure(key)

        if janus == "message":
            body = post_json.get("body")
            if not isinstance(body, dict):
                continue
            if body.get("request") != "configure":
                continue

            jsep = post_json.get("jsep")
            if not isinstance(jsep, dict):
                continue
            jsep_type = jsep.get("type")
            if jsep_type != "offer":
                continue

            sdp = jsep.get("sdp")
            if isinstance(sdp, str) and sdp.strip():
                slot["offer_sdp"] = sdp

        elif janus == "trickle":
            cand = post_json.get("candidate")
            if isinstance(cand, dict):
                slot["trickle_candidates"].append(cand)

    if not state:
        raise SystemExit(
            "har extraction: no matching videoroom gateway requests found "
            f"in {har_path} (janus_publisher_handle_id filter={janus_publisher_handle_id!r})"
        )

    chosen_key: tuple[str, str] | None = None

    if janus_publisher_handle_id is not None:
        # Find any state entry for the requested handle_id.
        keys_for_handle = [k for k in state.keys() if k[1] == janus_publisher_handle_id]
        if not keys_for_handle:
            raise SystemExit(
                "har extraction: requested janus_publisher_handle_id not present in gateway URLs: "
                f"{janus_publisher_handle_id}"
            )

        # Pick the first one that has an offer.
        for k in sorted(keys_for_handle):
            if state[k].get("offer_sdp"):
                chosen_key = k
                break

        if chosen_key is None:
            raise SystemExit(
                "har extraction: found handle_id but no videoroom configure offer_sdp in messages "
                f"for handle_id={janus_publisher_handle_id}"
            )

    else:
        candidates_with_offer: list[tuple[tuple[str, str], dict[str, Any]]] = [
            (k, v) for k, v in state.items() if isinstance(v.get("offer_sdp"), str) and v.get("offer_sdp")
        ]
        if not candidates_with_offer:
            raise SystemExit("har extraction: no videoroom configure offer_sdp found in HAR")

        # Deterministic: max number of trickle candidates; tie-break lexicographically.
        chosen_key = max(
            (k for k, _v in candidates_with_offer),
            key=lambda k: (len(state[k].get("trickle_candidates") or []), -ord(k[1][0]) if k[1] else 0, k),
        )

    offer_sdp = state[chosen_key].get("offer_sdp")
    trickle_candidates = state[chosen_key].get("trickle_candidates")

    if not isinstance(offer_sdp, str) or not offer_sdp.strip():
        raise SystemExit("har extraction: extracted offer_sdp is empty")
    if not isinstance(trickle_candidates, list) or not trickle_candidates:
        raise SystemExit("har extraction: extracted trickle_candidates is empty")

    # Normalize for downstream SDP handling.
    return offer_sdp.strip(), trickle_candidates
