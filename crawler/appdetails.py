"""采集 Steam appdetails（商店信息），写入 raw_appdetails。"""


def parse_appdetails(appid, response):
    """把接口返回的 JSON 变成 raw_appdetails 的一行（dict）。

    response 是接口返回的整个 JSON，形如 {"413150": {"success": true, "data": {...}}}。
    接口说“没有这款游戏”（success 为 false）时返回 None，由调用者记为“未收录”。
    """
    entry = response[str(appid)]
    if not entry["success"]:
        return None

    data = entry["data"]

    # 免费游戏没有 price_overview；价格单位是美分，除以 100 换成美元
    price = data.get("price_overview")
    initial_price_usd = price["initial"] / 100 if price else None

    # genres 是 [{"id": ..., "description": "RPG"}, ...]，只取名字，用 | 连起来
    genres = "|".join(g["description"] for g in data.get("genres", []))

    return {
        "appid": appid,
        "name": data["name"],
        "app_type": data["type"],
        "is_free": int(data["is_free"]),
        # raw 层原样保存：日期格式五花八门，怎么解析留给 pipeline 清洗时决定
        "release_date": data["release_date"]["date"],
        "initial_price_usd": initial_price_usd,
        "genres": genres,
    }
