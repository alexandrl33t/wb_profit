from __future__ import annotations

import json
import time
from datetime import timedelta
from typing import Any, Dict, Optional, List

import requests

ERROR_SLEEP_TIME = 60
MAX_RETRIES = 3
TIMEOUT = 30


def debug_print_resp(resp: requests.Response):
    try:
        payload = resp.json()
        print(json.dumps(payload, indent=4, ensure_ascii=False))
    except Exception:
        print(resp.text[:1000])


def debug_print_dict(dictionary):
    print(json.dumps(dictionary, indent=4, ensure_ascii=False))


SESSION = requests.Session()


def _request(
    method: str,
    url: str,
    headers: Dict[str, str],
    retry: float,
    params: Optional[Any] = None,
    json: Optional[Any] = None,
) -> Optional[requests.Response]:
    # session = requests.Session()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = SESSION.request(
                method, url, headers=headers, params=params, json=json, timeout=TIMEOUT
            )
        except requests.exceptions.Timeout:
            print(
                f"[WARN] HTTP {method} {url} TIMEOUT "
                f"(attempt {attempt}/{MAX_RETRIES}). Retry in {ERROR_SLEEP_TIME}s"
            )
            time.sleep(ERROR_SLEEP_TIME)
            continue
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] HTTP {method} {url} FAILED: {e}")
            return None  # фатальная ошибка, не будем ретраить

        if resp.ok:
            print(f"[INFO] HTTP {method} {url} OK ({resp.status_code})")
            if retry > 0:
                time.sleep(retry)
            return resp

        print(
            f"[WARN] HTTP {method} {url} -> {resp.status_code} "
            f"(attempt {attempt}/{MAX_RETRIES}). Retry in {ERROR_SLEEP_TIME}s"
        )
        debug_print_resp(resp)
        time.sleep(ERROR_SLEEP_TIME)

    # последняя попытка: вернём что есть
    return resp  # noqa


# ---------- WB: Stocks / Goods ----------


def get_sklad_by_api(token: str) -> requests.Response:
    return _request(
        "GET",
        "https://statistics-api.wildberries.ru/api/v1/supplier/stocks",
        {"Authorization": token, "Content-Type": "application/json"},
        0,
        {"dateFrom": "2023-05-04T09:00:00.12345"},
    )


def get_nm_art(token: str) -> Dict[str, Any]:
    resp = _request(
        "GET",
        "https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter",
        {"Authorization": token, "Content-Type": "application/json"},
        0,
        {"limit": 1000},
    )
    print(f"Requests get_NM_ART: {resp.status_code} STOP")
    return resp.json()


# ---------- WB: Sales / Orders ----------


def get_sales(token: str, data: str, one_day: bool = True) -> List[Dict[str, Any]]:
    resp = _request(
        "GET",
        "https://statistics-api.wildberries.ru/api/v1/supplier/sales",
        {"Authorization": token, "Content-Type": "application/json"},
        0,
        {"dateFrom": data, "flag": 1 if one_day else 0},
    )
    print(f"Requests get_sales: {resp.status_code} STOP")
    return resp.json()


def get_orders(data: str, token: str, one_day: bool = True) -> List[Dict[str, Any]]:
    resp = _request(
        "GET",
        "https://statistics-api.wildberries.ru/api/v1/supplier/orders",
        {"Authorization": token, "Content-Type": "application/json"},
        0,
        {"dateFrom": data, "flag": 1 if one_day else 0},
    )
    print(f"Requests get_orders: {resp.status_code} STOP")
    return resp.json()


def get_by_day(data: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    by_art_money: Dict[str, float] = {}
    by_art_count: Dict[str, int] = {}
    for i in data:
        art = i["supplierArticle"]
        price = i["priceWithDisc"]
        by_art_money[art] = by_art_money.get(art, 0) + price
        by_art_count[art] = by_art_count.get(art, 0) + 1
    return {"money": by_art_money, "count": by_art_count}


# ---------- WB: Analytics (funnel) ----------


def get_stat(day, token: str, offset: int) -> Dict[str, Any]:
    first_date = (day - timedelta(offset)).strftime("%Y-%m-%d 00:00:00")
    second_date = day.strftime("%Y-%m-%d 00:00:00")

    resp = _request(
        "POST",
        "https://seller-analytics-api.wildberries.ru/api/v2/nm-report/detail",
        {"Authorization": token},
        0,
        json={
            "period": {"begin": first_date, "end": second_date},
            "page": 1,
        },
    )
    print(f"Requests get_stat: {resp.status_code} STOP")
    return resp.json()


def funnel_table(token: str, day) -> Dict[str, float]:
    data_stat = get_stat(day=day, token=token, offset=7)
    return {
        i["vendorCode"]: i["statistics"]["selectedPeriod"]["conversions"][
            "buyoutsPercent"
        ]
        for i in data_stat["data"]["cards"]
    }


# ---------- WB: Advertising ----------


def get_ids_promotion_adverts(token: str, day, statuses=(7, 9, 11)) -> list[int]:
    day = day.strftime("%Y-%m-%d")
    ids: list[int] = []
    url = "https://advert-api.wildberries.ru/adv/v1/promotion/adverts"
    headers = {"Authorization": token, "Content-Type": "application/json"}

    for st in statuses:
        resp = _request(
            "POST", url, headers, 0, params={"type": 8, "status": st, "order": "change"}
        )
        if not resp or not resp.ok or resp.status_code == 204:
            continue

        for adv in resp.json():
            create = (adv.get("createTime"))[:10]
            end = (adv.get("endTime"))[:10]

            if create <= day <= end:
                ids.append(adv["advertId"])
    return ids


def get_ids_auction_adverts(token: str, day, statuses=[7, 9, 11]) -> list[int]:
    day = day.strftime("%Y-%m-%d")
    ids: list[int] = []
    url = "https://advert-api.wildberries.ru/adv/v0/auction/adverts"
    headers = {"Authorization": token}

    # for st in statuses:
    resp = _request("GET", url, headers, 0, params={"status": statuses})
    if not resp or not resp.ok:
        return ids
    data = resp.json()

    for adv in data["adverts"]:
        timestamps = adv.get("timestamps", {})
        create = (timestamps.get("created"))[:10]
        end = (timestamps.get("deleted"))[:10]

        if create <= day <= end:
            ids.append(adv["id"])
    return ids


def get_ids(token: str) -> requests.Response:
    resp = _request(
        "GET",
        "https://advert-api.wildberries.ru/adv/v1/promotion/count",
        {"Authorization": token, "Content-Type": "application/json"},
        0,
    )
    return resp


def get_ad_stat(token: str, day, ids: list[int]) -> list[dict]:
    day = day.strftime("%Y-%m-%d")
    url = "https://advert-api.wildberries.ru/adv/v2/fullstats"
    headers = {"Authorization": token, "Content-Type": "application/json"}
    result = []

    for i in range(0, len(ids), 100):  # шаг = 100
        chunk = ids[i : i + 100]
        body = [{"id": adv_id, "dates": [day]} for adv_id in chunk]
        resp = _request("POST", url, headers, 0, json=body)
        # возможные варианты: 200 с [] / 204 / 4xx
        if not resp or not resp.ok:
            print(
                f"[WARN] fullstats chunk {i // 100 + 1}: http {getattr(resp, 'status_code', None)}"
            )
            continue

        data = resp.json()  # WB вернёт [] если «ничего»
        if not data:
            continue  # пустой чанк → просто продолжаем

        result.extend(data)
    return result
