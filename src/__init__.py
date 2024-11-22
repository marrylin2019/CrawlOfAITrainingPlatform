from pathlib import Path

from yarl import URL

PARAMIKO_LOG_PATH = Path('.tmp/paramiko.log').absolute()
DB_PATH = Path('data/hebnu_ai.db').absolute()
TMP_PATH = Path('.tmp').absolute()
# 任务释放小于3天的任务
KEEPALIVE_INTERVAL = 3 * 24 * 3600

STATUS_MAP = {
    1: '镜像下载中',
    2: '镜像打包中',
    3: '创建中',
    4: '运行中',
    5: '关机中',
    6: '已关机',
    7: '不可用',
    8: '释放中',
    9: '无卡模式',
    10: '正在开机',
    11: '重启中',
    12: '无卡模式开机中',
    13: '正在重置系统'
}

BASE_URL = URL('https://scm.hebtu.edu.cn')
DEFAULT_HEADERS = {
    'Sec-Ch-Ua': '"Not/A)Brand";v="99", "Google Chrome";v="115", "Chromium";v="115"',
    'Accept': 'application/json, text/plain, */*',
    'Language': 'Chinese',
    'Sec-Ch-Ua-Mobile': '?0',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Dest': 'empty',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'zh-CN,zh;q=0.9,en-CN;q=0.8,en;q=0.7,zh-TW;q=0.6',
}
