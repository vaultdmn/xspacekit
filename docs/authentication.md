---
title: "Authentication & Bootstrap"
description: "How xspacekit handles X GraphQL and Periscope guest authorization chains."
---

# Authentication & Bootstrap

`xspacekit` bridges standard X web authentication (`auth_token` + `ct0`) with Periscope's guest and chat infrastructure (`proxsee-cf.pscp.tv`).

## The Authentication Chain

1. **X Session:** Uses standard X web credentials (`auth_token`, `ct0`, `guest_id`, and `Authorization: Bearer <X_BEARER>`) to access authenticated GraphQL endpoints like `AudioSpaceById`.
2. **Periscope Cookie Bootstrap:** Calls X GraphQL `AuthenticatePeriscope` to retrieve a pcp JWT, which is then exchanged via `loginTwitterToken` for a Periscope guest cookie (`atu` / `pscp_cookie`).
3. **Guest JWT Authorization:** Exchanges the pscp cookie via `authorizeToken` for a `GUEST_JWT` bearer token used by guest-cf endpoints (`audiospace/join`, `audiospace/request/submit`).
4. **Chat Token Derivation:** Automatically queries `live_video_stream/status/{media_key}` to retrieve a seed `chatToken`, then calls `accessChat` to convert it into a join-ready `access_token` (`chat_token`).

## Example Python Usage

```python
from xspacekit.config.cookie_loader import load_cookie_file
from xspacekit.core import build_flow_from_cookie_file
from xspacekit.periscope import bootstrap_periscope_pscp_cookie

# Load config from cookie.txt
cookie_cfg = load_cookie_file("cookie.txt")
flow = build_flow_from_cookie_file(cookie_cfg)

# Bootstrap Periscope pscp cookie
pscp_cookie = bootstrap_periscope_pscp_cookie(
    x_session=flow.x_session,
    guest_auth=flow.guest_auth,
)

# Obtain guest JWT for audiospace backend
guest_jwt = flow.guest_auth.authorize_token(atu_cookie=pscp_cookie)
print("Guest JWT obtained successfully!")
```
