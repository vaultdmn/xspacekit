---
title: "Spaces Lifecycle"
description: "Fetching metadata, joining spaces, requesting speaker access, and polling occupancy."
---

# Spaces Lifecycle

Managing an X Space involves several coordinated steps across GraphQL and Periscope APIs.

## AudioSpace Metadata & Stream Discovery

Fetch space metadata using `AudioSpaceById` via GraphQL:

```python
from xspacekit.config.cookie_loader import load_cookie_file
from xspacekit.core import build_flow_from_cookie_file
from xspacekit.spaces.m3u8_extract import find_first_m3u8_url

cookie_cfg = load_cookie_file("cookie.txt")
flow = build_flow_from_cookie_file(cookie_cfg)

raw_meta = flow.spaces_api.audio_space_by_id_raw(
    query_id="bpQedjCUnMgs3yXNi8fZlA",
    broadcast_id="1dJrPrXonkqKX",
    with_replays=True,
    with_listeners=True,
)

m3u8_url = find_first_m3u8_url(raw_meta)
print(f"HLS Playback URL: {m3u8_url}")
```

## Speaker Request & Stream Negotiation

To speak in a Space:
1. **Join** the space as a listener with a derived `chat_token`.
2. **Submit** a speaker request (`audiospace/request/submit`) to receive a `session_uuid`.
3. **Negotiate** the media stream (`audiospace/stream/negotiate`) to receive the `janus_jwt` and `webrtc_gw_url`.
