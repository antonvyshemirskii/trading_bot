import requests
import schedule
import time
from prophet import Prophet
from datetime import datetime, timedelta
import yfinance as yf
from pytz import timezone
import math

token = "6722775517:AAETw--kWj05Q4W4XJqEJucuK377CUQpoK4"
channel_id = "-1002026874897"
ukr_timezone = timezone("EET")

# GMT:
currency_close_time = "23:59"  # gmt
stock_market_close_time = "21:00"
target_times = ["14:00", "17:00", "20:00"]  # gmt
all_times = ["14:00", "17:00", "20:00", "21:00", "23:59"]

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
        "timezone": timezone("America/New_York"),
    },
}


def preprocess(data, offset=0.0001):
    data.reset_index(inplace=True)
    data["Datetime"] = data["Datetime"].dt.tz_localize(None)
    preprocessed_data = data[["Datetime", "Close"]].rename(
        columns={"Datetime": "ds", "Close": "y"}
    )
    preprocessed_data["cap"] = data["High"] + offset
    preprocessed_data["floor"] = data["Low"]
    return preprocessed_data


def fit_model(train_data):
    model = Prophet(changepoint_prior_scale=0.74, growth="logistic")
    model.add_seasonality(name="hourly", period=7, fourier_order=36)
    model.fit(train_data)
    return model


def get_prediction(model, periods, interval, train_data):
    future_df = model.make_future_dataframe(periods=periods, freq=interval)
    future_df.loc[future_df.index[:-periods], "cap"] = train_data["cap"].values
    future_df.loc[future_df.index[:-periods], "floor"] = train_data["floor"].values
    future_df.loc[future_df.index[-periods:], "cap"] = train_data["cap"].iloc[-1]
    future_df.loc[future_df.index[-periods:], "floor"] = train_data["floor"].iloc[-1]
    forecast = model.predict(future_df)
    target_prediction = forecast.iloc[-1]["yhat"]
    return target_prediction


def get_future_price(ticker, periods=3, start="2023-01-09", interval="1h"):
    data = yf.download(ticker, start, interval=interval)
    train_data = preprocess(data)
    model = fit_model(train_data)
    pred_value = get_prediction(model, periods, interval, train_data)
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


def msg_time_wrapper(msg_type, shift, header):
    (
        local_time,
        currency_time,
        stock_market_time,
    ) = get_shifted_times(shift)
    message = header
    message = f"{msg_type} prices at {local_time} (EET Ukraine)\n"
    message += f"{msg_type} currency time: {currency_time} (GMT)\n"
    message += f"{msg_type} stock market time: {stock_market_time} (EDT New York)\n"
    return message


def get_time_diff(time1_str, time2_str):
    time1 = datetime.strptime(time1_str, "%H:%M")
    time2 = datetime.strptime(time2_str, "%H:%M")
    time_diff_hours = (time1 - time2).total_seconds() / 3600
    time_diff = math.ceil(time_diff_hours)
    return time_diff


def append_prices(shift, pairs, message, msg_type):
    for pair in pairs:
        if msg_type == "future":
            price = round(get_future_price(pair["ticker"], shift), 5)
        elif msg_type == "real":
            price = round(get_current_price(pair["ticker"]), 5)
        message += f"{pair['name']} : {price}\n"
    return message


def price_message_wrapper(curr_time, msg_type):
    currency_shift = get_time_diff(currency_close_time, curr_time)
    currency_message = msg_time_wrapper(msg_type, currency_shift, "\ncurrency pairs\n")
    currency_message = append_prices(
        currency_shift,
        target_pairs["currency"]["currency_pairs"],
        currency_message,
        msg_type,
    )
    if curr_time == currency_close_time:
        return currency_message

    stock_market_shift = get_time_diff(stock_market_close_time, curr_time)
    stock_market_message = msg_time_wrapper(
        msg_type, stock_market_shift, "\nstock market shares:\n"
    )
    stock_market_message = append_prices(
        stock_market_shift,
        target_pairs["stock_market"]["stock_market_pairs"],
        stock_market_message,
        msg_type,
    )
    if curr_time == stock_market_close_time:
        return stock_market_message
    message = currency_message + stock_market_message
    return message


def create_url(message_text):
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={channel_id}&text={message_text}"
    return url


def send_future_prices(current_time):
    if current_time == currency_close_time or current_time == stock_market_close_time:
        return
    future_prices_text = price_message_wrapper(current_time, "future")
    message_url = create_url(future_prices_text)
    requests.get(message_url)


def send_current_prices(current_time):
    if current_time in target_times:
        return
    current_prices_text = price_message_wrapper(current_time, "real")
    message_url = create_url(current_prices_text)
    requests.get(message_url)


def send_messages(current_time):
    send_current_prices(current_time)
    send_future_prices(current_time)


def main():
    for t in all_times:
        schedule.every().monday.at(t).do(send_messages, t)
        schedule.every().tuesday.at(t).do(send_messages, t)
        schedule.every().wednesday.at(t).do(send_messages, t)
        schedule.every().thursday.at(t).do(send_messages, t)
        schedule.every().friday.at(t).do(send_messages, t)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
