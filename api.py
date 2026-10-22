"""ParkRefund HTTP API for the iOS app, plus a tiny ops page at /admin.

Stdlib only (CLAUDE.md: no new frameworks). Wraps claims.py; mock mode when no key.
    .venv/bin/python api.py                  # http://localhost:8000, this Mac only
    HOST=0.0.0.0 .venv/bin/python api.py     # also reachable from a phone on the same Wi-Fi (no auth!)
Off 127.0.0.1 the .env key and --chatgpt are refused unless PARKREFUND_SHARE_SERVER_KEY=1 (then capped per hour).
"""
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import claims

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "data", "claims_store.json")  # submissions from the app; synthetic only
STATUSES = ["new", "review", "filed", "won", "lost", "rejected"]


def _load():
    return json.load(open(STORE, encoding="utf-8")) if os.path.exists(STORE) else []


def _save(rows):
    json.dump(rows, open(STORE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


ADMIN_HTML = """<!doctype html><meta charset=utf-8><title>ParkRefund ops</title>
<style>body{font:15px system-ui;margin:24px;max-width:1100px}table{border-collapse:collapse;width:100%}
td,th{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}
.strong{color:#15803d}.medium{color:#b45309}.weak{color:#b91c1c}select{font:inherit}</style>
<h1>ParkRefund ops <small id=mode></small></h1>
<p>Submissions from the iOS app. Model recommends; a human files. Review band = 40–60 %.</p>
<table><thead><tr><th>When<th>Ticket<th>Issuer<th>DKK<th>Odds<th>Top ground<th>Status</thead><tbody id=rows></tbody></table>
<script>
// Claims and assessments come from POST /claims, so every value is escaped before it touches innerHTML.
const e=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
async function load(){
 const r=await fetch('/claims');const d=await r.json();
 document.getElementById('mode').textContent=d.live?'(live)':'(mock)';
 document.getElementById('rows').innerHTML=d.items.map(x=>{
  const a=x.assessment||{},c=x.claim||{},g=(a.grounds||[])[0];
  const opts=__STATUSES__.map(s=>`<option ${s===x.status?'selected':''}>${s}</option>`).join('');
  const band=a.success_probability>=40&&a.success_probability<=60?' ⚠︎ review':'';
  return `<tr><td>${e(x.created.slice(0,16).replace('T',' '))}<td>${e(c.ticket_number)}<td>${e(c.issuer_name)}<td>${e(c.amount_dkk)}
  <td class="${e(a.verdict)}">${e(a.success_probability)}% ${e(a.verdict)}${band}<td>${e(g&&g.title)}
  <td><select onchange="setStatus('${e(x.id)}',this.value)">${opts}</select></tr>`}).join('');
}
async function setStatus(id,s){await fetch('/claims/'+id+'/status',{method:'POST',body:JSON.stringify({status:s})});load();}
load();
</script>""".replace("__STATUSES__", json.dumps(STATUSES))


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def log_message(self, fmt, *args):  # one quiet line per request
        print(self.command, self.path, args[1] if len(args) > 1 else "")

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/health":
            return self._send(200, {"ok": True, "live": claims.is_live()})
        if u.path == "/cases":
            return self._send(200, json.load(open(os.path.join(HERE, "data", "sample_cases.json"), encoding="utf-8")))
        if u.path == "/payout":
            amt = int(parse_qs(u.query).get("amount", ["0"])[0])
            return self._send(200, claims.payout(amt))
        if u.path == "/claims":
            return self._send(200, {"live": claims.is_live(), "items": sorted(_load(), key=lambda r: r["created"], reverse=True)})
        if u.path in ("/", "/admin"):
            return self._send(200, ADMIN_HTML, "text/html")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        try:
            body = self._json()
            if u.path == "/assess":
                return self._send(200, claims.assess_claim(body))
            if u.path == "/draft":
                return self._send(200, {"letter": claims.draft_appeal(body["claim"], body["assessment"], body.get("language", "da"))})
            if u.path == "/extract":
                import base64
                return self._send(200, claims.extract_ticket(base64.b64decode(body["image_base64"]), body.get("media_type", "image/jpeg")))
            if u.path == "/claims":  # app submits a claim + its assessment for the ops queue
                rows = _load()
                row = {"id": uuid.uuid4().hex[:8], "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "status": "new", "claim": body["claim"], "assessment": body["assessment"]}
                rows.append(row)
                _save(rows)
                return self._send(201, row)
            if u.path.startswith("/claims/") and u.path.endswith("/status"):
                cid, status = u.path.split("/")[2], body.get("status")
                if status not in STATUSES:
                    return self._send(400, {"error": f"status must be one of {STATUSES}"})
                rows = _load()
                for r in rows:
                    if r["id"] == cid:
                        r["status"] = status
                        _save(rows)
                        return self._send(200, r)
                return self._send(404, {"error": "no such claim"})
            self._send(404, {"error": "not found"})
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            self._send(400, {"error": f"bad request: {e}"})
        except RuntimeError as e:  # claims.py wraps API failures in RuntimeError
            self._send(502, {"error": str(e)})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "127.0.0.1")  # no auth, so only open to the network on purpose
    shared_ok = claims.guard_server_credentials(host in claims.LOOPBACK)  # no .env key for strangers on the Wi-Fi
    if "--chatgpt" in sys.argv:  # run on the operator's ChatGPT plan; signs out when the server stops
        if not shared_ok:
            sys.exit(f"Refusing --chatgpt on HOST={host}: everyone who can reach this server would use your ChatGPT plan. "
                     "Use HOST=127.0.0.1, or set PARKREFUND_SHARE_SERVER_KEY=1 to share it (capped per hour).")
        import chatgpt
        chatgpt.login()
    print(f"ParkRefund API on http://{host}:{port}  mode={'LIVE' if claims.is_live() else 'MOCK'}  ops: /admin")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
