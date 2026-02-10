import time
from datetime import timedelta, datetime

import gspread
import pandas as pd
import schedule

import all_requests
from core.config import settings, bot, logger
from profit import Profit
from utils.gspread_utils import get_clients

logger.info("Starting")
times = {}

for i in range(-100, 0):
    times.update({i: None})


def smile(delta, yest):
    if yest == "Нет данных" or delta == "Нет данных":
        return "⚠️"
    delta = round(delta)
    # if delta == 0: delta += 1
    if yest == 0:
        yest = 0.0000001
    prc = round(abs(delta / yest) * 100, 1)
    if int(delta) >= 0:
        delta = f"🍀 +{int(delta)} ({prc}%)"
    else:
        delta = f"🌹 {int(delta)} ({prc}%)"
    return delta


class UpdateData(Profit):
    def to_user(self):
        logger.info(f"Start user: {self.name}")
        if self.wb_token != "" and self.id_tg != "0":
            self.screen_v1(self.id_tg)
            logger.info(f"Good done and send: {self.name}\n\n")
        else:
            date_now = datetime.now()
            super().to_google(date_now)
            logger.info(f"Good done: {self.name}\n\n")

    def to_chat(self):
        logger.info(f"start {self.name}")
        if self.wb_token != "":
            if self.chat_:
                self.screen_v2(self.id_chat)
            elif self.id_tg != "0":
                self.screen_v2(self.id_tg)
            logger.info(f"Good done chat: {self.name}\n\n")
        else:
            return True

    def by_api_get_data(self, today=False):
        def classic_subj(data):
            orders_subj = {}
            for i in data:
                old_money = orders_subj.get(i["subject"], 0)
                orders_subj.update({i["subject"]: old_money + i["priceWithDisc"]})
            return orders_subj

        date_now = datetime.now()
        first_date = date_now - timedelta(1)
        data_first_order = classic_subj(
            all_requests.get_orders(
                data=first_date.strftime("%Y-%m-%d"), token=self.wb_token
            )
        )
        time.sleep(10)
        data_first_sale = classic_subj(
            all_requests.get_sales(
                data=first_date.strftime("%Y-%m-%d"), token=self.wb_token
            )
        )
        if not today:
            time.sleep(10)
            second_date = date_now - timedelta(2)
            data_second_sale = classic_subj(
                all_requests.get_sales(
                    data=second_date.strftime("%Y-%m-%d"), token=self.wb_token
                )
            )
            time.sleep(10)
            data_second_order = classic_subj(
                all_requests.get_orders(
                    data=second_date.strftime("%Y-%m-%d"), token=self.wb_token
                )
            )
        else:
            data_second_order, data_second_sale = 0, 0

        return {
            "data_first_order": data_first_order,
            "data_second_order": data_second_order,
            "data_first_sale": data_first_sale,
            "data_second_sale": data_second_sale,
        }

    def screen_v1(self, who_send):  # ежечасно
        general_text = f"👤*{self.name}*"

        # slovar = {... 20: 80000 , 21:10000, 22:15000, 23: 18000}

        date_now = datetime.now()
        hour = int(date_now.strftime("%H"))

        if hour in self.profit_time:
            yesterday_profit = int(self.profit_time[hour]["total_profit"])
        else:
            yesterday_profit = "Нет данных"

        if hour in self.revenue_time:  # new
            yesterday_revenue = int(self.revenue_time[hour]["total_revenue"])
        else:
            yesterday_revenue = "Нет данных"

        if hour == 0:
            first_date = date_now - timedelta(1)
            date_for_google = first_date.strftime("%Y-%m-%d")
            logger.info(f"to google: {date_for_google}")
            data = super().to_google(first_date)
        else:
            date_for_google = date_now.strftime("%Y-%m-%d")
            logger.info(f"to google: {date_for_google}")
            data = super().to_google(date_now)

        money_ord = data["money_ord"]
        profit_now = round(data["profit"], 2)
        delta_profit = data["delta_profit"]
        if isinstance(yesterday_revenue, str):
            delta_revenue = "Нет данных"
        else:
            delta_revenue = money_ord - yesterday_revenue

        general_text += f"*\n📈ВЫРУЧКА: {int(money_ord)} ₽\n📈Δ {smile(delta_revenue, yesterday_revenue)}\n\n💰 ПРИБЫЛЬ: {int(profit_now)} RUB. \n💰 РЕНТА: {round(data['renta'] * 100, 2)}%\n💰 ДРР: {round(data['drr'] * 100, 2)}%*\n\n"
        general_text += f"*💰 ВЧЕРА В ЭТО ВРЕМЯ: {yesterday_profit} RUB.\n"
        general_text += f"💰 Δ {smile(delta_profit, yesterday_profit)}*"

        if not data["ad"]:
            general_text += "\n\n*!БЕЗ УЧЕТА РЕКЛАМЫ!*"
        bot.send_message(who_send, text=general_text, parse_mode="Markdown")

    def screen_v2(self, who_send):
        def general_text_today(data1, data2, type):
            all_sum1 = round(sum(list(data1.values())))
            all_sum2 = round(sum(list(data2.values())))
            result_text = f"*📍 {type}: {all_sum1} RUB.\n    От вчера: {smile(all_sum1 - all_sum2, all_sum2)}*\n\n"
            for i in data1:
                if i in list(data2.keys()):
                    delta = round(data1[i] - data2[i])
                else:  # если такого товара позавчера не было
                    delta = round(data1[i])
                    data2[i] = delta
                result_text += f"📌*{i}: {round(data1[i])} RUB.*\n    От вчера: {smile(delta, data2[i])}\n"

            return result_text

        general_text = f"👤*{self.name}*\n\n"

        date_now = datetime.now()
        first_date = date_now - timedelta(1)
        data_of_profit = super().to_google(first_date, 0)

        general_text += f"*💰 ПРИБЫЛЬ: {int(data_of_profit['profit'])} RUB. \n💰 РЕНТА: {round(data_of_profit['renta'] * 100, 2)}%\n💰 ДРР: {round(data_of_profit['drr'] * 100, 2)}%\n💰 Годовая доходность: {round(data_of_profit['prc_year'] * 100, 2)}%*\n\n"
        time.sleep(30)
        data = self.by_api_get_data()
        general_text += general_text_today(
            data["data_first_order"], data["data_second_order"], "Заказы"
        )
        general_text += "\n\n" + general_text_today(
            data["data_first_sale"], data["data_second_sale"], "Продажи"
        )

        if not data_of_profit["ad"]:
            general_text += "\n\n*! БЕЗ УЧЕТА РЕКЛАМЫ !*"

        bot.send_message(who_send, text=general_text, parse_mode="Markdown")


def all_start_to_user():
    for i in range(3):
        try:
            df = get_clients()
            break
        except Exception as ex:
            bot.send_message(
                "-1002417112074",
                f"ERROR ERROR ERROR TO USER - Clients haven't got \nError: {ex}",
            )
            time.sleep(60)

    for row in df.itertuples():
        if row.type == "Profit":
            if row.enabled == "1":
                id_tg = row.id_tg
                name = row.name
                # if name != "IP PILAT":
                #     continue
                wb_token = row.wb_token
                key_table = row.key_table
                chat_ = row.chat_
                chat_ = True if chat_ == "TRUE" else False
                for j in range(3):
                    try:
                        client = UpdateData(key_table, name, wb_token, chat_, id_tg)
                        client.to_user()
                        bot.send_message(
                            "-1002417112074",
                            f"✅GOOD SEND to USER\n name:{client.name}",
                        )
                        break
                    except Exception as ex:
                        bot.send_message(
                            "-1002417112074",
                            f"ERROR ERROR ERROR TO USER \nname:{name}\nError: {ex}",
                        )
                        time.sleep(90)


def all_start_to_chat():
    for i in range(3):
        try:
            df = get_clients()
            break
        except Exception as ex:
            bot.send_message(
                "-1002417112074",
                f"ERROR ERROR ERROR TO USER - Clients haven't got \nError: {ex}",
            )
            time.sleep(60)

    for row in df.itertuples():
        if row.type == "Profit":
            if row.enabled == "1":
                id_tg = row.id_tg
                name = row.name
                wb_token = row.wb_token
                key_table = row.key_table
                chat_ = row.chat_
                chat_ = True if chat_ == "TRUE" else False
                for j in range(3):
                    try:
                        client = UpdateData(key_table, name, wb_token, chat_, id_tg)
                        client.to_chat()
                        bot.send_message(
                            "-1002417112074",
                            f"✅GOOD SEND to CHAT\n name:{client.name}",
                        )
                        break
                    except Exception as ex:
                        bot.send_message(
                            "-1002417112074",
                            f"ERROR ERROR ERROR TO CHAT \nname:{client.name}\nError: {ex}",
                        )
                        time.sleep(120)


def updates_data():
    schedule.every().day.at("10:00").do(all_start_to_chat)
    schedule.every().hour.at(":00").do(all_start_to_user)
    while True:
        schedule.run_pending()
        time.sleep(1)


logger.info("Starting...")
all_start_to_user()
updates_data()
