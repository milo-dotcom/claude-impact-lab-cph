# ParkRefund iOS

SwiftUI client for the flow: photo → odds → appeal letter (you send it yourself). Talks to `api.py`.

## Run

```bash
# 1. backend (repo root). Mock mode without a key.
.venv/bin/python api.py                      # http://localhost:8000, ops page at /admin

# 2. app (needs Xcode on this Mac)
brew install xcodegen
cd ios && xcodegen && open ParkRefund.xcodeproj   # ⌘R on an iPhone simulator
```

Simulator reaches the Mac at `http://localhost:8000` (default). On a real phone, start the backend with
`HOST=0.0.0.0 .venv/bin/python api.py` and set the Mac's LAN IP in the "Server" field at the bottom of the
first screen. That opens the API (no login) to everyone on the Wi-Fi, so only do it on a network you trust.

Files: `Models.swift` mirrors the `claims.py` contract; `API.swift` is the client; one view per step.
