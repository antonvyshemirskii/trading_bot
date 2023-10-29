import asyncio

from datetime import date
import yfinance as yf
from prophet import Prophet

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

API_TOKEN = "6722775517:AAETw--kWj05Q4W4XJqEJucuK377CUQpoK4"

# Initialize bot and dispatcher
dp = Dispatcher()

market_pairs = ["EURUSD", "GBPUSD", "USDCHF", "USDCAD", "USDJPY", "AUDUSD", "NZDUSD"]
market_pairs_buttons = [KeyboardButton(text=btn_text) for btn_text in market_pairs]
# button_eur_usd = KeyboardButton(text="EURUSD")
# button_gbp_usd = KeyboardButton(text="GBPUSD")
# button_usd_chf = KeyboardButton(text="USDCHF")
# button_usd_cad = KeyboardButton(text="USDCAD")
# button_usd_jpy = KeyboardButton(text="USDJPY")
# button_aud_usd = KeyboardButton(text="AUDUSD")
# button_nzd_usd = KeyboardButton(text="NZDUSD")

back_button = KeyboardButton(text="get back to market pairs")

keyboard_market_pairs = ReplyKeyboardMarkup(
    resize_keyboard=True,
    one_time_keyboard=True,
    keyboard=[market_pairs_buttons],
)
# [
#     button_eur_usd,
#     button_aud_usd,
#     button_usd_cad,
#     button_gbp_usd,
#     button_nzd_usd,
#     button_usd_chf,
#     button_usd_jpy,
# ]
keyboard_get_back = ReplyKeyboardMarkup(
    resize_keyboard=True,
    one_time_keyboard=True,
    keyboard=[[back_button]],
)


# Start command handler
@dp.message(CommandStart())
async def start(message: Message):
    await message.reply(
        "Hello! I am market controller bot! Please choose the pair!",
        reply_markup=keyboard_market_pairs,
    )


def load_data(
    ticker, start_date="2015-01-01", end_date="2023-10-25"
):  # end_date=date.today().strftime("%Y-%m-%d")
    # ):
    data = yf.download(ticker, start_date, end_date)
    data.reset_index(inplace=True)
    return data


def preproc_data(data):
    data = data[["Date", "Close"]]
    data = data.rename(columns={"Date": "ds", "Close": "y"})
    return data


def create_model(df_train):
    model = Prophet()
    model.fit(df_train)
    return model


def forecast_future(model, period=1):
    future = model.make_future_dataframe(periods=period)
    forecast = model.predict(future)
    return forecast


def get_today_close_pice_prediction(ticker):
    dataset = load_data(ticker)
    df_train = preproc_data(dataset)
    model = create_model(df_train)
    forecast = forecast_future(model)
    todays_predictions = forecast.iloc[-1]
    return {
        "close_predicted_price": todays_predictions["yhat"],
        "close_lower_predicted_price": todays_predictions["yhat_lower"],
        "close_upper_predicted_price": todays_predictions["yhat_upper"],
    }


def check_weekend():
    current_day = date.today().strftime("%A")
    weekends = ["Saturday", "Sunday"]
    if current_day in weekends:
        return True
    return False


def generate_answer(ticker):
    answer = (
        "The market is closed. Take your time to relax, and come back on Monday. :)"
    )
    is_weekend = False  # check_weekend()
    if is_weekend:
        return answer
    predictions = get_today_close_pice_prediction("EURUSD=X")
    close_pred_price = predictions["close_predicted_price"]
    close_lower_pred_price = predictions["close_lower_predicted_price"]
    close_upper_pred_price = predictions["close_upper_predicted_price"]
    answer = f"close predicted price: {close_pred_price} \nclose lower predicted price: {close_lower_pred_price} \nclose upper predicted price: {close_upper_pred_price}"
    return answer


@dp.message(lambda message: message.text in market_pairs)
async def kb_market_pairs_answer(message: Message):
    if message.text == "EURUSD":
        answer_message = generate_answer("EURUSD=X")
    elif message.text == "GBPUSD":
        answer_message = generate_answer("GBPUSD=X")
    elif message.text == "USDCHF":
        answer_message = generate_answer("CHF=X")
    elif message.text == "USDCAD":
        answer_message = generate_answer("CAD=X")
    elif message.text == "USDJPY":
        answer_message = generate_answer("USDJPY=X")
    elif message.text == "AUDUSD":
        answer_message = generate_answer("AUDUSD=X")
    elif message.text == "NZDUSD":
        answer_message = generate_answer("NZDUSD=X")

    await message.reply(answer_message, reply_markup=keyboard_get_back)


@dp.message(lambda message: message.text == "get back to market pairs")
async def kb_answer(message: Message):
    await message.reply(
        "So let's pick up next market pair!",
        reply_markup=keyboard_market_pairs,
    )


async def main() -> None:
    bot = Bot(token=API_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
