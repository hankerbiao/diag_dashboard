import urllib.request
import os

# FTP 文件的完整 URL
ftp_url = "ftp://10.30.14.12/log//6102202904362178/1059_20260602103945_result.log"
# 保存到本地的文件名
local_filename = "1059_20260602103945_result.log"

print(f"正在从 {ftp_url} 下载文件...")

try:
    # 执行下载
    urllib.request.urlretrieve(ftp_url, local_filename)
    print(f"下载成功！文件已保存到当前目录: {os.path.abspath(local_filename)}")
except Exception as e:
    print(f"下载失败，错误信息: {e}")