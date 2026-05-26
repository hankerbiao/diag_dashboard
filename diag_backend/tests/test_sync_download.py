"""
测试脚本 - 独立测试三方数据下载，不依赖 FastAPI 启动
用法: python tests/test_sync_download.py
"""
import asyncio
import sys
import os

# 将项目根目录加入 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
from urllib.parse import urlencode

BASE_URL = "http://10.2.68.103"
HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/page/monitor_list.html",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}
COOKIES = {"rolePower": ""}


async def post(client: httpx.AsyncClient, path: str, data: dict) -> dict:
    body = urlencode({k: v for k, v in data.items() if v is not None})
    full_url = f"{BASE_URL}{path}"
    print(f"\n{'='*60}")
    print(f"[POST] {full_url}")
    print(f"[Body] {body[:300]}")
    resp = await client.post(path, content=body)
    print(f"[Status] {resp.status_code}")
    print(f"[Headers] {dict(resp.headers)}")
    print(f"[Body] {resp.text[:500]}")
    resp.raise_for_status()
    result = resp.json()
    data_len = len(result.get("data", [])) if isinstance(result, dict) else 0
    total = result.get("total", "?")
    print(f"[OK] {data_len} records, total={total}")
    return result


async def _fetch_servers(client: httpx.AsyncClient):
    """测试拉取服务器列表"""
    print("\n>>> Step 1: 拉取服务器列表")
    all_data = []
    page = 1
    limit = 100

    while True:
        resp = await post(client,
            "/stepsmanagement/monitor/queryTestingServers.action",
            data={"page": page, "limit": limit, "customerID": "", "salesReceipts": "", "orderID": "",
                  "serverSN": "", "serverState": "", "models": "", "productModels": "", "testItemName": ""}
        )
        batch = resp.get("data", [])
        all_data.extend(batch)
        print(f"  Page {page}: {len(batch)} records, running total={len(all_data)}")
        if len(batch) < limit:
            break
        page += 1

    print(f"\n>>> 服务器总数: {len(all_data)}")
    if all_data:
        print(f"  第一条 SN: {all_data[0].get('serverSN', 'N/A')}")
        print(f"  第一条 keys: {list(all_data[0].keys())[:10]}")
    return all_data


async def _fetch_details(client: httpx.AsyncClient, server_sn: str):
    """测试拉取某服务器的测试详情"""
    print(f"\n>>> Step 2: 拉取测试详情 (server={server_sn})")
    all_data = []
    start = 0
    limit = 500
    page = 1

    while True:
        resp = await post(client,
            "/stepsmanagement/resultInfo/queryTestList.action",
            data={"start": start, "limit": limit, "serverSN": server_sn, "customerID": ""}
        )
        batch = resp.get("data", [])
        all_data.extend(batch)
        print(f"  Page {page}: {len(batch)} records, running total={len(all_data)}")
        if len(batch) < limit:
            break
        start += limit
        page += 1

    print(f"\n>>> 测试详情总数: {len(all_data)}")
    if all_data:
        print(f"  第一条: {all_data[0]}")
    return all_data


async def main():
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=httpx.Timeout(30),
        headers=HEADERS,
        cookies=COOKIES,
    ) as client:
        # Step 1: 拉服务器
        servers = await _fetch_servers(client)

        # Step 2: 拉第一台服务器的详情
        if servers:
            first_sn = servers[0].get("serverSN", "")
            if first_sn:
                await _fetch_details(client, first_sn)

    print(f"\n{'='*60}")
    print("测试完成")


if __name__ == "__main__":
    asyncio.run(main())
