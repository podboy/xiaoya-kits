# coding:utf-8

from typing import Optional
from typing import Sequence

from xarg import add_command
from xarg import argp
from xarg import commands
from xarg import run_command

from .attribute import __description__
from .attribute import __project__
from .attribute import __url_home__
from .attribute import __version__
from .clear import add_cmd_clear_aliyundrive


@add_command(__project__)
def add_cmd(_arg: argp):
    _arg.add_argument("-r", "--root", dest="data_root", type=str,
                      help=f"数据根目录，默认值为当前运行目录",
                      nargs=1, metavar="DIR", default=["."])


@run_command(add_cmd, add_cmd_clear_aliyundrive)
def run_cmd(cmds: commands) -> int:
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    cmds = commands()
    cmds.version = __version__
    return cmds.run(
        root=add_cmd,
        argv=argv,
        description=__description__,
        epilog=f"For more, please visit {__url_home__}.")
