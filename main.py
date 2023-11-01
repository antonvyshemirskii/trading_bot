import requests
import schedule
import time
from prophet import Prophet
from datetime import datetime, timedelta
import yfinance as yf
from pytz import timezone

token = "6722775517:AAETw--kWj05Q4W4XJqEJucuK377CUQpoK4"
channel_id = "-1002026874897"
ukr_timezone = timezone("EET")

target_times = ["13:58", "14:00", "15:32", "18:32", "21:32"]
target_pairs = {
    "currency": {
        "currency_pairs": [
            {"name": "EURUSD", "ticker": "EURUSD=X"},
            {"name": "GBPUSD", "ticker": "GBPUSD=X"},
            {"name": "USDCHF", "ticker": "CHF=X"},
            {"name": "USDJPY", "ticker": "USDJPY=X"},
            {"name": "AUDUSD", "ticker": "AUDUSD=X"},
            {"name": "NZDUSD", "ticker": "NZDUSD=X"},
        ],
        "timezone": timezone("GMT"),
    },
    "stock_market": {
        "stock_market_pairs": [
            {"name": "SP-500", "ticker": "^GSPC"},
            {"name": "Tesla", "ticker": "TSLA"},
            {"name": "NVIDIA", "ticker": "NVDA"},
            {"name": "Apple", "ticker": "AAPL"},
            {"name": "Amazon", "ticker": "AMZN"},
        ],
        "timezone": timezone("EST"),
    },
}


def preprocess(data):
    data.reset_index(inplace=True)
    data["Datetime"] = data["Datetime"].dt.tz_localize(None)
    preprocessed_data = data[["Datetime", "Close"]].rename(
        columns={"Datetime": "ds", "Close": "y"}
    )
    print(preprocessed_data)
    return preprocessed_data


def fit_model(train_data):
    model = Prophet()
    model.fit(train_data)
    return model


def get_prediction(model, periods, interval):
    future_df = model.make_future_dataframe(periods=periods, freq=interval)
    forecast = model.predict(future_df)
    target_prediction = forecast.iloc[-1]["yhat"]
    return target_prediction


def get_future_price(ticker, periods=3, start="2023-06-09", interval="1h"):
    data = yf.download(ticker, start, interval=interval)
    train_data = preprocess(data)
    model = fit_model(train_data)
    pred_value = get_prediction(model, periods, interval)
    return pred_value


def get_current_price(ticker):
    ticker = yf.Ticker(ticker)
    todays_data = ticker.history(period="1d")
    return todays_data["Close"].iloc[0]


def get_shifted_times(shift):
    my_time = (
        (datetime.now(ukr_timezone) + timedelta(hours=shift))
        .replace(microsecond=0)
        .replace(tzinfo=None)
    )
    currency_time = (
        (datetime.now(target_pairs["currency"]["timezone"]) + timedelta(hours=shift))
        .replace(microsecond=0)
        .replace(tzinfo=None)
    )
    stock_market_time = (
        (
            datetime.now(target_pairs["stock_market"]["timezone"])
            + timedelta(hours=shift)
        )
        .replace(microsecond=0)
        .replace(tzinfo=None)
    )
    return my_time, currency_time, stock_market_time


def msg_time_wrapper(msg_type, our_time, currency_time, stock_market_time):
    message = f"{msg_type} prices at {our_time} (EET Ukraine)\n"
    message += f"{msg_type} currency time: {currency_time} (GMT)\n"
    message += f"{msg_type} stock market time: {stock_market_time} (EST)\n"
    return message


def price_message_wrapper(time_shift, msg_type, get_price):
    (
        local_time,
        currency_time,
        stock_market_time,
    ) = get_shifted_times(time_shift)
    message = msg_time_wrapper(msg_type, local_time, currency_time, stock_market_time)
    message += "\ncurrency_pairs:\n"
    for tg_pair in target_pairs["currency"]["currency_pairs"]:
        curr_price = round(get_price(tg_pair["ticker"]), 5)
        message += f"{tg_pair['name']} : {curr_price}\n"

    message += "\nstock market shares:\n"
    for sm_pair in target_pairs["stock_market"]["stock_market_pairs"]:
        curr_price = round(get_price(sm_pair["ticker"]), 5)
        message += f"{sm_pair['name']} : {curr_price}\n"

    return message


def current_price_wrapper():
    message = price_message_wrapper(0, "real", get_current_price)
    return message


def future_price_wrapper(periods=3):
    message = price_message_wrapper(periods, "future", get_future_price)
    return message


def create_url(message_text):
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={channel_id}&text={message_text}"
    return url


def send_future_prices(current_time):
    if current_time == target_times[-1]:
        return

    future_prices_text = future_price_wrapper()
    message_url = create_url(future_prices_text)
    requests.get(message_url)


def send_current_prices(current_time):
    current_prices_text = current_price_wrapper()
    message_url = create_url(current_prices_text)
    requests.get(message_url)


def send_messages(current_time):
    send_current_prices(current_time)
    send_future_prices(current_time)


def main():
    for t in target_times:
        schedule.every().monday.at(t).do(send_messages, t)
        schedule.every().tuesday.at(t).do(send_messages, t)
        schedule.every().wednesday.at(t).do(send_messages, t)
        schedule.every().thursday.at(t).do(send_messages, t)
        schedule.every().friday.at(t).do(send_messages, t)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
