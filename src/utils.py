import json
import re
import socket
import threading
from datetime import datetime
from pathlib import PurePosixPath as Path
from time import sleep
from typing import Optional, Literal

import requests
import select

from src import TMP_PATH, BASE_URL, DEFAULT_HEADERS, MIN_KEEPALIVE_INTERVAL
from src.persistence import DML


class Login:
    TOKEN_URL_PATH = Path('api/user/userLogin/login')
    PUB_KEY_URL_PATH = Path('js/app.1710315129059.js')
    PUB_KEY_LOC_PATH = TMP_PATH / 'pub_key'

    def __init__(self, user):
        self.__account = user.account
        self.__password = user.password
        self.__encrypted_passwd: str = ''
        pass

    @property
    def token(self):
        self.__encrypt_passwd(self.__get_public_key())
        resp = Request(
            'POST',
            self.TOKEN_URL_PATH,
            headers={
                'Origin': str(BASE_URL),
                'Referer': str(BASE_URL / 'login'),
                'Content-Type': 'application/json',
            },
            data=json.dumps({
                "account": "wangsiqi@stu.hebtu.edu.cn",
                "password": self.__encrypted_passwd
            }, separators=(',', ':')), )
        return json.loads(resp.content)['data']['token']

    def __get_public_key(self) -> str:
        # 存在pub_key文件，文件中内容不为空且不需要新的公钥，则直接返回
        if self.PUB_KEY_LOC_PATH.exists():
            with open(self.PUB_KEY_LOC_PATH, 'r') as f:
                pub_key = f.read()
            if pub_key and len(pub_key) > 0:
                return pub_key
        # 否则，请求新的公钥
        resp = Request(path=self.PUB_KEY_URL_PATH)
        # 解析js文件，获取公钥
        pub_key = re.search(r'const\s*?publicKey\s*?=\s*?`(.*?)\s*?`;', resp.text, re.S).group(1)
        pub_key = '\n'.join(pub_key.split('\\n\n                  '))
        pub_key = f'-----BEGIN PUBLIC KEY-----\n{pub_key}\n-----END PUBLIC KEY-----'
        # 保存公钥
        with open(self.PUB_KEY_LOC_PATH, 'w') as f:
            f.write(pub_key)
        return pub_key

    def __encrypt_passwd(self, pub_key):
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_v1_5
        import base64

        rsa_key = RSA.import_key(pub_key)
        cipher = PKCS1_v1_5.new(rsa_key)
        encrypted_text = cipher.encrypt(self.__password.encode('utf-8'))
        self.__encrypted_passwd = base64.b64encode(encrypted_text).decode('utf-8')


class ForwardServer(socket.socket):
    def __init__(self, local_port, remote_host, remote_port, transport, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.bind(('127.0.0.1', local_port))
        self.listen(5)
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.transport = transport

    def handle(self, client_socket):
        try:
            chan = self.transport.open_channel('direct-tcpip', (self.remote_host, self.remote_port),
                                               client_socket.getpeername())
        except Exception as e:
            print(f"Failed to open channel: {e}")
            return

        while True:
            r, w, x = select.select([client_socket, chan], [], [])
            if client_socket in r:
                data = client_socket.recv(1024)
                if len(data) == 0:
                    break
                chan.send(data)
            if chan in r:
                data = chan.recv(1024)
                if len(data) == 0:
                    break
                client_socket.send(data)

        chan.close()
        client_socket.close()

    def start(self):
        while True:
            client_socket, client_addr = self.accept()
            threading.Thread(target=self.handle, args=(client_socket,)).start()


def Request(
        method: Literal['GET', 'POST'] = 'GET',
        path: Path = Path(''),
        cookies: Optional[dict] = None,
        headers: Optional[dict] = None,
        data: Optional[str] = None
) -> requests.Response:
    url = BASE_URL.with_path(str(path))
    headers = {**DEFAULT_HEADERS, **headers} if headers else DEFAULT_HEADERS
    try:
        return requests.request(method, str(url), headers=headers, data=data, cookies=cookies)
    except TimeoutError:
        exit("网络连接异常！请检查网络连接！")


def GetTasks(user, pdbc: DML, force_refresh_token: bool = False) -> dict:
    """
    失败的返回值
    {'msg': '不合法的令牌!', 'code': '-2', 'data': ''}
    :param force_refresh_token:
    :param pdbc:
    :param user:
    :return:
    """
    # 确保token存在
    token = user.token if user.token and not force_refresh_token else Login(user).token
    # token写入数据库
    pdbc.update_user_token(user.account, token)

    resp = Request(
        'POST',
        path=Path('api/airestserver/task/taskPage'),
        headers={
            'Front-Token': token,
            'Origin': str(BASE_URL),
            'Referer': str(BASE_URL / 'ai-center/my-task'),
            'Content-Type': 'application/json',
        },
        cookies={
            'token': token
        },
        data=json.dumps({
            "taskId": "",
            "calculateDeviceId": "",
            "costType": "",
            "userId": "",
            "pageReq": {
                "pageNum": 1,
                "pageSize": 10
            },
            "taskName": "",
            "status": ""
        }, separators=(',', ':'))
    )
    resp = json.loads(resp.content)
    # 发生错误
    if int(resp['code']) < 0:
        # token失效，重新获取token后重试
        if int(resp['code']) == -2:
            return GetTasks(user, pdbc, True)
        else:
            # 未知的请求错误
            exit("请求异常！服务器响应信息：" + resp['msg'])
    # 未发生错误
    # 把tasks信息写入数据库
    # print(resp['data']['records'])
    # 删除数据库中不在当前任务列表中的任务
    missing_tasks = [task for task in pdbc.query_all_record() if
                     task.id not in [record['id'] for record in resp['data']['records']]]
    print('\n'.join([f"任务[{task.note}]({task.name})缺失，已在数据库中删除！" for task in missing_tasks]))
    pdbc.delete_records([task.id for task in missing_tasks])
    # 删除默认任务
    default_config_task = pdbc.query_config('default_task_id')
    if default_config_task and default_config_task not in [record['id'] for record in resp['data']['records']]:
        pdbc.update_config('default_task_id', '')
    pdbc.insert_records(resp['data']['records'])
    return resp


def StatusStabilizer(taskId: str, user, pdbc: DML, times: int = 0) -> int:
    """
    状态为1: '镜像下载中', 2: '镜像打包中', 3: '创建中', 5: '关机中', 7: '不可用', 8: '释放中', 10: '正在开机',
    11: '重启中', 12: '无卡模式开机中', 13: '正在重置系统'时，进行状态稳定化处理
    :param times:
    :param user:
    :param taskId:
    :param pdbc:
    :return:
    """
    UNSTABLE_STATUS = [1, 2, 3, 5, 7, 8, 10, 11, 12, 13]
    GetTasks(user, pdbc)
    if int(pdbc.query_record(taskId).status) in UNSTABLE_STATUS:
        if times > 6:
            exit("状态稳定化失败，请检查网络连接！若网络连接正常，请联系管理员！")
        sleep(5)
        return StatusStabilizer(taskId, user, pdbc, times + 1)
    return int(pdbc.query_record(taskId).status)


def SetUp(taskId: str, user, pdbc: DML, refresh_token: bool = False, no_gpu_mode=False) -> bool:
    """
    开机，返回是否开机成功
    :param no_gpu_mode:
    :param refresh_token:
    :param taskId:
    :param user:
    :param pdbc:
    :return:
    """
    token = user.token if not refresh_token else Login(user).token
    status = StatusStabilizer(taskId, user, pdbc)
    # 仅当状态为6（已关机）时，才执行开机操作
    if status == 6:
        # 执行开机
        resp = Request(
            'GET',
            # 根据是否使用无卡模式选择不同的开机接口
            path=Path(f'api/airestserver/task/{"notGpuModel" if no_gpu_mode else "startContainer"}/{taskId}'),
            headers={
                'Front-Token': token,
                'Referer': str(BASE_URL / 'ai-center/my-task'),
            },
            cookies={
                'token': token
            }
        )
        resp = json.loads(resp.content)
        # 发生错误
        if int(resp['code']) < 0:
            # token失效，重新获取token后重试
            if int(resp['code']) == -2:
                return SetUp(taskId, user, pdbc, refresh_token=True)
            else:
                # 未知的请求错误
                exit("请求异常！服务器响应信息：" + resp['msg'])
        status = StatusStabilizer(taskId, user, pdbc)
        if status == 4:
            GetTasks(user, pdbc)
            return True
        else:
            return False
    return False


def ShutDown(taskId: str, user, pdbc: DML, refresh_token: bool = False) -> bool:
    """
    关机，返回是否关机成功
    :param refresh_token:
    :param user:
    :param taskId:
    :param pdbc:
    :return:
    """
    token = user.token if not refresh_token else Login(user).token
    status = StatusStabilizer(taskId, user, pdbc)
    # 仅当状态为4（运行中）或9（无卡模式）时，才执行关机操作
    if status == 4 or status == 9:
        # 执行关机
        resp = Request(
            'GET',
            path=Path(f'api/airestserver/task/killContainer/{taskId}'),
            headers={
                'Front-Token': token,
                'Referer': str(BASE_URL / 'ai-center/my-task'),
            },
            cookies={
                'token': token
            }
        )
        resp = json.loads(resp.content)
        # 发生错误
        if int(resp['code']) < 0:
            # token失效，重新获取token后重试
            if int(resp['code']) == -2:
                return ShutDown(taskId, user, pdbc, True)
            else:
                # 未知的请求错误
                exit("请求异常！服务器响应信息：" + resp['msg'])
        status = StatusStabilizer(taskId, user, pdbc)
        if status == 6:
            GetTasks(user, pdbc)
            return True
        else:
            return False
    return False


def ShutDownAll(user, pdbc: DML):
    GetTasks(user, pdbc)
    tasks = pdbc.query_all_record()
    for task in tasks:
        ShutDown(task.id, user, pdbc)
    return "已关机所有运行中的任务！"


def CheckStatus(user, pdbc: DML, for_all: bool = False, task: Optional = None):
    if for_all:
        GetTasks(user, pdbc)
        tasks = pdbc.query_all_record()
        return '\n'.join([f"任务[{task.note}]({task.name})状态为：{task.str_status}" for task in tasks])
    elif task:
        return f"任务[{task.note}]({task.name})状态为：{task.str_status}"
    else:
        return "请指定task！"


def KeepAlive(user, pdbc: DML):
    """
    将临近过期的实例（任务）开机并关机以延长实例（任务）的有效期
    :param user:
    :param pdbc:
    :return:
    """
    # 更新任务状态
    GetTasks(user, pdbc)

    tasks = pdbc.query_all_record()
    kept_tasks = []
    for task in tasks:
        if task.release_time is not None:
            release_time = int(datetime.strptime(task.release_time, '%Y-%m-%d %H:%M:%S').timestamp()) - int(
                datetime.now().timestamp())
            if release_time < MIN_KEEPALIVE_INTERVAL:
                kept_tasks.append(task)
                SetUp(task.id, user, pdbc, no_gpu_mode=True)
                StatusStabilizer(task.id, user, pdbc)
                ShutDown(task.id, user, pdbc)
    if len(kept_tasks) == 0:
        return "没有需要续期的任务！"
    else:
        # 更新任务状态
        GetTasks(user, pdbc)
        return f"已续期以下任务：\n" + '\n'.join([f"[{task.note}]({task.name})" for task in kept_tasks])


def QBalance(user) -> str:
    """
    查询余额
    :param user:
    :return
    """
    resp = Request("POST", Path("api/user/user/account/balanceCoupon"), headers={
        'Front-Token': user.token,
        'Referer': str(BASE_URL / 'front-user/homepage'),
        'Content-Type': 'application/json',
    }, cookies={
        'token': user.token
    }, data=json.dumps({"productType": 1})).text

    try:
        resp = json.loads(resp)
    except json.JSONDecodeError:
        raise Exception("请求异常！服务器响应信息：" + resp)
    if not int(resp['code']) == 0:
        raise Exception("请求异常！服务器响应信息：" + resp['msg'])
    return f"账户余额：{resp['data']['balance']}元"
