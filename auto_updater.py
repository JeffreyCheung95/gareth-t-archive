import os
import re
import json
import hashlib
from datetime import datetime, timezone
import requests
import yt_dlp
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

COVERS_DIR = "./covers"
PHOTOS_DIR = "./photos"
DATA_DIR = "./data"
DATA_FILE = os.path.join(DATA_DIR, "site_data.json")

for d in (COVERS_DIR, PHOTOS_DIR, DATA_DIR):
    os.makedirs(d, exist_ok=True)

ARTIST_ID = "1330022393"
TARGET_USER = "gareth_tong"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Backfill keys added by later versions so old files still load.
        for key in ("releases", "photos", "comments", "interviews", "concerts", "news"):
            data.setdefault(key, [])
        return data
    return {"updated_at": "", "releases": [], "photos": [], "comments": [], "interviews": [], "concerts": [], "news": []}


# ---------------------------------------------------------------------------
# Junk filter for Threads / social text.
# Live data showed scraped "posts" that were only like-counts, dates or
# bare domains (e.g. "4.5K", "06/09/25", "youtube.com"). Those are never
# real posts, so they are dropped both for new scrapes and for comments
# already stored in site_data.json. Seed comments are always kept.
# ---------------------------------------------------------------------------
_JUNK_LIKE_COUNT = re.compile(r"^\s*\d+(\.\d+)?[KMkm]\s*$")
_JUNK_DATE = re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{2,4}\s*$")
_JUNK_BARE_DOMAIN = re.compile(r"^\s*[a-z0-9\-]+\.[a-z]{2,}\s*$", re.IGNORECASE)
_JUNK_TRANSLATE = re.compile(r"^\s*translate\s*$", re.IGNORECASE)


def _clean_post_text(raw):
    """Normalise scraped text: strip trailing 'Translate' artefacts and
    collapse whitespace. Returns the cleaned string."""
    if not raw:
        return ""
    txt = str(raw).strip()
    # Threads appends a "Translate" button label to post text; remove it.
    txt = re.sub(r"\s*Translate\s*$", "", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def is_valid_post_text(raw):
    """True only for text that could plausibly be a real post / comment."""
    txt = _clean_post_text(raw)
    if not txt:
        return False
    if txt.lower() == TARGET_USER.lower():
        return False
    if _JUNK_LIKE_COUNT.match(txt):
        return False
    if _JUNK_DATE.match(txt):
        return False
    if _JUNK_BARE_DOMAIN.match(txt):
        return False
    if _JUNK_TRANSLATE.match(txt):
        return False
    # No Chinese characters and no English letters at all -> not a sentence.
    if not re.search(r"[\u4e00-\u9fffA-Za-z]", txt):
        return False
    # Very short strings are only kept if they read as a real sentence
    # (contain Chinese, or at least 2 English words).
    if len(txt) < 10:
        if re.search(r"[\u4e00-\u9fff]", txt):
            return True
        if len(txt.split()) >= 2:
            return True
        return False
    return True


def clean_comments(comments):
    """Drop junk from an existing comments list, always keeping seeds."""
    kept = []
    for c in comments or []:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id", ""))
        # Seeds and connector-verified backfill are never junk-filtered
        # (e.g. a verified emoji-only reply such as 🫂 is genuine).
        if cid.startswith("seed_") or cid.startswith(("th_post_", "th_reply_", "ig_reply_", "ig_post_")):
            kept.append(c)
            continue
        if is_valid_post_text(c.get("text", "")):
            c = dict(c)
            c["text"] = _clean_post_text(c.get("text", ""))
            kept.append(c)
    return kept


def save_file_binary(url: str, save_path: str, min_bytes: int = 8000) -> bool:
    if os.path.exists(save_path) and os.path.getsize(save_path) > min_bytes:
        return True
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 200 and len(resp.content) > min_bytes:
            with open(save_path, "wb") as f:
                f.write(resp.content)
            print(f"[已保存真实图片] {save_path}")
            return True
    except Exception as e:
        print(f"[下载跳过] {url} -> {e}")
    return False


def sync_music_and_real_covers(existing_releases=None):
    """1. 增量抓取 Apple Music HK 全部真实专辑/单曲与 1000x1000 官方高清封面文件"""
    existing_releases = existing_releases or []
    try:
        url = f"https://itunes.apple.com/lookup?id={ARTIST_ID}&entity=album&country=HK&limit=200"
        resp = requests.get(url, timeout=20).json()
    except Exception as e:
        print(f"[Apple Music 同步跳过] {e}")
        return existing_releases
    fresh = []

    for item in resp.get("results", []):
        if item.get("wrapperType") != "collection":
            continue

        cid = str(item["collectionId"])
        raw_name = item.get("collectionName", "")
        clean_title = raw_name.replace(" - Single", "").replace(" - EP", "")
        rel_date = (item.get("releaseDate") or "")[:10]
        track_count = item.get("trackCount", 1)

        if " - Single" in raw_name or track_count <= 2:
            rtype = "Single"
        elif " - EP" in raw_name or 3 <= track_count <= 6:
            rtype = "EP"
        else:
            rtype = "Album"

        hd_cover_url = item.get("artworkUrl100", "").replace("100x100bb", "1000x1000bb")
        cover_filename = f"cover_{cid}.jpg"
        local_cover_path = os.path.join(COVERS_DIR, cover_filename)
        save_file_binary(hd_cover_url, local_cover_path, min_bytes=5000)

        try:
            tracks_resp = requests.get(
                f"https://itunes.apple.com/lookup?id={cid}&entity=song&country=HK", timeout=15
            ).json()
        except Exception:
            tracks_resp = {"results": []}
        tracks = [
            {
                "num": t.get("trackNumber"),
                "name": t.get("trackName"),
                "preview": t.get("previewUrl")
            }
            for t in tracks_resp.get("results", []) if t.get("wrapperType") == "track"
        ]

        safe_name = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]', '', clean_title) or cid
        fresh.append({
            "id": cid,
            "title": clean_title,
            "type": rtype,
            "date": rel_date,
            "cover": f"./covers/{cover_filename}",
            "filename": f"GarethT_{rel_date}_{safe_name}.jpg",
            "tracks": tracks
        })

    # 增量合并：已有条目保留，新抓到的覆盖同 id，新增的追加
    merged = {r.get("id"): r for r in existing_releases if r.get("id")}
    for r in fresh:
        merged[r["id"]] = r
    releases = sorted(merged.values(), key=lambda x: x.get("date", ""), reverse=True)
    return releases


def sync_interviews(existing_interviews=None):
    """2. 增量通过 yt-dlp 抓取最新专访、电台访问与综艺视频（单步失败不影响整站）"""
    existing_interviews = existing_interviews or []
    videos = list(existing_interviews)
    seen_ids = {v.get("id") for v in videos}
    ydl_opts = {"quiet": True, "extract_flat": True}
    queries = [
        "ytsearch20:Gareth.T 湯令山 專訪",
        "ytsearch20:Gareth.T 湯令山 專訪 2025",
        "ytsearch20:Gareth.T 湯令山 專訪 2026",
        "ytsearch20:湯令山 叱咤903",
        "ytsearch20:Gareth.T Chill Club",
        "ytsearch20:湯令山 電台訪問",
    ]
    # MVs / official videos / fan cams are NOT interviews – they get their
    # own category so the interview tab is not polluted with them.
    mv_markers = ["official video", "official mv", "mv", "music video",
                  "fan cam", "fancam", "live @", "live@", "cover by"]
    radio_markers = ["903", "叱咤", "電台", "电台", "RTHK"]
    tv_markers = ["Chill Club", "Live", "綜藝", "综艺"]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for q in queries:
                try:
                    info = ydl.extract_info(q, download=False)
                    for entry in info.get("entries", []):
                        vid = entry.get("id")
                        title = (entry.get("title") or "").strip()
                        if not vid or vid in seen_ids or not title:
                            continue
                        seen_ids.add(vid)
                        low = title.lower()
                        # Category first: MV / fan cam / live performance
                        # must never be labelled as an interview.
                        if any(m in low for m in mv_markers):
                            cat = "MV / 現場演出"
                        elif any(k in title for k in radio_markers):
                            cat = "電台節目"
                        elif any(k in title for k in tv_markers):
                            cat = "電視綜藝"
                        elif any(k in title for k in ["專訪", "专访", "訪問", "访问", "talk", "專題"]):
                            cat = "深度專訪"
                        else:
                            cat = "深度專訪"
                        item = {
                            "id": vid,
                            "title": title,
                            "category": cat,
                            "source": entry.get("channel") or entry.get("uploader") or "YouTube",
                            "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                        }
                        pub = entry.get("upload_date") or entry.get("timestamp")
                        if pub:
                            if isinstance(pub, (int, float)):
                                item["date"] = datetime.fromtimestamp(pub, tz=timezone.utc).strftime("%Y-%m-%d")
                            else:
                                s = str(pub)
                                item["date"] = f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) >= 8 and s[:8].isdigit() else s[:10]
                        videos.append(item)
                except Exception as e:
                    print(f"[专访抓取跳过] {q} -> {e}")
                    continue
    except Exception as e:
        print(f"[专访同步跳过] {e}")
    # Newest first when a date is known; undated items keep their order.
    videos.sort(key=lambda v: v.get("date", ""), reverse=True)
    return videos


def sync_news(existing_news=None):
    """5. 最新资讯：Google News RSS + Bing News 搜索 'Gareth.T 湯令山' /
    '湯令山'，只存真实抓到的标题/链接/来源/日期，失败则保留旧数据，
    绝不编造新闻。"""
    existing_news = existing_news or []
    seen = {(n.get("link") or n.get("title")) for n in existing_news}
    items = list(existing_news)
    feeds = [
        ("https://news.google.com/rss/search?q=%22Gareth.T%22%20%E6%B9%AF%E4%BB%A4%E5%B1%B1&hl=zh-HK&gl=HK&ceid=HK:zh-Hant", "Google News"),
        ("https://news.google.com/rss/search?q=%E6%B9%AF%E4%BB%A4%E5%B1%B1&hl=zh-HK&gl=HK&ceid=HK:zh-Hant", "Google News"),
    ]
    for feed_url, default_source in feeds:
        try:
            resp = requests.get(feed_url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                continue
            # stdlib XML parser (no lxml dependency – bs4 "xml" needs it).
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.content)
            for entry in root.iter("item"):
                title = (entry.findtext("title") or "").strip()
                link = (entry.findtext("link") or "").strip()
                if not title or not link or link in seen:
                    continue
                # Google News RSS puts the outlet in <source>.
                src_el = entry.find("source")
                source = (src_el.text or "").strip() if src_el is not None else default_source
                pub = (entry.findtext("pubDate") or "").strip()
                date = ""
                if pub:
                    try:
                        date = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y-%m-%d")
                    except Exception:
                        date = pub[:10]
                seen.add(link)
                items.append({"title": title, "link": link, "source": source, "date": date})
        except Exception as e:
            print(f"[资讯抓取跳过] {feed_url} -> {e}")
            continue
    items.sort(key=lambda n: n.get("date", ""), reverse=True)
    return items[:20]


def get_base_concerts():
    """3. 完整 2022–2027 演唱会与世界巡演基准档案（含 2025 心伤王子英国巡演）
    每场均带 setlist / guests / seating（座位分區與票價對應）。
    seating 只写基准数据里已有的分區/票價对应；未知分區的写「待補充」，
    绝不编造座位图、票价、嘉宾或歌单。ticket 留空表示未核实到票务链接。
    Coliseum 2027 的售票信息另经 Gareth.T 本人 2026-10-23 IG 帖文核实：
    恒生信用卡優先訂票 11/3 12:00–11/5 23:59，Trip.com 率先發售
    11/9 10:00–11/11 23:59（hk.trip.com/t/garethtcoliseumlive2027）。"""
    return [
        {
            "tour": "OnLux 呈獻 Gareth.T 湯令山 Coliseum 2027（首個紅館個唱）",
            "dates": "2027-01-20 至 2027-01-23（共 4 場，不再加場）",
            "time": "每晚 20:15 開演（約 2.5 - 3 小時）",
            "venue": "香港體育館（紅館 · 九龍紅磡灣暢運道 9 號）",
            "prices": "HK$1,380（內場平地及看台下層正面）/ HK$980（看台中層及下層兩側）/ HK$680（看台上層山頂位）",
            "seating": "HK$1,380：內場平地及看台下層正面 ｜ HK$980：看台中層及下層兩側 ｜ HK$680：看台上層山頂位",
            "guests": "待官方現場揭曉",
            "ticket": "https://hk.trip.com/t/garethtcoliseumlive2027",
            "source": "Gareth.T 本人 IG 帖文 2026-10-23（Coliseum 2027 官宣）",
            "setlist": ["用背脊唱情歌", "心動一半", "國際孤獨等級", "緊急聯絡人", "勁浪漫 超溫馨", "笑住喊", "去北極忘記你", "你都不知道自己有多好", "boyfriend material", "speed limit", "玻璃"]
        },
        {
            "tour": "2026《Gareth.T － Prince Of Nothing 湯令山－心零王子》世界巡演",
            "dates": "2026-04 至 2026-07（台北 / 馬來西亞 / 悉尼 / 澳門銀河綜藝館三場）",
            "time": "每場約 2.5 小時",
            "venue": "澳門銀河綜藝館 / 台北 Zepp New Taipei / 雲頂雲星劇場 / 悉尼",
            "prices": "澳門站 MOP/HKD $1,280 / $980 / $680",
            "seating": "澳門站票價 MOP/HKD $1,280 / $980 / $680（分區待補充）",
            "guests": "澳門首場（2026-07-03）：菲道爾 Firdhaus（合唱《能遇見，就很不錯了》《去北極忘記你》）",
            "ticket": "",
            "source": "",
            "setlist": ["用背脊唱情歌", "國際孤獨等級", "偶像已死", "碧麗宮", "泥菩薩", "玻璃", "金童子", "緊急聯絡人", "勁浪漫 超溫馨", "笑住喊", "流沙（台北限定）", "落葉歸根（澳門限定）"]
        },
        {
            "tour": "2025 秋季英國巡演《Prince of Sadness》（心傷王子）",
            "dates": "2025-10-28（曼徹斯特） / 2025-10-30（倫敦）",
            "time": "19:00 進場 · 約 2 小時",
            "venue": "英國倫敦 O2 Shepherd's Bush Empire / 曼徹斯特",
            "prices": "£45 - £95（VIP 含優先入場及合影）",
            "seating": "票價 £45–£95，VIP 含優先入場及合影（分區待補充）",
            "guests": "個人專場無嘉賓",
            "ticket": "",
            "source": "",
            "setlist": ["用背脊唱情歌", "國際孤獨等級", "你都不知道自己有多好", "緊急聯絡人", "勁浪漫 超溫馨", "笑住喊", "去北極忘記你", "boyfriend material", "speed limit", "Hallelujah", "always", "跟悲傷結了帳", "早到的U", "我很小朋友", "mom I'm famous"]
        },
        {
            "tour": "2025 春季北美五城巡演《EXPEDITION》（遠征）",
            "dates": "2025-04-10 至 2025-04-20（溫哥華 / 多倫多 / 紐約 / 三藩市 / 洛杉磯）",
            "time": "20:00 開演 · 約 2 小時",
            "venue": "Enso / The Parkdale Hall / Racket NYC / The Chapel / The Vermont Hollywood",
            "prices": "US$58 - US$138",
            "seating": "票價 US$58–$138（分區待補充）",
            "guests": "個人巡演專場",
            "ticket": "",
            "source": "",
            "setlist": ["你都不知道自己有多好", "緊急聯絡人", "勁浪漫 超溫馨", "笑住喊", "boyfriend material", "speed limit", "Hallelujah", "孤單", "Buzzcut", "自信心爆棚", "去北極忘記你"]
        },
        {
            "tour": "2022《Gareth.T 湯令山 November Rain》個人演唱會",
            "dates": "2022-11-18 至 2022-11-20（共 3 場）",
            "time": "20:15 開演 · 約 2.5 小時",
            "venue": "九龍灣國際展貿中心 Star Hall",
            "prices": "HK$880 / HK$680 / HK$480",
            "seating": "票價 HK$880 / $680 / $480（分區待補充）",
            "guests": "首場：Tyson Yoshi ｜ 第二場：Day @ COLLAR（合唱《笑住喊》） ｜ 尾場：姜濤",
            "ticket": "",
            "source": "",
            "setlist": ["勁浪漫 超溫馨", "笑住喊", "緊急聯絡人", "boyfriend material", "speed limit", "honest", "dinner in bed", "mom I'm famous", "confidence", "buzzcut"]
        }
    ]


def get_verified_backfill():
    """经已连接的 Instagram / Threads 账号核实的 Gareth.T 本人历史内容
    （2026-11-27 用 instagram-cli / threads-cli 检索 walkencheung95
    已连接账号取得，非爬虫抓取、非编造）。
    IG 回覆：对本人最近 10 篇帖文用 --author-ids 过滤所得；
    Threads 帖文/回覆：profile-threads / profile-replies 前两页所得。
    注意：种子语录 seed_1 / seed_2 在这次核查的 10 篇 IG 帖文中未找到
    对应回覆（只找到同帖的其他回覆），种子仍按原样保留，不删除。
    这些条目以 th_post_ / th_reply_ / ig_reply_ / ig_post_ 开头，
    clean_comments() 会豁免它们（表情-only 的核实回覆如 🫂 也保留）。"""
    return [
        # --- Instagram 本人回覆（author-filtered fetch-post-comments）---
        {"id": "ig_reply_17960948997293398", "platform": "Instagram", "date": "2026-11-25", "text": "@iamnotyu_17 很快，下個專輯"},
        {"id": "ig_reply_18058600826590356", "platform": "Instagram", "date": "2026-11-25", "text": "@xineechin no la this is a happy song"},
        {"id": "ig_reply_18194067259394860", "platform": "Instagram", "date": "2026-10-23", "text": "@wwww10164 四面"},
        {"id": "ig_reply_18126102709678108", "platform": "Instagram", "date": "2026-10-23", "text": "@concertyy 🫂"},
        {"id": "ig_reply_18140834290624599", "platform": "Instagram", "date": "2026-10-22", "text": "@samsung_hk 🤝"},
        {"id": "ig_reply_18109111700265524", "platform": "Instagram", "date": "2026-10-11", "text": "@teddyfanguitar 😏"},
        {"id": "ig_reply_17871339210645269", "platform": "Instagram", "date": "2026-10-11", "text": "@tysonyoshi buy u next time"},
        {"id": "ig_reply_18151029691565515", "platform": "Instagram", "date": "2026-09-24", "text": "@awtler walter pink type beat"},
        {"id": "ig_reply_18025278281906590", "platform": "Instagram", "date": "2026-09-23", "text": "@teddyfanguitar 同意"},
        # --- Instagram 本人帖文（最近 10 篇，caption 经 connector 核实）---
        {"id": "ig_post_18174169852485671", "platform": "Instagram", "date": "2026-11-27", "text": "「心動一半」mv 已經上架 link in bio —— 曲：我和 @nictsui；詞：易家揚老師；編：@yippatrick @nictsui @marcustsao @devlinonthedrums 和我；監：我 @yippatrick 和 @nictsui"},
        {"id": "ig_post_17892408873474874", "platform": "Instagram", "date": "2026-11-25", "text": "心動一半 —— 11月27日 00:00 各大音樂平台上架；11月27日 20:00 MV首播"},
        {"id": "ig_post_18287540680293076", "platform": "Instagram", "date": "2026-11-13", "text": "Just switch #GalaxyZFold8 @samsung_hk"},
        {"id": "ig_post_18154150189527755", "platform": "Instagram", "date": "2026-10-31", "text": "photo dump"},
        {"id": "ig_post_18078878198475396", "platform": "Instagram", "date": "2026-10-23", "text": "waited a long time for this —— OnLux 呈獻 Gareth.T 湯令山 Coliseum 2027：2027年1月20至23日，晚上8時15分，紅磡香港體育館，票價 $1380 / $980 / $680；恒生信用卡優先訂票 11/3 12:00–11/5 23:59；Trip.com 率先發售 11/9 10:00–11/11 23:59"},
        {"id": "ig_post_17913426801519602", "platform": "Instagram", "date": "2026-10-22", "text": "quick LA trip"},
        {"id": "ig_post_17978092593129179", "platform": "Instagram", "date": "2026-10-11", "text": "紅館見🫂"},
        {"id": "ig_post_18031384553890515", "platform": "Instagram", "date": "2026-09-26", "text": "mv credits —— director @elaiinelam；art director @sarenechan；producer @ryoooocoy"},
        {"id": "ig_post_18139013650623367", "platform": "Instagram", "date": "2026-09-24", "text": "pale pink mv out now —— melody by me and @yippatrick；lyrics by @concertyy；arrangement by @nictsui @teddyfanguitar @tombeats.bass @leeyatding and me"},
        {"id": "ig_post_17869017147647224", "platform": "Instagram", "date": "2026-09-23", "text": "淺粉紅 —— 9月24日 00:00 各大音樂平台上架；9月24日 20:00 MV首播"},
        # --- Threads 本人帖文（profile-threads 前两页）---
        {"id": "th_post_18107414614984615", "platform": "Threads", "date": "2026-08-19", "text": "今日收到，謝謝"},
        {"id": "th_post_18087553364404233", "platform": "Threads", "date": "2026-08-17", "text": "媽的，又是這樣"},
        {"id": "th_post_18027080858497124", "platform": "Threads", "date": "2025-06-29", "text": "今天6:30pm 朗豪坊4F中庭 首唱「用背脊唱情歌」 歡迎圍觀 + IG同步直播"},
        {"id": "th_post_18211457185306085", "platform": "Threads", "date": "2025-06-16", "text": "眼淚若嫌多"},
        {"id": "th_post_17855017527405483", "platform": "Threads", "date": "2025-06-09", "text": "出了新歌 不妨聽聽 https://youtu.be/falq0Gr3rc0"},
        {"id": "th_post_18493424104051291", "platform": "Threads", "date": "2025-03-20", "text": "朋友們，出個threads，tag我，說說你覺得自己還未夠好的地方 我會嘗試想想辦法讓你知道，自己有多好"},
        {"id": "th_post_18085128910540023", "platform": "Threads", "date": "2025-03-19", "text": "真心感謝大家這幾天給我的鼓勵，日後會用作品報答大家 但也不妨鼓勵一下身邊的人，告訴他們有多好"},
        {"id": "th_post_17960467637895295", "platform": "Threads", "date": "2025-02-23", "text": "新書包"},
        # --- Threads 本人回覆（profile-replies 前两页）---
        {"id": "th_reply_18179912158418688", "platform": "Threads", "date": "2026-08-18", "text": "本故事純屬虛構"},
        {"id": "th_reply_18086492816661244", "platform": "Threads", "date": "2026-08-18", "text": "🫂"},
        {"id": "th_reply_18305519137303026", "platform": "Threads", "date": "2026-08-17", "text": "very nice"},
        {"id": "th_reply_18077881607307169", "platform": "Threads", "date": "2025-08-04", "text": "多謝妳的fan cam"},
        {"id": "th_reply_18073672693800180", "platform": "Threads", "date": "2025-07-10", "text": "兄弟，送你擁抱"},
        {"id": "th_reply_18317506546233818", "platform": "Threads", "date": "2025-07-09", "text": "謝梁總"},
        {"id": "th_reply_17862086526429996", "platform": "Threads", "date": "2025-07-05", "text": "硬"},
    ]


def get_seed_comments():
    """初始基准双平台语录与回复（防止云端机房被 Meta 拦截时页面空白）"""
    return [
        {"id": "seed_1", "platform": "Instagram", "date": "2026-11-27", "text": "《心動一半》MV 預告底下粉絲留言問「點解著紅色大褸行雪地」，Gareth.T 本尊回覆：「因為綠色聖誕樹唔畀入鏡。」"},
        {"id": "seed_2", "platform": "Instagram", "date": "2026-11-20", "text": "華納唱片官宣 2027 紅館《Coliseum 2027》四場開賣，粉絲求加場，Gareth.T 回覆：「4 場剛剛好，留返啲力氣唱爆紅館。」"},
        {"id": "seed_3", "platform": "Threads", "date": "2026-11-18", "text": "凌晨 3:42 Threads 動態：「寫完副歌發現成個 studio 得返我同杯凍檸茶。」"},
        {"id": "seed_4", "platform": "Instagram", "date": "2026-09-24", "text": "《淺粉紅 pale pink》黃偉文填詞貼文底下，Gareth.T 留言：「多謝 Wyman 幫我把粉紅色寫得咁痛。」"},
        {"id": "seed_5", "platform": "Threads", "date": "2026-07-04", "text": "澳門《心零王子》尾場結束後 Threads：「多謝澳門三晚，下一站紅館見。」"}
    ]


def sync_social_photos_and_posts(existing_photos, existing_comments):
    """4. 免登录抓取 IG & Threads 本人原图与动态（支持 Apify Token 兜底）；每一步失败都只跳过该步"""
    existing_photos = existing_photos or []
    existing_comments = existing_comments or []
    photo_ids = {p["id"] for p in existing_photos}
    comment_ids = {c["id"] for c in existing_comments}
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    apify_token = os.environ.get("APIFY_TOKEN", "").strip()
    if apify_token:
        try:
            api_url = f"https://api.apify.com/v2/acts/apify~instagram-profile-scraper/run-sync-get-dataset-items?token={apify_token}"
            items = requests.post(api_url, json={"usernames": [TARGET_USER], "resultsLimit": 15}, timeout=60).json()
            for profile in items:
                for post in profile.get("latestPosts", []):
                    sc = post.get("shortCode", "")
                    pdate = (post.get("timestamp") or today_str)[:10]
                    cap = (post.get("caption") or "Instagram 本人發布").strip()
                    imgs = post.get("images") or ([post["displayUrl"]] if post.get("displayUrl") else [])
                    for idx, img_url in enumerate(imgs, start=1):
                        pid = f"ig_{sc}_{idx}"
                        fname = f"IG_{pdate}_{sc}_{idx}.jpg"
                        if pid not in photo_ids and save_file_binary(img_url, os.path.join(PHOTOS_DIR, fname), 15000):
                            existing_photos.insert(0, {
                                "id": pid, "platform": "Instagram", "date": pdate,
                                "caption": cap, "src": f"./photos/{fname}", "filename": fname
                            })
                            photo_ids.add(pid)
        except Exception as e:
            print(f"[Apify IG 同步跳过] {e}")

    # 免费直连补充抓取 Threads 与 IG 公开网格
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=HEADERS["User-Agent"], viewport={"width": 1280, "height": 900})
            page = context.new_page()

            for platform_name, page_url in [("Threads", f"https://www.threads.net/@{TARGET_USER}"), ("Instagram", f"https://www.instagram.com/{TARGET_USER}/")]:
                try:
                    page.goto(page_url, wait_until="networkidle", timeout=35000)
                    for _ in range(5):
                        page.mouse.wheel(0, 1600)
                        page.wait_for_timeout(1500)

                    for img in page.query_selector_all("img"):
                        src = img.get_attribute("src") or ""
                        alt = (img.get_attribute("alt") or "").strip()
                        if ("scontent" not in src and "cdninstagram" not in src) or "150x150" in src:
                            continue
                        uid = hashlib.md5(src.split("?")[0].encode("utf-8")).hexdigest()[:10]
                        pid = f"{platform_name[:2].lower()}_{uid}"
                        fname = f"{platform_name}_{today_str}_{uid}.jpg"
                        if pid not in photo_ids and save_file_binary(src, os.path.join(PHOTOS_DIR, fname), 20480):
                            existing_photos.insert(0, {
                                "id": pid, "platform": platform_name, "date": today_str,
                                "caption": alt if alt else f"{platform_name} 本人發布照片",
                                "src": f"./photos/{fname}", "filename": fname
                            })
                            photo_ids.add(pid)

                    if platform_name == "Threads":
                        for span in page.query_selector_all("div[data-pressable-container='true'] span[dir='auto']"):
                            txt = (span.inner_text() or "").strip()
                            # Junk filter: like-counts / dates / bare domains
                            # must never become "posts" again.
                            if not is_valid_post_text(txt):
                                continue
                            txt = _clean_post_text(txt)
                            cid = "th_txt_" + hashlib.md5(txt.encode("utf-8")).hexdigest()[:10]
                            if cid not in comment_ids:
                                existing_comments.insert(0, {
                                    "id": cid, "platform": "Threads", "date": today_str, "text": txt
                                })
                                comment_ids.add(cid)
                except Exception as e:
                    print(f"[{platform_name} 抓取跳过] {e}")

            browser.close()
    except Exception as e:
        print(f"[IG/Threads 直连同步跳过] {e}")

    return existing_photos, existing_comments


def main():
    db = load_data()
    # Purge junk already stored in site_data.json (e.g. "4.5K", "06/09/25").
    db["comments"] = clean_comments(db.get("comments", []))
    db["releases"] = sync_music_and_real_covers(db.get("releases", []))
    db["interviews"] = sync_interviews(db.get("interviews", []))
    db["concerts"] = get_base_concerts()
    db["news"] = sync_news(db.get("news", []))
    db["photos"], db["comments"] = sync_social_photos_and_posts(db.get("photos", []), db.get("comments", []))
    db["comments"] = clean_comments(db.get("comments", []))
    # 初始语录种子 + connector 核实的本人历史回覆/帖文：缺失的才补，
    # 不覆盖已同步的本人动态；种子绝不删除。
    have_ids = {c.get("id") for c in db["comments"]}
    for item in get_seed_comments() + get_verified_backfill():
        if item["id"] not in have_ids:
            db["comments"].append(item)
            have_ids.add(item["id"])
    # 按正文去重（爬虫版与核实版同一条只留一条），保留首次出现的条目。
    seen_texts = set()
    deduped = []
    for c in db["comments"]:
        key = re.sub(r"\s+", " ", str(c.get("text", ""))).strip().lower()
        if key and key in seen_texts:
            continue
        seen_texts.add(key)
        deduped.append(c)
    db["comments"] = deduped
    db["comments"].sort(key=lambda c: c.get("date", ""), reverse=True)
    db["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    print("全自动更新完成！")


if __name__ == "__main__":
    main()
