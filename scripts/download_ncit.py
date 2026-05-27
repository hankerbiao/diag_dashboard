import os
import requests

# ================= 配置信息 =================
BASE_URL = "http://ncit.cooacloud.com/shared_docs/"
DOWNLOAD_DIR = "downloaded_docs"

# ❗请将这里替换为你刚刚从浏览器抓取的最新 Cookie
COOKIE = "nc_portal=.eJwljjGOQzEIBe_iOgXmYfzJZSJsQLvtT1Kt9u75UsoZaaT5a4868_nT7q_znbf2-I12bzArxgLWIYt9ujL5sWPCV0hBfKCXGId0bB45yOLYA0lT0meniwh22SLTJbQldIe60RiC2GSJoeprTatgpepFkJ77wOjtGnk_8_zeqGXxlYnDO-amngxNbv8fBBk0jQ.ahZLEA.QZa0PPZeghn5xsnRrtoRHlk6Uco"

# 强化版请求头，完全模拟浏览器发起 Ajax 表单请求
HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",  # 明确声明是表单数据
    "Cookie": COOKIE,
    "Origin": "http://ncit.cooacloud.com",
    "Referer": "http://ncit.cooacloud.com/shared_docs/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"  # 很多后台接口强校验这个字段来判断是不是真正的 Ajax 请求
}


# ============================================

def main():
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
        print(f"📁 已创建下载目录: {DOWNLOAD_DIR}")

    session = requests.Session()
    session.headers.update(HEADERS)

    print("\n🔍 正在获取文档列表...")

    # 这里的字典配合 requests 的 data 参数，会自动转换为:
    # action=get_docs&payload={"selected_node":"root","query":""}&sorters=[]
    post_data = {
        "action": "get_docs",
        "payload": '{"selected_node":"root","query":""}',
        "sorters": '[]'
    }

    try:
        # 发送表单数据，使用 data 参数
        response_list = session.post(BASE_URL, data=post_data)

        # 打印一下实际发送出去的请求头和请求体，方便排错
        # print("请求头: ", response_list.request.headers)
        # print("请求体: ", response_list.request.body)

        response_list.raise_for_status()
        list_json = response_list.json()
        docs_list = list_json.get("data", [])

    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 错误: {e}")
        print(f"服务器返回内容: {response_list.text}")
        return
    except Exception as e:
        print(f"❌ 获取文档列表失败: {e}")
        return

    if not docs_list:
        print("未获取到任何文档数据，请检查 Cookie 是否有效。")
        return

    print(f"✅ 共发现 {len(docs_list)} 个文档，准备提取文件详情...\n")

    # 后续获取详情和下载逻辑保持不变
    for doc in docs_list:
        doc_id = doc.get("id")
        doc_title = doc.get("title", "未知标题")

        if not doc_id:
            continue

        print(f"📄 正在处理文档: {doc_title} (doc_id: {doc_id})")

        doc_detail_url = f"{BASE_URL}?action=get_doc&doc_id={doc_id}"

        try:
            response_detail = session.get(doc_detail_url)
            response_detail.raise_for_status()
            detail_data = response_detail.json().get("data", {})
        except Exception as e:
            print(f"  ❌ 获取文档详情失败: {e}")
            continue

        files = detail_data.get("files", [])
        if not files:
            print("  ⚠️ 该文档下没有附件。")
            continue

        for file_info in files:
            file_id = file_info.get("id")
            filename = file_info.get("filename", f"unknown_file_{file_id}")

            if not file_id:
                continue

            download_url = f"{BASE_URL}download?file_id={file_id}"
            save_path = os.path.join(DOWNLOAD_DIR, filename)

            print(f"  ⬇️ 正在下载: {filename} (file_id: {file_id})...")

            try:
                response_download = session.get(download_url, stream=True)
                response_download.raise_for_status()

                with open(save_path, 'wb') as f:
                    for chunk in response_download.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                print(f"  ✅ 下载成功，已保存至: {save_path}")
            except Exception as e:
                print(f"  ❌ 下载文件失败: {e}")

    print("\n🎉 所有任务处理完毕！")


if __name__ == "__main__":
    main()