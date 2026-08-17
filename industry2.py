# -*- coding: utf-8 -*-
"""New industry/thematic universe (70 ETFs) vs SPY, grouped for the panel."""

BENCH = "SPY"
GROUPS = {
    "科技/AI": {"SMH": "半导体", "IGV": "软件", "CIBR": "网络安全", "SKYY": "云计算",
               "FDN": "互联网", "BOTZ": "机器人AI", "AIQ": "人工智能", "QTUM": "量子计算",
               "SOCL": "社交媒体", "ESPO": "电竞游戏", "XTL": "电信", "IPAY": "支付科技",
               "FINX": "金融科技"},
    "金融": {"KRE": "区域银行", "KBE": "银行", "IAI": "券商", "KIE": "保险",
            "PSP": "私募股权", "BIZD": "商业发展BDC"},
    "医疗": {"XBI": "生物科技", "XPH": "制药", "IHI": "医疗器械", "IHF": "医疗服务",
            "XHS": "医疗服务2", "XHE": "医疗设备", "IDNA": "基因组", "HTEC": "医疗科技"},
    "工业国防运输": {"XAR": "航空国防", "IYT": "运输", "JETS": "航空", "PAVE": "基建",
                "AIRR": "工业复兴", "BOAT": "航运", "PHO": "水资源"},
    "消费": {"XRT": "零售", "IBUY": "网购", "XHB": "住宅建筑", "PEJ": "休闲娱乐",
            "AWAY": "旅游", "CARZ": "汽车", "DRIV": "自驾电动", "PBJ": "食品饮料", "IYK": "必需消费"},
    "能源电力": {"XOP": "油气勘探", "OIH": "油服", "FCG": "天然气", "AMLP": "能源管道",
              "TAN": "太阳能", "ICLN": "清洁能源", "URA": "铀矿", "RNRG": "可再生能源",
              "UTES": "公用事业", "GRID": "智能电网"},
    "材料金属农业": {"XME": "金属矿", "SLX": "钢铁", "COPX": "铜矿", "GDX": "黄金矿",
                "SIL": "白银矿", "REMX": "稀土", "LIT": "锂电", "WOOD": "木材", "MOO": "农业"},
    "房地产REIT": {"SRVR": "数据中心REIT", "REZ": "住宅REIT", "INDS": "工业REIT",
                 "NETL": "净租赁REIT", "REM": "抵押REIT", "IYR": "地产"},
    "其他": {"PXQ": "网络设备", "PBS": "媒体"},
}
SECTORS = {t: n for g in GROUPS.values() for t, n in g.items()}
G_OF = {t: g for g, ts in GROUPS.items() for t in ts}


def all_tickers():
    return list(SECTORS.keys())
