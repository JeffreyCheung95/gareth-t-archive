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


KNOWN_TEXT_INTERVIEWS = [{'id': 'text_cool_20260430', 'title': 'Gareth.T 專訪｜湯令山從心傷到心零！想嘗試珍奶對決，對台灣第一個聯想是這個', 'category': '文字專訪', 'source': 'COOL-STYLE 潮流生活網', 'date': '2026-04-30', 'link': 'https://www.cool-style.com.tw/wd2/archives/1296564-gareth-t-%E5%B0%88%E8%A8%AA%EF%BD%9C%E6%B9%AF%E4%BB%A4%E5%B1%B1%E5%BE%9E%E5%BF%83%E5%82%B7%E5%88%B0%E5%BF%83%E9%9B%B6%EF%BC%81%E6%83%B3%E5%98%97%E8%A9%A6%E7%8F%8D%E5%A5%B6%E5%B0%8D%E6%B1%BA%EF%BC%8C', 'thumb': ''}, {'id': 'text_60s_202509', 'title': '〖60秒鐘音樂雜誌·歌手專訪·790話〗專訪湯令山 Gareth.T ——— 參見…不再傷心的心傷王子？！', 'category': '文字專訪', 'source': '閱評流（LINE TODAY）', 'date': '2025-09', 'link': 'https://today.line.me/hk/v3/article/j7gLOza', 'thumb': ''}, {'id': 'text_hbx_202206', 'title': 'HBX 專訪唱作人 Gareth.T 湯令山，談首張個人專輯《to be honest》', 'category': '文字專訪', 'source': 'Hypebeast', 'date': '2022-06', 'link': 'https://hypebeast.com/zh/2022/6/hbx-gareth-t-to-be-honest', 'thumb': ''}, {'id': 'text_ubeat_202203', 'title': '革新香港音樂的湯令山 Gareth.T（人物專訪）', 'category': '文字專訪', 'source': '大學線月刊 UBeat（香港中文大學）', 'date': '2022-03', 'link': 'https://ubeat.com.cuhk.edu.hk/ebook/158/files/basic-html/page20.html', 'thumb': ''}]
ARTIST_INTERACTIONS = [{'artist': 'Tyson Yoshi', 'where': 'Instagram 回覆', 'date': '2026-10-11', 'text': '@tysonyoshi buy u next time', 'post_url': 'https://www.instagram.com/reel/DeW1VEvyrwm/', 'source': 'instagram-cli fetch-post-comments（author-filtered）'}, {'artist': 'Tyson Yoshi', 'where': 'Instagram 帖文內文（作詞 credit）', 'date': '2024-04-10', 'text': '《遇上你之前的我》作詞：@tysonyoshi', 'post_url': 'https://www.instagram.com/reel/C5lJWc_vorB/', 'source': 'Gareth.T 本人 IG 帖文（connector 核實）'}, {'artist': 'Tyson Yoshi', 'where': 'Instagram 帖文內文', 'date': '2023-12-26', 'text': 'december christmas remix 🎄 original by @tysonyoshi', 'post_url': 'https://www.instagram.com/reel/C1UkkRtvTxq/', 'source': 'Gareth.T 本人 IG 帖文（connector 核實）'}, {'artist': 'Teddy Fan（結他手）', 'where': 'Instagram 回覆', 'date': '2026-10-11', 'text': '@teddyfanguitar 😏', 'post_url': 'https://www.instagram.com/reel/DeW1VEvyrwm/', 'source': 'instagram-cli fetch-post-comments（author-filtered）'}, {'artist': 'Teddy Fan（結他手）', 'where': 'Instagram 回覆', 'date': '2026-09-23', 'text': '@teddyfanguitar 同意', 'post_url': 'https://www.instagram.com/reel/DdoROSQyJHA/', 'source': 'instagram-cli fetch-post-comments（author-filtered）'}, {'artist': 'Teddy Fan（結他手）', 'where': 'Instagram 回覆', 'date': '2025-08-30', 'text': '@teddyfanguitar 來', 'post_url': 'https://www.instagram.com/p/DOAogtUEu2_/', 'source': 'instagram-cli fetch-post-comments（author-filtered）'}, {'artist': 'Teddy Fan（結他手）', 'where': 'Instagram 帖文內文（作曲 credit）', 'date': '2024-04-10', 'text': '《遇上你之前的我》作曲：me and @teddyfanguitar', 'post_url': 'https://www.instagram.com/reel/C5lJWc_vorB/', 'source': 'Gareth.T 本人 IG 帖文（connector 核實）'}, {'artist': 'MC 張天賦', 'where': '華納家族演唱會《WM!GO!》澳門站', 'date': '2025-08-02', 'text': 'Gareth.T 伙拍 MC 及 Lewsz 合唱《孤單》', 'post_url': '', 'source': '明報 2025-08-03'}, {'artist': 'MC 張天賦', 'where': '歌曲合作《金童子》', 'date': '2026-02-26', 'text': 'MC 張天賦 x Gareth Tong《金童子》官方 MV', 'post_url': 'https://www.youtube.com/watch?v=hgGoXAwA6J4', 'source': 'YouTube Gareth.T 官方 MV'}, {'artist': 'moon tang', 'where': '華納家族演唱會《WM!GO!》澳門站', 'date': '2025-08-02', 'text': 'Gareth.T 及 moon tang 繼香港站後，於澳門站再度合唱《Honest》', 'post_url': '', 'source': '明報 2025-08-03'}, {'artist': '林峯', 'where': '林峯澳門演唱會（嘉賓合唱）', 'date': '2025', 'text': 'Gareth T X 林峯《用背脊唱情歌》Go With The Flow 林峯澳門演唱會', 'post_url': '', 'source': 'YouTube 現場片段標題（已收錄於現場演出清單；完整連結見 lives）'}, {'artist': '姜濤', 'where': 'November Rain 2022 尾場', 'date': '2022-11-20', 'text': '姜濤原定任尾場嘉賓，因腳傷手術未能到場，僅 encore 電話連線打氣；Gareth 獨唱《Master Class》《鏡中鏡》送他；Gareth.T 曾為姜濤創作《Master Class》《鏡中鏡》', 'post_url': '', 'source': '明報 / am730 / HK01 尾場報道；中時新聞 2026-04-30（創作 credit）'}, {'artist': 'Day @ COLLAR', 'where': 'November Rain 2022 第二場嘉賓', 'date': '2022-11-19', 'text': 'Day @ COLLAR 合唱《笑住喊》', 'post_url': '', 'source': '原基準資料'}, {'artist': '菲道爾 Firdhaus', 'where': 'Prince Of Nothing 澳門站 2026-07-03 嘉賓', 'date': '2026-07-03', 'text': '合唱《能遇見，就很不錯了》《去北極忘記你》', 'post_url': '', 'source': 'mpweekly / 星島頭條 / am730 澳門站報道（已核實）'}, {'artist': '攬佬', 'where': '歌曲合作〈悲傷結了帳〉', 'date': '2026', 'text': '與攬佬合作的〈悲傷結了帳〉，為過去劃下句點', 'post_url': '', 'source': 'COOL 專訪 2026-04-30'}, {'artist': '黃偉文 Wyman', 'where': '填詞合作（長期）', 'date': '2026', 'text': '《THE PROTÉGÉ》全專輯填詞、專輯名亦由其命名；另填詞《勁浪漫 超溫馨》《國際孤獨等級》《緊急聯絡人》《偶像已死》《你都不知道自己有多好》《用背脊唱情歌》《泥菩薩》', 'post_url': '', 'source': 'Blow 吹音樂 / topick 倫敦站報道'}, {'artist': '黃偉文 Wyman', 'where': '倫敦站現場', 'date': '2025-10-30', 'text': "黃偉文親臨倫敦 O2 Shepherd's Bush Empire 現場支持；Gareth.T 台上隔空致謝", 'post_url': '', 'source': '明周 / topick 倫敦站報道'}, {'artist': '黃偉文 Wyman', 'where': 'Instagram 留言（Gemini 种子 seed_4，未核實）', 'date': '2026-09-24', 'text': '《淺粉紅 pale pink》黃偉文填詞貼文底下，Gareth.T 留言：「多謝 Wyman 幫我把粉紅色寫得咁痛。」', 'post_url': '', 'source': 'Gemini 种子（未在已掃描帖文中核實，保留原樣）'}, {'artist': '容祖兒', 'where': '創作合作', 'date': '2024', 'text': 'Gareth.T 為容祖兒創作〈九秒九〉，成五台冠軍曲', 'post_url': '', 'source': '緯來新聞網（2024 台北 T-Time 報道）'}, {'artist': '梁總', 'where': 'Threads 回覆', 'date': '2025-07-09', 'text': '謝梁總', 'post_url': '', 'source': 'threads-cli profile-replies（author-filtered）；梁總身份未能查證'}, {'artist': 'R.O.O.T', 'where': 'Chill Club 現場演出', 'date': '未能查證', 'text': '《CHILL CLUB》Gareth.T X R.O.O.T《Master Class》（現場演出）', 'post_url': '', 'source': 'YouTube 現場片段標題（已收錄於現場演出清單）'}, {'artist': '葉崇恩 Patrick Yip / 徐偉臻 nictsui', 'where': 'Instagram 帖文內文（製作 credit）', 'date': '2026-11-27', 'text': '「心動一半」曲：我和 @nictsui；編：@yippatrick @nictsui @marcustsao @devlinonthedrums 和我；監：我 @yippatrick 和 @nictsui', 'post_url': 'https://www.instagram.com/reel/DgPo6T1Sjz4/', 'source': 'Gareth.T 本人 IG 帖文（connector 核實）'}]
# 已确认非 Gareth / 重复的照片文件：每次运行都从数据里清除，
# 主 agent 另需从仓库 photos/ 删除这些文件。
BAD_PHOTO_FILES = ['Instagram_2026-11-27_dfa0d9915a.jpg', 'Threads_2026-11-27_2d9242db6f.jpg', 'Threads_2026-11-27_ba6dba162c.jpg', 'Threads_2026-11-27_d046f1d12b.jpg']
# 已核實不是 MV/現場的影片：頒獎片段、紅毯、新聞片段、別人翻唱、專輯試聽、電台首播。
# 2026-11-27 人工核實後移除，永不再收錄（sync_videos 跳過、main() 清除）。
BLOCKED_VIDEO_IDS = {
    'hF5Uujo64b0',  # THE PROTÉGÉ 全專輯試聽（不是 MV）
    '_JJiBX5vAIE',  # 金童子 叱咤首播（電台首播，不是 MV；正式 MV 是 hgGoXAwA6J4）
    'MOtvboXPivM',  # 叱咤至尊歌曲頒獎片段（不唱歌）
    'KJuqcUyQrQ8',  # 2021 叱咤生力軍金獎：MC 張天賦（不是 Gareth）
    'uoUMwd7e9rY',  # 叱咤填詞人大獎：黃偉文（不是 Gareth 演出）
    '00QuVKrzZkY',  # 2022 叱咤專業推介十大第八位（榜單公佈，不是演出）
    '1ASWIUhawI8',  # 浪潮音樂大賞紅毯現場（不唱歌）
    'ZGD2MacSzQ4',  # 明報新聞片段（姜濤現身尾場報道，不是演出片）
    'tAQNaaDnUoA',  # 娛聞新村新聞片段（不是演出片）
    'gWSF0lPkNC0',  # 緊急聯絡人 Cover by MC 張天賦 X 希晉（別人翻唱）
    'kOowvGoiTWw',  # 用背脊唱情歌 Cover by MC 張天賦 澳門（別人翻唱）
    '8zNy4Q6jaZc',  # 玻璃 demo（demo 不是現場 MV，也不是正式 MV）
}
# 已确认非 Gareth 的两张图的內容 MD5（去重用）：
BAD_PHOTO_MD5 = {"1fa713edb965b14388a3550f9e696d2e"}  # 駕駛考試成績表

# 手工核實加入的現場影片：每次運行都確保在 lives 裡，sync_videos 絕不刪除、
# 絕不因分類器改動而丟失。若某次上傳的 site_data.json 缺了它們，會自動補回。
KEEP_LIVES = {
    "owRghq0jMVk": {"id": "owRghq0jMVk", "title": "THE NEXT 20 張敬軒演唱會 第17場嘉賓 | Gareth.T 湯令山 懷舊情人 勁浪漫超溫馨", "date": "2022-05-18", "category": "現場演出", "source": "The Show Must Go On（YouTube 頻道，非官方上載）", "thumb": "https://i.ytimg.com/vi/owRghq0jMVk/hqdefault.jpg", "link": "https://www.youtube.com/watch?v=owRghq0jMVk", "songs": ["懷舊情人", "勁浪漫 超溫馨"]},
    "xPdNKcngYU8": {"id": "xPdNKcngYU8", "title": "【Janice Vidal Be Still Live 2022 現場直擊！】 第二場嘉賓： Gareth. T《心亂如麻》＋《Boyfriend Material》", "date": "2022-07-10", "category": "現場演出", "source": "Warner Music Hong Kong（官方）", "thumb": "https://i.ytimg.com/vi/xPdNKcngYU8/hqdefault.jpg", "link": "https://www.youtube.com/watch?v=xPdNKcngYU8", "songs": ["心亂如麻", "Boyfriend Material"]},
}
# 每輪自動同步最多新增影片數（硬上限）。新發行 MV/現場通常一輪只有 0–2 條；
# 超過即停，剩下的留待人工核實，絕不批量灌入。
MAX_NEW_VIDEOS_PER_RUN = 5


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
_JUNK_BARE_URL = re.compile(r"^\s*(https?://)?(www\.)?[a-z0-9\-]+\.[a-z]{2,}(/\S*)?\s*$", re.IGNORECASE)
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
    if _JUNK_BARE_URL.match(txt):
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
    releases = sorted(merged.values(), key=lambda x: x.get("date") or "", reverse=True)
    return releases


INTERVIEW_STRONG = ["專訪", "专访", "訪問", "访问", "訪談", "访谈", "interview",
                    "田木集作", "Channel專訪", "口水多過浪花", "誠實小測驗", "默契大考驗",
                    "相愛相殺", "COVER STORY", "大師請指教", "囝囝研究所", "His Story",
                    "成長故事", "音樂圈", "電笠", "娛壹", "MING'S", "Cosmopolitan",
                    "TALK", "對談", "人物專訪", "Honesty Test", "拉闊 少於三"]
LIVE_STRONG = ["Fan Cam", "fancam", "現場版", "live @", "live in",
               "足本重溫", "慈善演唱會", "慈善運音會", "音樂會", "Cartier",
               "multi angle", "medley", "演唱會", "倫敦站", "live show", "Chill Club",
               "CHILL CLUB", "年度之歌", "推介榜"]
# 「頒獎」「紅毯現場」「表演片段」已從 LIVE_STRONG 刪除：頒獎/紅毯/榜單公佈
# 片段不是演出，之前靠這三個詞被誤分進 lives。

def _is_rejected_video(vid, title):
    """Run-#5 驗證過的垃圾標題，一律拒收（回傳 True）。
    適用於新抓到的影片；已在清單內的舊條目不受影響（sync_videos 只對新
    條目呼叫此函數，舊條目按 id 原樣保留）。"""
    t = title or ""
    low = t.lower()
    # 頒獎/得獎訪問、紅毯、新聞片段、榜單公佈：不是演出也不是專訪。
    # 注意：只拒「得獎訪問」這類完整詞組，不拒「得獎心路歷程」這類專訪標題。
    if any(k in t for k in ("得獎訪問", "獨家得獎", "得獎後", "Chart Awards",
                            "頒獎典禮", "紅毯", "娛樂新聞", "娛聞新村",
                            "明報娛樂新聞")):
        return True
    # demo 不是 MV 也不是現場：demo 錄音/試聽不收（例：玻璃 demo）。
    if "demo" in low:
        return True
    # 「加冕年度之歌」若無演唱字眼（唱/live/現場）就是頒獎新聞，不是演出。
    # 已核實的現場 w_Lg2gecd_0 標題含「孭背包唱情歌」有「唱」字，不會被拒。
    if "加冕" in t and "年度之歌" in t and "唱" not in t and "live" not in low and "現場" not in t:
        return True
    # 別人翻唱：標題以他人名字開頭的 Cover（例：洪嘉豪 - 國際孤獨等級…、
    # MC 張天賦 X Gareth.T … Cover）。Gareth 自己翻唱他人歌曲（標題以
    # Gareth 開頭，或寫明 Cover by Gareth.T）不在此限。
    if "cover" in low:
        if t.startswith(("Gareth", "湯令山")):
            return False
        if "cover by gareth" in low or "cover by 湯令山" in low:
            return False
        return True
    # 「藝人 - 歌曲」格式而開頭藝人不是 Gareth：別人的影片。
    m = re.match(r"^\s*([^\-\(（《\[]+?)\s*[-–—]\s*", t)
    if m:
        artist = m.group(1).strip()
        if artist and "gareth" not in artist.lower() and "湯令山" not in artist:
            return True
    return False


def classify_video(vid, title, source=""):
    """Strict classifier (tested in /tmp/test_updater_fix.py).
    Returns interviews / mvs / lives / fancams, or None for videos that are
    none of those (album trial, award clip, red carpet, news segment, another
    artist's cover) — those must be dropped, never filed under another heading.
    Fan cams are NEVER official live. MVs are official videos only.
    Unknown talk/feature pieces also return None now: the old fallback that
    dumped everything into interviews is what inflated interviews 47 -> 124
    in run #5. New interviews are added only by manual verification."""
    t = title or ""
    low = t.lower()
    # 以下 7 個 id 是人工核實過的舊條目，最先判斷，絕不誤殺（其中
    # aVsEQRptqNY 標題/來源未提 Gareth，故必須在點名規則之前）。
    if vid == "pc9nZ2syMs0":
        return "lives"        # 拉闊音樂會 少於三足本重溫 = concert replay
    if vid == "aVsEQRptqNY":
        return "lives"        # 2021 叱咤群星表演片段（Gareth.T 有份演出）
    if vid == "CSf511CFkYc":
        return "lives"        # Live at HYPEBEAST SOUNDS = 正式現場演出
    if vid == "sRE_YbVibMU":
        return "lives"        # Concrete Woods Live Session = 正式現場錄製
    if vid == "XIf9Nc-b9tk":
        return "lives"        # Master Class + 鏡中鏡 @ November Rain 2022 = 演唱會現場
    if vid == "L0gsbDmZLh4":
        return "interviews"   # 叱咤2022 後台訪問 = backstage interview
    # 標題與來源完全未提 Gareth：與他無關的影片（肥媽倫敦演唱會、Day 許軼
    # fan cam、洪嘉豪紀錄片、MC/姜濤專訪等），一律拒收。
    if ("gareth" not in low and "湯令山" not in t
            and "gareth" not in (source or "").lower()
            and "湯令山" not in (source or "")):
        return None
    if "fan cam" in low or "fancam" in low:
        return "fancams"
    if _is_rejected_video(vid, t):
        return None
    if "live studio" in low or "live session" in low:
        return "lives"        # live studio / live session = 正式現場錄製
    if "全專輯試聽" in t:
        return None           # album trial, not an MV
    if ("official video" in low or "official mv" in low
            or "official music video" in low):
        return "mvs"
    if "叱咤" in t or "叱吒" in t:
        if any(k in t for k in ["頒獎", "金獎", "大獎", "專業推介", "填詞人"]):
            return None       # award clip, he does not sing
        if "表演片段" in t:
            return "lives"
        return "interviews"
    if "紅毯" in t:
        return None           # red carpet, not a performance
    if any(k in t for k in ["娛聞新村", "明報娛樂新聞", "娛樂新聞"]):
        return None           # news segment, not a performance
    if "Chill Club" in t or "CHILL CLUB" in t:
        return "lives"
    if any(k in t for k in INTERVIEW_STRONG):
        return "interviews"
    if any(k in t for k in LIVE_STRONG):
        return "lives"
    return None  # 未知內容一律拒收，絕不預設歸入專訪（run #5 教訓）


def _video_upload_date(entry):
    """Return a search result's upload date as YYYY-MM-DD, or '' if unknown."""
    pub = entry.get("upload_date") or entry.get("timestamp")
    if not pub:
        return ""
    if isinstance(pub, (int, float)):
        return datetime.fromtimestamp(pub, tz=timezone.utc).strftime("%Y-%m-%d")
    s = str(pub)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) >= 8 and s[:8].isdigit() else ""


def _title_mentions_gareth(title, channel=""):
    """Gate (c): title or channel must name Gareth.T / 湯令山.
    肥媽倫敦演唱會、Day 許軼 fan cam 這類與他無關的影片就靠這關擋下。"""
    t = f"{title or ''} {channel or ''}"
    low = t.lower()
    return ("gareth" in low) or ("湯令山" in t) or ("湯令山" in t)


def sync_videos(existing=None, newest_release_date=""):
    """2. 只為「新發行」增量抓取 MV / 現場演出（yt-dlp）。
    保護原則（run #5 之後寫死）：
    - 已有清單原樣保留，只追加；絕不重掃整個舊目錄。
    - 新影片必須全部通過：不在 BLOCKED_VIDEO_IDS；classify_video() 給出
      真實分類（未知內容回傳 None 即拒收）；標題/頻道提到 Gareth.T /
      湯令山；不是頒獎/紅毯/新聞/別人翻唱；上載日期晚於檔案內最新發行
      日期（newest_release_date）；未在任何清單內；每輪最多新增 5 條。
    - KEEP_LIVES 的兩段手工核實現場缺失時自動補回。
    單步失敗不影響整站；本地 VM 抓不到時保留已有清單（不清空）。"""
    existing = existing or {}
    out = {
        "interviews": list(existing.get("interviews", [])),
        "mvs": list(existing.get("mvs", [])),
        "lives": list(existing.get("lives", [])),
        "fancams": list(existing.get("fancams", [])),
    }
    # 已核實剔除的影片（頒獎/紅毯/新聞/別人翻唱/專輯試聽）永不回來。
    for key in out:
        out[key] = [v for v in out[key] if v.get("id") not in BLOCKED_VIDEO_IDS]
    # 兼容旧版：interviews 曾是混合清单，先按 classify_video() 重分一次。
    legacy = existing.get("interviews_legacy")
    if legacy:
        for v in legacy:
            if v.get("id") in BLOCKED_VIDEO_IDS:
                continue
            cat = classify_video(v.get("id", ""), v.get("title", ""), v.get("source", ""))
            if cat is None:
                continue  # 未知內容不入任何清單
            if v.get("id") not in {x.get("id") for x in out[cat]}:
                out[cat].append(v)
    seen_ids = {v.get("id") for lst in out.values() for v in lst}
    added_count = 0
    ydl_opts = {"quiet": True, "extract_flat": True}
    # 窄化查詢：只找新發行相關影片，不再按年份重掃舊專訪/舊演出。
    # 舊內容由日期門檻（晚於最新發行日）一併擋下。
    queries = [
        "ytsearch10:Gareth.T 湯令山 official video",
        "ytsearch10:Gareth.T 湯令山 MV",
        "ytsearch10:Gareth.T 湯令山 live",
        "ytsearch10:湯令山 專訪",
    ]
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
                        if vid in BLOCKED_VIDEO_IDS:
                            continue
                        # 五道門檻，任一不通過即丟棄，絕不入任何清單。
                        if not _title_mentions_gareth(title, entry.get("channel") or entry.get("uploader") or ""):
                            continue  # (c) 標題/頻道未提 Gareth.T / 湯令山
                        if _is_rejected_video(vid, title):
                            continue  # (d) 頒獎/紅毯/新聞/別人翻唱
                        up_date = _video_upload_date(entry)
                        if not newest_release_date or not up_date or up_date <= newest_release_date:
                            continue  # 新發行限定：上載日必須晚於最新發行日
                        if added_count >= MAX_NEW_VIDEOS_PER_RUN:
                            break  # 硬上限：每輪最多新增 5 條
                        seen_ids.add(vid)
                        cat = classify_video(vid, title, entry.get("channel") or "")
                        if cat is None:
                            continue  # (b) 未知內容：直接丟棄，不入任何清單
                        added_count += 1
                        item = {
                            "id": vid, "title": title,
                            "category": {"interviews": "深度專訪", "mvs": "歌曲MV",
                                         "lives": "現場演出", "fancams": "Fan Cam"}[cat],
                            "source": entry.get("channel") or entry.get("uploader") or "YouTube",
                            "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                            "link": f"https://www.youtube.com/watch?v={vid}",
                        }
                        pub = entry.get("upload_date") or entry.get("timestamp")
                        if pub:
                            if isinstance(pub, (int, float)):
                                item["date"] = datetime.fromtimestamp(pub, tz=timezone.utc).strftime("%Y-%m-%d")
                            else:
                                s = str(pub)
                                item["date"] = f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) >= 8 and s[:8].isdigit() else s[:10]
                        out[cat].append(item)
                except Exception as e:
                    print(f"[影音抓取跳过] {q} -> {e}")
                    continue
    except Exception as e:
        print(f"[影音同步跳过] {e}")
    # 手工核實的兩段現場：缺失時自動補回（run #5 曾令它們在 live 檔消失）。
    have_ids = {v.get("id") for lst in out.values() for v in lst}
    for vid, item in KEEP_LIVES.items():
        if vid not in have_ids and vid not in BLOCKED_VIDEO_IDS:
            out["lives"].append(dict(item))
    # 已核实的文字专访（无 YouTube 片源，yt-dlp 抓不到）：缺失才補。
    have = {v.get("id") for lst in out.values() for v in lst}
    for t in KNOWN_TEXT_INTERVIEWS:
        if t["id"] not in have:
            out["interviews"].append({
                "id": t["id"], "title": t["title"], "category": t["category"],
                "source": t["source"], "thumb": "", "link": t["link"],
                "date": t["date"], "is_text": True})
    for lst in out.values():
        lst.sort(key=lambda v: v.get("date") or "", reverse=True)
    return out


def sync_interviews(existing_interviews=None):
    """兼容旧入口：只返回专访清单（供外部调用）。"""
    existing = {}
    if isinstance(existing_interviews, list):
        existing = {"interviews": existing_interviews}
    elif isinstance(existing_interviews, dict):
        existing = existing_interviews
    return sync_videos(existing)["interviews"]
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
    items.sort(key=lambda n: n.get("date") or "", reverse=True)
    return items[:40]  # 保留最近 40 條：舊版 20 條會把代言相關舊聞（如 Uber 2026-08）頂掉


def get_base_concerts():
    """32 場已核實演出（2022–2027，按日期升序，逐場拆分）。
    注意：這是 2026-11-27 人工核實版（嘉賓已核實、場地已更正、紅館
    歌單標「暫未公開」），與 data/site_data.json 內的一致。嘉賓欄只寫
    名字，絕不寫合唱曲目（用戶規則）。main() 只有在檔案完全沒有演
    唱會時才會用它；檔案內已有清單時絕不覆寫。
    另含 3 場非個人專場：2024-02-04 香港大球場開場演出（kind=event）、
    2025-12-20 姜濤演唱會嘉賓、2026-07-11 MC 演唱會嘉賓（kind=guest）。
    曼徹斯特 2025-10-28 未經核實，已刪除；倫敦為心傷王子巡演首站。"""
    return [{'tour': '2022《Gareth.T 湯令山 November Rain》個人演唱會（首場）', 'date_sort': '2022-11-18', 'dates': '2022-11-18（星期五）', 'city': '香港', 'venue': '九龍灣國際展貿中心 Star Hall', 'time': '20:15 開演（約 2.5 小時）', 'prices': 'HK$880 / $680 / $480', 'seating': '票價 HK$880 / $680 / $480；分區未能查證', 'guests': 'Tyson Yoshi、Moon Tang 鄧凱文', 'ticket': '', 'source': '原基準資料（2022 首個個人演唱會）', 'source_link': 'https://www.hk01.com/%E7%9C%BE%E6%A8%82%E8%BF%B7/838398/%E6%B9%AF%E4%BB%A4%E5%B1%B1%E6%BC%94%E5%94%B1%E6%9C%83-day-collar%E6%80%A7%E6%84%9F%E7%8F%BE%E8%BA%AB-%E5%90%8C%E5%8F%B0%E5%90%88%E5%94%B1-%E7%AC%91%E4%BD%8F%E5%96%8A-%E8%B6%85%E9%A9%9A%E5%96%9C?utm_source=01articlecopy&utm_medium=referra', 'setlist': ['勁浪漫 超溫馨', '笑住喊', '緊急聯絡人', 'boyfriend material', 'speed limit', 'honest', 'dinner in bed', "mom I'm famous", 'confidence', 'buzzcut'], 'setlist_label': '實際歌單'}, {'tour': '2022《Gareth.T 湯令山 November Rain》個人演唱會（第二場）', 'date_sort': '2022-11-19', 'dates': '2022-11-19（星期六）', 'city': '香港', 'venue': '九龍灣國際展貿中心 Star Hall', 'time': '20:15 開演（約 2.5 小時）', 'prices': 'HK$880 / $680 / $480', 'seating': '票價 HK$880 / $680 / $480；分區未能查證', 'guests': 'Day @ COLLAR、衛蘭 Janice、衛詩 Jill、Moon Tang 鄧凱文', 'ticket': '', 'source': '原基準資料', 'source_link': 'https://www.hk01.com/%E7%9C%BE%E6%A8%82%E8%BF%B7/838398/%E6%B9%AF%E4%BB%A4%E5%B1%B1%E6%BC%94%E5%94%B1%E6%9C%83-day-collar%E6%80%A7%E6%84%9F%E7%8F%BE%E8%BA%AB-%E5%90%8C%E5%8F%B0%E5%90%88%E5%94%B1-%E7%AC%91%E4%BD%8F%E5%96%8A-%E8%B6%85%E9%A9%9A%E5%96%9C?utm_source=01articlecopy&utm_medium=referra', 'setlist': ['勁浪漫 超溫馨', '笑住喊', '緊急聯絡人', 'boyfriend material', 'speed limit', 'honest', 'dinner in bed', "mom I'm famous", 'confidence', 'buzzcut'], 'setlist_label': '實際歌單'}, {'tour': '2022《Gareth.T 湯令山 November Rain》個人演唱會（尾場）', 'date_sort': '2022-11-20', 'dates': '2022-11-20（星期日）', 'city': '香港', 'venue': '九龍灣國際展貿中心 Star Hall', 'time': '20:15 開演（約 2.5 小時）', 'prices': 'HK$880 / $680 / $480', 'seating': '票價 HK$880 / $680 / $480；分區未能查證', 'guests': 'Tyson Yoshi、Moon Tang 鄧凱文（原定嘉賓姜濤因傷缺席，僅電話連線）', 'ticket': '', 'source': '原基準資料', 'source_link': 'https://ol.mingpao.com/ldy/showbiz/news/20221122/1669056832081/%E5%A7%9C%E6%BF%A4%E9%9A%94%E7%A9%BA%E6%89%93%E6%B0%A3-%E6%B9%AF%E4%BB%A4%E5%B1%B1%E6%89%BF%E8%AB%BE%E5%AF%AB%E6%AD%8C%E5%9B%9E%E7%A6%AE', 'setlist': ['勁浪漫 超溫馨', '笑住喊', '緊急聯絡人', 'boyfriend material', 'speed limit', 'honest', 'dinner in bed', "mom I'm famous", 'confidence', 'buzzcut'], 'setlist_label': '實際歌單'}, {'tour': 'Tone Music Festival 2023（音樂節演出）', 'date_sort': '2023-10-01', 'dates': '2023-10-01（星期日）', 'city': '香港', 'venue': '亞洲國際博覽館 Arena（AsiaWorld-Arena Hall 1）', 'time': '音樂節時段，未能查證', 'prices': '未能查證', 'seating': '音樂節場地', 'guests': '無表演嘉賓', 'ticket': '', 'source': '現場 Fan Cam 標題：[4K Fan Cam] 231001 Gareth.T - 鏡中鏡 (Spiege im Spiegel) @ Tone Music 2023', 'source_link': 'https://topick.hket.com/article/3625799/周國賢雲浩影20個單位傾力演出\u3000絵麗奈任嘉賓直言緊張?mtc=40001&srkw=%E6%AD%8C%E6%89%8B', 'setlist': ['鏡中鏡', '孤單（加入林子祥《邁步向前》重新編曲）'], 'setlist_label': '部分核實'}, {'tour': '2024 國際邁阿密訪港表演賽開場演出', 'date_sort': '2024-02-04', 'dates': '2024-02-04（星期日）', 'city': '香港', 'venue': '香港大球場', 'time': '約 14:30 開場前演出', 'prices': '未能查證', 'seating': '未能查證', 'guests': '無表演嘉賓（個人開場演出）', 'ticket': '', 'source': 'HK01／am730（2024-02-04 開場演出報道）', 'source_link': 'https://www.hk01.com/%E7%9C%BE%E6%A8%82%E8%BF%B7/987866/%E7%BE%8E%E6%96%AF%E8%A8%AA%E6%B8%AF-gareth-t%E7%96%91%E7%B7%8A%E5%BC%B5%E5%A4%B1%E6%BA%96%E8%B5%B0%E9%9F%B3-%E9%9D%9A%E4%BB%94%E7%B5%90%E4%BB%96%E6%89%8B%E5%8B%81%E5%A4%9A%E5%A4%A7%E9%A0%AD%E6%88%90%E7%84%A6%E9%BB%9E', 'setlist': ['勁浪漫 超溫馨', '緊急聯絡人'], 'setlist_label': '實際歌單', 'kind': 'event'}, {'tour': '2024 Gareth.T 湯令山 “T-Time” 馬來西亞站（首次馬來西亞專場）', 'date_sort': '2024-09-01', 'dates': '2024-09-01（星期日）', 'city': 'Petaling Jaya（Klang Valley）', 'venue': 'JioSpace, Petaling Jaya', 'time': '未能查證', 'prices': 'VIP RM390 / 普通門票 RM220', 'seating': '未能查證', 'guests': '未能查證', 'ticket': '', 'source': 'HYPE Malaysia／LUCID Live Music', 'source_link': 'https://hype.my/hk-singer-songwriter-gareth-tong-to-perform-in-malaysia-in-september-ticket-details-announced/', 'setlist': [], 'setlist_label': '未能查證', 'kind': 'concert'}, {'tour': '2024 Gareth.T 湯令山 “T-Time” 墨爾本站', 'date_sort': '2024-09-04', 'dates': '2024-09-04（星期三）', 'city': '墨爾本', 'venue': 'Corner Hotel, Richmond, Melbourne（57 Swan St, Richmond）', 'time': '19:00 開演', 'prices': '未能查證', 'seating': '未能查證', 'guests': '未能查證', 'ticket': '', 'source': 'LUCID Live Music／Bandsintown', 'source_link': 'https://www.bandsintown.com/e/1032721136-gareth.t-at-corner-hotel', 'setlist': [], 'setlist_label': '未能查證', 'kind': 'concert'}, {'tour': '2024 Gareth.T 湯令山 “T-Time” 悉尼站', 'date_sort': '2024-09-05', 'dates': '2024-09-05（星期四）', 'city': '悉尼', 'venue': 'Manning Bar, Level 2, Manning House, Sydney University', 'time': '20:00–23:30', 'prices': 'GA A$91.76 / VIP A$142.73（含見面會）', 'seating': '未能查證', 'guests': '未能查證', 'ticket': '', 'source': 'Moshtix／LUCID Live Music', 'source_link': 'https://www.moshtix.com.au/v2/event/gareth-t/168774', 'setlist': [], 'setlist_label': '未能查證', 'kind': 'concert'}, {'tour': '2024 Gareth.T 湯令山 “T-Time” 台北站（首次台北專場）', 'date_sort': '2024-09-20', 'dates': '2024-09-20（星期五）', 'city': '台北', 'venue': 'NUZONE 展演空間（台北市大安區市民大道三段198號2樓；原訂 Zepp New Taipei，9月18日公告改場地）', 'time': '20:00 開演（原訂 19:00）', 'prices': '未能查證', 'seating': '未能查證', 'guests': '未能查證', 'ticket': '', 'source': 'KKTIX 活動頁（更換場地公告 2024-09-18）', 'source_link': 'https://spaceport.kktix.cc/events/5b26fa2a?locale=zh-TW', 'setlist': [], 'setlist_label': '未能查證'}, {'tour': '2025 春季北美五城巡演《EXPEDITION》（遠征）— 溫哥華站', 'date_sort': '2025-04-10', 'dates': '2025-04-10（星期四）', 'city': '溫哥華', 'venue': 'ENSŌ, Vancouver BC', 'time': '約 2 小時', 'prices': '巡演票價 US$58–$138（分站票價未能查證）', 'seating': '未能查證', 'guests': '無表演嘉賓', 'ticket': '', 'source': 'EXPEDITION 巡演海報（Fun In Toronto 2025-02-01）', 'source_link': 'https://www.instagram.com/p/DFi7cLTSwUf/', 'setlist': ['你都不知道自己有多好', '緊急聯絡人', '勁浪漫 超溫馨', '笑住喊', 'boyfriend material', 'speed limit', 'Hallelujah', '孤單', 'Buzzcut', '自信心爆棚', '去北極忘記你', '顏色（溫哥華站現場 fan video 證實有唱）'], 'setlist_label': '巡演歌單'}, {'tour': '2025 春季北美五城巡演《EXPEDITION》（遠征）— 多倫多站', 'date_sort': '2025-04-12', 'dates': '2025-04-12（星期六）', 'city': '多倫多', 'venue': 'The Parkdale Hall, Toronto ON', 'time': '約 2 小時', 'prices': '巡演票價 US$58–$138（分站票價未能查證）', 'seating': '未能查證', 'guests': '無表演嘉賓', 'ticket': '', 'source': 'EXPEDITION 巡演海報（Fun In Toronto 2025-02-01）；註：有樂迷帖文稱演出為 4月13日，與海報 4月12日有出入，待核實', 'source_link': 'https://www.instagram.com/p/DFi7cLTSwUf/', 'setlist': ['你都不知道自己有多好', '緊急聯絡人', '勁浪漫 超溫馨', '笑住喊', 'boyfriend material', 'speed limit', 'Hallelujah', '孤單', 'Buzzcut', '自信心爆棚', '去北極忘記你'], 'setlist_label': '巡演歌單'}, {'tour': '2025 春季北美五城巡演《EXPEDITION》（遠征）— 紐約站', 'date_sort': '2025-04-16', 'dates': '2025-04-16（星期三）', 'city': '紐約', 'venue': 'Racket NYC, New York City NY', 'time': '約 2 小時', 'prices': '巡演票價 US$58–$138（分站票價未能查證）', 'seating': '未能查證', 'guests': '無表演嘉賓', 'ticket': '', 'source': 'EXPEDITION 巡演海報（Fun In Toronto 2025-02-01）', 'source_link': 'https://www.instagram.com/p/DFi7cLTSwUf/', 'setlist': ['你都不知道自己有多好', '緊急聯絡人', '勁浪漫 超溫馨', '笑住喊', 'boyfriend material', 'speed limit', 'Hallelujah', '孤單', 'Buzzcut', '自信心爆棚', '去北極忘記你'], 'setlist_label': '巡演歌單'}, {'tour': '2025 春季北美五城巡演《EXPEDITION》（遠征）— 三藩市站', 'date_sort': '2025-04-18', 'dates': '2025-04-18（星期五）', 'city': '三藩市', 'venue': 'The Chapel, San Francisco CA', 'time': '約 2 小時', 'prices': '巡演票價 US$58–$138（分站票價未能查證）', 'seating': '未能查證', 'guests': '無表演嘉賓', 'ticket': '', 'source': 'EXPEDITION 巡演海報（Fun In Toronto 2025-02-01）', 'source_link': 'https://www.instagram.com/p/DFi7cLTSwUf/', 'setlist': ['你都不知道自己有多好', '緊急聯絡人', '勁浪漫 超溫馨', '笑住喊', 'boyfriend material', 'speed limit', 'Hallelujah', '孤單', 'Buzzcut', '自信心爆棚', '去北極忘記你'], 'setlist_label': '巡演歌單'}, {'tour': '2025 春季北美五城巡演《EXPEDITION》（遠征）— 洛杉磯站', 'date_sort': '2025-04-20', 'dates': '2025-04-20（星期日）', 'city': '洛杉磯', 'venue': 'The Vermont Hollywood, Los Angeles CA', 'time': '約 2 小時', 'prices': '巡演票價 US$58–$138（分站票價未能查證）', 'seating': '未能查證', 'guests': '無表演嘉賓', 'ticket': '', 'source': 'EXPEDITION 巡演海報（Fun In Toronto 2025-02-01）', 'source_link': 'https://www.instagram.com/p/DFi7cLTSwUf/', 'setlist': ['你都不知道自己有多好', '緊急聯絡人', '勁浪漫 超溫馨', '笑住喊', 'boyfriend material', 'speed limit', 'Hallelujah', '孤單', 'Buzzcut', '自信心爆棚', '去北極忘記你'], 'setlist_label': '巡演歌單'}, {'tour': '華納家族演唱會《WM!GO!》澳門站（群星演唱會，非個人專場）', 'date_sort': '2025-08-02', 'dates': '2025-08-02（星期六）', 'city': '澳門', 'venue': '澳門威尼斯人綜藝館（The Venetian Macao Cotai Arena），四面台，約 12,000 觀眾', 'time': '未能查證', 'prices': '未能查證', 'seating': '未能查證', 'guests': 'MC 張天賦、Lewsz、moon tang（群星演唱會）', 'ticket': '', 'source': '明報 2025-08-03〈湯令山宣布10月英國開騷 陳康堤初登舞台展大將之風〉', 'source_link': 'https://ol.mingpao.com/ldy/showbiz/latest/20250803/1754213952176/%E6%B9%AF%E4%BB%A4%E5%B1%B1%E5%AE%A3%E5%B8%8310%E6%9C%88%E8%8B%B1%E5%9C%8B%E9%96%8B%E9%A8%B7-%E9%99%B3%E5%BA%B7%E5%A0%A4%E5%88%9D%E7%99%BB%E8%88%9E%E5%8F%B0%E5%B1%95%E5%A4%A7%E5%B0%87%E4%B9%8B%E9%A2%A2', 'setlist': ['孤單（與 MC、Lewsz 合唱）', 'Honest（與 moon tang 合唱）', '886（男團合唱跳，薛凱琪原唱）'], 'setlist_label': '部分核實'}, {'tour': '2025 秋季英國巡演《Prince of Sadness》（心傷王子）— 倫敦站（歐洲首演）', 'date_sort': '2025-10-30', 'dates': '2025-10-30（星期四）', 'city': '倫敦', 'venue': "O2 Shepherd's Bush Empire, London", 'time': '19:30 開演（當地時間）', 'prices': '£68 / £78 / £88 / £98 / £118', 'seating': '地下站區 + 一至三樓座位（現場一至三樓座無虛席，連地下站區亦擠得水泄不通）', 'guests': '無表演嘉賓', 'ticket': 'https://www.ticketmaster.co.uk', 'source': 'Bastillepost / 明周 / topick 倫敦站報道；票價見 Bastillepost', 'source_link': 'https://www.bastillepost.com/hongkong/article/15231977-%e3%80%8agareth-t-prince-of-sadness%e3%80%8b%e7%86%b1%e6%bd%ae%e6%8c%81%e7%ba%8c%e5%bb%b6%e7%87%92%e5%80%ab%e6%95%a6%e6%88%90%e9%a6%96%e7%ab%99-%e3%80%8c%e5%bf%83%e5%82%b7%e7%8e%8b%e5%ad%90', 'setlist': ['花樣年華（開場，小提琴）', '偶像已死', '去北極忘記你', '遇上你之前的我', '蜚蜚（陳僖儀翻唱，英國站限定）', '孤單（林子祥翻唱，英國站限定）', '國際孤獨等級', '緊急聯絡人', '用背脊唱情歌（全場三唱）', '你都不知道自己有多好', '勁浪漫 超溫馨'], 'setlist_label': '部分核實'}, {'tour': '2025《湯令山 – 心傷王子》澳門站（第一場）', 'date_sort': '2025-12-05', 'dates': '2025-12-05（星期五）', 'city': '澳門', 'venue': '「澳門百老匯™」— 百老匯舞台', 'time': '20:00 開演', 'prices': 'MOP/HKD 1,288 / 988 / 688', 'seating': '百老匯舞台劇場座位；分區未能查證', 'guests': '未能查證', 'ticket': '', 'source': 'LINE TODAY 閱評流（澳門站 5–7/12/2025，三場）；Trip.com（2025-12-05 至 12-07）', 'source_link': 'https://today.line.me/hk/v3/article/j7gLOza', 'setlist': ['用背脊唱情歌', '國際孤獨等級', '你都不知道自己有多好', '緊急聯絡人', '勁浪漫 超溫馨', '笑住喊', '去北極忘記你', 'boyfriend material', 'speed limit', 'Hallelujah', 'always', '跟悲傷結了帳', '早到的U', '我很小朋友', "mom I'm famous"], 'setlist_label': '巡演歌單'}, {'tour': '2025《湯令山 – 心傷王子》澳門站（第二場）', 'date_sort': '2025-12-06', 'dates': '2025-12-06（星期六）', 'city': '澳門', 'venue': '「澳門百老匯™」— 百老匯舞台', 'time': '20:00 開演', 'prices': 'MOP/HKD 1,288 / 988 / 688', 'seating': '百老匯舞台劇場座位；分區未能查證', 'guests': '未能查證', 'ticket': '', 'source': '香港01 澳門站攻略；Bastillepost（12月6日首度登陸百老匯舞台）', 'source_link': 'https://www.hk01.com/%E7%9C%BE%E6%A8%82%E8%BF%B7/60273256/gareth-t%E6%B9%AF%E4%BB%A4%E5%B1%B1%E6%BC%94%E5%94%B1%E6%9C%832025%E6%BE%B3%E9%96%80-%E9%96%80%E7%A5%A8%E5%84%AA%E5%85%88-%E5%85%AC%E5%94%AE%E6%94%BB%E7%95%A5-%E8%B3%BC%E7%A5%A8%E9%80%A3%E7%B5%90', 'setlist': ['用背脊唱情歌', '國際孤獨等級', '你都不知道自己有多好', '緊急聯絡人', '勁浪漫 超溫馨', '笑住喊', '去北極忘記你', 'boyfriend material', 'speed limit', 'Hallelujah', 'always', '跟悲傷結了帳', '早到的U', '我很小朋友', "mom I'm famous"], 'setlist_label': '巡演歌單'}, {'tour': '2025《湯令山 – 心傷王子》澳門站（第三場）', 'date_sort': '2025-12-07', 'dates': '2025-12-07（星期日）', 'city': '澳門', 'venue': '「澳門百老匯™」— 百老匯舞台', 'time': '18:00 開演', 'prices': 'MOP/HKD 1,288 / 988 / 688', 'seating': '百老匯舞台劇場座位；分區未能查證', 'guests': '未能查證', 'ticket': '', 'source': 'LINE TODAY 閱評流（7/12 18:00）；Trip.com（2025-12-05 至 12-07）', 'source_link': 'https://today.line.me/hk/v3/article/j7gLOza', 'setlist': ['用背脊唱情歌', '國際孤獨等級', '你都不知道自己有多好', '緊急聯絡人', '勁浪漫 超溫馨', '笑住喊', '去北極忘記你', 'boyfriend material', 'speed limit', 'Hallelujah', 'always', '跟悲傷結了帳', '早到的U', '我很小朋友', "mom I'm famous"], 'setlist_label': '巡演歌單'}, {'tour': '2025 KEUNG TO “LAVA” LIVE 2025 第四場（嘉賓演出）', 'date_sort': '2025-12-20', 'dates': '2025-12-20（星期六）', 'city': '香港', 'venue': '亞洲國際博覽館 Arena', 'time': '未能查證', 'prices': '未能查證', 'seating': '未能查證', 'guests': 'Gareth.T 為姜濤演唱會嘉賓', 'ticket': '', 'source': 'U Lifestyle／星島頭條（嘉賓名單報道）', 'source_link': 'https://hk.ulifestyle.com.hk/topic/detail/20084915/%E5%A7%9C%E6%BF%A4%E6%BC%94%E5%94%B1%E6%9C%83-%E5%A0%B4%E5%98%89%E8%B3%93%E5%90%8D%E5%96%AE%E6%AF%8F%E5%A0%B4%E4%B8%8D%E6%96%B7%E6%9B%B4%E6%96%B0-%E4%B8%80%E6%96%87%E7%9D%87%E6%B8%85%E6%AD%8C%E6%89%8B%E9%99%A3%E5%AE%B9%E5%90%88%E5%94%B1%E6%AD%8C%E6%9B%B2', 'setlist': ['用背脊唱情歌', '去北極忘記你'], 'setlist_label': '實際歌單（嘉賓演出）', 'kind': 'guest'}, {'tour': 'oddshapes 音樂節（墨爾本站演出）', 'date_sort': '2026-03-28', 'dates': '2026-03-28（星期六）', 'city': '墨爾本', 'venue': '墨爾本 oddshapes 音樂節（場地未能查證）', 'time': '音樂節時段，未能查證', 'prices': '未能查證', 'seating': '音樂節戶外場地', 'guests': '無表演嘉賓', 'ticket': '', 'source': '明報 2026-03-31〈湯令山6月悉尼開騷〉（3月28日墨爾本 oddshapes 音樂節，唱《用背脊唱情歌》、首唱《早到的u》）', 'source_link': 'https://ol.mingpao.com/ldy/showbiz/latest/20260331/1774934311786/%E6%B9%AF%E4%BB%A4%E5%B1%B16%E6%9C%88%E6%82%89%E5%B0%BC%E9%96%8B%E9%A8%B7-%E7%8D%B2%E4%B8%BB%E8%BE%A6%E8%B4%88%E9%9B%A8%E8%81%B2%E6%A3%92-%E5%AF%93%E6%84%8F%E4%BB%A5%E9%9F%B3%E6%A8%82%E6%B4%97%E6%BB%8C%E5%BF%83%E9%9D%88', 'setlist': ['用背脊唱情歌', '早到的u（首唱）'], 'setlist_label': '部分核實'}, {'tour': '2026《Gareth.T － Prince Of Nothing 湯令山－心零王子》世界巡演 — 台北站（巡演首站）', 'date_sort': '2026-05-01', 'dates': '2026-05-01（星期五）', 'city': '台北', 'venue': 'Zepp New Taipei（新北市新莊區新北大道四段3號8樓）', 'time': '19:30 開演', 'prices': 'NT$4,200（一樓站席）/ NT$3,600（二樓座席）/ NT$2,100（身心障礙者優惠席）', 'seating': '一樓站席（依票面序號整隊入場）/ 二樓座席（對號入座）', 'guests': '無表演嘉賓', 'ticket': 'https://tixcraft.com/activity/detail/26_garetht', 'source': 'PlayMusic / KKBOX / WeKenGo 台北站資訊；am730 台北站報道（唱《玻璃》、翻唱陶喆《流沙》、encore《陀飛輪》）', 'source_link': 'https://www.playmusic.tw/column_info.php?id=26984&type=news', 'setlist': ['遇上你之前的我', '跟悲傷結了帳', '流沙（陶喆翻唱，台北限定）', '玻璃', 'honest（演唱中遇 6.1 級地震，暫停演出確認安全後繼續）', 'boyfriend material', '勁浪漫 超溫馨', 'speed limit', "mom I'm famous", '陀飛輪（陳奕迅翻唱，encore 再唱一次）'], 'setlist_label': '部分核實'}, {'tour': '2026《Gareth.T － Prince Of Nothing 湯令山－心零王子》世界巡演 — 馬來西亞雲頂站', 'date_sort': '2026-06-13', 'dates': '2026-06-13（星期六）', 'city': '雲頂', 'venue': 'Arena Of Stars 雲頂世界雲星劇場, Resorts World Genting', 'time': '18:00 開演', 'prices': 'RM 788（VIP）/ 688（PS1）/ 388（PS2）/ 288（PS3）', 'seating': 'VIP / PS1 / PS2 / PS3 分區', 'guests': '無表演嘉賓', 'ticket': 'https://www.ticket2u.com.my/event/49345', 'source': 'ticket2u 馬來西亞站頁面；中國報 2026-03-24（票價）；hk01 / Bastillepost 馬來西亞站報道（唱《會呼吸的痛》《我只懂》《刻在我心底的名字》）', 'source_link': 'https://www.ticket2u.com.my/event/49345', 'setlist': ['玻璃', '會呼吸的痛（梁靜茹翻唱）', '我只懂（首唱，全新國語作品，錄好兩天）', '刻在我心底的名字（盧廣仲翻唱）', '用背脊唱情歌（全場大合唱）', '跟悲傷結了帳（encore，由觀眾席步出）'], 'setlist_label': '部分核實'}, {'tour': '2026《Gareth.T － Prince Of Nothing 湯令山－心零王子》世界巡演 — 悉尼站', 'date_sort': '2026-06-27', 'dates': '2026-06-27（星期六）', 'city': '悉尼', 'venue': 'Sydney Event Centre, 2 Crofts Ave, Hurstville NSW', 'time': '20:00 開演', 'prices': 'AUD VIP $329（含合照）/ A $259 / B $219 / C $179 / D $129', 'seating': 'VIP / A / B / C / D 分區', 'guests': '未能查證', 'ticket': 'https://www.ticketmaster.com.au/gareth-t-tickets/artist/4382304', 'source': 'Chinatown Cinema 宣傳帖（2026-04-22，票價）；Concert Archives（Sydney Event Centre）', 'source_link': 'https://www.threads.com/@chinatown_cinema/post/DXa0dN2E8mi', 'setlist': ['緊急聯絡人', '用背脊唱情歌', '去北極忘記你', 'always（首唱，全新英文歌）'], 'setlist_label': '部分核實'}, {'tour': '2026《Gareth.T － Prince Of Nothing 湯令山－心零王子》世界巡演 — 澳門站（終極加場）', 'date_sort': '2026-07-03', 'dates': '2026-07-03（星期五）', 'city': '澳門', 'venue': '銀河綜藝館（澳門路氹城「澳門銀河™」綜合渡假城）', 'time': '20:00 開演', 'prices': 'MOP/HKD 1,288 / 988 / 788 / 588', 'seating': '銀河綜藝館；分區未能查證', 'guests': '菲道爾 Firdhaus', 'ticket': '', 'source': '香港01 澳門加場攻略；星島頭條（7月3日終極加場，6月16日發售）', 'source_link': 'https://www.hk01.com/%E7%9C%BE%E6%A8%82%E8%BF%B7/60350324/gareth-t%E6%B9%AF%E4%BB%A4%E5%B1%B1%E6%BC%94%E5%94%B1%E6%9C%832026%E6%BE%B3%E9%96%80%E5%8A%A0%E5%A0%B4-%E9%96%80%E7%A5%A8%E5%84%AA%E5%85%88-%E5%85%AC%E5%94%AE%E6%94%BB%E7%95%A5-%E9%80%A3%E7%B5%90', 'setlist': ['Hallelujah', '你的背包', '早到的U', '跟悲傷結了帳（前奏時提示「今晚無攬佬」）', 'boyfriend material', 'speed limit', 'always', '玻璃 demo', '能遇見，就很不錯了（與菲道爾合唱）', '去北極忘記你（與菲道爾合唱）', '落葉歸根（王力宏翻唱，澳門限定）', '國際孤獨等級', '我很小朋友', '你都不知道自己有多好', '顏色', "mom I'm famous"], 'setlist_label': '部分核實'}, {'tour': '2026《Gareth.T － Prince Of Nothing 湯令山－心零王子》世界巡演 — 澳門站', 'date_sort': '2026-07-04', 'dates': '2026-07-04（星期六）', 'city': '澳門', 'venue': '銀河綜藝館（澳門路氹城「澳門銀河™」綜合渡假城）', 'time': '20:00 開演', 'prices': 'MOP/HKD 1,288 / 988 / 788 / 588', 'seating': '銀河綜藝館；分區未能查證', 'guests': '文社長', 'ticket': '', 'source': 'timable 澳門站（7月4日至5日）；香港01 澳門加場攻略', 'source_link': 'https://timable.com/hk/zh/event/6a0ecbb4a8e802042b34b429', 'setlist': ['Hallelujah', '你的背包', '早到的U', '跟悲傷結了帳', 'boyfriend material', 'speed limit', 'always', '玻璃 demo', 'Thinkin Bout You（與文W社長合唱，Frank Ocean 原唱）', '去北極忘記你（與文W社長合唱）', '落葉歸根（王力宏翻唱，與文W社長合唱，澳門限定）', '國際孤獨等級', '我很小朋友', '你都不知道自己有多好', '顏色', "mom I'm famous"], 'setlist_label': '部分核實'}, {'tour': '2026《Gareth.T － Prince Of Nothing 湯令山－心零王子》世界巡演 — 澳門站（最終場）', 'date_sort': '2026-07-05', 'dates': '2026-07-05（星期日）', 'city': '澳門', 'venue': '銀河綜藝館（澳門路氹城「澳門銀河™」綜合渡假城）', 'time': '18:00 開演', 'prices': 'MOP/HKD 1,288 / 988 / 788 / 588', 'seating': '銀河綜藝館；分區未能查證', 'guests': '攬佬 SKAI ISYOURGOD', 'ticket': '', 'source': 'timable 澳門站（7月5日 18:00）；星島頭條（7月5日最終場）', 'source_link': 'https://timable.com/hk/zh/event/6a0ecbb4a8e802042b34b429', 'setlist': ['Hallelujah', '你的背包', '早到的U', '跟悲傷結了帳（與攬佬合唱，encore）', 'boyfriend material', 'speed limit', 'always', '玻璃 demo', '大展鴻圖（與攬佬合唱，encore）', '落葉歸根（王力宏翻唱，澳門限定）', '國際孤獨等級', '我很小朋友', '你都不知道自己有多好', '顏色', "mom I'm famous"], 'setlist_label': '部分核實'}, {'tour': '2026 MC 張天賦《E=MC² 演唱會2026》尾場（嘉賓演出）', 'date_sort': '2026-07-11', 'dates': '2026-07-11（星期六）', 'city': '香港', 'venue': '香港體育館（紅館）', 'time': '未能查證', 'prices': '未能查證', 'seating': '未能查證', 'guests': 'Gareth.T 為 MC 張天賦演唱會嘉賓', 'ticket': '', 'source': '巴士的報／am730（尾場嘉賓報道）', 'source_link': 'https://www.bastillepost.com/hongkong/article/16349105-mc%e5%bc%b5%e5%a4%a9%e8%b3%a6%e5%bc%b7%e5%bf%8d%e6%b7%9a%e6%b0%b4%e5%ae%8c%e6%88%90%e7%b4%85%e9%a4%a8%e5%b0%be%e5%a0%b4-%e6%b9%af%e4%bb%a4%e5%b1%b1%e4%bb%bb%e5%98%89%e8%b3%93%e9%a9%9a%e5%96%9c', 'setlist': ['泥菩薩', '去北極忘記你'], 'setlist_label': '實際歌單（嘉賓演出）', 'kind': 'guest'}, {'tour': 'OnLux 呈獻 Gareth.T 湯令山 Coliseum 2027（首個紅館個唱）— 第 1 場', 'date_sort': '2027-01-20', 'dates': '2027-01-20（星期三）', 'city': '香港', 'venue': '香港體育館（紅館 · 九龍紅磡灣暢運道 9 號）', 'time': '20:15 開演（約 2.5–3 小時）', 'prices': 'HK$1,380（內場平地及看台下層正面）/ HK$980（看台中層及下層兩側）/ HK$680（看台上層山頂位）', 'seating': 'HK$1,380：內場平地及看台下層正面 ｜ HK$980：看台中層及下層兩側 ｜ HK$680：看台上層山頂位', 'guests': '待官方揭曉', 'ticket': 'https://hk.trip.com/t/garethtcoliseumlive2027', 'source': 'Gareth.T 本人 IG 帖文 2026-10-23（Coliseum 2027 官宣：2027年1月20至23日，恒生優先 11/3–11/5，Trip.com 11/9–11/11）', 'source_link': 'https://www.instagram.com/p/De1ALSnyrL4/', 'setlist': ['暫未公開，待更新'], 'setlist_label': '暫未公開'}, {'tour': 'OnLux 呈獻 Gareth.T 湯令山 Coliseum 2027（首個紅館個唱）— 第 2 場', 'date_sort': '2027-01-21', 'dates': '2027-01-21（星期四）', 'city': '香港', 'venue': '香港體育館（紅館 · 九龍紅磡灣暢運道 9 號）', 'time': '20:15 開演（約 2.5–3 小時）', 'prices': 'HK$1,380（內場平地及看台下層正面）/ HK$980（看台中層及下層兩側）/ HK$680（看台上層山頂位）', 'seating': 'HK$1,380：內場平地及看台下層正面 ｜ HK$980：看台中層及下層兩側 ｜ HK$680：看台上層山頂位', 'guests': '待官方揭曉', 'ticket': 'https://hk.trip.com/t/garethtcoliseumlive2027', 'source': 'Gareth.T 本人 IG 帖文 2026-10-23（Coliseum 2027 官宣）', 'source_link': 'https://www.instagram.com/p/De1ALSnyrL4/', 'setlist': ['暫未公開，待更新'], 'setlist_label': '暫未公開'}, {'tour': 'OnLux 呈獻 Gareth.T 湯令山 Coliseum 2027（首個紅館個唱）— 第 3 場', 'date_sort': '2027-01-22', 'dates': '2027-01-22（星期五）', 'city': '香港', 'venue': '香港體育館（紅館 · 九龍紅磡灣暢運道 9 號）', 'time': '20:15 開演（約 2.5–3 小時）', 'prices': 'HK$1,380（內場平地及看台下層正面）/ HK$980（看台中層及下層兩側）/ HK$680（看台上層山頂位）', 'seating': 'HK$1,380：內場平地及看台下層正面 ｜ HK$980：看台中層及下層兩側 ｜ HK$680：看台上層山頂位', 'guests': '待官方揭曉', 'ticket': 'https://hk.trip.com/t/garethtcoliseumlive2027', 'source': 'Gareth.T 本人 IG 帖文 2026-10-23（Coliseum 2027 官宣）', 'source_link': 'https://www.instagram.com/p/De1ALSnyrL4/', 'setlist': ['暫未公開，待更新'], 'setlist_label': '暫未公開'}, {'tour': 'OnLux 呈獻 Gareth.T 湯令山 Coliseum 2027（首個紅館個唱）— 第 4 場', 'date_sort': '2027-01-23', 'dates': '2027-01-23（星期六）', 'city': '香港', 'venue': '香港體育館（紅館 · 九龍紅磡灣暢運道 9 號）', 'time': '20:15 開演（約 2.5–3 小時）', 'prices': 'HK$1,380（內場平地及看台下層正面）/ HK$980（看台中層及下層兩側）/ HK$680（看台上層山頂位）', 'seating': 'HK$1,380：內場平地及看台下層正面 ｜ HK$980：看台中層及下層兩側 ｜ HK$680：看台上層山頂位', 'guests': '待官方揭曉', 'ticket': 'https://hk.trip.com/t/garethtcoliseumlive2027', 'source': 'Gareth.T 本人 IG 帖文 2026-10-23（Coliseum 2027 官宣）；註：MoreTickets 列表曾顯示 2027-02-05 至 02-07，與華納官宣 1月20–23日衝突，以官宣為準，待核實', 'source_link': 'https://www.instagram.com/p/De1ALSnyrL4/', 'setlist': ['暫未公開，待更新'], 'setlist_label': '暫未公開'}]

def get_verified_backfill():
    """经已连接的 Instagram / Threads 账号核实的 Gareth.T 本人内容
    （2026-11-27 用 instagram-cli / threads-cli 检索 walkencheung95
    已连接账号取得，非爬虫抓取、非编造）。
    回覆：IG 50 篇帖文（2024-09-06 至 2026-11-27）author-filtered
    fetch-post-comments + Threads profile-replies 前 3 页，共 64 + 12 条。
    帖文：IG 最近 10 篇 caption + Threads profile-threads 前 3 页，共 23 条。
    回覆与帖文严格分开，绝不混放。"""
    return {'replies': [{'id': 'ig_reply_17960948997293398', 'platform': 'Instagram', 'date': '2026-11-25', 'text': '@iamnotyu_17 很快，下個專輯', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/reel/DgKen2lypND/'}, {'id': 'ig_reply_18058600826590356', 'platform': 'Instagram', 'date': '2026-11-25', 'text': '@xineechin no la this is a happy song', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/reel/DgKen2lypND/'}, {'id': 'ig_reply_18194067259394860', 'platform': 'Instagram', 'date': '2026-10-23', 'text': '@wwww10164 四面', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/De1ALSnyrL4/'}, {'id': 'ig_reply_18126102709678108', 'platform': 'Instagram', 'date': '2026-10-23', 'text': '@concertyy 🫂', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/De1ALSnyrL4/'}, {'id': 'ig_reply_18140834290624599', 'platform': 'Instagram', 'date': '2026-10-22', 'text': '@samsung_hk 🤝', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DezJpf5kvEP/'}, {'id': 'ig_reply_18109111700265524', 'platform': 'Instagram', 'date': '2026-10-11', 'text': '@teddyfanguitar 😏', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/reel/DeW1VEvyrwm/'}, {'id': 'ig_reply_17871339210645269', 'platform': 'Instagram', 'date': '2026-10-11', 'text': '@tysonyoshi buy u next time', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/reel/DeW1VEvyrwm/'}, {'id': 'ig_reply_18151029691565515', 'platform': 'Instagram', 'date': '2026-09-24', 'text': '@awtler walter pink type beat', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/Ddq2c12Em8e/'}, {'id': 'ig_reply_18025278281906590', 'platform': 'Instagram', 'date': '2026-09-23', 'text': '@teddyfanguitar 同意', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/reel/DdoROSQyJHA/'}, {'id': 'th_reply_18179912158418688', 'platform': 'Threads', 'date': '2026-08-18', 'text': '本故事純屬虛構', 'kind': 'reply', 'verified': True, 'post_url': ''}, {'id': 'th_reply_18086492816661244', 'platform': 'Threads', 'date': '2026-08-18', 'text': '🫂', 'kind': 'reply', 'verified': True, 'post_url': ''}, {'id': 'th_reply_18305519137303026', 'platform': 'Threads', 'date': '2026-08-17', 'text': 'very nice', 'kind': 'reply', 'verified': True, 'post_url': ''}, {'id': 'ig_reply_18406939915151179', 'platform': 'Instagram', 'date': '2026-05-16', 'text': '@1yuaan_ 下星期', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DWlq1OpEq7r/'}, {'id': 'ig_reply_18087052583202160', 'platform': 'Instagram', 'date': '2026-03-26', 'text': '@mayocreme 🙂\u200d↕️', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DWTrkuuEifR/'}, {'id': 'ig_reply_18060500732338507', 'platform': 'Instagram', 'date': '2026-02-16', 'text': '@liar_memo 月底🙂\u200d↕️', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DU0CSyXkhVH/'}, {'id': 'ig_reply_17978372966973059', 'platform': 'Instagram', 'date': '2026-02-16', 'text': '@xhuiii__0504 心靈', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DU0CSyXkhVH/'}, {'id': 'ig_reply_18081880835185268', 'platform': 'Instagram', 'date': '2026-02-16', 'text': '@lcheuka91 not yet my friend', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DU0CSyXkhVH/'}, {'id': 'ig_reply_18091902428061134', 'platform': 'Instagram', 'date': '2026-02-01', 'text': '@imweekend1 雪褸只有這一件🙂\u200d↕️', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DUNmWpNErYP/'}, {'id': 'ig_reply_18067530356630193', 'platform': 'Instagram', 'date': '2026-01-21', 'text': '@liuchauyuk you’re welcomeee', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DTw_SJnErZv/'}, {'id': 'ig_reply_18070540670151137', 'platform': 'Instagram', 'date': '2026-01-21', 'text': '@llllshye 造型來的🙂\u200d↔️', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DTw_SJnErZv/'}, {'id': 'ig_reply_18088101560107118', 'platform': 'Instagram', 'date': '2026-01-21', 'text': '@l03_926 是', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DTw_SJnErZv/'}, {'id': 'ig_reply_18092089979493203', 'platform': 'Instagram', 'date': '2025-12-17', 'text': '@gareth.t_fans_page 67', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DSXAQ2fkhiw/'}, {'id': 'ig_reply_18089984056753032', 'platform': 'Instagram', 'date': '2025-12-08', 'text': '@slowyouth940303 放了在 story, 可以去 cap 圖', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DSALxybktfZ/'}, {'id': 'ig_reply_17929119462097568', 'platform': 'Instagram', 'date': '2025-09-14', 'text': '@louischeung2013 謝謝你', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DOlWk1-kqZS/'}, {'id': 'ig_reply_18165391933367390', 'platform': 'Instagram', 'date': '2025-08-30', 'text': '@teddyfanguitar 來', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DOAogtUEu2_/'}, {'id': 'ig_reply_17895130125289024', 'platform': 'Instagram', 'date': '2025-08-30', 'text': '@ari_ullixu 今次的一定估不到', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DOAogtUEu2_/'}, {'id': 'ig_reply_17898674223267199', 'platform': 'Instagram', 'date': '2025-08-30', 'text': '@yayaxu_bobo 要找到一個能愛得很透明的人才發', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DOAogtUEu2_/'}, {'id': 'ig_reply_18071493260171391', 'platform': 'Instagram', 'date': '2025-08-30', 'text': '@coeklamz 快了', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DOAogtUEu2_/'}, {'id': 'th_reply_17844725400543460', 'platform': 'Threads', 'date': '2025-08-29', 'text': '是想開 close friend 的 live 😐', 'kind': 'reply', 'verified': True, 'post_url': '', 'reply_to': '回覆 iamnoturcutie「當你想錄片但唔小心撳咗開live」'}, {'id': 'th_reply_18077881607307169', 'platform': 'Threads', 'date': '2025-08-04', 'text': '多謝妳的fan cam', 'kind': 'reply', 'verified': True, 'post_url': ''}, {'id': 'th_reply_18073672693800180', 'platform': 'Threads', 'date': '2025-07-10', 'text': '兄弟，送你擁抱', 'kind': 'reply', 'verified': True, 'post_url': ''}, {'id': 'th_reply_18317506546233818', 'platform': 'Threads', 'date': '2025-07-09', 'text': '謝梁總', 'kind': 'reply', 'verified': True, 'post_url': ''}, {'id': 'th_reply_17862086526429996', 'platform': 'Threads', 'date': '2025-07-05', 'text': '硬', 'kind': 'reply', 'verified': True, 'post_url': ''}, {'id': 'th_reply_17978489612853515', 'platform': 'Threads', 'date': '2025-07-04', 'text': '🥰', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.threads.com/@gareth_tong/post/DLsNP5Ryclf', 'reply_to': '回覆 kk.higanbana 仔仔練習「令山轉」'}, {'id': 'ig_reply_18166730353360628', 'platform': 'Instagram', 'date': '2025-07-03', 'text': '@change_4.6 等我再戀愛時，就會出', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DLpFpIGv_1J/'}, {'id': 'ig_reply_18294747301247527', 'platform': 'Instagram', 'date': '2025-07-03', 'text': '@kim_kim_bb nah', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DLpFpIGv_1J/'}, {'id': 'ig_reply_17954438123970695', 'platform': 'Instagram', 'date': '2025-07-03', 'text': '@leotheasian sometime at night', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DLpFpIGv_1J/'}, {'id': 'ig_reply_18526323214049656', 'platform': 'Instagram', 'date': '2025-07-03', 'text': '@yuqiryang 謝啦', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DLpFpIGv_1J/'}, {'id': 'ig_reply_18062044916337190', 'platform': 'Instagram', 'date': '2025-07-03', 'text': '@kep_mtb.090511 bro got caught red handed', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DLpFpIGv_1J/'}, {'id': 'ig_reply_18015257423750374', 'platform': 'Instagram', 'date': '2025-07-03', 'text': '@qiao_oqx11 終於🈶了', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DLpFpIGv_1J/'}, {'id': 'th_reply_18122477887457713', 'platform': 'Threads', 'date': '2025-06-30', 'text': '加油', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.threads.com/@gareth_tong/post/DLh9HB-Sz17', 'reply_to': '回覆 hahamanyu 全職追星帖'}, {'id': 'th_reply_18036043361385160', 'platform': 'Threads', 'date': '2025-06-29', 'text': '有的', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.threads.com/@gareth_tong/post/DLgyyJ1SYSF', 'reply_to': '回覆 yan301149「如果有錄影就好，我考試」'}, {'id': 'th_reply_18048335591403411', 'platform': 'Threads', 'date': '2025-06-29', 'text': '有零衫轉', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.threads.com/@gareth_tong/post/DLgyuuMyPxR', 'reply_to': '回覆 siunam27「會有令山轉嘛？」'}, {'id': 'ig_reply_18070043638825299', 'platform': 'Instagram', 'date': '2025-06-10', 'text': '@gareth_tong tissues', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DKuDAO4Pp8p/'}, {'id': 'ig_reply_18366135046181010', 'platform': 'Instagram', 'date': '2025-06-10', 'text': '@enam.t stop wasting tissyes', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DKuDAO4Pp8p/'}, {'id': 'ig_reply_17913232356021757', 'platform': 'Instagram', 'date': '2025-06-10', 'text': '@laamlaamlaam goat', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DKuDAO4Pp8p/'}, {'id': 'ig_reply_17853551712415809', 'platform': 'Instagram', 'date': '2025-06-10', 'text': '@concertyy you 2', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DKuDAO4Pp8p/'}, {'id': 'ig_reply_17874289227360941', 'platform': 'Instagram', 'date': '2025-06-10', 'text': '@awtler idol', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DKuDAO4Pp8p/'}, {'id': 'ig_reply_18081041932823384', 'platform': 'Instagram', 'date': '2025-06-10', 'text': '@renalee9318 十幾take吧', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DKuDAO4Pp8p/'}, {'id': 'ig_reply_18090363109609768', 'platform': 'Instagram', 'date': '2025-05-05', 'text': '@yayaxu_bobo 用心去做吧', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DJTOozYPej6/'}, {'id': 'ig_reply_18054304184247735', 'platform': 'Instagram', 'date': '2025-05-05', 'text': '@a2m.film_ Thankyou for the amazing pictures', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DJTOozYPej6/'}, {'id': 'ig_reply_18339719746080544', 'platform': 'Instagram', 'date': '2025-04-22', 'text': 'Hahahaha we went 0/5, will try again next time', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DIxyBwRR7oE/'}, {'id': 'ig_reply_17847914436356460', 'platform': 'Instagram', 'date': '2025-01-01', 'text': '@kalostarz 有度數的', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DESYnDXvVfg/'}, {'id': 'ig_reply_17966576450826948', 'platform': 'Instagram', 'date': '2025-01-01', 'text': '@69.chui u know its@oakley', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DESYnDXvVfg/'}, {'id': 'ig_reply_18322501435086669', 'platform': 'Instagram', 'date': '2024-11-16', 'text': '@ajisaiii___ kodak ultramax 400', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DCdugXTPHPq/'}, {'id': 'ig_reply_17963891642697044', 'platform': 'Instagram', 'date': '2024-11-16', 'text': '@morada1026 跟 @warnermusichk 跟進一下', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DCdugXTPHPq/'}, {'id': 'ig_reply_18027969803597450', 'platform': 'Instagram', 'date': '2024-11-16', 'text': '@nuhes_926 不是啦，只在地鐵巧遇🙂\u200d↕️', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DCdugXTPHPq/'}, {'id': 'ig_reply_18045777677476758', 'platform': 'Instagram', 'date': '2024-11-16', 'text': '@affachan thanks affa, i still have lots to learn', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DCdugXTPHPq/'}, {'id': 'ig_reply_18033887243085964', 'platform': 'Instagram', 'date': '2024-11-16', 'text': '@xxhaclxx canonet ql17', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DCdugXTPHPq/'}, {'id': 'ig_reply_18045734366505325', 'platform': 'Instagram', 'date': '2024-11-16', 'text': '@canisssmama_ 應該係翹埋咗', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DCbxFmQP2qQ/'}, {'id': 'ig_reply_18289345339235099', 'platform': 'Instagram', 'date': '2024-11-16', 'text': '@wini_weiwl next time perhaps', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DCbxFmQP2qQ/'}, {'id': 'ig_reply_17938827839925407', 'platform': 'Instagram', 'date': '2024-11-16', 'text': '@wini_weiwl it was amazing', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DCbxFmQP2qQ/'}, {'id': 'ig_reply_17971084598666066', 'platform': 'Instagram', 'date': '2024-11-16', 'text': '@jyoexu 太感謝了🥺', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DCbxFmQP2qQ/'}, {'id': 'ig_reply_18045858589841189', 'platform': 'Instagram', 'date': '2024-10-20', 'text': '@jiushi5e5 會出啊，只想找一個好的時間', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DBV7vvVP-UD/'}, {'id': 'ig_reply_18367091260119621', 'platform': 'Instagram', 'date': '2024-10-20', 'text': '@haslen_y 看看心情', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DBV7vvVP-UD/'}, {'id': 'ig_reply_18046943021084666', 'platform': 'Instagram', 'date': '2024-10-20', 'text': '@vickyl6262 永遠不會放棄', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/DBV7vvVP-UD/'}, {'id': 'ig_reply_18050626138871205', 'platform': 'Instagram', 'date': '2024-09-06', 'text': '@yipingg_ 一言為定🙂\u200d↕️', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/C_kyJiNvHeD/'}, {'id': 'ig_reply_18337757590121113', 'platform': 'Instagram', 'date': '2024-09-06', 'text': '@___ay_u next or next next year perhapsssss', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/C_kyJiNvHeD/'}, {'id': 'ig_reply_18057317668689986', 'platform': 'Instagram', 'date': '2024-09-06', 'text': '@katie_11ss yall were amazing', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/C_kyJiNvHeD/'}, {'id': 'ig_reply_17926971251946511', 'platform': 'Instagram', 'date': '2024-09-06', 'text': '@xxijun_y_ang 下次安排一下', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/C_kyJiNvHeD/'}, {'id': 'ig_reply_18058621168674132', 'platform': 'Instagram', 'date': '2024-09-06', 'text': '@cerisecherrr 下次來吧🥺', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/C_kyJiNvHeD/'}, {'id': 'ig_reply_18065057017624328', 'platform': 'Instagram', 'date': '2024-09-06', 'text': '@69.chui worked out', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/C_kyJiNvHeD/'}, {'id': 'ig_reply_18039597716078087', 'platform': 'Instagram', 'date': '2024-09-06', 'text': '@shuxinxie0411 我想', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/C_kyJiNvHeD/'}, {'id': 'ig_reply_18050622526888236', 'platform': 'Instagram', 'date': '2024-09-06', 'text': '@dwaynehx_x gotta write more English bangers before us tour 🙂\u200d↕️', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/C_kyJiNvHeD/'}, {'id': 'ig_reply_18075712801534214', 'platform': 'Instagram', 'date': '2024-09-06', 'text': '@jeungayu_fii 希望之後可以', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/C_kyJiNvHeD/'}, {'id': 'ig_reply_17877687534084350', 'platform': 'Instagram', 'date': '2024-09-06', 'text': '@zak.sux thanksss brother, more to come hopefully, hope you’re doing good too', 'kind': 'reply', 'verified': True, 'post_url': 'https://www.instagram.com/p/C_kyJiNvHeD/'}], 'posts': [{'id': 'ig_post_18174169852485671', 'platform': 'Instagram', 'date': '2026-11-27', 'text': '「心動一半」mv 已經上架 link in bio —— 曲：我和 @nictsui；詞：易家揚老師；編：@yippatrick @nictsui @marcustsao @devlinonthedrums 和我；監：我 @yippatrick 和 @nictsui', 'kind': 'post', 'verified': True, 'post_url': 'https://www.instagram.com/reel/DgPo6T1Sjz4/'}, {'id': 'ig_post_17892408873474874', 'platform': 'Instagram', 'date': '2026-11-25', 'text': '心動一半 —— 11月27日 00:00 各大音樂平台上架；11月27日 20:00 MV首播', 'kind': 'post', 'verified': True, 'post_url': 'https://www.instagram.com/reel/DgKen2lypND/'}, {'id': 'ig_post_18287540680293076', 'platform': 'Instagram', 'date': '2026-11-13', 'text': 'Just switch #GalaxyZFold8 @samsung_hk', 'kind': 'post', 'verified': True, 'post_url': 'https://www.instagram.com/reel/DftRKO4SnHn/'}, {'id': 'ig_post_18154150189527755', 'platform': 'Instagram', 'date': '2026-10-31', 'text': 'photo dump', 'kind': 'post', 'verified': True, 'post_url': 'https://www.instagram.com/p/DfMAxvukpSj/'}, {'id': 'ig_post_18078878198475396', 'platform': 'Instagram', 'date': '2026-10-23', 'text': 'waited a long time for this —— OnLux 呈獻 Gareth.T 湯令山 Coliseum 2027：2027年1月20至23日，晚上8時15分，紅磡香港體育館，票價 $1380 / $980 / $680；恒生信用卡優先訂票 11/3 12:00–11/5 23:59；Trip.com 率先發售 11/9 10:00–11/11 23:59', 'kind': 'post', 'verified': True, 'post_url': 'https://www.instagram.com/p/De1ALSnyrL4/'}, {'id': 'ig_post_17913426801519602', 'platform': 'Instagram', 'date': '2026-10-22', 'text': 'quick LA trip', 'kind': 'post', 'verified': True, 'post_url': 'https://www.instagram.com/p/DezJpf5kvEP/'}, {'id': 'ig_post_17978092593129179', 'platform': 'Instagram', 'date': '2026-10-11', 'text': '紅館見🫂', 'kind': 'post', 'verified': True, 'post_url': 'https://www.instagram.com/reel/DeW1VEvyrwm/'}, {'id': 'ig_post_18031384553890515', 'platform': 'Instagram', 'date': '2026-09-26', 'text': 'mv credits —— director @elaiinelam；art director @sarenechan；producer @ryoooocoy', 'kind': 'post', 'verified': True, 'post_url': 'https://www.instagram.com/p/Ddv_ua3kms8/'}, {'id': 'ig_post_18139013650623367', 'platform': 'Instagram', 'date': '2026-09-24', 'text': 'pale pink mv out now —— melody by me and @yippatrick；lyrics by @concertyy；arrangement by @nictsui @teddyfanguitar @tombeats.bass @leeyatding and me', 'kind': 'post', 'verified': True, 'post_url': 'https://www.instagram.com/p/Ddq2c12Em8e/'}, {'id': 'ig_post_17869017147647224', 'platform': 'Instagram', 'date': '2026-09-23', 'text': '淺粉紅 —— 9月24日 00:00 各大音樂平台上架；9月24日 20:00 MV首播', 'kind': 'post', 'verified': True, 'post_url': 'https://www.instagram.com/reel/DdoROSQyJHA/'}, {'id': 'th_post_18107414614984615', 'platform': 'Threads', 'date': '2026-08-19', 'text': '今日收到，謝謝', 'kind': 'post', 'verified': True, 'post_url': ''}, {'id': 'th_post_18087553364404233', 'platform': 'Threads', 'date': '2026-08-17', 'text': '媽的，又是這樣', 'kind': 'post', 'verified': True, 'post_url': ''}, {'id': 'th_post_18027080858497124', 'platform': 'Threads', 'date': '2025-06-29', 'text': '今天6:30pm 朗豪坊4F中庭 首唱「用背脊唱情歌」 歡迎圍觀 + IG同步直播', 'kind': 'post', 'verified': True, 'post_url': ''}, {'id': 'th_post_18211457185306085', 'platform': 'Threads', 'date': '2025-06-16', 'text': '眼淚若嫌多', 'kind': 'post', 'verified': True, 'post_url': ''}, {'id': 'th_post_17855017527405483', 'platform': 'Threads', 'date': '2025-06-09', 'text': '出了新歌 不妨聽聽 https://youtu.be/falq0Gr3rc0', 'kind': 'post', 'verified': True, 'post_url': ''}, {'id': 'th_post_18493424104051291', 'platform': 'Threads', 'date': '2025-03-20', 'text': '朋友們，出個threads，tag我，說說你覺得自己還未夠好的地方 我會嘗試想想辦法讓你知道，自己有多好', 'kind': 'post', 'verified': True, 'post_url': ''}, {'id': 'th_post_18085128910540023', 'platform': 'Threads', 'date': '2025-03-19', 'text': '真心感謝大家這幾天給我的鼓勵，日後會用作品報答大家 但也不妨鼓勵一下身邊的人，告訴他們有多好', 'kind': 'post', 'verified': True, 'post_url': ''}, {'id': 'th_post_17960467637895295', 'platform': 'Threads', 'date': '2025-02-23', 'text': '新書包', 'kind': 'post', 'verified': True, 'post_url': ''}, {'id': 'th_post_18029337467567728', 'platform': 'Threads', 'date': '2025-01-13', 'text': '其實覺得還沒唱出歌詞應有的感覺，但這總算是一個完整的版本吧', 'kind': 'post', 'verified': True, 'media_type': 'VIDEO', 'post_url': ''}, {'id': 'th_post_18092595115476097', 'platform': 'Threads', 'date': '2024-09-15', 'text': '隨意彈', 'kind': 'post', 'verified': True, 'media_type': 'IMAGE', 'post_url': ''}, {'id': 'th_post_18009484130246116', 'platform': 'Threads', 'date': '2024-06-06', 'text': '除了音樂，我還能為社會貢獻些什麼?', 'kind': 'post', 'verified': True, 'media_type': 'TEXT_ONLY', 'post_url': ''}, {'id': 'th_post_18029762740973308', 'platform': 'Threads', 'date': '2024-04-29', 'text': '如果下次有人搵我影相，我會提醒自己笑🙂\u200d↕️', 'kind': 'post', 'verified': True, 'media_type': 'TEXT_ONLY', 'post_url': ''}, {'id': 'th_txt_mv_share', 'platform': 'Threads', 'date': '未能查證', 'text': 'gareth.t - 用背脊唱情歌 (official video)', 'kind': 'post', 'verified': False, 'post_url': '', 'note': '原 th_txt 抓取條目，無日期記錄；疑為 2025-06-09《用背脊唱情歌》MV 分享，未經核實'}]}
def get_seed_comments():
    """Gemini 种子语录 5 条，原样保留，绝不删除。
    核实状态：截至 2026-11-27，在已扫描的 50 篇 IG 帖文与 Threads
    回覆/帖文前 3 页中均未找到 seed_1–seed_5 的对应原文，
    故全部标注 verified=False；若日后核实到，再改 True。"""
    return [{'id': 'seed_1', 'platform': 'Instagram', 'date': '2026-11-27', 'text': '《心動一半》MV 預告底下粉絲留言問「點解著紅色大褸行雪地」，Gareth.T 本尊回覆：「因為綠色聖誕樹唔畀入鏡。」', 'kind': 'seed', 'verified': False, 'note': 'Gemini 种子（未在已掃描帖文中核實，保留原樣）', 'post_url': ''}, {'id': 'seed_2', 'platform': 'Instagram', 'date': '2026-11-20', 'text': '華納唱片官宣 2027 紅館《Coliseum 2027》四場開賣，粉絲求加場，Gareth.T 回覆：「4 場剛剛好，留返啲力氣唱爆紅館。」', 'kind': 'seed', 'verified': False, 'note': 'Gemini 种子（未在已掃描帖文中核實，保留原樣）', 'post_url': ''}, {'id': 'seed_3', 'platform': 'Threads', 'date': '2026-11-18', 'text': '凌晨 3:42 Threads 動態：「寫完副歌發現成個 studio 得返我同杯凍檸茶。」', 'kind': 'seed', 'verified': False, 'note': 'Gemini 种子（未在已掃描帖文中核實，保留原樣）', 'post_url': ''}, {'id': 'seed_4', 'platform': 'Instagram', 'date': '2026-09-24', 'text': '《淺粉紅 pale pink》黃偉文填詞貼文底下，Gareth.T 留言：「多謝 Wyman 幫我把粉紅色寫得咁痛。」', 'kind': 'seed', 'verified': False, 'note': 'Gemini 种子（未在已掃描帖文中核實，保留原樣）', 'post_url': ''}, {'id': 'seed_5', 'platform': 'Threads', 'date': '2026-07-04', 'text': '澳門《心零王子》尾場結束後 Threads：「多謝澳門三晚，下一站紅館見。」', 'kind': 'seed', 'verified': False, 'note': 'Gemini 种子（未在已掃描帖文中核實，保留原樣）', 'post_url': ''}]
def sync_social_photos_and_posts(existing_ig, existing_th, existing_comments, existing_posts):
    """4. 只从 Gareth 本人帖文取原图（Apify post-based；无 token 则跳过）。
    绝不再抓 IG/Threads 首页网格——之前那两张错图（IG 宣传图、驾驶考试
    成绩表）就是首页/广告/推荐内容混进来的。只保留来自 @gareth_tong
    本人帖文的图片，按内容 MD5 去重，坏图黑名单直接丢弃。
    照片按平台分开存：photos_ig / photos_threads，绝不混放。
    文字动态不靠爬虫：回覆/帖文以 connector 核实的 backfill 为准。"""
    photos_ig = list(existing_ig or [])
    photos_th = list(existing_th or [])
    comments = list(existing_comments or [])
    posts = list(existing_posts or [])
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seen_md5 = set()
    for p in photos_ig + photos_th:
        fp = os.path.join(PHOTOS_DIR, p.get("filename", ""))
        if os.path.exists(fp):
            try:
                seen_md5.add(hashlib.md5(open(fp, "rb").read()).hexdigest())
            except Exception:
                pass
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
                    post_url = f"https://www.instagram.com/p/{sc}/" if sc else ""
                    imgs = post.get("images") or ([post["displayUrl"]] if post.get("displayUrl") else [])
                    for idx, img_url in enumerate(imgs, start=1):
                        fname = f"IG_{pdate}_{sc}_{idx}.jpg"
                        fpath = os.path.join(PHOTOS_DIR, fname)
                        if not save_file_binary(img_url, fpath, 15000):
                            continue
                        try:
                            md5 = hashlib.md5(open(fpath, "rb").read()).hexdigest()
                        except Exception:
                            continue
                        if md5 in seen_md5 or md5 in BAD_PHOTO_MD5 or fname in BAD_PHOTO_FILES:
                            try:
                                os.remove(fpath)
                            except Exception:
                                pass
                            continue
                        seen_md5.add(md5)
                        photos_ig.insert(0, {
                            "id": f"ig_{sc}_{idx}", "platform": "Instagram", "date": pdate,
                            "caption": cap, "src": f"./photos/{fname}", "filename": fname,
                            "source_post": post_url})
        except Exception as e:
            print(f"[Apify IG 同步跳过] {e}")
    return photos_ig, photos_th, comments, posts
def main():
    db = load_data()
    # --- 迁移旧版混合数据 ---
    # 旧 comments 里混入的帖文（ig_post_/th_post_/th_txt_）移去 posts。
    posts = list(db.get("posts", []))
    comments = []
    for c in db.get("comments", []):
        cid = c.get("id", "")
        if cid.startswith(("ig_post_", "th_post_", "th_txt_")):
            if cid not in {p.get("id") for p in posts}:
                posts.append(c)
        else:
            comments.append(c)
    db["comments"] = clean_comments(comments)
    db["posts"] = posts
    # 旧 photos（混合清单）按 platform 拆成 photos_ig / photos_threads。
    photos_ig = list(db.get("photos_ig", []))
    photos_th = list(db.get("photos_threads", []))
    _have_photo_ids = {p.get("id") for p in photos_ig + photos_th}
    for p in db.get("photos", []) or []:
        if p.get("id") in _have_photo_ids:
            continue
        _have_photo_ids.add(p.get("id"))
        (photos_ig if p.get("platform") == "Instagram" else photos_th).append(p)
    db.pop("photos", None)
    # 清除已确认的坏图（宣传图/驾驶考试表/重复）。
    for lst in (photos_ig, photos_th):
        lst[:] = [p for p in lst if p.get("filename") not in BAD_PHOTO_FILES]
    # 旧 interviews 若仍是混合清单（无 mvs 分表），按 classify_video() 重分。
    if "mvs" not in db and isinstance(db.get("interviews"), list):
        legacy = db.pop("interviews")
        split = {"interviews": [], "mvs": [], "lives": [], "fancams": []}
        for v in legacy:
            if v.get("id") in BLOCKED_VIDEO_IDS:
                continue
            split[classify_video(v.get("id", ""), v.get("title", ""), v.get("source", "")) or "interviews"].append(v)
        db["interviews"] = split["interviews"]
        db["mvs"] = split["mvs"]
        db["lives"] = split["lives"]
        db["fancams"] = split["fancams"]
    db["releases"] = sync_music_and_real_covers(db.get("releases", []))
    # 新發行門檻：只有上載日晚於檔案內最新發行日的影片才可新增。
    newest_release_date = max((r.get("date") or "" for r in db.get("releases", [])), default="")
    videos = sync_videos({
        "interviews": db.get("interviews", []),
        "mvs": db.get("mvs", []),
        "lives": db.get("lives", []),
        "fancams": db.get("fancams", []),
    }, newest_release_date=newest_release_date)
    db["interviews"] = videos["interviews"]
    db["mvs"] = videos["mvs"]
    db["lives"] = videos["lives"]
    db["fancams"] = videos["fancams"]
    # 演唱會清單：檔案內的核實版是唯一權威，絕不以 get_base_concerts()
    # 覆寫（run #5 就是這一行把 26 場嘉賓/歌單打回舊版）。嘉賓欄只寫名字，
    # 絕不寫合唱曲目（用戶規則）。只有檔案完全沒有演唱會時才用 base
    # （而 base 本身現已是核實版，見下）。
    if not db.get("concerts"):
        db["concerts"] = get_base_concerts()
    db["news"] = sync_news(db.get("news", []))
    photos_ig, photos_th, db["comments"], db["posts"] = sync_social_photos_and_posts(
        photos_ig, photos_th, db.get("comments", []), db.get("posts", []))
    db["photos_ig"] = photos_ig
    db["photos_threads"] = photos_th
    # 种子 + connector 核实的回覆/帖文/艺人互动：缺失才补，绝不删除种子。
    have_c = {c.get("id") for c in db["comments"]}
    for item in get_seed_comments():
        if item["id"] not in have_c:
            db["comments"].append(item)
            have_c.add(item["id"])
    bf = get_verified_backfill()
    for item in bf["replies"]:
        if item["id"] not in have_c:
            db["comments"].append(item)
            have_c.add(item["id"])
    have_p = {p.get("id") for p in db["posts"]}
    for item in bf["posts"]:
        if item["id"] not in have_p:
            db["posts"].append(item)
            have_p.add(item["id"])
    # 藝人互動同理：檔案內已有即保留；只有檔案缺失時才用檔案內建常數。
    if not db.get("artist_interactions"):
        db["artist_interactions"] = ARTIST_INTERACTIONS
    # 按正文去重（爬虫版与核实版同一条只留一条），保留首次出现的条目。
    for key_name in ("comments", "posts"):
        seen_texts = set()
        deduped = []
        for c in db.get(key_name, []):
            key = re.sub(r"\s+", " ", str(c.get("text", ""))).strip().lower()
            if key and key in seen_texts:
                continue
            seen_texts.add(key)
            deduped.append(c)
        db[key_name] = deduped
    db["comments"].sort(key=lambda c: c.get("date", "") or "0000-00-00", reverse=True)
    db["posts"].sort(key=lambda c: c.get("date", "") or "0000-00-00", reverse=True)
    db["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    print("全自动更新完成！")
    print(f"counts: releases={len(db.get('releases', []))} photos_ig={len(db.get('photos_ig', []))} "
          f"photos_threads={len(db.get('photos_threads', []))} comments={len(db.get('comments', []))} "
          f"posts={len(db.get('posts', []))} interviews={len(db.get('interviews', []))} "
          f"mvs={len(db.get('mvs', []))} lives={len(db.get('lives', []))} "
          f"fancams={len(db.get('fancams', []))} concerts={len(db.get('concerts', []))} "
          f"news={len(db.get('news', []))}")


if __name__ == "__main__":
    main()
