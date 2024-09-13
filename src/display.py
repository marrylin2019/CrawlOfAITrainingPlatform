import curses
from typing import Optional


def table(stdscr, data_dict: list[dict]) -> Optional[int]:
    COLUMN_WIDTH = 15
    # 初始化 curses
    curses.curs_set(0)  # 隐藏光标
    stdscr.nodelay(True)  # 设置非阻塞模式

    # 当前选中的用户索引
    selected_index = 0
    # 清屏
    stdscr.erase()
    stdscr.refresh()

    # 列标题
    headers = [key.upper() for key in data_dict[0]]

    while True:
        base_row = 2
        # 清屏
        stdscr.erase()
        stdscr.addstr(base_row, 0, '(press "q" to quit)')
        base_row += 1

        # 绘制表头
        for col, header in enumerate(headers):
            stdscr.addstr(base_row, col * COLUMN_WIDTH, header.center(COLUMN_WIDTH))
        base_row += 1

        # 绘制表格数据
        for row, user in enumerate(data_dict):
            for col, (key, value) in enumerate(user.items()):
                value = str(value)[:COLUMN_WIDTH - 3] + '...' if len(str(value)) > COLUMN_WIDTH - 3 else str(value)
                if row == selected_index:
                    stdscr.addstr(row + base_row, col * COLUMN_WIDTH, value.center(COLUMN_WIDTH), curses.A_REVERSE)
                else:
                    stdscr.addstr(row + base_row, col * COLUMN_WIDTH, value.center(COLUMN_WIDTH))

        # 刷新屏幕
        stdscr.refresh()

        # 获取用户输入
        key = stdscr.getch()

        if key == curses.KEY_UP and selected_index > 0:
            # 上移选择
            selected_index -= 1
        elif key == curses.KEY_DOWN and selected_index < len(data_dict) - 1:
            # 下移选择
            selected_index += 1
        elif key == 10:  # 回车键
            # 返回当前选中的用户
            return selected_index
        elif key == ord('q'):  # q 键退出
            return None
