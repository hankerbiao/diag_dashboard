"""MES 维修数据同步工具 - 支持全量同步和日级增量同步

使用方法:
    # 全年全量同步
    python sync_mes.py

    # 指定年份同步
    python sync_mes.py --year 2026

    # 单月全量同步
    python sync_mes.py --month 3

    # 单日增量同步
    python sync_mes.py --sync-day 2026-05-26

    # 最近 N 天增量同步
    python sync_mes.py --sync-recent 7

    # 查看同步状态
    python sync_mes.py --status

    # 查询维修数据
    python sync_mes.py --query
    python sync_mes.py --query --chassis CN123456789
    python sync_mes.py --query --defect PCIE
    python sync_mes.py --query --limit 20

    # 重置同步状态
    python sync_mes.py --reset 2026-05       # 重置整月
    python sync_mes.py --reset 2026-05-26    # 重置单日

数据存储:
    - MongoDB: diag_ai.maintenance_records
    - 本地文件: ./data/maintenance_records/YYYY-MM/
    - RAGFlow: 知识库文档
"""
import os, asyncio, calendar
from datetime import datetime, timedelta
from typing import Optional

import requests, httpx
from pymongo import MongoClient
from tqdm import tqdm

# ══════════════════════════════════════════════════════════════════
# 配置
# ══════════════════════════════════════════════════════════════════
MES_API = "http://10.8.101.49:9991/api/QMS/getQMSList"
MES_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiIzNTY4IiwiaWF0IjoiMTc3OTg0NDE3MiIsIm5iZiI6MTc3OTg0NDE3MiwiZXhwIjoiMTc3OTg1MTM3MiIsImlzcyI6InZvbC5jb3JlLm93bmVyIiwiYXVkIjoidm9sLmNvcmUifQ.emtq-lGeXeXIGr2JyAFthbmX80rJOg-2ShUk1LAMBnE",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}
MONGO_URI, MONGO_DB = "mongodb://10.17.154.252:27018", "diag_ai"
RAGFLOW_URL, RAGFLOW_KEY, DATASET_ID = "http://10.17.150.235:8080", "ragflow-7tTny1FXkDM2gLS3wawIS9YjKmR_hOBaRe02_sCYs8E", "f8060b12597e11f1948453f09d4804bb"
BATCH_SIZE, DATA_DIR = 100, "./data/maintenance_records"


# ══════════════════════════════════════════════════════════════════
# 数据库操作
# ══════════════════════════════════════════════════════════════════
def _db():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    return db

def _sync_col():
    col = _db()["sync_job_records"]
    col.create_index([("sync_type", 1), ("month_key", 1)], unique=True)
    return col

def _maint_col():
    col = _db()["maintenance_records"]
    col.create_index([("s_CHASSISNO", 1)])
    col.create_index([("s_WMSLOCATIONNAME", 1), ("s_CHASSISNO", 1), ("nG_TXNDATE", 1)], unique=True)
    return col


# ══════════════════════════════════════════════════════════════════
# 日期工具
# ══════════════════════════════════════════════════════════════════
def _month_range(y, m):
    """(start, end) 格式 YYYYMMDDHHMMSS"""
    start = f"{y}{m:02d}01000000"
    last_day = calendar.monthrange(y, m)[1]
    end = f"{y}{m:02d}{last_day}235959"
    return start, end

def _day_range(d):
    """单日范围"""
    return d.strftime("%Y%m%d000000"), d.strftime("%Y%m%d235959")

def _get_pending_days(year):
    """获取需同步的日期（昨天截止）"""
    today = datetime.now()
    end = today - timedelta(days=1)
    return [datetime(year, 1, 1) + timedelta(days=i) for i in range((end - datetime(year, 1, 1)).days + 1)]


# ══════════════════════════════════════════════════════════════════
# 数据获取
# ══════════════════════════════════════════════════════════════════
MES_BASES = ["9000", "D000"]  # 多区域配置

def _fetch(start: str, end: str) -> list:
    """获取 MES 数据（支持多区域）"""
    all_data = []

    for base in MES_BASES:
        url = f"{MES_API}?Base={base}&keyType=k1&keyValue=null&firstappear=null&secondappear=null&FromLot=null&issueTime1={start}&issueTime2={end}"
        print(f"  📡 POST [Base={base}] {url}")
        try:
            resp = requests.post(url, headers=MES_HEADERS, timeout=60)
            resp.raise_for_status()
            data = resp.json().get('data', [])
            print(f"     ← {resp.status_code} | Base={base}: {len(data)} 条")
            all_data.extend(data)
        except Exception as e:
            print(f"     ✗ Base={base} 请求失败: {e}")

    print(f"  ✓ 共获取 {len(all_data)} 条记录")
    return all_data

def _check_ragflow_docs() -> set:
    """获取 RAGFlow 已有的文档名"""
    try:
        url = f"{RAGFLOW_URL}/api/v1/datasets/{DATASET_ID}/documents?page=1&page_size=1000"
        resp = requests.get(url, headers={"Authorization": f"Bearer {RAGFLOW_KEY}"}, timeout=30)
        body = resp.json()
        if body.get("code") == 0:
            docs = body.get("data", {})
            if isinstance(docs, dict):
                docs = docs.get("docs", docs.get("items", []))
            return {d.get("name", "") for d in docs}
    except:
        pass
    return set()


# ══════════════════════════════════════════════════════════════════
# 数据格式化
# ══════════════════════════════════════════════════════════════════
def _format_record(d: dict) -> str:
    g = d.get
    return f"""## 维修工单

### 设备信息
设备位置: {g('s_WMSLOCATIONNAME')} | 产品家族: {g('productfamilyname')}
机箱序列号: {g('s_CHASSISNO')} | 产品名称: {g('productname')} | 产品描述: {g('description')}

### NG 工序
工序: {g('nG_SPECNAME')} | 操作员: {g('nG_FULLNAME')} | 时间: {g('nG_TXNDATE')}

### 缺陷描述
二级缺陷: {g('s_2NDDEFECTAPPEARNAME')} | 三级缺陷: {g('s_3RDDEFECTAPPEARNAME')}
缺陷类别: {g('s_DEFECTCATEGORYNAME')} | 二次缺陷: {g('s_TWICEDEFECTFLAGNAME') or '否'}

### 维修处理
维修员: {g('r_FULLNAME')} | 组长: {g('d_FULLNAME')} | 完成时间: {g('r_TXNDATE')}
处理方式: {g('s_3RDLOSSCODENAME')} | 涉及组件: {g('s_INVOLVEDCOMPONENTNAME')}
维修描述: {g('s_DESCRIPTION') or g('faulT_DESCRIPTION')}

### 物料信息
坏件: 序列号 {g('b_SG')} | 物料号 {g('b_MATERIAL')}
替换件: 序列号 {g('a_BG')} | 物料号 {g('a_MATERIAL')}

### 复判结果
复判人员: {g('s_ReJudge')} | 结果: {g('s_ReJudgeResult')}
问题描述: {g('s_ReJudgeProblemDesc')} | 备注: {g('s_ReJudgeNote')}
"""

def _format_batch(data_list: list, batch_num: int, y: int, m: int) -> str:
    lines = [f"# 维修工单批次 #{batch_num} ({y}-{m:02d}) ({len(data_list)} 条)\n"]
    lines += [_format_record(d) + "\n" for d in data_list]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# 存储操作
# ══════════════════════════════════════════════════════════════════
def _save_local(content: str, y: int, m: int, name: str) -> str:
    path = os.path.join(DATA_DIR, f"{y}-{m:02d}")
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, name), 'w', encoding='utf-8') as f:
        f.write(content)
    return path

def _save_mongo(data_list: list, y: int, m: int) -> int:
    if not data_list:
        return 0
    col = _maint_col()
    ts = datetime.now()
    count = 0
    for d in data_list:
        doc = {**d, "sync_year": y, "sync_month": f"{y}-{m:02d}", "synced_at": ts}
        try:
            if col.update_one(
                {"s_WMSLOCATIONNAME": d.get("s_WMSLOCATIONNAME"),
                 "s_CHASSISNO": d.get("s_CHASSISNO"),
                 "nG_TXNDATE": d.get("nG_TXNDATE")},
                {"$set": doc}, upsert=True
            ).upserted_id:
                count += 1
        except:
            pass
    return count

async def _upload_ragflow(path: str, name: str) -> Optional[str]:
    try:
        with open(path, 'rb') as f:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{RAGFLOW_URL}/api/v1/datasets/{DATASET_ID}/documents",
                    headers={"Authorization": f"Bearer {RAGFLOW_KEY}"},
                    files={"file": (name, f, "application/octet-stream")}
                )
        body = resp.json()
        if body.get("code") == 0:
            return body.get("data", [{}])[0].get("id", "")
    except Exception as e:
        print(f"    ✗ {name} 上传失败: {e}")
    return None

async def _trigger_parse(doc_ids: list):
    if not doc_ids:
        return
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{RAGFLOW_URL}/api/v1/datasets/{DATASET_ID}/chunks",
                headers={"Authorization": f"Bearer {RAGFLOW_KEY}", "Content-Type": "application/json"},
                json={"document_ids": doc_ids}
            )
        if resp.json().get("code") != 0:
            print(f"    ⚠ 解析触发失败")
    except:
        pass


# ══════════════════════════════════════════════════════════════════
# 同步核心
# ══════════════════════════════════════════════════════════════════
async def _sync_data(data_list: list, y: int, m: int, label: str):
    """通用数据同步：本地 + MongoDB + RAGFlow"""
    if not data_list:
        return {"count": 0, "docs": 0}

    # 本地文件
    dir_path = _save_local(_format_batch(data_list, 1, y, m), y, m, f"maintenance_{y}{m:02d}.txt")
    count = len(data_list)
    print(f"    ✓ 本地文件: {dir_path}/")

    # MongoDB
    mongo_count = _save_mongo(data_list, y, m)
    print(f"    ✓ MongoDB: 新增 {mongo_count} 条")

    # RAGFlow
    existing = _check_ragflow_docs()
    files = [f for f in os.listdir(dir_path) if f.endswith('.txt') and f not in existing]
    doc_ids = []
    if files:
        print(f"    上传 RAGFlow ({len(files)} 个文件)...")
        for fn in tqdm(files, desc="      上传", unit="file", ncols=70):
            doc_id = await _upload_ragflow(os.path.join(dir_path, fn), fn)
            if doc_id:
                doc_ids.append(doc_id)
        await _trigger_parse(doc_ids)
    else:
        print(f"    ✓ RAGFlow 无需上传")

    return {"count": count, "docs": len(doc_ids), "mongo": mongo_count}


async def _sync_period(start_date: str, end_date: str, y: int, m: int, label: str):
    """同步指定时间范围的数据"""
    print(f"\n{'─'*50}\n📥 {label}\n{'─'*50}")
    print(f"  调用 MES API: {start_date[:8]} ~ {end_date[:8]}")

    data = _fetch(start_date, end_date)
    print(f"  ✓ 获取到 {len(data)} 条记录")

    if not data:
        return {"status": "completed", "count": 0}

    result = await _sync_data(data, y, m, label)
    print(f"  ✓ {label} 完成: {result['count']} 条")

    # 记录同步日期
    _sync_col().update_one(
        {"sync_type": "mes_maintenance", "month_key": f"{y}-{m:02d}"},
        {"$addToSet": {"synced_dates": start_date[:10]}}, upsert=True
    )

    return {"status": "completed", **result}


# ══════════════════════════════════════════════════════════════════
# 主功能函数
# ══════════════════════════════════════════════════════════════════
async def sync_month(y: int, m: int):
    """全量同步单月"""
    s, e = _month_range(y, m)
    await _sync_period(s, e, y, m, f"{y}-{m:02d} 月")

async def sync_day(d: datetime):
    """增量同步单日"""
    s, e = _day_range(d)
    label = d.strftime("%Y-%m-%d")

    # 检查是否已同步
    synced = {date for r in _sync_col().find({}, {"synced_dates": 1}) for date in r.get("synced_dates", [])}
    if label in synced:
        print(f"  ⏭️ {label} 已同步，跳过")
        return {"status": "skipped"}

    result = await _sync_period(s, e, d.year, d.month, label)
    result["date"] = label
    return result

async def sync_recent(days: int = 7):
    """增量同步最近 N 天（一次性请求 + 按日分组）"""
    print(f"\n{'='*50}\n🚀 增量同步最近 {days} 天\n{'='*50}")

    today = datetime.now()
    start = (today - timedelta(days=days)).replace(hour=0, minute=0, second=0)
    end = (today - timedelta(days=1)).replace(hour=23, minute=59, second=59)

    # 一次性请求所有数据
    print(f"  批量请求: {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}")
    all_data = _fetch(start.strftime("%Y%m%d%H%M%S"), end.strftime("%Y%m%d%H%M%S"))
    print(f"  ✓ 获取 {len(all_data)} 条记录")

    if not all_data:
        print("  无数据")
        return

    # 按日期分组
    from collections import defaultdict
    by_date = defaultdict(list)
    for d in all_data:
        ng_date = d.get('nG_TXNDATE', '')[:10]  # 取日期部分
        by_date[ng_date].append(d)

    # 获取已同步的日期
    synced = {date for r in _sync_col().find({}, {"synced_dates": 1}) for date in r.get("synced_dates", [])}

    # 统计
    total_count = sum(len(v) for v in by_date.values())
    new_count = sum(len(v) for k, v in by_date.items() if k not in synced)
    print(f"  按日期分布: {len(by_date)} 天有数据, 新数据 {new_count} 条")

    # 同步新日期的数据
    count, new_days = 0, 0
    for date_str in tqdm(sorted(by_date.keys()), desc="  处理日期", unit="天", ncols=70):
        if date_str in synced:
            continue

        data = by_date[date_str]
        y, m, d = map(int, date_str.split('-'))

        # 存储
        _save_mongo(data, y, m)
        dir_path = _save_local(_format_batch(data, 1, y, m), y, m, f"maintenance_{date_str.replace('-', '')}.txt")

        # 上传 RAGFlow
        existing = _check_ragflow_docs()
        files = [f for f in os.listdir(dir_path) if f.endswith('.txt') and f not in existing]
        for fn in files:
            doc_id = await _upload_ragflow(os.path.join(dir_path, fn), fn)

        # 记录同步日期
        _sync_col().update_one(
            {"sync_type": "mes_maintenance", "month_key": f"{y}-{m:02d}"},
            {"$addToSet": {"synced_dates": date_str}}, upsert=True
        )

        count += len(data)
        new_days += 1

    print(f"\n📊 完成: {new_days} 天, {count} 条新记录")

async def sync_full(year: int = None):
    """全年全量同步"""
    year = year or datetime.now().year
    print(f"\n{'='*50}\n🚀 {year} 年全量同步\n{'='*50}")

    # 获取所有已同步的月份（一次查询）
    synced_months = {r["month_key"] for r in _sync_col().find({}, {"month_key": 1})}

    # 按月汇总所有日期，收集待同步月份
    all_days = _get_pending_days(year)
    pending_months = set()
    for d in all_days:
        label = d.strftime("%Y-%m")
        if label not in synced_months:
            pending_months.add((d.year, d.month))

    pending_months = sorted(pending_months)
    print(f"待同步月份: {len(pending_months)} 个")
    for y, m in pending_months:
        await sync_month(y, m)

def show_status():
    """显示同步状态"""
    print(f"\n{'='*50}\n📋 同步状态\n{'='*50}")
    col = _sync_col()
    for r in col.find({"sync_type": "mes_maintenance"}).sort("month_key", 1):
        icon = "✓" if r["status"] == "completed" else "✗"
        print(f"  {icon} {r['month_key']}: {r['status']} ({r.get('record_count', 0)} 条)")

    maint = _maint_col()
    total = maint.count_documents({})
    print(f"\n📊 MongoDB 总记录: {total} 条")

def query(chassis: str = None, defect: str = None, limit: int = 10):
    """查询维修数据"""
    print(f"\n{'='*50}\n🔍 维修数据查询\n{'='*50}")
    col = _maint_col()
    q = {}
    if chassis: q["s_CHASSISNO"] = chassis
    if defect: q["s_3RDDEFECTAPPEARNAME"] = {"$regex": defect}

    for i, doc in enumerate(col.find(q).sort("nG_TXNDATE", -1).limit(limit), 1):
        print(f"\n  [{i}] {doc.get('s_WMSLOCATIONNAME')} - {doc.get('s_CHASSISNO')}")
        print(f"      缺陷: {doc.get('s_3RDDEFECTAPPEARNAME')}")
        print(f"      维修: {doc.get('s_3RDLOSSCODENAME')} - {doc.get('r_FULLNAME')}")

def reset(target: str):
    """重置同步状态"""
    col = _sync_col()
    if len(target) == 10:  # YYYY-MM-DD
        col.update_one({"sync_type": "mes_maintenance"}, {"$pull": {"synced_dates": target}})
        print(f"✓ 已移除同步记录: {target}")
    else:  # YYYY-MM
        col.delete_one({"sync_type": "mes_maintenance", "month_key": target})
        print(f"✓ 已重置: {target}")


# ══════════════════════════════════════════════════════════════════
# 命令行入口
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="MES 维修数据同步工具")
    p.add_argument("--year", type=int, default=datetime.now().year)
    p.add_argument("--month", type=int)
    p.add_argument("--status", action="store_true")
    p.add_argument("--reset", type=str)
    p.add_argument("--query", action="store_true")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--chassis", type=str)
    p.add_argument("--defect", type=str)
    p.add_argument("--sync-day", type=str)
    p.add_argument("--sync-recent", type=int, metavar="N")
    args = p.parse_args()

    if args.query: query(args.chassis, args.defect, args.limit)
    elif args.status: show_status()
    elif args.reset: reset(args.reset)
    elif args.sync_day: asyncio.run(sync_day(datetime.strptime(args.sync_day, "%Y-%m-%d")))
    elif args.sync_recent: asyncio.run(sync_recent(args.sync_recent))
    elif args.month: asyncio.run(sync_month(args.year, args.month))
    else: asyncio.run(sync_full(args.year))