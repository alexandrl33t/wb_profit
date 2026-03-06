import os
import pickle
import time
from datetime import datetime

import gspread

import all_requests
from core.config import bot, settings, logger


class Profit:
    def __init__(self, key_table, name, wb_token, chat_, id_tg=0, key="e"):
        self.key_table = key_table
        self.name = name
        self.wb_token = wb_token
        self.id_tg = id_tg
        self.chat_ = chat_
        self.id_chat = "-1002468321363"
        gc = gspread.service_account(filename=settings.gspread_credentials_file)
        self.sh = gc.open_by_key(key_table)
        profit_file_path = os.path.join(
            settings.base_dir, "data", f"{self.name}_profit_time.pkl"
        )
        try:
            with open(profit_file_path, "rb") as f:
                loaded_dict = pickle.load(f)
            self.profit_time = loaded_dict
        except Exception:
            self.profit_time = {}
            with open(profit_file_path, "wb") as f:
                pickle.dump(self.profit_time, f)
        revenue_file_path = os.path.join(
            settings.base_dir, "data", f"{self.name}_revenue_time.pkl"
        )
        try:
            with open(revenue_file_path, "rb") as f:
                loaded_dict = pickle.load(f)
            self.revenue_time = loaded_dict
        except Exception:
            self.revenue_time = {}
            with open(revenue_file_path, "wb") as f:
                pickle.dump(self.revenue_time, f)

        logger.info(f"Registetion: {self.name}")

    def sklad_by_api(self):
        result_sklad = {}
        for i in range(3):
            result = all_requests.get_sklad_by_api(self.wb_token)
            if result.status_code == 200:
                result = result.json()
                break
            else:
                logger.error(
                    f"ERROR BY SKLAD BY API. CODE: {result.status_code}\nsleep-10"
                )
                time.sleep(10)
        for i in result:
            if i["warehouseName"] == "Санкт-Петербург Шушары":
                continue
            art = i["supplierArticle"]
            if art not in list(result_sklad.keys()):
                result_sklad.update({art: [i["quantity"]]})
            else:
                result_sklad[art][0] += i["quantity"]
        result_sklad = dict(sorted(result_sklad.items()))
        return result_sklad

    def get_data_from_table(self):
        worksheet = self.sh.worksheet("settings")
        list_of_lists = worksheet.get_all_values()
        logger.info("GOOD")
        art_params = {}
        for i in list_of_lists[1:]:
            if i[1].replace(",", ".") == "":
                continue
            art_params.update(
                {
                    i[0]: {
                        "logistic": float(i[1].replace(",", ".").replace("\xa0", "")),
                        "sebes": float(i[2].replace(",", ".").replace("\xa0", "")),
                        "save": float(i[3].replace(",", ".").replace("\xa0", "")),
                        "tax": float(i[4].replace(",", ".").replace("\xa0", "")),
                        "comis": float(i[5].replace(",", ".").replace("\xa0", "")),
                    }
                }
            )
        return art_params

    def get_orders(self, day):
        result = all_requests.get_by_day(
            data=all_requests.get_orders(data=day, token=self.wb_token, one_day=True)
        )
        return result

    def get_sales(self, day):
        result = all_requests.get_by_day(
            data=all_requests.get_sales(data=day, token=self.wb_token, one_day=True)
        )
        return result

    def get_buyout(self, day):
        result = all_requests.funnel_table(self.wb_token, day=day)
        return result

    def get_nm(self):
        result = {}
        res = all_requests.get_nm_art(self.wb_token)["data"]["listGoods"]
        for i in res:
            result.update({i["nmID"]: i["vendorCode"]})
        return result

    def _get_ids(self):
        result = []
        resp = all_requests.get_ids(self.wb_token).json()
        for group in resp["adverts"]:
            for adv in group["advert_list"]:
                result.append(adv["advertId"])
        return result

    # def _get_ids_now(self, day):
    #     return all_requests.get_ids_promotion_adverts(
    #         self.wb_token, day
    #     ) + all_requests.get_ids_auction_adverts(self.wb_token, day)

    def _get_ad(self, day):
        result = {}
        ids = all_requests.get_ids_auction_adverts(self.wb_token, day)
        if not ids:
            return result
        ids = list(set(ids))  # убираем дубл
        data = all_requests.get_ad_stat(self.wb_token, day, ids)
        art_by_nm = self.get_nm()

        for h in data:
            days = h.get("days", [])
            if not days:
                continue
            for app in days[0].get("apps", []):
                if app.get("appType") == 0:
                    continue
                for nm in app.get("nms", []):
                    art = art_by_nm.get(nm.get("nmId"))
                    if not art:
                        continue
                    result[art] = result.get(art, 0) + nm.get("sum", 0)
        return result

    def generate_table(self, day, check_screen):
        hour = day.hour
        if check_screen == 0:
            hour = 10
        if hour not in self.profit_time.keys():
            old_profits = {}
        else:
            old_profits = self.profit_time[hour]

        sklad = self.sklad_by_api()
        table = []
        art_profits = {}
        art_revenues = {}
        logger.info("GET ORDER | ")
        orders = self.get_orders(day)
        logger.info("GET PVS | ")
        pvs = self.get_buyout(day)
        logger.info("GET DATA_SET | ")
        data_set = self.get_data_from_table()
        logger.info("GET AD | \n")
        try:
            ads = self._get_ad(day)
            good_ad = True
        except Exception as ex:
            logger.warning("WITHOUT ADS")
            good_ad = False
            ads = {}
            bot.send_message(
                "-1002417112074",
                f"ERROR ERROR ERROR Without ads\nname:{self.name}\nError: {ex}",
            )
        sum_goods = 0  # сумма стоимостей товаров на складах
        total_row = {
            "ИТОГО": "ИТОГО",
            "money_ord": 0,
            "count_ord": 0,
            "pv": 0,
            "money_sell": 0,
            "count_sell": 0,
            "sebes": 0,
            "komis": 0,
            "logistic": 0,
            "tax": 0,
            "save": 0,
            "ad": 0,
            "drr": 0,
            "profit": 0,
            "marja": 0,
            "prc_year": 0,
            "delta_profit": 0,
        }
        work = False
        sklad_keys = list(sklad.keys())
        orders_keys = list(orders["money"].keys())
        for i in list(data_set.keys()):
            if (i not in sklad_keys) and (i not in orders_keys):
                append_row = [
                    i,
                    0,
                    0,
                    "-",
                    0,
                    0,
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    0,
                    "-",
                    "-",
                    0,
                ]
                table.append(append_row)
                continue
            if i not in orders_keys:
                if i not in sklad_keys:
                    save = 0
                else:
                    save = round(data_set[i]["save"] * sklad[i][0])
                total_row["save"] += save
                if i in list(ads.keys()):
                    ad = round(ads[i], 2)
                else:
                    ad = 0
                total_row["ad"] += ad
                profit = 0 - save - ad
                total_row["profit"] += profit
                old_profit = old_profits.get(i, "None")
                if old_profit != "None":
                    delta_profit = profit - old_profit
                    total_row["delta_profit"] += delta_profit
                else:
                    delta_profit = "No data"
                append_row = [
                    i,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    f"{save} руб",
                    ad,
                    0,
                    profit,
                    0,
                    0,
                    delta_profit,
                ]
                table.append(append_row)
                art_profits.update({i: round(profit, 2)})
                art_revenues.update({i: 0})  # new
                continue

            money_ord = orders["money"][i]
            count_ord = orders["count"][i]
            work = True
            art = i
            if i not in pvs:
                pv = 0.5
            else:
                pv = pvs[i] / 100
            if pv == 0:
                pv = 0.65
                art = i + "NOT PV"
            money_sell = round(money_ord * pv, 2)
            count_sell = round(count_ord * pv, 2)
            sebes = data_set[i]["sebes"] * count_sell
            komis = round(data_set[i]["comis"] * money_sell, 2)
            logistic = round(data_set[i]["logistic"] * count_sell, 2)
            tax = round(data_set[i]["tax"] * money_sell, 2)
            if i not in sklad_keys:
                save = 0
            else:
                save = round(data_set[i]["save"] * sklad[i][0])
            if i in list(ads.keys()):
                ad = round(ads[i], 2)
            else:
                ad = 0
            if money_sell != 0:
                drr = round(ad / money_sell, 4)
            else:
                drr = 0
            profit = money_sell - sebes - komis - logistic - tax - save - ad
            art_profits.update({i: round(profit, 2)})
            # logger.debug(f"profit {profit} |money sell {money_sell} | sebes {sebes} | komis {komis} | logis {logistic} | tax {tax} | save {save} | ad {ad}")

            if money_sell != 0:
                marja = round(profit / money_sell, 4)
            else:
                marja = 0
                money_sell = 0.01

            if save == 0 or sklad[i][0] == 0 or data_set[i]["sebes"] == 0:
                prc_year = 0
            else:
                sum_good = data_set[i]["sebes"] * sklad[i][0]
                sum_goods += sum_good
                prc_year = round(profit * 365 / sum_good, 2)

            old_profit = old_profits.get(art, "None")
            if old_profit != "None":
                delta_profit = profit - old_profit
                total_row["delta_profit"] += delta_profit
            else:
                delta_profit = "No data"

            append_row = {
                "art": art,
                "money_ord": money_ord,
                "count_ord": count_ord,
                "pv": pv,
                "money_sell": money_sell,
                "count_sell": count_sell,
                "sebes": round(sebes / money_sell, 100),
                "komis": round(komis / money_sell, 100),
                "logistic": round(logistic / money_sell, 100),
                "tax": round(tax / money_sell, 100),
                "save": round(save / money_sell, 100),
                "ad": ad,
                "drr": drr,
                "profit": profit,
                "marja": marja,
                "prc_year": prc_year,
                "delta_profit": delta_profit,
            }

            total_row["money_ord"] += money_ord
            total_row["count_ord"] += count_ord
            total_row["pv"] += pv
            total_row["money_sell"] += money_sell
            total_row["count_sell"] += count_sell
            total_row["sebes"] += sebes
            total_row["komis"] += komis
            total_row["logistic"] += logistic
            total_row["tax"] += tax
            total_row["save"] += save
            total_row["ad"] += ad
            total_row["profit"] += profit
            table.append(list(append_row.values()))

        if not work:
            return {"table": table, "ad": good_ad}

        total_row["sebes"] = round(total_row["sebes"] / total_row["money_sell"], 2)
        total_row["komis"] = round(total_row["komis"] / total_row["money_sell"], 4)
        total_row["logistic"] = round(
            total_row["logistic"] / total_row["money_sell"], 4
        )
        total_row["tax"] = round(total_row["tax"] / total_row["money_sell"], 4)
        total_row["save"] = round(total_row["save"] / total_row["money_sell"], 4)
        total_row["drr"] = round(total_row["ad"] / total_row["money_sell"], 4)
        total_row["pv"] = round(total_row["money_sell"] / total_row["money_ord"], 4)
        total_row["marja"] = round(total_row["profit"] / total_row["money_sell"], 4)
        if sum_goods == 0:
            total_row["prc_year"] = 0
        else:
            total_row["prc_year"] = round(total_row["profit"] * 365 / sum_goods, 4)

        table.append(list(total_row.values()))

        art_profits.update({"total_profit": total_row["profit"]})
        art_revenues.update({"total_revenue": total_row["money_ord"]})  # new

        if check_screen and hour == 10:
            return {"table": table, "ad": good_ad}
        self.profit_time.update({hour: art_profits})

        profit_file_path = os.path.join(
            settings.base_dir, "data", f"{self.name}_profit_time.pkl"
        )
        with open(profit_file_path, "wb") as f:
            pickle.dump(self.profit_time, f)

        self.revenue_time.update({hour: art_revenues})
        revenue_file_path = os.path.join(
            settings.base_dir, "data", f"{self.name}_revenue_time.pkl"
        )
        # new
        with open(revenue_file_path, "wb") as f:
            pickle.dump(self.revenue_time, f)

        return {"table": table, "ad": good_ad}

    def _ensure_size(self, ws, min_rows: int, min_cols: int):
        # текущие размеры
        rows = ws.row_count
        cols = ws.col_count
        need_rows = max(min_rows, rows)
        need_cols = max(min_cols, cols)
        if need_rows != rows or need_cols != cols:
            ws.resize(rows=need_rows, cols=need_cols)

    def to_google(self, day, check_screen=1):
        data = self.generate_table(day, check_screen)
        table = data["table"]

        table_name = day.strftime("%d.%m.%Y")
        title_list = []
        worksheets = self.sh.worksheets()
        for i in worksheets:
            title_list.append(i.title)
        if table_name not in title_list:
            worksheet1 = self.sh.worksheet("Образец")
            worksheet = worksheet1.duplicate(new_sheet_name=table_name)
            # при созданни нового листа с датой лист "Обобщено" двигаем влево
            ws_common = next((ws for ws in worksheets if ws.title == "Обобщенно"), None)
            if ws_common is not None:
                self.sh.reorder_worksheets([ws_common])
        else:
            worksheet = self.sh.worksheet(table_name)

        last_data_row = 1 + len(table)
        MIN_COLS = 30
        self._ensure_size(worksheet, min_rows=last_data_row, min_cols=MIN_COLS)
        worksheet.format(
            f"A{len(table) + 1}:O{len(table) + 1}",
            {
                "backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.8},
                "textFormat": {"bold": True},
            },
        )

        # table[0].append(" ")
        # table[0].append(f"Обновлено: {datetime.now()}")

        worksheet.update("A2", table)
        worksheet.update_acell("S1", f"Обновлено: {datetime.now()}")

        if len(table) == 1:
            return {
                "ad": data["ad"],
                "profit": 0,
                "renta": 0,
                "prc_year": 0,
                "drr": 0,
                "money_ord": 0,
            }
        else:
            return {
                "ad": data["ad"],
                "profit": round(table[-1][-4], 2),
                "renta": round(table[-1][-3], 4),
                "drr": round(table[-1][-5], 4),
                "prc_year": round(table[-1][-2], 4),
                "money_ord": round(table[-1][1]),
                "delta_profit": round(table[-1][-1]),
            }
