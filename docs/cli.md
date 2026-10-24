---
title: "Command Line Interface (CLI)"
description: "Using the xspacekit CLI to listen to and speak in X Spaces."
---

# Command Line Interface (CLI)

`xspacekit` installs a convenient command-line tool `xspacekit`.

## Global Options

- `--cookie-file <path>`: Path to your `cookie.txt` file. Defaults to `$XSPACEKIT_COOKIE_FILE` or `./cookie.txt`.

---

## Subcommands

### `listen`

Listen to or inspect an X Space.

```bash
xspacekit listen --broadcast-id <BROADCAST_ID> [--poll]
```

**Options:**
- `--broadcast-id <id>`: X Space broadcast rest_id.
- `--query-id <id>`: GraphQL query ID for `AudioSpaceById`.
- `--m3u8 <url>`: Directly output an M3U8 playback URL.
- `--poll`: Poll occupancy call status (`audiospace/call/status`).

---

### `speak`

Attempt to speak / publish audio into an X Space.

```bash
xspacekit speak --broadcast-id <BROADCAST_ID> --live-audio --duration-s 10
```

**Options:**
- `--broadcast-id <id>`: X Space broadcast rest_id.
- `--live-audio`: Enable live WebRTC media streaming via `aiortc`.
- `--duration-s <float>`: Duration in seconds to stream live audio (default: `5.0`).
- `--har-file <path>`: Optional captured HAR file to replay static SDP/trickle signals.
- `--poll`: Poll occupancy during request/submit.
