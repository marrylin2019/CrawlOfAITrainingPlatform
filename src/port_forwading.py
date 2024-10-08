import os
import socket

import paramiko
import pyperclip

from src import PARAMIKO_LOG_PATH
from src.persistence import DML
from src.utils import ForwardServer


def forward_tunnel(local_port, remote_host, remote_port, transport):
    server = ForwardServer(local_port, remote_host, remote_port, transport, socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.start()
    except KeyboardInterrupt:
        print("Port forwarding stopped.")
    finally:
        server.close()


def create_local_forwarding(task, pdbc: DML, client: paramiko.SSHClient):
    """
    创建本地ssh代理
    :param client:
    :param task:
    :param pdbc:
    :return:
    """
    # 清屏
    os.system("cls")
    # 使用库将密码复制到剪切板，不要写入换行
    pyperclip.copy(task.ssh_passwd)
    print(f"正在创建本地ssh端口转发\n当前实例：{task.note}({task.name})\n当前ssh密码：{task.ssh_passwd}(已复制到剪切板)")
    # 获取本地ssh代理端口
    local_port = pdbc.query_config('ssh_tunnel_port')
    if not local_port:
        ssh_tunnel_port = input("请输入本地ssh代理端口(建议设定在20000-40000)：")
        pdbc.update_config('ssh_tunnel_port', ssh_tunnel_port)
        local_port = ssh_tunnel_port

    try:
        # 创建SSH客户端
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # 自动添加未知主机密钥
        # 使用提供的凭据连接
        client.connect(task.agent_ip, username='root', password=task.ssh_passwd, port=int(task.ssh_port))
    except paramiko.ssh_exception.SSHException as e:
        exit(f"Failed to connect to agent: {e}\n详细信息请查看日志文件{PARAMIKO_LOG_PATH}")

    # 创建隧道
    try:
        forward_tunnel(
            local_port=int(local_port),
            remote_host='127.0.0.1',
            remote_port=int(task.ssh_port),
            transport=client.get_transport()
        )
        # 清屏
        os.system("cls")
        print("已创建本地ssh端口转发，请勿关闭此窗口！")
    except Exception as e:
        print(f"Failed to forward port: {e}")
    finally:
        client.close()
        exit("Port forwarding stopped.")
