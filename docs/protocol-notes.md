# xspacekit protocol notes (from `captures/spaces.har`)

**Source:** HAR captured from a browser session (LibreWolf) visiting an X Spaces page.

**Sensitive-data rule:** the HAR includes live cookies/tokens. This document **does not** include any of those values. Every token-like field is replaced with placeholders such as `<AUTH_TOKEN>`, `<CT0>`, `<X_BEARER>`, `<GUEST_JWT>`, `<CHAT_TOKEN>`, `<SESSION_UUID>`, `<JANUS_JWT>`, etc.

**Legend:**
- ✅ = directly observed in the HAR
- 🔶 = inferred from observed shapes (explicitly marked)
- ❓ = not enough data in the HAR

---

## 1) Auth

### 1.1 What gets authenticated

#### X web session (GraphQL)
✅ GraphQL calls to `https://x.com/i/api/graphql/...` include:
- `authorization: Bearer <X_BEARER>`
- `x-csrf-token: <CT0>`
- `Cookie: auth_token=<AUTH_TOKEN>; ct0=<CT0>; ...`

The web session is likely refreshed/rotated by the normal browser login and cookie lifecycle.

#### Per-session “guest” authorization for Audiospace/Periscope backend
✅ Requests to `https://guest-cf.pscp.tv/api/v1/audiospace/...` include:
- `Authorization: <GUEST_JWT>` (JWT-like bearer)
- Some calls additionally pass “chat tokens” and “session UUIDs” in the JSON body.

✅ The guest JWT is obtained by calling Periscope’s token endpoint:
- `POST https://proxsee-cf.pscp.tv/api/v2/authorizeToken`

✅ TURN credentials are obtained separately via:
- `POST https://proxsee-cf.pscp.tv/api/v2/turnServers`

---

### 1.2 Endpoint: X GraphQL session bootstrap (example)

#### Viewer badge counts (GraphQL)
- **Observed method:** `GET`
- **URL pattern:**
  - `https://x.com/i/api/graphql/<QUERY_ID>/ViewerBadgeCounts?variables={...}`
- **Observed query id:** `q4Npr1-FYRWyXsRzPckwEA` ✅
- **Observed request id:** `x-client-transaction-id: <X_CLIENT_TX_ID>` ✅ (present in the HAR)

**Required headers (observed):**
- `authorization: Bearer <X_BEARER>` ✅
- `x-csrf-token: <CT0>` ✅
- `x-twitter-auth-type: OAuth2Session` ✅
- `x-client-transaction-id: <X_CLIENT_TX_ID>` ✅
- `x-twitter-active-user: yes` ✅

**Optional-ish (not validated in HAR):**
- `Accept-Language`, `x-twitter-client-language` ✅ (present)

**Redacted example request:**
```http
GET https://x.com/i/api/graphql/q4Npr1-FYRWyXsRzPckwEA/ViewerBadgeCounts?variables=%7B%7D
authorization: Bearer <X_BEARER>
x-csrf-token: <CT0>
x-client-transaction-id: <X_CLIENT_TX_ID>
Cookie: auth_token=<AUTH_TOKEN>; ct0=<CT0>; guest_id=<GUEST_ID>; ...
```

**Redacted example response (shape):**
```json
{
  "data": {
    "viewer_v2": {
      "user_results": {
        "result": {
          "__typename": "User",
          "badge_counts": {
            "total_unread_count": 0,
            "xchat_unread_count": 0,
            "is_from_urt": true
          }
        }
      }
    }
  }
}
```

---

### 1.3 Endpoint: Guest token bootstrap

#### AuthorizeToken
- **Observed method:** `POST`
- **URL pattern:** `https://proxsee-cf.pscp.tv/api/v2/authorizeToken`
- **Observed request id:** none/empty in HAR ✅

**Required headers (observed):**
- `Content-Type: application/json` ✅
- Standard browser CORS headers were present (e.g. `Origin`, `Referer`) ✅

**Body (observed shape):**
```json
{
  "service": "guest",
  "cookie": "atu<REDACTED>"
}
```

**Redacted example response (shape):**
```json
{
  "authorization_token": "eyJ...<REDACTED>..."
}
```

**Refresh/TTL:** ❓ Not fully characterized in HAR.

---

### 1.4 Endpoint: TURN credential bootstrap

#### TurnServers
- **Observed method:** `POST`
- **URL pattern:** `https://proxsee-cf.pscp.tv/api/v2/turnServers`
- **Observed request id:** none/empty in HAR ✅

**Required headers (observed):**
- `Content-Type: application/json` ✅

**Body (observed shape):**
```json
{
  "cookie": "atu<REDACTED>"
}
```

**Redacted example response (shape):**
```json
{
  "ttl": "86400",
  "username": "<TURN_USERNAME>",
  "password": "<TURN_PASSWORD>",
  "uris": ["turns:turn.pscp.tv:443?transport=tcp"]
}
```

**Interpretation:**
- ✅ `ttl` suggests credentials last ~24 hours.

---

### 1.5 Minimum credentials the SDK likely needs

Based on the HAR, the SDK needs access to a browser-like authenticated context.

**Minimum to observe Audiospace backend behavior:**
- ✅ An X session cookie set that allows the client to obtain the `atu` cookie value used by `authorizeToken` / `turnServers`.

**Practical minimum (observed cookies/headers):**
- `auth_token=<AUTH_TOKEN>` and `ct0=<CT0>` cookies ✅
- `guest_id=<GUEST_ID>` (present in Cookie header) ✅
- A way to include the `ct0` value as `x-csrf-token` for GraphQL calls ✅

**Required headers vs optional:**
- For GraphQL: `authorization` + `x-csrf-token` were present and needed for observed requests.
- For Periscope endpoints: the `Authorization: <GUEST_JWT>` header was present for audiospace join/stream actions.

**❓ Unknown:** whether a truly “guest-only” flow (no logged-in account) is sufficient end-to-end for *speaking*.

---

## 2) Space lifecycle

### 2.1 Fetching Space metadata from a Space URL/ID

#### AudioSpaceById (GraphQL)
- **Observed method:** `GET`
- **URL pattern:**
  - `https://x.com/i/api/graphql/<QUERY_ID>/AudioSpaceById?variables=<JSON>&features=<JSON>`
- **Observed query id:** `bpQedjCUnMgs3yXNi8fZlA` ✅
- **Observed request id:** `x-client-transaction-id: <X_CLIENT_TX_ID>` ✅

**variables (observed):**
```json
{
  "id": "<BROADCAST_ID>",
  "isMetatagsQuery": false,
  "withReplays": true,
  "withListeners": true
}
```

**Response (relevant fields, observed):**
- `audioSpace.metadata` including:
  - `rest_id` (same as broadcast id) ✅
  - `state` (e.g. `Running`) ✅
  - `title` ✅
  - `started_at` ✅
  - `max_admin_capacity`, `max_guest_sessions` ✅
  - `participants` including `admins[]` and `speakers[]` ✅

**Redacted example response excerpt (shape):**
```json
{
  "data": {
    "audioSpace": {
      "is_subscribed": false,
      "metadata": {
        "rest_id": "<BROADCAST_ID>",
        "state": "Running",
        "title": "<TITLE>",
        "max_admin_capacity": 3,
        "max_guest_sessions": 10,
        "participants": {
          "admins": [ {"guest_is_audio_only": true, "guest_username": "<...>"} ],
          "speakers": [ {"guest_is_audio_only": true, "guest_username": "<...>"} ],
          "listeners": [],
          "total": 1
        }
      }
    }
  }
}
```

**Features flags:** ✅ The request includes a large `features={...}` object.

**❓ Unknown:** Which feature flags are essential vs optional for the minimum metadata subset.

---

### 2.2 Joining as a listener

#### Audiospace join

**`chat_token` source (auto-derivation):** In the current SDK flow, `audiospace/join.chat_token` is derived automatically via:
- `live_video_stream/status` (using a `media_key` extracted from the `AudioSpaceById` response)
- then `accessChat` (which returns a join-ready `access_token`, used as `chat_token`)

So `cookie.txt.chat_token` is treated as **legacy/optional**: callers may omit `chat_token` from the cookie file/CLI flags as long as they provide the X+Periscope cookie inputs required to reach `accessChat`.

- **Observed method:** `POST`
- **URL pattern:** `https://guest-cf.pscp.tv/api/v1/audiospace/join`
- **Observed request id:** none/empty ✅

**Required headers (observed):**
- `authorization: <GUEST_JWT>` ✅
- `Content-Type: application/json` ✅

**Body (observed):**
```json
{
  "ntpForBroadcasterFrame": 2208988800021999900,
  "ntpForLiveFrame": 2208988800021999900,
  "broadcast_id": "<BROADCAST_ID>",
  "join_as_admin": false,
  "should_auto_join": false,
  "chat_token": "<CHAT_TOKEN>"
}
```

**Response (observed):**
```json
{
  "can_auto_join": false
}
```

**Interpretation:**
- This session did *not* auto-join.
- ✅ It still returned enough data to proceed with later speaker/request flows (likely via `request/submit`).

---

### 2.3 Being approved as a speaker

#### Submit a speaker request
- **Observed method:** `POST`
- **URL pattern:** `https://guest-cf.pscp.tv/api/v1/audiospace/request/submit`
- **Observed request id:** none/empty ✅

**Required headers (observed):**
- `authorization: <GUEST_JWT>` ✅

**Body (observed):**
```json
{
  "ntpForBroadcasterFrame": 2208988800021999900,
  "ntpForLiveFrame": 2208988800021999900,
  "broadcast_id": "<BROADCAST_ID>",
  "chat_token": "<CHAT_TOKEN>"
}
```

**Redacted example response:**
```json
{
  "success": true,
  "session_uuid": "<SESSION_UUID>"
}
```

#### Admin mute/unmute / permissions
- **Endpoints observed (speaker moderation controls):**
  - `POST https://guest-cf.pscp.tv/api/v1/audiospace/muteSpeaker`
  - `POST https://guest-cf.pscp.tv/api/v1/audiospace/unmuteSpeaker`

**Observed behavior in this capture:** both unmute/mute calls returned `410 Gone` in this timeline.

**Body shape (observed for mute/unmute):**
```json
{
  "ntpForBroadcasterFrame": 2208988800021999900,
  "ntpForLiveFrame": 2208988800021999900,
  "session_uuid": "<SESSION_UUID>",
  "broadcast_id": "<BROADCAST_ID>",
  "chat_token": "<CHAT_TOKEN>"
}
```

**❓ Unknown:** The exact “speaker approval” step (what triggers state transition) because the capture’s control calls landed after a `can_auto_join: false` case and resulted in `410`.

---

### 2.4 Creating or hosting a Space

❓ Not captured in this HAR.

---

### 2.5 Signaling / chat WebSocket alternative

The HAR does not show a raw `wss://` WebSocket in captured requests (heuristic/grep found none).

Instead, the capture shows an HTTP streaming chat feed:

#### Live chat feed
- **Observed method:** `GET`
- **URL pattern:** `https://api.x.com/live-chat?broadcastId=<BROADCAST_ID>&sessionId=<SESSION_ID>` ✅

**Observed request headers (subset):**
- `authorization: <X_BEARER>` ✅
- `x-csrf-token: <CT0>` ✅

**Response content-type:** `application/x-ndjson` ✅

**Redacted example response (shape):**
```ndjson
{"ts":"<TS>","chatType":40,"userId":"<USER_ID>","isBackfill":true,"controlType":17,"targetUserId":"<USER_ID>","targetSessionUuid":"<SESSION_UUID>"}
{"ts":"<TS>","chatType":51,"userId":"<USER_ID>"}
```

**Interpretation (🔶):**
- `chatType` and `controlType` likely correspond to event types like speaker actions, occupancy updates, or chat messages.
- ✅ Occupancy transitions were also visible via `audiospace/call/status`.

**❓ Unknown:** Whether `live-chat` also transports speaker-request approvals or whether `audiospace/call/status` is the canonical source.

#### accessChat (chat backend bootstrap)
Source: user-provided cURL/response (not present in the HAR file).

**SDK usage:** `accessChat` is the final step in the join-ready `chat_token` derivation chain (seeded by `live_video_stream/status`).

- **Observed method:** `POST`
- **URL pattern:** `https://proxsee-cf.pscp.tv/api/v2/accessChat`
- **Observed request headers (minimum set, rest were typical browser CORS headers):**
  - `Content-Type: application/json`
  - `X-Periscope-User-Agent: Twitter/m5`
  - `Alt-Used: proxsee-cf.pscp.tv`

- **Body (observed):**
```json
{
  "chat_token": "<CHAT_TOKEN>",
  "cookie": "<AUTH_COOKIE_BLOB>"
}
```

- **Response fields (redacted example shape):**
```json
{
  "endpoint": "https://prod-chatman-ancillary-<REGION>.pscp.tv",
  "replay_endpoint": "https://chatman-replay-<REGION>.pscp.tv",
  "room_id": "<ROOM_ID>",
  "participant_index": <PARTICIPANT_INDEX>,
  "access_token": "<CHATMAN_ACCESS_TOKEN>",
  "replay_access_token": "<CHATMAN_REPLAY_ACCESS_TOKEN>",

  "signer_key": "<REDACTED>",
  "signer_token": "-",
  "should_verify_signature": false,
  "read_only": false,
  "should_log": false,

  "chan_perms": { "pb": 0, "cm": 15 }
}
```

**Interpretation (🔶):**
- `accessChat` likely authorizes the client to join an internal “chatman” room for the space and provides tokens + endpoints for subsequent chat messaging/signaling.

**❓ Open:** In this capture we used `api.x.com/live-chat` (NDJSON) for events, but we did not see WebSocket-level `chatman` traffic. Determine whether `accessChat` is required for certain event types (speaker requests, occupancy, etc.) and how it relates to `live-chat`.

---

### 2.6 Occupancy / participant state

#### Call status polling
- **Observed method:** `POST`
- **URL pattern:** `https://guest-cf.pscp.tv/api/v1/audiospace/call/status`
- **Observed request id:** none/empty ✅

**Body (observed):**
```json
{
  "broadcast_id": "<BROADCAST_ID>",
  "include_non_active_sessions": false
}
```

**Redacted example response excerpt (shape):**
```json
{
  "success": true,
  "host_broadcast_id": "<BROADCAST_ID>",
  "call_in_disabled": false,
  "guest_sessions": [
    {
      "session_uuid": "<SESSION_UUID>",
      "session_state": 9,
      "guest_is_audio_only": true,
      "is_muted_by_admin": false,
      "is_muted_by_guest": true,
      "ended_at": "0001-01-01T00:00:00Z"
    }
  ]
}
```

**Interpretation:**
- ✅ This is the best observed “occupancy/state” source in the HAR.
- 🔶 `session_state` numeric codes aren’t fully decoded, but in this capture the speaker session appears to move from `session_state=9` (immediately after `stream/negotiate`) to `session_state=10` soon after, and whenever `session_state=10` was observed, `is_muted_by_guest=true` was also true. Exact semantic meaning is still ❓ incomplete.

---

## 3) Audio transport

### 3.1 Listening / speaking transports in this HAR

This capture strongly shows **two** audio delivery mechanisms:

1) ✅ **HLS playback endpoints**
   - `application/x-mpegURL` (m3u8)
   - `audio/aac` chunks
   - Host(s) observed:
     - `https://prod-fastly-ap-south-1.video.pscp.tv/...`
     - `https://video.twimg.com/amplify_video/...`

2) ✅ **WebRTC/Janus negotiation bootstrap** (Janus runs over the HTTP gateway)
   - `POST https://guest-cf.pscp.tv/api/v1/audiospace/stream/negotiate`
     - returns `janus_jwt` and `webrtc_gw_url`
   - Subsequent Janus signaling uses:
     - `POST https://gw-.../v1/gateway` (Janus session create + videoroom attach + message requests)
     - `GET https://gw-.../v1/gateway/<session>?maxev=1` (long-poll event delivery)
   - ✅ SDP/ICE are carried inside Janus payloads:
     - `jsep` (offer/answer) fields in `configure`/`start` messages
     - ICE candidates via `janus: "trickle"` requests

3) ❓ **RTMPS ingest path**
   - No direct `rtmps://` / `rtmp://` / ingest URL / stream key was found in the HAR.

---

### 3.2 Endpoint: Janus/WEBRTC bootstrap (negotiation)

#### Stream negotiate
- **Observed method:** `POST`
- **URL pattern:** `https://guest-cf.pscp.tv/api/v1/audiospace/stream/negotiate`
- **Observed request id:** none/empty ✅

**Required headers (observed):**
- `authorization: <GUEST_JWT>` ✅

**Body (observed):**
```json
{
  "session_uuid": "<SESSION_UUID>"
}
```

**Redacted example response (shape):**
```json
{
  "janus_jwt": "<JANUS_JWT>",
  "webrtc_gw_url": "<WEBRTC_GATEWAY_URL>"
}
```

In this capture, the gateway URL matched:
- `https://gw-prod-hydra-ap-south-1.pscp.tv/s=prod:11/v1/gateway` ✅

**ICE/TURN:**
- ✅ TURN creds were obtained from `turnServers` endpoint (Section 1.4).

**Keepalive behavior / SDP exchange:** ✅
- Janus gateway “keepalive”/event delivery is done via repeated HTTP long-poll calls with `?maxev=1`.
- SDP exchange is embedded in Janus requests (best-effort role mapping from this HAR):
  - **Publisher / speaking** side: `request: "configure"` includes `jsep: { type: "offer", sdp: ... }` ✅
  - **Subscriber / listening** side: `request: "start"` includes `jsep: { type: "answer", sdp: ... }` ✅ (observed in a separate gateway session)
  - `start` was not present in the limited publisher window captured here, so treat this as “offer ↔ answer” sequencing rather than a universal rule.
- ICE gathering is exchanged via Janus `trickle` messages (multiple `janus: "trickle"` calls with `candidate` objects).

#### Janus gateway message (videoroom joined)
✅ Observed in HAR (speaker-side videoroom joined event).

- **Observed method:** `GET`
- **URL pattern:**
  - `https://gw-prod-hydra-ap-south-1.pscp.tv/s=prod:<X>/v1/gateway/<JANUS_SESSION_ID>?maxev=1`
- **Required headers (observed minimum):**
  - `Authorization: <JANUS_JWT>`
  - `Content-Type: application/json` (present)

- **Response (redacted example shape):**
```json
{
  "janus": "event",
  "session_id": "<JANUS_SESSION_ID>",
  "transaction": "<TXN>",
  "sender": "<SENDER>",
  "plugindata": {
    "plugin": "janus.plugin.videoroom",
    "data": {
      "videoroom": "joined",
      "room": "<ROOM_ID>",
      "description": "Room <ROOM_ID>",
      "id": "<PRIVATE_ID>",
      "private_id": "<PRIVATE_ID>",
      "publishers": [
        {
          "id": "<PUBLISHER_ID>",
          "audio_codec": "opus",
          "streams": [
            {
              "type": "audio",
              "mid": "0",
              "codec": "opus",
              "fec": true,
              "talking": false
            }
          ],
          "talking": false
        }
      ]
    }
  }
}
```

**Inferences from provided event (🔶):**
- Spaces audio uses Janus `videoroom` plugin with `audio_codec: "opus"` and (at least in this run) `fec: true`.

---

### 3.4 Live aiortc Audio Streaming Implementation

`xspacekit` includes native support for live audio streaming via `aiortc`:
- **Dynamic Offer Generation:** `WebRtcTransport.publish_audio_live(...)` initializes a local `RTCPeerConnection`, adds an `AudioStreamTrack` backed by `AudioStream` (which encodes/packs mono/stereo 16-bit PCM into Opus frames), and generates a live SDP offer with correct DTLS-SRTP fingerprints.
- **ICE Gathering & Trickle:** Local ICE candidates are gathered asynchronously and dispatched via Janus `trickle` messages over the HTTP long-poll gateway.
- **Signaling Completion:** The transport sends `join` and `configure` with the live offer, parses the remote answer SDP from Janus long-poll events, completes the DTLS/ICE handshake, and streams audio packets directly into the X Space.

- The “room id” (`room`) matches the `chatman`/room_id concept from `accessChat` response.

**❓ Remaining gaps / full-implementation needs:**
- Codify full role mapping between Janus `videoroom` messages and “listening” vs “speaking/publishing” (this HAR contains `join ptype=publisher` + later `configure offer`, and a separate gateway session with `join ptype=subscriber` + `start jsep=answer`, but we still need the complete state machine).
- Determine exactly how `vidman_token` / `stream_name` are used (e.g. whether `stream_name` == `room` for configure in all cases, and whether `vidman_token` changes per session).
- Extract and normalize SDP/ICE parameters into a reusable WebRTC adapter (this doc records presence, but not every field).
- Confirm whether RTMPS ingest is used for any publishing path (not observed via `rtmps://` in this HAR).

---

### 3.3 Endpoint: HLS delivery (observed listening playback)

The HAR shows multiple `GET` requests for:
- `application/x-mpegURL` (m3u8 playlists)
- `audio/aac` (audio segments)

**Examples (redacted):**
- `GET https://prod-fastly-ap-south-1.video.pscp.tv/Transcoding/v1/hls/<STREAM_ID>/index.m3u8` ✅ (m3u8 observed; some `404` attempts also observed)
- `GET https://prod-fastly-ap-south-1.video.pscp.tv/.../<SEGMENT>.aac` ✅

**Interpretation (🔶):**
- These URLs likely come from AudioSpace metadata + player logic.
- HLS may be used for passive listening while WebRTC/Janus is used for interactive speaker streams.

**❓ Codec expectation:**
- AAC segments are observed, but full HLS variant details (bitrates, profiles) are not extracted in this HAR analysis.

---

### 3.4 RTMPS ingest path

❓ No `rtmps://` or ingest endpoint was captured.

We can’t infer:
- how the ingest URL is obtained
- what the stream key is
- what input audio format is expected

---

### 3.5 Which transport is needed for which feature

Based on observed endpoints:

- **Listen (consumer playback):**
  - ✅ HLS endpoints are used for audio playback.
  - WebRTC path presence is uncertain (negotiation happened, so listen could also use WebRTC).

- **Speak (interactive speaker role):**
  - ✅ Speaker role likely requires successful `audiospace/request/submit` and a stream negotiation (`stream/negotiate`).
  - 🔶 In this HAR, the publisher path uses Janus `videoroom` with `join ptype=publisher` followed by `configure` with `jsep` **offer** + `trickle` candidates (no RTMPS ingest URLs were captured). RTMPS ingest still remains ❓ unverified for other timelines.

- **Broadcast (creating/hosting speaker/admin):**
  - ❓ Not in HAR.

---

## 4) Output format requirements for the SDK (endpoints + examples)

This section summarizes the endpoints already observed, grouped by protocol area.

> All examples below redact sensitive values.

### 4.1 GraphQL

#### AudioSpaceById
- Method: `GET`
- URL: `https://x.com/i/api/graphql/bpQedjCUnMgs3yXNi8fZlA/AudioSpaceById?variables=...&features=...`
- Required headers (observed):
  - `authorization: Bearer <X_BEARER>`
  - `x-csrf-token: <CT0>`
- Request id: `x-client-transaction-id: <X_CLIENT_TX_ID>`
- Redacted request: see Section 2.1
- Redacted response: see Section 2.1

---

### 4.2 Space join / speaker

#### Audiospace join
- Method: `POST`
- URL: `https://guest-cf.pscp.tv/api/v1/audiospace/join`
- Required headers (observed):
  - `authorization: <GUEST_JWT>`
  - `Content-Type: application/json`
- Request id: none/empty
- Redacted request/response: see Section 2.2

#### Audiospace request/submit (speaker request)
- Method: `POST`
- URL: `https://guest-cf.pscp.tv/api/v1/audiospace/request/submit`
- Required headers (observed): `authorization: <GUEST_JWT>`
- Request id: none/empty
- Redacted request/response: see Section 2.3

---

### 4.3 Signaling/chat

#### Live chat feed
- Method: `GET`
- URL: `https://api.x.com/live-chat?broadcastId=<BROADCAST_ID>&sessionId=<SESSION_ID>`
- Required headers (observed): `authorization`, `x-csrf-token`
- Request id: none/empty ✅ (request id not captured as x-client-transaction-id in this entry)
- Redacted response: see Section 2.5

---

### 4.4 WebRTC/Janus bootstrap

#### Stream negotiate
- Method: `POST`
- URL: `https://guest-cf.pscp.tv/api/v1/audiospace/stream/negotiate`
- Required headers (observed): `authorization: <GUEST_JWT>`
- Request id: none/empty
- Redacted request/response: see Section 3.2

---

### 4.5 TURN

#### TurnServers
- Method: `POST`
- URL: `https://proxsee-cf.pscp.tv/api/v2/turnServers`
- Required headers (observed): `Content-Type: application/json`
- Request id: none/empty
- Redacted request/response: see Section 1.4

---

## 5) Inferences vs unknowns

### Updated observations (from a deeper Janus scrape)
- ✅ Gateway session create is a `POST <gw>/v1/gateway` returning a gateway “session id”.
- ✅ Plugin attach uses `POST <gw>/v1/gateway/<session>` with `{ "janus": "attach", "plugin": "janus.plugin.videoroom" }`.
- ✅ Videoroom publisher path in this HAR:
  - `POST .../gateway/<session> { janus: "message", request: "create", audiocodec: "opus", videocodec: "h264" }`
  - `request: "join", ptype: "publisher"`
  - `request: "configure", jsep: { type: "offer" }` (includes `session_uuid`, `stream_name`, `vidman_token`)
  - `janus: "trickle"` candidates
- ✅ Separate subscriber/listening path exists in another gateway session:
  - `request: "join", ptype: "subscriber"`
  - `request: "start", jsep: { type: "answer" }`
  - additional `janus: "trickle"` candidates

### Items confidently observed
- ✅ GraphQL query id and variables structure for `AudioSpaceById`
- ✅ Guest auth bootstrap via `authorizeToken`
- ✅ TURN credential bootstrap via `turnServers`
- ✅ AudioSpace join, speaker request submission, call status polling
- ✅ Janus negotiation endpoint returning `janus_jwt` and `webrtc_gw_url`
- ✅ Live chat feed endpoint returns NDJSON events
- ✅ HLS audio playback (m3u8 + AAC segments)

### Items not captured (must be verified)
- ❓ Janus WebSocket URL and message sequence (session create / plugin attach / publish / subscribe)
- ❓ SDP offer/answer exchange and negotiated codecs
- ❓ RTMPS ingest path and stream key mechanics
- ❓ Full mapping of `session_state` integers to semantic states
- ❓ Speaker approval workflow (what transition indicates “can publish speaking audio”)
- ❓ “host/create space” backend sequence

---

## 6) Plan: xspacekit architecture

### 6.1 Language choice: TypeScript (recommended)

Rationale:
- WebRTC (RTCPeerConnection, RTP sender/receiver, data channel) and Janus-like gateways are naturally ergonomic in TypeScript/JavaScript.
- Node.js can run the WebSocket/HTTP pieces for signaling.
- Consistent cross-platform package distribution and typing for a public SDK.

Alternative (Python): viable with `aiortc` + websockets, but WebRTC codec/packet plumbing can be more cumbersome.

### 6.2 Package layout

Proposed monorepo or single package layout:
- `auth/`
  - `XSession.ts` (cookie/config loading + GraphQL request signing headers)
  - `GuestAuth.ts` (calls `authorizeToken`, manages `<GUEST_JWT>` lifecycle)
- `spaces/`
  - `SpacesApi.ts` (GraphQL `AudioSpaceById` wrapper)
  - `types.ts` (Space metadata shapes)
- `signaling/`
  - `LiveChatClient.ts` (NDJSON `live-chat` polling/stream parsing)
  - `JanusGateway.ts` (🔶 implement once WebSocket/Janus messages are captured)
- `transports/`
  - `HlsTransport.ts` (listen-only playback URLs -> demux/decoder integration)
  - `WebRtcTransport.ts` (speaker/listener media via SDP exchange)
  - `RtmpsTransport.ts` (❓ once RTMPS path is captured)
- `audio/`
  - `codecs/Opus.ts` and `codecs/Pcm.ts` (encode/decode utilities)
  - `AudioStream.ts` abstraction: in/out interface for “PCM” and “Opus in/out”
- `cli/`
  - `xspacekit listen <space-url>`
  - `xspacekit speak <space-url> --audio <file>`
  - `xspacekit agent <space-url> --provider <llm> ...` (pipes realtime agent voice)

### 6.3 Public API sketch (no implementation)

```ts
const kit = new XSpaceKit({
  auth: {
    // user supplies cookies or a browser-session export
    xSession: { authToken: '<AUTH_TOKEN>', ct0: '<CT0>', guestId: '<GUEST_ID>' }
  }
});

const space = await kit.spaces.openByUrl('https://x.com/<user>/spaces/<id>');

// 1) Listen
const listener = await space.join({ role: 'listener' });
listener.on('occupancy', (state) => console.log(state));
await listener.play(); // uses HLS by default

// 2) Speak
const speaker = await space.join({ role: 'speaker', approveMode: 'request' });
const stream = await speaker.negotiateStream(); // returns Janus/WebRTC transport
await speaker.publishAudio({
  input: audioFileStream('voice.wav'),
  format: 'pcm_s16le'
});

// 3) Pipe a realtime LLM voice agent
const agent = new RealtimeVoiceAgent({ /* provider config */ });
await speaker.publishAgent(agent, { inputFormat: 'opus' });
```

### 6.4 Risks and isolation strategy

**Key risks (observed endpoints are brittle):**
- GraphQL query ids and feature flags may rotate.
- Periscope endpoints may require different JSON shapes over time.
- WebRTC/Janus signaling is likely not fully compatible with naive assumptions.

**Isolation:**
- Keep each protocol area behind interfaces:
  - `GuestAuth` behind `AuthProvider`
  - `JanusGateway` behind `WebRtcSignaling` interface
  - `Transports` behind `MediaTransport` interface
  - `Chat` behind `EventStream` abstraction

So when endpoints rotate, only one adapter needs patching.

### 6.5 Phased milestones (smallest end-to-end first)

1) **Auth bootstrap (guest)**
   - Inputs: user-provided cookie/config
   - Calls: `authorizeToken` + `turnServers`
   - Output: `<GUEST_JWT>`, TURN servers list

2) **Fetch Space metadata**
   - Calls: GraphQL `AudioSpaceById`
   - Output: normalized `Space` model (state, participants, ids)

3) **Join as listener**
   - Calls: `audiospace/join` + `audiospace/call/status`
   - Output: session UUID (if provided later), occupancy events

4) **Live chat event ingestion**
   - Calls: `api.x.com/live-chat` (NDJSON)
   - Output: speaker-request/occupancy event mapping (initial best-effort)

5) **WebRTC transport bring-up (Janus)**
   - Requires additional capture of Janus WebSocket / SDP exchange.
   - Implement `JanusGateway` to complete SDP offer/answer.

6) **Speaking publish**
   - Calls: `request/submit` -> `stream/negotiate` -> Janus publish
   - Output: local audio -> remote audio (start with a simple PCM->Opus path)

7) **RTMPS path (optional)**
   - Only after capturing ingest URL/stream key.

8) **CLI + LLM voice piping**
   - Once WebRTC speaking works, add a CLI and wire an agent voice generator into the `AudioStream` abstraction.

---

## 7) Clarifying questions / what to capture next (required to finish transport)

1) **Janus signaling capture (must include WebSocket + SDP):**
   - Capture a browser session where the client *actually publishes or subscribes WebRTC media*.
   - Ensure the HAR includes the Janus gateway `wss://...` requests and SDP payloads.

2) **RTMPS ingest capture:**
   - Capture when the speaker path uses RTMPS (if any), including any `rtmps://` URLs, stream keys, and payload formats.

3) **Speaker approval state mapping:**
   - Capture the moment after `request/submit` when speaking becomes enabled (state transitions in `audiospace/call/status`).

4) **Host/create flow:**
   - Capture creating/hosting an AudioSpace if xspacekit will support broadcasting.

---

## Appendix: open questions

- ❓ What are the exact Janus plugin IDs / operations used for audiospaces?
- ❓ What are `session_state` code meanings?
- ❓ Which feature flags are required for `AudioSpaceById` to include speaking capability fields?
- ❓ Does HLS correspond only to listener mode, or also to speaker mode?
- ❓ Is RTMPS used at all for X Spaces audio transport, or only for internal transcoding/backup paths?
