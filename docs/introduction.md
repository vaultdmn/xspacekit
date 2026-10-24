---
title: "Introduction"
description: "Unofficial Python SDK and CLI for X Spaces audio, built via network reverse-engineering."
---

# Introduction to xspacekit

`xspacekit` is a powerful, unofficial Python SDK and CLI designed for interacting with **X Spaces audio**. It provides clean abstractions for authentication, metadata fetching, HLS stream discovery, Janus WebRTC gateway signaling, and live Opus audio publishing (`aiortc`).

## Key Features

- **Automated Periscope & X Auth:** Seamlessly bootstrap guest authorization tokens, login tokens, and chat tokens (`accessChat`) from your standard X web session cookies (`auth_token`, `ct0`).
- **Space Lifecycle Management:** Fetch space metadata (`AudioSpaceById`), resolve stream `media_key`s, join spaces as a listener, and poll guest session call status and occupancy in real-time.
- **Janus WebRTC Gateway Signaling:** Full support for Janus videoroom plugin message sequencing (`join`, `configure`, `start`, and ICE `trickle`) over HTTP long-polling.
- **Live End-to-End Audio Publishing (`aiortc`):** Dynamically generate WebRTC SDP offers, gather local ICE candidates, complete DTLS-SRTP handshakes, and stream Opus audio packets directly into an X Space.
- **Command Line Interface (CLI):** Ready-to-use commands for listening (`xspacekit listen`) and speaking (`xspacekit speak`) with automatic token derivation.
