import urllib.request
import os

# FTP 文件的完整 URL
ftp_url = "ftp://10.39.102.31/log//6102261604345142/2078_20260602210405_test.log"
# 保存到本地的文件名
local_filename = "2078_20260602210405_test.log"

print(f"正在从 {ftp_url} 下载文件...")

try:
    # 执行下载
    urllib.request.urlretrieve(ftp_url, local_filename)
    print(f"下载成功！文件已保存到当前目录: {os.path.abspath(local_filename)}")
except Exception as e:
    print(f"下载失败，错误信息: {e}")