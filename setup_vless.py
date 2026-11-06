import os
import sys
import json
import urllib.parse

def main():
    vless_uri = os.environ.get("VLESS_URI", "").strip()
    if not vless_uri:
        print("VLESS_URI is not set", file=sys.stderr)
        sys.exit(1)

    parsed = urllib.parse.urlparse(vless_uri)
    if parsed.scheme != "vless":
        print(f"Error: expected vless://, got {parsed.scheme}://", file=sys.stderr)
        sys.exit(1)

    uuid = parsed.username
    host = parsed.hostname
    port = parsed.port or 443
    qs = urllib.parse.parse_qs(parsed.query)

    security = qs.get("security", ["tls"])[0]
    flow = qs.get("flow", [""])[0]
    sni = qs.get("sni", [host])[0]
    fp = qs.get("fp", ["chrome"])[0]
    network = qs.get("type", ["tcp"])[0]
    alpn_str = qs.get("alpn", [""])[0]
    alpn = [x.strip() for x in alpn_str.split(",") if x.strip()]

    tls_settings = {
        "serverName": sni,
        "fingerprint": fp
    }
    if alpn:
        tls_settings["alpn"] = alpn

    stream_settings = {
        "network": network,
        "security": security,
    }
    if security == "tls":
        stream_settings["tlsSettings"] = tls_settings
    elif security == "reality":
        stream_settings["realitySettings"] = {
            "serverName": sni,
            "fingerprint": fp,
            "publicKey": qs.get("pbk", [""])[0],
            "shortId": qs.get("sid", [""])[0],
            "spiderX": qs.get("spx", [""])[0]
        }

    user_obj = {
        "id": uuid,
        "encryption": qs.get("encryption", ["none"])[0]
    }
    if flow:
        user_obj["flow"] = flow

    config = {
        "log": {
            "loglevel": "warning"
        },
        "inbounds": [
            {
                "port": 10808,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {
                    "auth": "noauth",
                    "udp": True
                }
            },
            {
                "port": 10809,
                "listen": "127.0.0.1",
                "protocol": "http",
                "settings": {}
            }
        ],
        "outbounds": [
            {
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {
                            "address": host,
                            "port": port,
                            "users": [user_obj]
                        }
                    ]
                },
                "streamSettings": stream_settings
            }
        ]
    }

    # Mask host and SNI in GitHub Actions logs if running in CI
    if os.environ.get("GITHUB_ACTIONS") == "true":
        if host:
            print(f"::add-mask::{host}")
        if sni and sni != host:
            print(f"::add-mask::{sni}")

    out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/xray_config.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print("Xray config generated successfully.")

if __name__ == "__main__":
    main()
