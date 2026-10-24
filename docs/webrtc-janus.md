---
title: "WebRTC & Janus Signaling"
description: "HTTP long-poll gateway signaling and live Opus audio streaming via aiortc."
---

# WebRTC & Janus Signaling

`xspacekit` provides full orchestration of the Janus WebRTC gateway over HTTP long-polling, paired with `aiortc` for live media transport.

## Janus Gateway Architecture

- **Session Creation:** `POST <gateway_base_url>` creates a Janus session.
- **Plugin Attachment:** `POST <gateway_base_url>/<session_id>` attaches the `janus.plugin.videoroom` plugin.
- **Signaling Messages:** `POST <gateway_base_url>/<session_id>/<handle_id>` dispatches videoroom requests (`join`, `configure`, `start`) and ICE `trickle` candidates.
- **Event Polling:** `GET <gateway_base_url>/<session_id>?maxev=1` fetches keepalives, events, and JSEP answer SDPs.

## Live Audio Publishing (`aiortc`)

To stream live audio into a Space:

```python
from xspacekit.signaling import JanusGateway, JanusGatewayConfig
from xspacekit.transports import WebRtcTransport, WebRtcTransportConfig

gateway = JanusGateway(
    JanusGatewayConfig(
        gateway_base_url="https://gw-prod-hydra-ap-south-1.pscp.tv/s=prod:11/v1/gateway",
        janus_jwt="<JANUS_JWT>",
    )
)
transport = WebRtcTransport(WebRtcTransportConfig(janus_gateway=gateway))

# Publish live audio (e.g. silent frames or mic input for 5 seconds)
result = transport.publish_audio_live(
    room_id="1dJrPrXonkqKX",
    stream_name="1dJrPrXonkqKX",
    vidman_token="<JANUS_JWT>",
    periscope_user_id="<USER_ID>",
    session_uuid="<SESSION_UUID>",
    duration_s=5.0,
)
print("Live publication result:", result)
```
