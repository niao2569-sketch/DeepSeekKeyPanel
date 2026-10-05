import json, urllib.request, urllib.error

FAKE = "sk-00000000000000000000000000000000"


def call(url, method="GET", body=None, origin="null", extra=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + FAKE)
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")
    if origin:
        req.add_header("Origin", origin)
        if method == "OPTIONS":
            req.add_header("Access-Control-Request-Method", "POST")
            req.add_header("Access-Control-Request-Headers", "authorization,content-type")
    req.add_header("User-Agent", "Mozilla/5.0")
    for k, v in (extra or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, dict(r.headers), r.read(600).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), (e.read(600).decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return None, {}, str(e)


def show(tag, code, h, body):
    acao = h.get("Access-Control-Allow-Origin") or h.get("access-control-allow-origin")
    print(json.dumps({"case": tag, "status": code, "ACAO": acao, "body": body[:230]}, ensure_ascii=False))


print("--- 1. GET /models 是否可用于验证 Key 有效性 ---")
for o in ("null", None):
    show("models origin=" + str(o), *call("https://api.deepseek.com/models", origin=o))

print("\n--- 2. OPTIONS 预检 /models（浏览器直连是否可行）---")
show("models preflight", *call("https://api.deepseek.com/models", method="OPTIONS"))

print("\n--- 3. OPTIONS 预检 /chat/completions（真实调用测试是否可行）---")
show("chat preflight", *call("https://api.deepseek.com/chat/completions", method="OPTIONS"))

print("\n--- 4. POST /chat/completions 极小额（假 Key，看错误结构）---")
show("chat post", *call("https://api.deepseek.com/chat/completions", method="POST",
                        body={"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}],
                              "max_tokens": 1, "stream": False}))
