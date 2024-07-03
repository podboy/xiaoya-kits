# coding:utf-8

from datetime import datetime
import os
from typing import Any
from typing import Dict
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Optional

import requests
from xarg import cmds

from .exception import PostException
from .utils import bytes_to_human_readable


class aliyundrive_file():
    DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    def __init__(self, info: Dict[str, Any]):
        self.__info: Dict[str, Any] = info
        self.__created_at: datetime = datetime.strptime(info["created_at"], self.DATE_FORMAT)  # noqa
        self.__updated_at: datetime = datetime.strptime(info["updated_at"], self.DATE_FORMAT)  # noqa

    @property
    def info(self) -> Dict[str, Any]:
        return self.__info

    @property
    def type(self) -> str:
        return self.info["type"]

    @property
    def size(self) -> int:
        return self.info.get("size", 0)

    @property
    def name(self) -> str:
        return self.info["name"]

    @property
    def file_id(self) -> str:
        return self.info["file_id"]

    @property
    def created_at(self) -> datetime:
        return self.__created_at

    @property
    def updated_at(self) -> datetime:
        return self.__updated_at


class aliyundrive_stat():
    def __init__(self, items: Iterable[aliyundrive_file] = []):
        self.__folders: List[aliyundrive_file] = []
        self.__files: List[aliyundrive_file] = []
        for item in items:
            if item.type == "folder":
                self.__folders.append(item)
            elif item.type == "file":
                self.__files.append(item)
        self.__files_size: int = sum([item.size for item in self.__files])

    @property
    def folders(self) -> List[aliyundrive_file]:
        return self.__folders

    @property
    def files(self) -> List[aliyundrive_file]:
        return self.__files

    @property
    def size(self) -> int:
        return self.__files_size

    @property
    def readable_size(self) -> str:
        return bytes_to_human_readable(self.__files_size)

    def add(self, file: aliyundrive_file):
        if file.type == "folder" and file not in self.__folders:
            self.__folders.append(file)
        elif file.type == "file" and file not in self.__files:
            self.__files_size += file.size
            self.__files.append(file)


class aliyundrive_req:
    MIN_TIMEOUT: float = 3.0

    def __init__(self, headers: Dict[str, str] = {}, timeout: float = 5.0):
        headers.setdefault("Content-Type", "application/json")
        self.__timeout: float = max(self.MIN_TIMEOUT, timeout)
        self.__headers: Dict[str, Any] = headers

    @property
    def timeout(self) -> float:
        return self.__timeout

    @property
    def headers(self) -> Dict[str, str]:
        return self.__headers

    def post(self, url: str, data: Dict[str, Any] = {}) -> Dict[str, Any]:
        response: requests.Response = requests.post(url, json=data,
                                                    headers=self.headers,
                                                    timeout=self.timeout)

        if response.status_code != 200:
            raise PostException(url=url, status_code=response.status_code,
                                text=response.text)

        return response.json()


class aliyundrive_api:
    FILE_TOKEN = "mytoken.txt"
    FILE_FOLDER_ID = "temp_transfer_folder_id.txt"
    FILE_FOLDER_TYPE = "folder_type.txt"
    URL_V1_FILE_GET_PATH: str = "https://api.aliyundrive.com/adrive/v1/file/get_path"  # noqa
    URL_V2_ACCOUNT_TOKEN: str = "https://api.aliyundrive.com/v2/account/token"
    URL_V2_USER_GET: str = "https://user.aliyundrive.com/v2/user/get"
    URL_V2_FILE_LIST: str = "https://api.aliyundrive.com/adrive/v2/file/list"
    URL_V3_BATCH: str = "https://api.aliyundrive.com/v3/batch"

    def __init__(self, data_root: str):
        self.__data_root: str = data_root
        self.__refresh_token: Optional[str] = None
        self.__folder_type: Optional[str] = None
        self.__folder_id: Optional[str] = None
        self.__access_token: Optional[str] = None
        self.__default_drive_id: Optional[str] = None
        self.__resource_drive_id: Optional[str] = None
        self.__files: List[aliyundrive_file] = []

    def __iter__(self) -> Iterator[aliyundrive_file]:
        return iter(self.files)

    @property
    def files(self) -> List[aliyundrive_file]:
        return self.__files

    @property
    def data_root(self) -> str:
        return self.__data_root

    @property
    def refresh_token(self) -> str:
        if self.__refresh_token is None:
            self.__refresh_token = self.__read_file(self.FILE_TOKEN).strip()
            cmds.logger.debug(f"refresh_token: {self.__refresh_token}")
        assert isinstance(self.__refresh_token, str)
        return self.__refresh_token

    @property
    def folder_type(self) -> str:
        if self.__folder_type is None:
            self.__folder_type = self.__read_file(self.FILE_FOLDER_TYPE).strip()  # noqa
            cmds.logger.debug(f"folder_type: {self.__folder_type}")
        assert isinstance(self.__folder_type, str)
        return self.__folder_type

    @property
    def folder_type_name(self) -> str:
        if self.folder_type_is_backup:
            return "备份盘"
        if self.folder_type_is_resource:
            return "资源盘"
        return "资源盘"

    @property
    def folder_type_is_backup(self) -> bool:
        return self.folder_type == "b"

    @property
    def folder_type_is_resource(self) -> bool:
        return self.folder_type == "r"

    @property
    def folder_id(self) -> str:
        if self.__folder_id is None:
            self.__folder_id = self.__read_file(self.FILE_FOLDER_ID).strip()
            cmds.logger.debug(f"folder_id: {self.__folder_id}")
        assert isinstance(self.__folder_id, str)
        return self.__folder_id

    @property
    def access_token(self) -> str:
        if self.__access_token is None:
            response = aliyundrive_req().post(self.URL_V2_ACCOUNT_TOKEN, {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token
            })
            self.__access_token = response["access_token"]
            cmds.logger.debug(f"access_token: {self.__access_token}")
        assert isinstance(self.__access_token, str)
        return self.__access_token

    @property
    def default_drive_id(self) -> str:
        if self.__default_drive_id is None:
            self.__request_drive_id()
        assert isinstance(self.__default_drive_id, str)
        return self.__default_drive_id

    @property
    def resource_drive_id(self) -> str:
        if self.__resource_drive_id is None:
            self.__request_drive_id()
            cmds.logger.debug(f"drive_id: {self.__resource_drive_id}")
        assert isinstance(self.__resource_drive_id, str)
        return self.__resource_drive_id

    def __read_file(self, filename: str) -> str:
        path: str = os.path.join(self.data_root, filename)
        return open(path, mode="r", encoding="utf-8").read()

    def __request_drive_id(self):
        response = aliyundrive_req(
            headers={"Authorization": f"Bearer {self.access_token}"}
        ).post(self.URL_V2_USER_GET)
        self.__default_drive_id = response["default_drive_id"]
        self.__resource_drive_id = self.__default_drive_id\
            if self.folder_type_is_backup else\
            response.get("resource_drive_id", self.__default_drive_id)

    def get_file_path(self, file_id: str) -> str:
        response = aliyundrive_req(
            headers={"Authorization": f"Bearer {self.access_token}"}
        ).post(self.URL_V1_FILE_GET_PATH, data={
            "drive_id": self.resource_drive_id,
            "file_id": file_id})
        items: List[str] = [item["name"] for item in response["items"]]
        items.reverse()
        return os.path.join(*items)

    def list_files(self) -> List[aliyundrive_file]:
        response = aliyundrive_req(
            headers={"Authorization": f"Bearer {self.access_token}"}
        ).post(self.URL_V2_FILE_LIST, data={
            "drive_id": self.resource_drive_id,
            "parent_file_id": self.folder_id})
        self.__files = [aliyundrive_file(file) for file in response["items"]]
        stat: aliyundrive_stat = aliyundrive_stat(self.files)
        cmds.logger.info(f"扫描到 {len(stat.files)} 个文件和 {len(stat.folders)} 个文件夹，总计 {stat.readable_size} 空间")  # noqa
        return self.files

    def __delete(self, file_id: str):
        aliyundrive_req(
            headers={"Authorization": f"Bearer {self.access_token}"}
        ).post(self.URL_V3_BATCH, data={
            "requests": [
                {
                    "body": {
                        "drive_id": self.resource_drive_id,
                        "file_id": file_id,
                    },
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "id": file_id,
                    "method": "POST",
                    "url": "/file/delete",
                }
            ],
            "resource": "file"})

    def delete_file(self, file_id: str, size: int) -> str:
        file_path = self.get_file_path(file_id)
        cmds.logger.info(f"删除{self.folder_type_name}文件：{file_path}，大小 {size}")  # noqa
        self.__delete(file_id)
        cmds.logger.info(f"删除{self.folder_type_name}文件：{file_path} 成功")
        return file_path

    def delete_folder(self, file_id: str) -> str:
        file_path = self.get_file_path(file_id)
        cmds.logger.info(f"删除{self.folder_type_name}文件夹：{file_path}")
        self.__delete(file_id)
        cmds.logger.info(f"删除{self.folder_type_name}文件夹：{file_path} 成功")
        return file_path
