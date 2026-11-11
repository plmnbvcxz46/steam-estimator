import pytest
import requests

from crawler import http


class FakeResponse:
    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


def fake_get_factory(responses):
    """返回一个假的 get（代替会话的 get）：每调用一次，依次吐出 responses 里的下一项。
    项是 FakeResponse 就当作响应返回，是异常就抛出。"""
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        item = responses[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    fake_get.calls = calls
    return fake_get


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    # 测试里不真的等待，否则退避会让测试慢好几十秒
    monkeypatch.setattr(http.time, "sleep", lambda seconds: None)


def test_retries_then_succeeds(monkeypatch):
    # 先超时，再被限流，第三次成功：应该自动重试并返回数据
    fake_get = fake_get_factory([
        requests.Timeout(),
        FakeResponse(429),
        FakeResponse(200, {"ok": True}),
    ])
    monkeypatch.setattr(http._session, "get", fake_get)

    assert http.get_json("https://example.com/a") == {"ok": True}
    assert len(fake_get.calls) == 3


def test_404_is_not_retried(monkeypatch):
    # 404 重试没用，应该只请求一次就抛错
    fake_get = fake_get_factory([FakeResponse(404)])
    monkeypatch.setattr(http._session, "get", fake_get)

    with pytest.raises(http.CrawlError) as err:
        http.get_json("https://example.com/a")
    assert err.value.status == 404
    assert len(fake_get.calls) == 1


def test_gives_up_after_max_retries(monkeypatch):
    # 一直 500：试 1 + MAX_RETRIES 次后放弃，状态记为 500
    fake_get = fake_get_factory([FakeResponse(500)] * (http.MAX_RETRIES + 1))
    monkeypatch.setattr(http._session, "get", fake_get)

    with pytest.raises(http.CrawlError) as err:
        http.get_json("https://example.com/a")
    assert err.value.status == 500
    assert len(fake_get.calls) == http.MAX_RETRIES + 1


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
