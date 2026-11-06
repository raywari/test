import json
import urllib.request
import sys

VIDEO_ID = "5c9327074e25ca86f3111d4085cbbb65"
OUTPUT_TXT = "U-TV.txt"
OUTPUT_M3U = "playlist.m3u"

CHANNEL_META = {
    "name": "Ю ТВ",
    "tvg_id": "u",
    "tvg_name": "Ю",
    "tvg_logo": "https://pic.rtbcdn.ru/user/aa/d1/aad18574ca01169022fd46514b0c69ed.jpg",
    "group_title": "Развлекательные",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": f"https://rutube.ru/play/embed/{VIDEO_ID}",
}

def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")

def build_m3u_content(stream_url: str) -> str:
    return (
        "#EXTM3U url-tvg=\"http://www.teleguide.info/download/new3/xmltv.xml.gz\"\n"
        f"#EXTINF:-1 tvg-id=\"{CHANNEL_META['tvg_id']}\" "
        f"tvg-name=\"{CHANNEL_META['tvg_name']}\" "
        f"tvg-logo=\"{CHANNEL_META['tvg_logo']}\" "
        f"group-title=\"{CHANNEL_META['group_title']}\","
        f"{CHANNEL_META['name']}\n"
        f"{stream_url}\n"
    )

def main():
    # 1. Запрос к API Rutube
    api_url = f"https://rutube.ru/api/play/options/{VIDEO_ID}/?format=json"
    print(f"Запрос API: {api_url}")
    
    api_raw = fetch_text(api_url)
    api_data = json.loads(api_raw)
    
    hls_streams = api_data.get("live_streams", {}).get("hls", [])
    if not hls_streams:
        print("Ошибка: В ответе API нет секции live_streams -> hls", file=sys.stderr)
        sys.exit(1)
        
    master_m3u8_url = hls_streams[0].get("url")
    print(f"Мастер-манифест: {master_m3u8_url}")

    # 2. Скачивание манифеста
    manifest_body = fetch_text(master_m3u8_url)

    # 3. Извлечение 720p потока
    stream_720p = None
    for line in manifest_body.splitlines():
        line = line.strip()
        if "720p_stream.m3u8" in line:
            stream_720p = line
            break

    if not stream_720p:
        print("Ошибка: Ссылка на 720p поток не найдена в манифесте", file=sys.stderr)
        sys.exit(1)

    print(f"Найдена 720p ссылка:\n{stream_720p}")

    # 4. Запись U-TV.txt
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(stream_720p + "\n")
    print(f"Успешно записано в {OUTPUT_TXT}")

    # 5. Запись playlist.m3u
    m3u_content = build_m3u_content(stream_720p)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print(f"Успешно записано в {OUTPUT_M3U}")

if __name__ == "__main__":
    main()
