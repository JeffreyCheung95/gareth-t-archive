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
            return json.load(f)
    return {"updated_at": "", "releases": [], "photos": [], "comments": [], "interviews": [], "concerts": []}


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
        "ytsearch15:Gareth.T 叱咤903 Chill Club"
    ]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for q in queries:
                try:
                    info = ydl.extract_info(q, download=False)
                    for entry in info.get("entries", []):
                        vid = entry.get("id")
                        title = entry.get("title", "")
                        if not vid or vid in seen_ids:
                            continue
                        seen_ids.add(vid)
                        cat = "深度專訪"
                        if any(k in title for k in ["903", "叱咤", "電台", "电台", "RTHK"]):
                            cat = "電台節目"
                        elif any(k in title for k in ["Chill Club", "Live", "綜藝", "综艺"]):
                            cat = "電視綜藝"
                        videos.append({
                            "id": vid,
                            "title": title,
                            "category": cat,
                            "source": entry.get("channel") or entry.get("uploader") or "YouTube",
                            "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                        })
                except Exception as e:
                    print(f"[专访抓取跳过] {q} -> {e}")
                    continue
    except Exception as e:
        print(f"[专访同步跳过] {e}")
    return videos


def get_base_concerts():
    """3. 完整 2022–2027 演唱会与世界巡演基准档案（含 2025 心伤王子英国巡演）"""
    return [
        {
            "tour": "OnLux 呈獻 Gareth.T 湯令山 Coliseum 2027（首個紅館個唱）",
            "dates": "2027-01-20 至 2027-01-23（共 4 場，不再加場）",
            "time": "每晚 20:15 開演（約 2.5 - 3 小時）",
            "venue": "香港體育館（紅館 · 九龍紅磡灣暢運道 9 號）",
            "prices": "HK$1,380（內場平地及看台下層正面）/ HK$980（看台中層及下層兩側）/ HK$680（看台上層山頂位）",
            "guests": "待官方現場揭曉",
            "setlist": ["用背脊唱情歌", "心動一半", "國際孤獨等級", "緊急聯絡人", "勁浪漫 超溫馨", "笑住喊", "去北極忘記你", "你都不知道自己有多好", "boyfriend material", "speed limit", "玻璃"]
        },
        {
            "tour": "2026《Gareth.T － Prince Of Nothing 湯令山－心零王子》世界巡演",
            "dates": "2026-04 至 2026-07（台北 / 馬來西亞 / 悉尼 / 澳門銀河綜藝館三場）",
            "time": "每場約 2.5 小時",
            "venue": "澳門銀河綜藝館 / 台北 Zepp New Taipei / 雲頂雲星劇場 / 悉尼",
            "prices": "澳門站 MOP/HKD $1,280 / $980 / $680",
            "guests": "澳門首場（2026-07-03）：菲道爾 Firdhaus（合唱《能遇見，就很不錯了》《去北極忘記你》）",
            "setlist": ["用背脊唱情歌", "國際孤獨等級", "偶像已死", "碧麗宮", "泥菩薩", "玻璃", "金童子", "緊急聯絡人", "勁浪漫 超溫馨", "笑住喊", "流沙（台北限定）", "落葉歸根（澳門限定）"]
        },
        {
            "tour": "2025 秋季英國巡演《Prince of Sadness》（心傷王子）",
            "dates": "2025-10-28（曼徹斯特） / 2025-10-30（倫敦）",
            "time": "19:00 進場 · 約 2 小時",
            "venue": "英國倫敦 O2 Shepherd's Bush Empire / 曼徹斯特",
            "prices": "£45 - £95（VIP 含優先入場及合影）",
            "guests": "個人專場無嘉賓",
            "setlist": ["用背脊唱情歌", "國際孤獨等級", "你都不知道自己有多好", "緊急聯絡人", "勁浪漫 超溫馨", "笑住喊", "去北極忘記你", "boyfriend material", "speed limit", "Hallelujah", "always", "跟悲傷結了帳", "早到的U", "我很小朋友", "mom I'm famous"]
        },
        {
            "tour": "2025 春季北美五城巡演《EXPEDITION》（遠征）",
            "dates": "2025-04-10 至 2025-04-20（溫哥華 / 多倫多 / 紐約 / 三藩市 / 洛杉磯）",
            "time": "20:00 開演 · 約 2 小時",
            "venue": "Enso / The Parkdale Hall / Racket NYC / The Chapel / The Vermont Hollywood",
            "prices": "US$58 - US$138",
            "guests": "個人巡演專場",
            "setlist": ["你都不知道自己有多好", "緊急聯絡人", "勁浪漫 超溫馨", "笑住喊", "boyfriend material", "speed limit", "Hallelujah", "孤單", "Buzzcut", "自信心爆棚", "去北極忘記你"]
        },
        {
            "tour": "2022《Gareth.T 湯令山 November Rain》個人演唱會",
            "dates": "2022-11-18 至 2022-11-20（共 3 場）",
            "time": "20:15 開演 · 約 2.5 小時",
            "venue": "九龍灣國際展貿中心 Star Hall",
            "prices": "HK$880 / HK$680 / HK$480",
            "guests": "首場：Tyson Yoshi ｜ 第二場：Day @ COLLAR（合唱《笑住喊》） ｜ 尾場：姜濤",
            "setlist": ["勁浪漫 超溫馨", "笑住喊", "緊急聯絡人", "boyfriend material", "speed limit", "honest", "dinner in bed", "mom I'm famous", "confidence", "buzzcut"]
        }
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
                    for _ in range(3):
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
                            if len(txt) >= 4 and txt.lower() != TARGET_USER:
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
    db["releases"] = sync_music_and_real_covers(db.get("releases", []))
    db["interviews"] = sync_interviews(db.get("interviews", []))
    db["concerts"] = get_base_concerts()
    db["photos"], db["comments"] = sync_social_photos_and_posts(db.get("photos", []), db.get("comments", []))
    # 初始语录种子：缺失的才补，不覆盖已同步的本人动态
    have_ids = {c.get("id") for c in db["comments"]}
    for seed in get_seed_comments():
        if seed["id"] not in have_ids:
            db["comments"].append(seed)
    db["comments"].sort(key=lambda c: c.get("date", ""), reverse=True)
    db["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    print("全自动更新完成！")


if __name__ == "__main__":
    main()
