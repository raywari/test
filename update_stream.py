import json
import urllib.request
import sys
import time

VIDEO_ID = "5c9327074e25ca86f3111d4085cbbb65"
OUTPUT_TXT_720 = "U-TV.txt"
OUTPUT_TXT_360 = "U-TV-360.txt"
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

def fetch_text(url: str, max_retries: int = 5, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            last_error = e
            print(f"Попытка {attempt}/{max_retries} для {url} не удалась: {e}", file=sys.stderr)
            if attempt < max_retries:
                sleep_time = attempt * 2
                print(f"Повтор через {sleep_time} сек...", file=sys.stderr)
                time.sleep(sleep_time)
    raise last_error

def build_m3u_entry(name_suffix: str, stream_url: str) -> str:
    display_name = f"{CHANNEL_META['name']} ({name_suffix})" if name_suffix else CHANNEL_META['name']
    return (
        f"#EXTINF:-1 tvg-id=\"{CHANNEL_META['tvg_id']}\" "
        f"tvg-name=\"{CHANNEL_META['tvg_name']}\" "
        f"tvg-logo=\"{CHANNEL_META['tvg_logo']}\" "
        f"group-title=\"{CHANNEL_META['group_title']}\","
        f"{display_name}\n"
        f"{stream_url}\n"
    )

def build_m3u_content(streams: dict) -> str:
    content = "#EXTM3U url-tvg=\"http://www.teleguide.info/download/new3/xmltv.xml.gz\"\n"
    if "720p" in streams:
        content += build_m3u_entry("720p", streams["720p"])
    if "360p" in streams:
        content += build_m3u_entry("360p", streams["360p"])
    return content

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

    # 3. Извлечение потоков (720p и 360p)
    stream_720p = None
    stream_360p = None

    for line in manifest_body.splitlines():
        line = line.strip()
        if "720p_stream.m3u8" in line and not stream_720p:
            stream_720p = line
        elif "360p_stream.m3u8" in line and not stream_360p:
            stream_360p = line

    if not stream_720p and not stream_360p:
        print("Ошибка: Ни один поток не найден в манифесте", file=sys.stderr)
        sys.exit(1)

    print(f"Найдена 720p ссылка:\n{stream_720p}")
    print(f"Найдена 360p ссылка:\n{stream_360p}")

    # 4. Запись текстовых файлов
    if stream_720p:
        with open(OUTPUT_TXT_720, "w", encoding="utf-8") as f:
            f.write(stream_720p + "\n")
        print(f"Успешно записано в {OUTPUT_TXT_720}")

    if stream_360p:
        with open(OUTPUT_TXT_360, "w", encoding="utf-8") as f:
            f.write(stream_360p + "\n")
        print(f"Успешно записано в {OUTPUT_TXT_360}")

    # 5. Запись playlist.m3u
    streams = {}
    if stream_720p:
        streams["720p"] = stream_720p
    if stream_360p:
        streams["360p"] = stream_360p

    m3u_content = build_m3u_content(streams)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print(f"Успешно записано в {OUTPUT_M3U}")

if __name__ == "__main__":
    main()
