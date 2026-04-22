from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


PROJECT_NAME = "WTPN"
OUTPUT_PATH = Path("docs/data/news.json")
MAX_ITEMS_PER_QUERY = int(os.getenv("MAX_ITEMS_PER_QUERY", "50"))
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "365"))
TIMEOUT_SECONDS = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)

GENERAL_SEARCH_KEYWORDS = [
    "員警風紀",
    "警員風紀",
    "警察風紀",
    "警紀案",
    "色警",
    "員警 違紀",
    "警員 違紀",
    "員警 違法違紀",
    "警員 違法違紀",
    "員警 風紀案",
    "警員 風紀案",
]

BROAD_ROLE_SEARCH_TERMS = (
    "員警",
    "警員",
    "警察",
)

BROAD_MISCONDUCT_SEARCH_TERMS = (
    "收賄",
    "索賄",
    "貪污",
    "涉貪",
    "貪瀆",
    "圖利",
    "包庇",
    "包庇 詐團",
    "包庇 賭場",
    "包庇 賭博電玩",
    "洩密",
    "洩個資",
    "偷查個資",
    "查個資",
    "查詢個資",
    "私查個資",
    "濫查個資",
    "濫查",
    "違法查個資",
    "非法查詢個資",
    "違規查詢",
    "非因公查詢",
    "勾結 詐團",
    "勾結 博弈",
    "勾結 黑道",
    "通風報信",
    "洩漏 臨檢情資",
    "改單",
    "銷單",
    "吞贓",
    "酒駕",
    "吸毒",
    "販毒",
    "性騷",
    "性騷擾",
    "職場性騷",
    "性平會",
    "開黃腔",
    "熊抱",
    "性侵",
    "猥褻",
    "援交",
    "偷拍",
    "無故攝錄性影像",
    "攝錄性影像",
    "妨害秘密",
    "宿舍 偷拍",
    "盥洗室 偷拍",
    "浴室 偷拍",
    "洗澡 偷拍",
    "如廁 偷拍",
    "合成 性影像",
    "不當交往",
    "討債",
    "債務糾紛",
    "詐領加班費",
    "浮報 加班費",
    "偽造文書",
    "登載不實",
    "報復檢舉人",
    "盜用電話",
    "惡作劇訂餐",
)

SPECIAL_SEARCH_KEYWORDS = [
    "員警 不當交往",
    "非法查詢個資 員警",
    "員警 偷查個資",
    "警察 偷查個資",
    "員警 私查個資",
    "警察 私查個資",
    "員警 濫查個資",
    "警察 濫查個資",
    "員警 查詢個資",
    "警察 查詢個資",
    "副所長 偷查個資",
    "員警 違法查個資",
    "警察 違法查個資",
    "員警 違規查詢 個資",
    "警察 違規查詢 個資",
    "員警 非因公 查詢",
    "警察 非因公 查詢",
    "員警 查個資 討債",
    "警察 查個資 討債",
    "員警 查詢個資 討債",
    "警察 查詢個資 討債",
    "員警 債務糾紛 個資",
    "警察 債務糾紛 個資",
    "員警 幫友人 查個資",
    "警察 幫友人 查個資",
    "色警 偷查個資",
    "色警 個資 討債",
    "鍾文智 偷查個資",
    "鍾文智 查個資",
    "鍾文智 警察 個資",
    "鍾文智 員警 個資",
    "鍾文智 討債 警察",
    "黃文烈 親信 偷查個資",
    "黃文烈 親信 查個資",
    "黃文烈 親信 警察 個資",
    "黃文烈 親信 個資 討債",
    "警察 博弈 洩密",
    "員警 包庇 博弈",
    "員警 包庇 電玩",
    "員警 包庇 詐團",
    "員警 包庇 賭場",
    "員警 警示帳戶",
    "員警 165 系統 收賄",
    "員警 臨檢情資",
    "員警 個資外洩",
    "員警 外流 監視器",
    "員警 違反個資法",
    "員警 白單 圖利",
    "員警 紅單 圖利",
    "員警 開假罰單",
    "員警 製單 違法",
    "員警 侵占 證物",
    "員警 贓款",
    "員警 創意私房",
    "員警 針孔 偷拍",
    "員警 無故攝錄性影像",
    "警察 無故攝錄性影像",
    "員警 偷拍 女警",
    "警察 偷拍 女警",
    "男警 偷拍 女警",
    "女警 偷拍",
    "女警 洗澡 偷拍",
    "女警 沐浴 偷拍",
    "女警 盥洗室 偷拍",
    "色警 偷拍",
    "色警 偷拍 女警",
    "警局 宿舍 偷拍",
    "分局 宿舍 偷拍",
    "員警 妨害秘密",
    "員警 性招待",
    "員警 養生館",
    "員警 護膚店",
    "員警 合成 性影像",
    "男警 合成 性影像",
    "員警 詐領加班費",
    "員警 浮報 加班費",
    "員警 偽造文書",
    "員警 登載不實",
    "偵查佐 性騷",
    "偵查佐 性騷擾",
    "偵查佐 女警 性騷",
    "偵查佐 女同事 性騷",
    "偵查佐 熊抱 女同事",
    "偵查佐 性平會",
    "信義分局 性騷",
    "信義分局 偵查佐 性騷",
    "鑑識小隊 性騷",
    "分局 性平會 性騷",
    "性平會 記過調職 警",
    "警察 性平會",
    "員警 性平會",
    "警官 性騷",
    "警官 性騷擾",
    "警官 職場性騷",
    "警官 開黃腔",
    "警官 性平會",
    "2線3星 警官 性騷",
    "兩線三星 警官 性騷",
    "2線3警官 性騷",
    "女同事 開黃腔 警官",
    "女同事 性騷 分局",
    "高雄 警官 性騷",
    "高雄 分局 性平會",
    "高雄 警官 開黃腔",
    "刑大隊長 偷查個資",
    "北市刑大隊長 偷查個資",
    "王大陸 警官 偷查個資",
    "王大陸 刑大隊長 個資",
    "王大陸 個資 判刑",
    "分局長 辣椒水",
    "警界 辣椒水",
    "誤噴 辣椒水 警",
    "柯文哲 辣椒水 分局長",
    "柯P 辣椒水 分局長",
    "110 勤指 警員",
    "110勤指 警員",
    "勤務指揮中心 警員 報復",
    "勤務指揮中心 警員 檢舉電話",
    "勤指警員 報復 檢舉",
    "勤指警員 盜用電話",
    "警員 報復 訂披薩",
    "警員 惡作劇 訂餐",
    "警員 檢舉電話 盜用",
    "警察 報復 檢舉人",
    "民眾檢舉 警員 報復",
    "檢舉違停 警員 報復",
    "檢舉電話 訂披薩",
]

RANK_FOCUSED_QUERY_MAP = {
    "巡佐": ("涉貪", "包庇", "酒駕", "偷拍", "改單", "性騷", "性騷擾"),
    "偵查佐": (
        "涉貪",
        "洩密",
        "吞贓",
        "偷拍",
        "偽造文書",
        "偷查個資",
        "性騷",
        "性騷擾",
        "性平會",
        "熊抱",
        "記過調職",
    ),
    "副所長": ("涉貪", "收賄", "洩密", "包庇", "偷查個資"),
    "所長": ("收賄", "包庇", "洩個資", "不當交往", "偷查個資"),
    "小隊長": ("涉貪", "洩密", "包庇", "偷拍"),
    "警務員": ("涉貪", "酒駕", "吸毒", "洩密"),
    "巡官": ("詐領加班費", "浮報 加班費", "酒駕"),
    "交通警察": ("改單", "銷單", "洩密", "開假罰單"),
    "刑警": ("洩密", "包庇", "涉貪", "勾結 詐團"),
    "刑大隊長": ("偷查個資", "查個資", "偽造文書", "個資 判刑"),
    "警官": ("性騷", "性騷擾", "職場性騷", "開黃腔", "性平會", "偷查個資", "涉貪"),
    "分局長": ("辣椒水", "誤噴 辣椒水", "警紀", "拔官", "調職"),
    "勤務指揮中心": ("報復", "檢舉電話", "盜用電話", "惡作劇訂餐"),
    "勤指警員": ("報復", "檢舉電話", "盜用電話", "訂披薩"),
    "警政監": ("博弈 洩密", "涉貪", "收賄"),
    "男警": ("偷拍", "性騷", "性侵", "妨害秘密", "不實影像"),
    "女警": ("偷拍", "妨害秘密", "性騷", "性侵", "針孔 偷拍"),
}


def dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def build_search_keywords() -> list[str]:
    keywords: list[str] = list(GENERAL_SEARCH_KEYWORDS)

    for role in BROAD_ROLE_SEARCH_TERMS:
        keywords.extend(
            f"{role} {misconduct}"
            for misconduct in BROAD_MISCONDUCT_SEARCH_TERMS
        )

    for role, misconducts in RANK_FOCUSED_QUERY_MAP.items():
        keywords.extend(f"{role} {misconduct}" for misconduct in misconducts)

    keywords.extend(SPECIAL_SEARCH_KEYWORDS)
    return dedupe_preserve_order(keywords)


SEARCH_KEYWORDS = build_search_keywords()

TRUSTED_SOURCES = {
    "中央社",
    "中時新聞網",
    "公視新聞網",
    "台視新聞網",
    "台灣好新聞",
    "台灣華報",
    "品觀點",
    "民眾新聞網",
    "民視新聞網",
    "自由時報",
    "聯合新聞網",
    "華視新聞網",
    "翻爆",
    "鏡新聞",
    "鏡週刊",
    "壹蘋新聞網",
    "CTWANT",
    "ETtoday新聞雲",
    "LINE TODAY",
    "MSN",
    "NOWnews今日新聞",
    "TVBS新聞網",
    "Yahoo新聞",
    "yesmedia.com.tw",
    "鏡報",
    "三立新聞網 Setn.com",
    "太報",
    "東森新聞",
    "風傳媒",
}

TRUSTED_SOURCE_ALIASES = {
    "三立新聞網 Setn.com": {
        "三立新聞網",
        "setn",
        "setn.com",
        "三立",
    },
    "東森新聞": {
        "東森新聞",
        "EBC東森新聞",
        "東森新聞雲",
    },
    "CTWANT": {
        "周刊王",
        "周刊王CTWANT",
        "CTWANT周刊王",
        "crwant",
    },
    "ETtoday新聞雲": {
        "ETtoday",
        "ETtoday新聞",
        "ettoday.net",
    },
    "聯合新聞網": {
        "聯合報",
        "udn",
        "udn.com",
        "udn聯合新聞網",
    },
    "LINE TODAY": {
        "LINE TODAY",
        "LINE Today",
        "linetoday",
    },
}

MANUAL_ARTICLE_SEEDS = [
    {
        "title": "與黃文烈親信有債務糾紛 鍾文智找警察偷查個資 北檢另案偵辦中",
        "source": "LINE TODAY",
        "link": "https://liff.line.me/1454987169-1WAXAP3K/v3/article/l2GO2yk",
        "summary": (
            "檢方偵辦鍾文智偽造簽到案時發現，鍾文智因與黃文烈親信有債務糾紛，"
            "涉嫌透過南港派出所警員偷查親友個資討債，目前由北檢另案偵辦中。"
        ),
        "published_at": "2026-04-15T20:02:00Z",
        "matched_keywords": [
            "鍾文智 偷查個資",
            "黃文烈 親信 偷查個資",
            "警察 查個資 討債",
        ],
    },
    {
        "title": "南投女警沐浴驚見鏡頭崩潰求醫！分局揪色警「知法犯法」二審重判",
        "source": "Yahoo新聞",
        "link": "https://tw.news.yahoo.com/%E5%8D%97%E6%8A%95%E5%A5%B3%E8%AD%A6%E6%B2%90%E6%B5%B4%E9%A9%9A%E8%A6%8B%E9%8F%A1%E9%A0%AD%E5%B4%A9%E6%BD%B0%E6%B1%82%E9%86%AB-%E5%88%86%E5%B1%80%E6%8F%AA%E8%89%B2%E8%AD%A6-%E7%9F%A5%E6%B3%95%E7%8A%AF%E6%B3%95-%E4%BA%8C%E5%AF%A9%E9%87%8D%E5%88%A4-041243223.html",
        "summary": (
            "南投一名張姓員警趁女同事在分局宿舍盥洗時持手機從門板上方偷拍，"
            "二審認定知法犯法且犯後試圖刪除影像，改判有期徒刑8月。"
        ),
        "published_at": "2026-03-25T16:12:00Z",
        "matched_keywords": [
            "色警 偷拍",
            "女警 沐浴 偷拍",
            "警局 宿舍 偷拍",
        ],
    },
    {
        "title": "王大陸與女友雙雙遭判刑！非法搜刮個資追討「閃兵款」一審判刑6月",
        "source": "LINE TODAY",
        "link": "https://today.line.me/tw/v3/article/gz95gyz",
        "summary": (
            "王大陸因疑遭閃兵集團詐騙，找前北市刑大隊長劉居榮協助查個資討款；"
            "新北地院一審判王大陸與女友闕沐軒各6月，劉居榮涉偽造文書另判刑。"
        ),
        "published_at": "2026-04-21T15:09:00Z",
        "matched_keywords": [
            "刑大隊長 偷查個資",
            "王大陸 刑大隊長 個資",
            "王大陸 個資 判刑",
        ],
    },
    {
        "title": "快訊／曾是警界明日之星！誤噴柯P辣椒水　台中六分局長最新職務出爐",
        "source": "ETtoday新聞雲",
        "link": "https://www.ettoday.net/news/20260422/3153463.htm",
        "summary": (
            "台中六分局長因柯文哲相關勤務誤噴辣椒水事件引發警紀與職務調整討論，"
            "ETtoday報導其最新職務安排。"
        ),
        "published_at": "2026-04-22T03:25:00Z",
        "matched_keywords": [
            "分局長 辣椒水",
            "警界 辣椒水",
            "柯P 辣椒水 分局長",
        ],
    },
    {
        "title": "北市信義分局驚傳偵查佐性騷女警　提報性平竟反調爽缺",
        "source": "CTWANT",
        "link": "https://www.ctwant.com/article/478121/",
        "summary": (
            "北市信義分局孫姓偵查佐遭同隊女同事指控在分局內熊抱性騷，"
            "申訴後僅被記過調職且疑調往較輕勤務，引發被害女警不滿。"
        ),
        "published_at": "2026-04-21T11:12:06Z",
        "matched_keywords": [
            "信義分局 偵查佐 性騷",
            "偵查佐 女警 性騷",
            "偵查佐 熊抱 女同事",
            "性平會 記過調職 警",
        ],
    },
    {
        "title": "獨／高雄傳2線3星警官對女同事開黃腔性騷 分局：已組性平會調查",
        "source": "LINE TODAY",
        "link": "https://today.line.me/tw/v3/article/JP1wBak",
        "summary": (
            "高雄某分局2線3星警官遭指控對女同事開黃腔、涉及職場性騷；"
            "分局表示已依規定邀外部委員組性平會調查。"
        ),
        "published_at": "2026-04-21T00:02:00Z",
        "matched_keywords": [
            "2線3星 警官 性騷",
            "女同事 開黃腔 警官",
            "高雄 分局 性平會",
        ],
    },
    {
        "title": "快訊／民眾檢舉違停遭報復狂訂披薩　竟是蘆洲110勤指警員幹的",
        "source": "三立新聞網 Setn.com",
        "link": "https://www.setn.com/News.aspx?NewsID=1826219",
        "summary": (
            "新北民眾檢舉違停後遭人盜用電話大量訂披薩與餐廳訂位，"
            "警方調查確認為勤務指揮中心一名員警所為，後續交由督察單位處理。"
        ),
        "published_at": "2026-04-22T02:55:00Z",
        "matched_keywords": [
            "110勤指 警員",
            "警員 報復 訂披薩",
            "警員 檢舉電話 盜用",
            "檢舉電話 訂披薩",
        ],
    },
]

TAG_RULES = {
    "收賄": ["收賄", "賄賂", "貪瀆", "貪污", "涉貪", "圖利", "索賄", "回扣"],
    "性紀律": [
        "性騷",
        "性騷擾",
        "職場性騷",
        "性平",
        "性平會",
        "開黃腔",
        "熊抱",
        "性侵",
        "猥褻",
        "援交",
        "性招待",
        "護膚店",
        "不當場所",
    ],
    "酒駕": ["酒駕"],
    "包庇": ["包庇", "關說", "護航", "縱放"],
    "洩密": [
        "洩密",
        "洩個資",
        "偷查個資",
        "查個資",
        "查詢個資",
        "私查個資",
        "濫查個資",
        "違規查詢",
        "非因公查詢",
        "個資",
        "偵查資料",
        "監視器",
        "警示帳戶",
        "討債",
        "檢舉電話",
        "報案電話",
        "盜用電話",
        "惡作劇訂餐",
        "訂披薩",
        "報復檢舉",
    ],
    "詐欺": ["詐欺", "詐團", "詐騙集團", "洗錢", "車手"],
    "博弈": ["博弈", "賭場", "賭博電玩", "地下匯兌"],
    "毒品": ["毒品", "吸毒", "販毒", "安非他命", "K他命"],
    "吞贓": ["吞贓", "贓款", "證物室", "侵占"],
    "偷拍": [
        "偷拍",
        "針孔",
        "妨害秘密",
        "不實影像",
        "性影像",
        "私密影像",
        "無故攝錄性影像",
        "攝錄性影像",
        "創意私房",
    ],
    "文書造假": [
        "偽造文書",
        "登載不實",
        "開假罰單",
        "假罰單",
        "白單",
        "紅單",
        "製單違法",
        "詐領加班費",
        "浮報加班費",
        "浮報",
    ],
    "風紀": ["風紀", "警紀", "違紀", "懲處", "記過", "免職", "色警", "不肖警", "貪警"],
    "勤務爭議": ["勤務疏失", "執勤爭議", "用械", "辣椒水", "誤噴", "拔官"],
}

STRONG_ROLE_TERMS = (
    "警察",
    "員警",
    "警員",
    "色警",
    "不肖警",
    "貪警",
    "男警",
    "女警",
    "警官",
    "高階警官",
    "警職",
    "警界",
    "警局",
    "警察局",
    "警政署",
    "警分局",
    "派出所",
    "分局",
    "督察組",
    "偵查隊",
    "刑大",
    "刑大隊長",
    "刑事警察大隊",
    "刑事警察局",
    "勤務指揮中心",
    "勤指中心",
    "勤指警員",
    "110勤指",
    "交通分隊",
    "國道警",
    "北市警",
    "新北警",
    "中市警",
    "高市警",
    "市警",
    "縣警",
)

SEMI_EXPLICIT_ROLE_TERMS = (
    "巡官",
    "警務員",
    "偵查佐",
    "巡佐",
    "副所長",
    "所長",
    "警政監",
)

AMBIGUOUS_ROLE_TERMS = (
    "小隊長",
)

POLICE_CONTEXT_TERMS = (
    *STRONG_ROLE_TERMS,
    *SEMI_EXPLICIT_ROLE_TERMS,
    "警政",
    "警用",
    "勤務",
    "查勤",
)

RELEVANT_MISCONDUCT_TERMS = (
    "風紀",
    "警紀",
    "違紀",
    "違法",
    "收賄",
    "索賄",
    "貪污",
    "涉貪",
    "貪瀆",
    "圖利",
    "包庇",
    "洩密",
    "通風報信",
    "臨檢情資",
    "個資",
    "偷查個資",
    "查個資",
    "查詢個資",
    "私查個資",
    "濫查個資",
    "濫查",
    "違法查個資",
    "違反個資法",
    "違規查詢",
    "非因公查詢",
    "不實查詢事由",
    "警示帳戶",
    "詐團",
    "詐騙集團",
    "黑道",
    "博弈",
    "賭場",
    "賭博電玩",
    "改單",
    "銷單",
    "白單",
    "紅單",
    "吞贓",
    "贓款",
    "證物",
    "酒駕",
    "毒品",
    "吸毒",
    "販毒",
    "性騷",
    "性騷擾",
    "職場性騷",
    "性平",
    "性平會",
    "開黃腔",
    "熊抱",
    "性侵",
    "猥褻",
    "援交",
    "偷拍",
    "無故攝錄性影像",
    "攝錄性影像",
    "私密影像",
    "針孔",
    "妨害秘密",
    "不實影像",
    "性影像",
    "創意私房",
    "不當交往",
    "討債",
    "債務糾紛",
    "性招待",
    "養生館",
    "護膚店",
    "詐領加班費",
    "浮報",
    "加班費",
    "偽造文書",
    "登載不實",
    "開假罰單",
    "假罰單",
    "報復檢舉人",
    "報復檢舉",
    "報復",
    "盜用電話",
    "檢舉電話",
    "報案電話",
    "惡作劇訂餐",
    "訂披薩",
    "狂訂披薩",
    "亂訂餐",
    "免職",
    "停職",
    "未繳槍",
    "勤務疏失",
    "執勤爭議",
)

SERVICE_MISCONDUCT_TERMS = (
    "辣椒水",
    "誤噴",
)

SERVICE_MISCONDUCT_CONTEXT_TERMS = (
    "分局長",
    "警紀",
    "拔官",
    "調職",
    "記過",
    "送辦",
    "職務",
    "柯文哲",
    "柯P",
)

REPORTER_RETALIATION_TERMS = (
    "報復",
    "報復檢舉",
    "報復檢舉人",
    "盜用電話",
    "惡作劇",
    "惡作劇訂餐",
    "訂披薩",
    "狂訂披薩",
    "亂訂餐",
    "訂位",
)

REPORTER_RETALIATION_CONTEXT_TERMS = (
    "檢舉",
    "檢舉人",
    "檢舉電話",
    "報案",
    "報案電話",
    "110",
    "勤務指揮中心",
    "勤指中心",
    "勤指警員",
    "違停",
    "電話",
)

RELEVANT_CASE_CONTEXT_TERMS = (
    "涉",
    "疑",
    "遭",
    "指控",
    "申訴",
    "提報",
    "通報",
    "調查",
    "確認",
    "起訴",
    "被訴",
    "遭訴",
    "送辦",
    "法辦",
    "收押",
    "羈押",
    "交保",
    "聲押",
    "判刑",
    "認罪",
    "免職",
    "停職",
    "記過",
    "記大過",
    "撤職",
    "搜索",
    "約談",
    "函送",
    "偵辦",
    "查辦",
    "臨檢",
    "開鍘",
    "求刑",
    "拒測",
    "拒檢",
    "二審",
    "上訴",
    "重判",
    "下場出爐",
    "羈押禁見",
    "裁定",
    "處分",
    "被害人",
    "加害人",
    "性平",
    "性平會",
    "調離",
    "調職",
    "職務調整",
    "記小過",
    "記過調職",
    "提告",
    "啟動調查",
    "拔官",
    "出爐",
)

PERSONAL_DATA_ABUSE_TERMS = (
    "個資",
    "偷查個資",
    "查個資",
    "查詢個資",
    "私查個資",
    "濫查個資",
    "違法查個資",
    "非法查詢個資",
    "違規查詢",
    "非因公查詢",
)

PERSONAL_DATA_ABUSE_CONTEXT_TERMS = (
    "討債",
    "債務糾紛",
    "幫友人",
    "請託",
    "提供",
    "洩漏",
    "外流",
    "不法利用",
    "不實查詢事由",
)

VOYEURISM_EVIDENCE_TERMS = (
    "偷拍",
    "針孔",
    "妨害秘密",
    "無故攝錄性影像",
    "攝錄性影像",
    "私密影像",
    "鏡頭",
    "錄影",
)

VOYEURISM_SCENE_TERMS = (
    "洗澡",
    "沐浴",
    "浴室",
    "盥洗室",
    "如廁",
    "宿舍",
    "女警",
    "女同事",
    "同事",
)

RSS_TEMPLATE = (
    "https://news.google.com/rss/search"
    "?q={query}+when:{lookback_days}d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
)

IRRELEVANT_ARTICLE_PATTERNS = (
    "花蓮縣府主任遭爆刁難基層員警",
    "花縣府主任違停嗆警",
    "花蓮縣府官員遭檢舉違停",
    "違停開單警控遭刁難",
    "交通糾紛警察不開單",
    "北市警未開單遭檢舉圖利",
    "檢舉達人不爽警沒開單",
    "調查官超速扣牌銷單",
    "假警察",
    "假刑警",
    "盜用警察照片",
    "圍棋師猥褻",
    "警方及時阻詐",
)

ROLE_MARKER_PATTERN = re.compile(r"[0-9一二三四五六七八九十兩]+警")
POLICE_SHORTHAND_PATTERN = re.compile(
    r"(?:^|[「『（(／\s])警(?=利用職權|涉|涉犯|幫友人|偷查|洩密|查詢|違法|違規|遭|爆|捲)"
)


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_request(url: str) -> Request:
    return Request(url, headers={"User-Agent": USER_AGENT})


def normalize_source_name(value: str) -> str:
    return re.sub(r"[\s._-]+", "", value).lower()


def canonicalize_source(source: str) -> str:
    if source in TRUSTED_SOURCES:
        return source

    normalized_source = normalize_source_name(source)
    for canonical, aliases in TRUSTED_SOURCE_ALIASES.items():
        alias_candidates = {canonical, *aliases}
        if any(
            normalize_source_name(alias) in normalized_source
            for alias in alias_candidates
        ):
            return canonical

    return ""


def fetch_feed(query: str) -> bytes:
    url = RSS_TEMPLATE.format(
        query=quote_plus(query),
        lookback_days=LOOKBACK_DAYS,
    )
    with urlopen(build_request(url), timeout=TIMEOUT_SECONDS) as response:
        return response.read()


def parse_datetime(value: str) -> tuple[str, str]:
    dt = parsedate_to_datetime(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    iso_value = dt.isoformat().replace("+00:00", "Z")
    label = dt.astimezone().strftime("%Y-%m-%d %H:%M")
    return iso_value, label


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_title(title: str, source: str) -> str:
    suffix = f" - {source}"
    if title.endswith(suffix):
        return title[: -len(suffix)].strip()
    return title.strip()


def clean_summary(summary: str, title: str, source: str) -> str:
    compact = re.sub(r"\s+", " ", summary).strip()
    trivial_summaries = {
        title,
        f"{title} {source}",
        f"{title} - {source}",
        f"{title}{source}",
    }
    if compact in trivial_summaries:
        return ""
    return compact


def load_existing_payload(output_path: Path = OUTPUT_PATH) -> dict:
    if not output_path.exists():
        return {}

    return json.loads(output_path.read_text(encoding="utf-8"))


def count_term_hits(haystack: str, terms: Iterable[str]) -> int:
    return sum(1 for term in terms if term in haystack)


def content_tags(title: str, summary: str = "") -> list[str]:
    haystack = " ".join([title, summary])
    tags = classify_tags([title, summary])
    if (
        "偷拍" not in tags
        and any(term in haystack for term in VOYEURISM_EVIDENCE_TERMS)
        and any(term in haystack for term in VOYEURISM_SCENE_TERMS)
    ):
        tags.append("偷拍")
    return sorted(set(tags))


def is_relevant_article(
    title: str,
    summary: str = "",
    matched_keywords: Iterable[str] = (),
) -> bool:
    haystack = " ".join([title, summary, *matched_keywords])
    if any(pattern in haystack for pattern in IRRELEVANT_ARTICLE_PATTERNS):
        return False

    content_haystack = " ".join([title, summary])
    has_role = (
        any(term in content_haystack for term in STRONG_ROLE_TERMS)
        or any(term in content_haystack for term in SEMI_EXPLICIT_ROLE_TERMS)
        or (
            any(term in content_haystack for term in AMBIGUOUS_ROLE_TERMS)
            and any(term in content_haystack for term in POLICE_CONTEXT_TERMS)
        )
        or bool(ROLE_MARKER_PATTERN.search(content_haystack))
        or bool(POLICE_SHORTHAND_PATTERN.search(content_haystack))
    )
    misconduct_hits = count_term_hits(content_haystack, RELEVANT_MISCONDUCT_TERMS)
    has_misconduct = misconduct_hits > 0
    has_case_context = any(
        term in content_haystack for term in RELEVANT_CASE_CONTEXT_TERMS
    )
    has_personal_data_abuse_pattern = (
        any(term in content_haystack for term in PERSONAL_DATA_ABUSE_TERMS)
        and any(term in content_haystack for term in PERSONAL_DATA_ABUSE_CONTEXT_TERMS)
    )
    has_voyeurism_pattern = (
        any(term in content_haystack for term in VOYEURISM_EVIDENCE_TERMS)
        and any(term in content_haystack for term in VOYEURISM_SCENE_TERMS)
        and has_case_context
    )
    has_service_misconduct_pattern = (
        any(term in content_haystack for term in SERVICE_MISCONDUCT_TERMS)
        and any(term in content_haystack for term in SERVICE_MISCONDUCT_CONTEXT_TERMS)
        and has_case_context
    )
    has_reporter_retaliation_pattern = (
        any(term in content_haystack for term in REPORTER_RETALIATION_TERMS)
        and any(term in content_haystack for term in REPORTER_RETALIATION_CONTEXT_TERMS)
        and has_case_context
    )
    return has_role and (
        has_personal_data_abuse_pattern
        or has_voyeurism_pattern
        or has_service_misconduct_pattern
        or has_reporter_retaliation_pattern
        or (has_misconduct and (has_case_context or misconduct_hits >= 2))
    )


def classify_tags(chunks: Iterable[str]) -> list[str]:
    haystack = " ".join(chunks)
    tags: list[str] = []
    for tag, needles in TAG_RULES.items():
        if any(needle in haystack for needle in needles):
            tags.append(tag)
    return tags


def article_id(source: str, title: str, published_at: str) -> str:
    seed = f"{source}|{title}|{published_at}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def article_key(article: dict) -> str:
    return article.get("id") or article.get("link") or ""


def build_search_text(article: dict) -> str:
    return " ".join(
        [
            article["title"],
            article["source"],
            article["link"],
            article["summary"],
            " ".join(article["matched_keywords"]),
            " ".join(article["tags"]),
        ]
    ).lower()


def format_published_label(value: str) -> str:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def build_manual_articles() -> list[dict]:
    entries: list[dict] = []

    for seed in MANUAL_ARTICLE_SEEDS:
        matched_keywords = dedupe_preserve_order(seed.get("matched_keywords") or [])
        article = {
            "id": article_id(seed["source"], seed["title"], seed["published_at"]),
            "title": seed["title"],
            "source": seed["source"],
            "link": seed["link"],
            "summary": seed.get("summary", ""),
            "published_at": seed["published_at"],
            "published_label": format_published_label(seed["published_at"]),
            "matched_keywords": matched_keywords,
            "tags": content_tags(seed["title"], seed.get("summary", "")),
        }
        if is_relevant_article(article["title"], article["summary"], matched_keywords):
            entries.append(article)

    return entries


def hydrate_article(article: dict, default_seen_at: str | None = None) -> dict:
    item = dict(article)
    item["matched_keywords"] = sorted(set(item.get("matched_keywords") or []))
    item["summary"] = item.get("summary") or ""
    item["source"] = item.get("source") or ""
    item["title"] = item.get("title") or ""
    item["link"] = item.get("link") or ""
    item["tags"] = sorted(set(content_tags(item["title"], item["summary"])))
    item["published_label"] = item.get("published_label") or format_published_label(
        item["published_at"]
    )
    item["first_seen_at"] = item.get("first_seen_at") or default_seen_at or item["published_at"]
    item["last_seen_at"] = item.get("last_seen_at") or item["first_seen_at"]
    item["search_text"] = build_search_text(item)
    return item


def parse_feed(xml_bytes: bytes, query: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    entries: list[dict] = []

    for item in root.findall("./channel/item")[:MAX_ITEMS_PER_QUERY]:
        raw_source = (item.findtext("source") or "").strip()
        source = canonicalize_source(raw_source)
        if not source:
            continue

        raw_title = (item.findtext("title") or "").strip()
        title = clean_title(raw_title, source)
        link = (item.findtext("link") or "").strip()
        description = clean_summary(
            strip_html(item.findtext("description") or ""),
            title,
            source,
        )
        if not is_relevant_article(title, description, [query]):
            continue

        published_at, published_label = parse_datetime(item.findtext("pubDate") or "")
        tags = content_tags(title, description)

        entries.append(
            {
                "id": article_id(source, title, published_at),
                "title": title,
                "source": source,
                "link": link,
                "summary": description,
                "published_at": published_at,
                "published_label": published_label,
                "matched_keywords": [query],
                "tags": tags,
            }
        )

    return entries


def load_existing_articles(
    output_path: Path = OUTPUT_PATH,
    payload: dict | None = None,
) -> list[dict]:
    payload = payload or load_existing_payload(output_path)
    if not payload:
        return []

    generated_at = payload.get("generated_at")
    articles = payload.get("articles") or []
    hydrated = [
        hydrate_article(article, default_seen_at=generated_at)
        for article in articles
    ]
    return [
        article
        for article in hydrated
        if is_relevant_article(
            article["title"],
            article["summary"],
            article["matched_keywords"],
        )
    ]


def merge_articles(
    existing_articles: Iterable[dict],
    fresh_articles: Iterable[dict],
    refreshed_at: str,
) -> list[dict]:
    merged: dict[str, dict] = {}

    for article in existing_articles:
        item = hydrate_article(article, default_seen_at=refreshed_at)
        merged[article_key(item)] = item

    for article in fresh_articles:
        item = hydrate_article(article, default_seen_at=refreshed_at)
        item["last_seen_at"] = refreshed_at
        key = article_key(item)
        existing = merged.get(key)

        if existing is None:
            item["first_seen_at"] = item.get("first_seen_at") or refreshed_at
            item["search_text"] = build_search_text(item)
            merged[key] = item
            continue

        existing["matched_keywords"] = sorted(
            set(existing["matched_keywords"]) | set(item["matched_keywords"])
        )
        existing["tags"] = sorted(set(existing["tags"]) | set(item["tags"]))
        existing["summary"] = existing["summary"] or item["summary"]
        existing["source"] = existing["source"] or item["source"]
        existing["title"] = existing["title"] or item["title"]
        existing["link"] = existing["link"] or item["link"]
        existing["published_label"] = existing["published_label"] or item["published_label"]
        existing["first_seen_at"] = existing.get("first_seen_at") or item["first_seen_at"]
        existing["last_seen_at"] = refreshed_at
        existing["search_text"] = build_search_text(existing)

    return sorted(
        merged.values(),
        key=lambda article: article["published_at"],
        reverse=True,
    )


def build_payload(
    articles: list[dict],
    *,
    generated_at: str,
    refresh_attempted_at: str,
    fetched_articles: int,
    new_articles: int,
    failed_queries: list[dict[str, str]],
) -> dict:
    sources = sorted({article["source"] for article in articles})
    tags = sorted({tag for article in articles for tag in article["tags"]})
    return {
        "project": PROJECT_NAME,
        "generated_at": generated_at,
        "refresh_attempted_at": refresh_attempted_at,
        "lookback_days": LOOKBACK_DAYS,
        "keywords": SEARCH_KEYWORDS,
        "trusted_sources": sorted(TRUSTED_SOURCES),
        "available_sources": sources,
        "available_tags": tags,
        "fetched_articles": fetched_articles,
        "new_articles": new_articles,
        "failed_query_count": len(failed_queries),
        "failed_queries": failed_queries,
        "total_articles": len(articles),
        "articles": articles,
    }


def refresh_news_index(output_path: Path = OUTPUT_PATH) -> dict:
    refreshed_at = iso_utc_now()
    existing_payload = load_existing_payload(output_path)
    existing_generated_at = existing_payload.get("generated_at")
    existing_articles = merge_articles(
        load_existing_articles(output_path, payload=existing_payload),
        [],
        refreshed_at,
    )
    collected: list[dict] = []
    failed_queries: list[dict[str, str]] = []

    for query in SEARCH_KEYWORDS:
        try:
            feed_bytes = fetch_feed(query)
            collected.extend(parse_feed(feed_bytes, query))
        except Exception as exc:  # pragma: no cover - operational fallback
            failed_queries.append({"query": query, "error": str(exc)})
            print(f"[warn] failed to fetch '{query}': {exc}", file=sys.stderr)

    collected.extend(build_manual_articles())
    fresh_articles = merge_articles([], collected, refreshed_at)
    existing_keys = {article_key(article) for article in existing_articles}
    new_articles = sum(
        1 for article in fresh_articles if article_key(article) not in existing_keys
    )
    articles = merge_articles(existing_articles, fresh_articles, refreshed_at)
    successful_fetch = len(failed_queries) < len(SEARCH_KEYWORDS)
    generated_at = refreshed_at if successful_fetch or not existing_generated_at else existing_generated_at
    payload = build_payload(
        articles,
        generated_at=generated_at,
        refresh_attempted_at=refreshed_at,
        fetched_articles=len(fresh_articles),
        new_articles=new_articles,
        failed_queries=failed_queries,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def main() -> int:
    payload = refresh_news_index()
    print(
        "Wrote "
        f"{payload['total_articles']} stored articles "
        f"({payload['new_articles']} new, {payload['fetched_articles']} fetched)"
        f" to {OUTPUT_PATH}"
    )
    if payload["failed_query_count"] >= len(SEARCH_KEYWORDS):
        print("All queries failed; dataset freshness was not updated.", file=sys.stderr)
        return 1
    if payload["failed_query_count"] > 0:
        print(
            f"{payload['failed_query_count']} queries failed during refresh.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
