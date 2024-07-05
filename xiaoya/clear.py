# coding:utf-8

from datetime import datetime
from time import sleep
from typing import Iterable
from typing import List
from typing import Tuple

from xarg import add_command
from xarg import argp
from xarg import commands
from xarg import run_command

from .aliyundrive import aliyundrive_api
from .aliyundrive import aliyundrive_file
from .aliyundrive import aliyundrive_stat
from .utils import bytes_to_human_readable


DEFAULT_MIN_INTERVAL_SECOND: int = 30
DEFAULT_MAX_INTERVAL_SECOND: int = 300


class clear_aliyundrive(aliyundrive_api):
    DEFAULT_MAX_RESERVED_FILE: int = 100
    DEFAULT_MAX_RESERVED_BYTE: int = 50 * 1024 ** 3
    DEFAULT_MAX_RESERVED_MINUTE: int = 24 * 60
    FORCE_RESERVED_SECOND: int = 60
    FORCE_RESERVED_FILE: int = 3

    def __init__(self, data_root: str,
                 max_reserved_file: int = DEFAULT_MAX_RESERVED_FILE,
                 max_reserved_byte: int = DEFAULT_MAX_RESERVED_BYTE,
                 max_reserved_minute: int = DEFAULT_MAX_RESERVED_MINUTE):
        super().__init__(data_root=data_root)
        self.__max_reserved_file: int = max_reserved_file
        self.__max_reserved_byte: int = max_reserved_byte
        self.__max_reserved_minute: int = max_reserved_minute
        self.__max_reserved_second: int = max_reserved_minute * 60

    @property
    def max_reserved_file(self) -> int:
        return self.__max_reserved_file

    @property
    def max_reserved_byte(self) -> int:
        return self.__max_reserved_byte

    @property
    def max_reserved_minute(self) -> int:
        return self.__max_reserved_minute

    @property
    def max_reserved_second(self) -> int:
        return self.__max_reserved_second

    def filter(self) -> Tuple[aliyundrive_file, ...]:
        reserved_stat: aliyundrive_stat = aliyundrive_stat()
        all_files: List[aliyundrive_file] = sorted(self, key=lambda file: file.updated_at, reverse=True)  # noqa
        delete_files: List[aliyundrive_file] = []

        for file in all_files:
            timedalta = datetime.utcnow() - file.updated_at
            commands().logger.debug(f"{file.file_id}：更新于{file.updated_at}，时间差{timedalta}")  # noqa
            # 按照更新时间排序，最新文件排在前面，总是保留最新的文件
            if timedalta.seconds <= self.FORCE_RESERVED_SECOND:
                reserved_stat.add(file)  # 强制保留刚刚更新过的文件
                continue
            if file.type == "folder":  # 文件夹无法统计占用空间
                commands().logger.debug(f"{file.file_id}：文件夹总是清理")
                delete_files.append(file)
                continue
            if timedalta.seconds >= self.max_reserved_second:
                commands().logger.debug(f"{file.file_id}：超过最大保留时间")
                delete_files.append(file)
                continue
            if len(reserved_stat.files) >= self.max_reserved_file:
                commands().logger.debug(f"{file.file_id}：超过最大保留文件个数")
                delete_files.append(file)
                continue
            if len(reserved_stat.files) < self.FORCE_RESERVED_FILE:
                # 检测空间前至少保留一些文件，否则那些超大得文件将总是会被删除
                reserved_stat.add(file)
                continue
            if reserved_stat.size + file.size > self.max_reserved_byte:
                commands().logger.debug(f"{file.file_id}：超过最大保留空间")
                delete_files.append(file)
                continue
            reserved_stat.add(file)
        return tuple(delete_files)

    def delete(self, files: Iterable[aliyundrive_file]) -> aliyundrive_stat:
        stat: aliyundrive_stat = aliyundrive_stat()

        for file in files:
            commands().logger.debug(f"{file.file_id}: {file.created_at}, {file.updated_at}, {file.type},  {file.name}")  # noqa
            if file.type == "file":
                self.delete_file(file.file_id, file.size)
            elif file.type == "folder":
                self.delete_folder(file.file_id)
            else:
                commands().logger.error(f"未知的文件类型：{file.type}")
            stat.add(file)

        return stat


@add_command("clear-aliyundrive", help="清理阿里云盘中的小雅转存文件")
def add_cmd_clear_aliyundrive(_arg: argp):
    _arg.add_opt_on("--daemon", dest="daemon", help="守护模式（持续清理），默认是单次清理")  # noqa
    _arg.add_argument("--max-interval", dest="max_interval", type=int,
                      help=f"守护模式下两次清理的最大间隔时间，默认值为：{DEFAULT_MAX_INTERVAL_SECOND}，单位秒",  # noqa
                      nargs=1, metavar="NUM", default=[DEFAULT_MAX_INTERVAL_SECOND])  # noqa
    _arg.add_argument("-f", "--file", dest="reserved_file", type=int,
                      help=f"最大保留的文件数，默认值为：{clear_aliyundrive.DEFAULT_MAX_RESERVED_FILE}",  # noqa
                      nargs=1, metavar="NUM", default=[clear_aliyundrive.DEFAULT_MAX_RESERVED_FILE])  # noqa
    _arg.add_argument("-b", "--byte", dest="reserved_byte", type=int,
                      help=f"最大保留的空间量，默认值为：{bytes_to_human_readable(clear_aliyundrive.DEFAULT_MAX_RESERVED_BYTE)}，单位字节数",  # noqa
                      nargs=1, metavar="NUM", default=[clear_aliyundrive.DEFAULT_MAX_RESERVED_BYTE])  # noqa
    _arg.add_argument("-m", "--minute", dest="reserved_minute", type=int,
                      help=f"最大保留的分钟值，默认值为：{clear_aliyundrive.DEFAULT_MAX_RESERVED_MINUTE}，单位分钟",  # noqa
                      nargs=1, metavar="NUM", default=[clear_aliyundrive.DEFAULT_MAX_RESERVED_MINUTE])  # noqa


@run_command(add_cmd_clear_aliyundrive)
def run_cmd_clear_aliyundrive(cmds: commands) -> int:
    data_root: str = cmds.args.data_root[0]
    max_interval: int = cmds.args.max_interval[0]  # 最大休眠间隔时间，单位秒
    reserved_file: int = cmds.args.reserved_file[0]
    reserved_byte: int = cmds.args.reserved_byte[0]
    reserved_minute: int = cmds.args.reserved_minute[0]

    interval: float = DEFAULT_MIN_INTERVAL_SECOND * 2  # 休眠间隔时间初始值，单位秒

    def calc_sleep_interval(prev: float, rate: float) -> float:
        if rate >= 0.8:
            prev /= 2  # 清理文件过多，休眠时间倍减
        elif rate >= 0.5:
            prev -= DEFAULT_MIN_INTERVAL_SECOND * rate  # 清理文件过多，休眠时间减少
        elif rate >= 0.2:
            prev += DEFAULT_MIN_INTERVAL_SECOND * (1.0 - rate)  # 清理文件过少，休眠时间增加
        else:
            prev *= 2  # 清理文件过少，休眠时间倍增
        return min(max(DEFAULT_MIN_INTERVAL_SECOND, prev), max_interval)  # noqa

    while True:
        try:
            interface = clear_aliyundrive(
                data_root=data_root,
                max_reserved_file=reserved_file,
                max_reserved_byte=reserved_byte,
                max_reserved_minute=reserved_minute
            )
            cmds.logger.info("扫描阿里云盘小雅转存文件")
            for index, file in enumerate(interface.list_files()):
                cmds.logger.debug(f"{index}: {file.file_id}, {file.created_at}, {file.updated_at}, {file.type}, {file.name}")  # noqa
            cmds.logger.info("过滤阿里云盘小雅转存文件")
            todo: Tuple[aliyundrive_file, ...] = interface.filter()
            cmds.logger.info("清理阿里云盘小雅转存文件")
            stat: aliyundrive_stat = interface.delete(todo)
            cmds.logger.info(f"本次共清理 {len(stat.files)} 个文件和 {len(stat.folders)} 个文件夹，总计 {stat.readable_size} 空间")  # noqa
            if not cmds.args.daemon:
                break  # 退出单次运行
            # 根据清理文件的大小计算休眠时间
            interval = calc_sleep_interval(interval, stat.size / reserved_byte)
        except Exception as e:
            cmds.logger.error(f"清理阿里云盘小雅转存文件出错：{e}")
            if not cmds.args.daemon:
                raise
            interval = DEFAULT_MIN_INTERVAL_SECOND  # 清理失败，尽快重试
        cmds.logger.info(f"休眠 {int(interval)} 秒")
        sleep(interval)  # 动态休眠
    return 0
