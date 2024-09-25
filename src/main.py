import argparse
import curses
import sys

import paramiko
import requests

from src.display import table
from src.persistence import DML
from src.port_forwading import create_local_forwarding
from src.utils import GetTasks, ShutDown, SetUp


def choose_account(pdbc: DML, using_default=False, mark: bool = True):
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
        return choose_account(pdbc, mark=False)
    else:
        # 存在用户信息，用户选择哪个用户登录
        # 存在默认用户，询问用户是否选择默认用户
        d_u = pdbc.query_config('default_user_account')
        if d_u:
            flag = input(f"是否使用默认用户{d_u}(Y/n): ").lower() if not using_default else 'y'
            for user in all_users:
                if user.account == d_u and (flag == '' or flag == 'y' or flag == 'yes'):
                    return user

        user = all_users[curses.wrapper(table, [user.to_dict() for user in all_users]) if mark else 0]
        # 设置默认用户
        flag = input(f"是否设置{user.account}为默认用户(Y/n): ").lower()
        if flag == '' or flag == 'y' or flag == 'yes':
            pdbc.update_config('default_user_account', user.account)
    return user


def choose_task(user, pdbc: DML, using_default=False):
    GetTasks(user, pdbc)
    all_tasks = pdbc.query_all_record()
    d_t = pdbc.query_config('default_task_id')
    if d_t:
        flag = input(
            f"是否使用默认任务{[task.note for task in all_tasks if task.id == d_t][0]}({d_t})(Y/n): "
        ).lower() if not using_default else 'y'
        for task in all_tasks:
            if task.id == d_t and (flag == '' or flag == 'y' or flag == 'yes'):
                return task
    task = all_tasks[curses.wrapper(table, [task.to_risc_dict() for task in all_tasks])]
    # 设置默认任务
    flag = input(
        f"是否设置{task.note}({task.name})为默认任务(Y/n): ").lower()
    if flag == '' or flag == 'y' or flag == 'yes':
        pdbc.update_config('default_task_id', task.id)
    return task


def args_parser():
    # 添加一个-s参数
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--shutdown', type=str, choices=['true', 'false'], help='shutdown the task')
    parser.add_argument('-d', '--default_all', type=str, choices=['true', 'false'], help='use default user and task')
    parser.add_argument('-dt', '--default_task', type=str, choices=['true', 'false'], help='use default task')
    parser.add_argument('-du', '--default_user', type=str, choices=['true', 'false'], help='use default user')

    args = parser.parse_args()
    s_flag = args.shutdown.lower() == 'true'
    d_flag = args.default_all.lower() == 'true'
    dt_flag = args.default_task.lower() == 'true' or d_flag
    du_flag = args.default_user.lower() == 'true' or d_flag
    return s_flag, dt_flag, du_flag


def main(client: paramiko.SSHClient):
    shutdown_flag, default_task_flag, default_user_flag = args_parser()

    s = requests.Session()
    # 移除默认的 Connection 头部
    if 'Connection' in s.headers:
        del s.headers['Connection']
    pdbc = DML()
    user = choose_account(pdbc, using_default=default_user_flag)
    # 更新Tasks
    task = choose_task(user, pdbc, using_default=default_task_flag)
    # ShutDown(task.id, user, pdbc)
    # 仅当状态为6（已关机）时，才执行开机操作
    # 若存在-s参数，则执行关机指令
    if shutdown_flag:
        ShutDown(task.id, user, pdbc)
        exit("关机成功！")
    if int(task.status) == 6:
        if SetUp(task.id, user, pdbc):
            print("开机成功！")
        else:
            exit("开机失败！")
    # 启用本地ssh代理
    create_local_forwarding(task, pdbc, client)


if __name__ == '__main__':
    cli = paramiko.SSHClient()
    try:
        main(cli)
    except KeyboardInterrupt as e:
        cli.close()
        sys.exit("Program stopped by user.")
