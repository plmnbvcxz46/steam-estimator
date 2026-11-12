import pytest
import requests

from crawler import http


class FakeResponse:
    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


def fake_request_factory(responses):
    """返回一个假的 request（代替会话的 request）：每调用一次，依次吐出 responses 里的下一项。
    项是 FakeResponse 就当作响应返回，是异常就抛出。calls 记下每次的 (方法, 网址, 请求体)。"""
    calls = []

    def fake_request(method, url, params=None, json=None, timeout=None):
        calls.append((method, url, json))
        item = responses[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    fake_request.calls = calls
    return fake_request


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    # 测试里不真的等待，否则退避会让测试慢好几十秒
    monkeypatch.setattr(http.time, "sleep", lambda seconds: None)


def test_retries_then_succeeds(monkeypatch):
    # 先超时，再被限流，第三次成功：应该自动重试并返回数据
    fake_request = fake_request_factory([
        requests.Timeout(),
        FakeResponse(429),
        FakeResponse(200, {"ok": True}),
    ])
    monkeypatch.setattr(http._session, "request", fake_request)

    assert http.get_json("https://example.com/a") == {"ok": True}
    assert len(fake_request.calls) == 3


def test_404_is_not_retried(monkeypatch):
    # 404 重试没用，应该只请求一次就抛错
    fake_request = fake_request_factory([FakeResponse(404)])
    monkeypatch.setattr(http._session, "request", fake_request)

    with pytest.raises(http.CrawlError) as err:
        http.get_json("https://example.com/a")
    assert err.value.status == 404
    assert len(fake_request.calls) == 1


def test_gives_up_after_max_retries(monkeypatch):
    # 一直 500：试 1 + MAX_RETRIES 次后放弃，状态记为 500
    fake_request = fake_request_factory([FakeResponse(500)] * (http.MAX_RETRIES + 1))
    monkeypatch.setattr(http._session, "request", fake_request)

    with pytest.raises(http.CrawlError) as err:
        http.get_json("https://example.com/a")
    assert err.value.status == 500
    assert len(fake_request.calls) == http.MAX_RETRIES + 1


def test_post_json_sends_body(monkeypatch):
    # ITAD 换编号要 POST 一个列表：确认用的是 POST，列表原样放进请求体
    fake_request = fake_request_factory([FakeResponse(200, {"app/10": "x"})])
    monkeypatch.setattr(http._session, "request", fake_request)

    assert http.post_json("https://example.com/a", ["app/10"]) == {"app/10": "x"}
    assert fake_request.calls == [("POST", "https://example.com/a", ["app/10"])]


def test_wait_for_turn_queues_requests(monkeypatch):
    # 时钟停在 100 秒不动，相当于三个请求同时到达（多线程时就是这种情况）。
    # 间隔 1 秒：第一个不等，第二个等 1 秒，第三个要排在第二个后面，等 2 秒
    sleeps = []
    monkeypatch.setattr(http, "_next_slot", {})
    monkeypatch.setattr(http.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(http.time, "sleep", sleeps.append)

    for _ in range(3):
        http._wait_for_turn("https://example.com/a", 1.0)

    assert sleeps == [1.0, 2.0]
