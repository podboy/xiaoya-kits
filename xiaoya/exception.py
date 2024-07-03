# coding:utf-8


class CommonException(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class ResponseException(CommonException):
    pass


class PostException(ResponseException):
    def __init__(self, url: str, status_code: int, text: str):
        super().__init__(f"请求 {url} 失败，状态码：{status_code}\n{text}")
