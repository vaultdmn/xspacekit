---
title: "Quickstart"
description: "Get up and running with xspacekit in under 2 minutes."
---

# Quickstart

## Installation

Install `xspacekit` from source or PyPI with WebRTC support (`aiortc`):

```bash
pip install xspacekit
```

Or install in editable mode with development dependencies:

```bash
pip install -e .[dev]
```

---

## Configuration (`cookie.txt`)

Create a `cookie.txt` file in your working directory containing your X web session cookies and optional broadcast defaults:

```ini
auth_token=<YOUR_X_AUTH_TOKEN>
ct0=<YOUR_X_CT0_TOKEN>
guest_id=<YOUR_GUEST_ID>
x_bearer=AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7xxfk8pu5TWIMqonantSQSzPSps9pAiFRKRcexQ
broadcast_id=1dJrPrXonkqKX
query_id=bpQedjCUnMgs3yXNi8fZlA
```

---

## CLI Usage

### 1. Listen to a Space (HLS Stream Discovery)

```bash
xspacekit listen --broadcast-id 1dJrPrXonkqKX --poll
```

### 2. Speak in a Space (Live WebRTC Audio)

```bash
xspacekit speak --broadcast-id 1dJrPrXonkqKX --live-audio --duration-s 10
```
