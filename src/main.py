import argparse
import curses
import os
import sys
from pathlib import Path

import paramiko
import requests

from src import PARAMIKO_LOG_PATH
from src.display import table
from src.persistence import DML
from src.port_forwading import create_local_forwarding
from src.utils import GetTasks, ShutDown, SetUp, KeepAlive, CheckStatus, ShutDownAll, QBalance


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

    # 如果没有任务，返回None
    if not all_tasks:
        return None

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


def args_parser() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    # -ka -s -c两两不能同时使用
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-s', '--shutdown', action='store_true', help='shutdown the task')
    group.add_argument('-c', '--check_status', action='store_true', help='check the status of the task')
    group.add_argument('-ka', '--keep_alive', action='store_true', help='delay the task release time')
    group.add_argument('-b', '--balance', action='store_true', help='balance the task')

    parser.add_argument('-d', '--default_all', action='store_true', help='use default user and task')
    parser.add_argument('-dt', '--default_task', action='store_true', help='use default task')
    parser.add_argument('-du', '--default_user', action='store_true', help='use default user')
    parser.add_argument('-a', '--all', action='store_true', help='choose all. This CAN NOT use with -da, -dt, -du, -ka')

    parser.add_argument('-r', '--requirements', action='store_true',
                        help='Install the dependencies based on ./requirements.txt;')

    parser.add_argument('--python_path', type=str, help='python path')
    parser.add_argument('--pip_path', type=str, help='pip path')
    parser.add_argument('--requirements_path', type=str, help='requirements path')

    args = parser.parse_args()

    # TODO: 允许-a在-c的情况下与-du同时使用
    # TODO: 允许-a在-s的情况下与-du同时使用
    # TODO: 不允许-a与-d或-dt同时使用，但允许-a与-du同时使用
    # TODO: 不允许-ka与-d或-dt同时使用，但允许-ka与-du同时使用
    # TODO: 不允许-ka与-a同时使用
    # -a 与 -da、-dt、-du、-ka 中的任何一个不能同时使用
    if args.all and (args.default_all or args.default_task or args.default_user or args.keep_alive):
        parser.error(
            'argument -a/--all: '
            'not allowed with argument -d/--default_user, -da/--default_all, -dt/--default_task or -ka/--keep_alive'
        )

    args.default_task = args.default_all or args.default_task
    args.default_user = args.default_all or args.default_user
    args.python_path = Path(args.python_path)
    args.pip_path = Path(args.pip_path)
    args.requirements_path = Path(args.requirements_path)
    return args


def main(client: paramiko.SSHClient):
    args = args_parser()

    if args.requirements:
        if not (args.python_path.exists() and args.pip_path.exists() and args.requirements_path.exists()):
            exit(
                "文件不完整，缺少python、pip或requirements文件，请检查batch文件中的python、pip或requirements参数设置是否正确！")
        os.system(f'{args.python_path} -m pip install -r requirements.txt')
        os.system('cls')
        print('依赖安装完成！')

    s = requests.Session()
    # 移除默认的 Connection 头部
    if 'Connection' in s.headers:
        del s.headers['Connection']
    pdbc = DML()
    user = choose_account(pdbc, using_default=args.default_user)
    # 若同时存在-a和-c参数，则执行查询指令，查询所有任务的状态，并退出
    if args.all and args.check_status:
        exit(CheckStatus(user, pdbc, for_all=True))
    # 若同时存在-a和-s参数，则执行关机指令，并退出
    if args.all and args.shutdown:
        print("正在关机...")
        ShutDownAll(user, pdbc)
        exit("关机成功！")
    # 若存在-ka参数，则延长任务释放时间
    if args.keep_alive:
        exit(KeepAlive(user, pdbc))
    # 若存在-b参数，则执行余额查询
    if args.balance:
        exit(QBalance(user, pdbc))

    # 更新Tasks
    task = choose_task(user, pdbc, using_default=args.default_task)

    if not task:
        exit("当前没有实例，请登录平台创建实例后再使用本脚本！")

    # 若存在-c参数，则执行查询指令，查询任务状态，并退出
    if args.check_status:
        exit(CheckStatus(user, pdbc, task))

    # 若存在-s参数，则执行关机指令，并退出
    if args.shutdown:
        print("正在关机...")
        ShutDown(task.id, user, pdbc)
        exit("关机成功！")
    if int(task.status) == 6:
        print("正在开机...")
        if SetUp(task.id, user, pdbc):
            print("开机成功！")
        else:
            exit("开机失败！")
    # 启用本地ssh代理
    create_local_forwarding(task, pdbc, client)


if __name__ == '__main__':
    # 记录日志
    paramiko.util.log_to_file(PARAMIKO_LOG_PATH)

    cli = paramiko.SSHClient()
    try:
        main(cli)
    except KeyboardInterrupt as e:
        cli.close()
        sys.exit("Program stopped by user.")
