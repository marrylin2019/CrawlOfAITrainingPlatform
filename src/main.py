# 大致逻辑为：
# 直接使用保存的Token进行登录
#   若Token过期，则使用用户名密码登录
#       使用保存的publicKey加密密码
#           若登录成功，则保存Token
#           若登录失败，则获取新的publicKey并重试
import curses
import json
import re
from pathlib import PurePosixPath as Path
from time import sleep
from typing import Optional, Literal

import requests

from src import TMP_PATH, BASE_URL, DEFAULT_HEADERS
from src.display import table
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


def Request(
        method: Literal['GET', 'POST'] = 'GET',
        path: Path = Path(''),
        cookies: Optional[dict] = None,
        headers: Optional[dict] = None,
        data: Optional[str] = None
) -> requests.Response:
    url = BASE_URL.with_path(str(path))
    headers = {**DEFAULT_HEADERS, **headers} if headers else DEFAULT_HEADERS
    return requests.request(method, str(url), headers=headers, data=data, cookies=cookies)


def RequestDebug(
        method: Literal['GET', 'POST'] = 'GET',
        path: Path = Path(''),
        cookies: Optional[dict] = None,
        headers: Optional[dict] = None,
        data: Optional[str] = None
):
    url = BASE_URL.with_path(str(path))
    headers = {**DEFAULT_HEADERS, **headers} if headers else DEFAULT_HEADERS
    resp = requests.Request(method, str(url), headers=headers, data=data, cookies=cookies)
    prepared = requests.Session().prepare_request(resp)
    print(f"Method: {prepared.method}")
    print(f"URL: {prepared.url}")
    print(f"Headers: {prepared.headers}")
    print(f"Body: {prepared.body}")
    # return prepared.headers
    # return prepared
    # response = requests.Session().send(prepared)


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
            exit("未知的请求错误！")
    # 未发生错误
    # 把tasks信息写入数据库
    # print(resp['data']['records'])
    pdbc.insert_records(resp['data']['records'])
    return resp
    # print(resp.content.decode())


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


def SetUp(taskId: str, user, pdbc: DML, refresh_token: bool = False) -> bool:
    """
    开机，返回是否开机成功
    :param taskId:
    :param user:
    :param pdbc:
    :return:
    """
    token = user.token if not refresh_token else Login(user).token
    status = StatusStabilizer(taskId, user, pdbc)
    if status == 6:
        # 执行开机
        resp = Request(
            'GET',
            path=Path(f'api/airestserver/task/startContainer/{taskId}'),
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
                return SetUp(taskId, user, pdbc, True)
            else:
                # 未知的请求错误
                exit("未知的请求错误！")
        status = StatusStabilizer(taskId, user, pdbc)
        return status == 4
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
    if status == 4:
        # 执行开机
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
                return SetUp(taskId, user, pdbc, True)
            else:
                # 未知的请求错误
                exit("未知的请求错误！")
        status = StatusStabilizer(taskId, user, pdbc)
        return status == 6
    return False


def choose_account(pdbc: DML, mark: bool = True):
    """
    用户选择要使用的账户
    :return:
    """
    all_users = pdbc.query_all_users()
    if not all_users:
        # 不存在用户信息，需要录入
        account = input("输入用户名：\t")
        password = input("输入密码：\t")
        pdbc.insert_user(account, password)
        return choose_account(pdbc, False)
    else:
        # 存在用户信息，用户选择哪个用户登录
        # 存在默认用户，询问用户是否选择默认用户
        d_u = pdbc.query_config('default_user_account')
        if d_u:
            flag = input(f"是否使用默认用户{d_u}(Y/n): ").lower()
            for user in all_users:
                if user.account == d_u and (flag == '' or flag == 'y' or flag == 'yes'):
                    return user

        user = all_users[curses.wrapper(table, [user.to_dict() for user in all_users]) if mark else 0]
        # 设置默认用户
        flag = input(f"是否设置{user.account}为默认用户(Y/n): ").lower()
        if flag == '' or flag == 'y' or flag == 'yes':
            pdbc.update_config('default_user_account', user.account)
    return user


def choose_task(user, pdbc: DML):
    all_tasks = pdbc.query_all_record()
    if not all_tasks:
        GetTasks(user, pdbc)
        return choose_task(user, pdbc)
    else:
        d_t = pdbc.query_config('default_task_id')
        if d_t:
            flag = input(
                f"是否使用默认任务{[task.note for task in all_tasks if task.id == d_t][0]}({d_t})(Y/n): ").lower()
            for task in all_tasks:
                if task.id == d_t and (flag == '' or flag == 'y' or flag == 'yes'):
                    return task
        task = all_tasks[curses.wrapper(table, [task.to_risc_dict() for task in all_tasks])]
        # 设置默认任务
        flag = input(
            f"是否设置{[task.note for task in all_tasks if task.id == d_t][0]}({d_t})为默认任务(Y/n): ").lower()
        if flag == '' or flag == 'y' or flag == 'yes':
            pdbc.update_config('default_task_id', task.id)
    return task


import paramiko
import socket
import select
import threading


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


def forward_tunnel(local_port, remote_host, remote_port, transport):
    server = ForwardServer(local_port, remote_host, remote_port, transport, socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.start()
    except KeyboardInterrupt:
        print("Port forwarding stopped.")
    finally:
        server.close()


def create_local_forwarding(stdscr, task, pdbc: DML):
    """
    创建本地ssh代理
    :param task:
    :param pdbc:
    :return:
    """
    # 获取本地ssh代理端口
    local_port = pdbc.query_config('ssh_tunnel_port')
    if not local_port:
        ssh_tunnel_port = input("请输入本地ssh代理端口(建议设定在20000-40000)：")
        pdbc.update_config('ssh_tunnel_port', ssh_tunnel_port)
        local_port = ssh_tunnel_port

    # 创建SSH客户端
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # 自动添加未知主机密钥

    # 使用提供的凭据连接
    client.connect(task.agent_ip, username='root', password=task.ssh_passwd, port=int(task.ssh_port))

    # 创建隧道
    try:
        forward_tunnel(
            local_port=int(local_port),
            remote_host='127.0.0.1',
            remote_port=int(task.ssh_port),
            transport=client.get_transport()
        )
        stdscr.erase()
        stdscr.addstr(1, 0, 'SSH端口转发已建立，请务关闭本窗口！！！', curses.color_pair(1))
    except Exception as e:
        print(f"Failed to forward port: {e}")
    finally:
        client.close()


def main():
    s = requests.Session()
    # 移除默认的 Connection 头部
    if 'Connection' in s.headers:
        del s.headers['Connection']
    pdbc = DML()
    user = choose_account(pdbc)
    # 更新Tasks
    task = choose_task(user, pdbc)
    # ShutDown(task.id, user, pdbc)
    # 仅当状态为4（已关机）时，才执行开机操作
    if task.status == 4:
        SetUp(task.id, user, pdbc)
    # 启用本地ssh代理
    curses.wrapper(create_local_forwarding, task, pdbc)
    pass


if __name__ == '__main__':
    main()
