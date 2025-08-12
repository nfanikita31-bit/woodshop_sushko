import asyncio
import requests
import os
from math import radians, sin, cos, sqrt, atan2
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# 🔧 Настройки через переменные окружения
TOKEN = os.getenv("TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WAREHOUSE_COORDS = [53.136631, 25.805957]

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
user_data = {}

# 🔥 Цены
firewood_prices = {
    "Береза колотая": {2.5: 260, 5: 520},
    "Береза чурками": {2.5: 240, 5: 500},
    "Ольха колотая": {2.5: 260, 5: 495},
    "Ольха чурками": {2.5: 240, 5: 475},
    "Микс(береза+ольха)колотая": {2.5: 260, 5: 500},
    "Микс(береза+ольха)чурками": {2.5: 240, 5: 480},
    "Обрезки 3-4 метра": {5: 169},
    "Обрезки резанные (30-40 см)": {5: 235}
}

# 🎯 Скидки
discount_map = {
    "Пенсионер": 0.05,
    "Инвалид": 0.05,
    "Без скидки": 0.0
}

# 📱 Клавиатуры
wood_types = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=key)] for key in firewood_prices.keys()],
    resize_keyboard=True
)

volume_types = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="2.5 куба")], [KeyboardButton(text="5 кубов")]],
    resize_keyboard=True
)

discount_types = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=key)] for key in discount_map.keys()],
    resize_keyboard=True
)

restart_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔁 Новый заказ")]],
    resize_keyboard=True
)

# 🌍 Геокодинг
def get_coords(address):
    try:
        url = "https://geocode-maps.yandex.ru/1.x/"
        params = {
            "apikey": YANDEX_API_KEY,
            "geocode": address,
            "format": "json"
        }
        response = requests.get(url, params=params).json()
        members = response['response']['GeoObjectCollection']['featureMember']
        if not members:
            return None
        pos = members[0]['GeoObject']['Point']['pos']
        lon, lat = map(float, pos.split())
        return [lat, lon]
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None

# 📏 Расчёт расстояния
def get_distance_km(from_coords, to_coords):
    R = 6371
    lon1, lat1 = map(radians, from_coords[::-1])
    lon2, lat2 = map(radians, to_coords[::-1])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return round(R * c, 2)

# 📩 Хендлеры
@dp.message()
async def handle_message(msg: types.Message):
    uid = msg.from_user.id
    text = msg.text

    if text in ["/start", "🔁 Новый заказ"]:
        user_data[uid] = {}
        await msg.answer("Выберите вид дров:", reply_markup=wood_types)
        return

    if text in firewood_prices:
        user_data[uid] = {'wood': text}
        await msg.answer("Выберите объем:", reply_markup=volume_types)
        return

    if text in ["2.5 куба", "5 кубов"] and 'wood' in user_data.get(uid, {}):
        selected_wood = user_data[uid]['wood']
        selected_volume = float(text.split()[0])
        if selected_volume not in firewood_prices[selected_wood]:
            await msg.answer("Для выбранного вида дров доступен только объем 5 кубов.")
            return
        user_data[uid]['volume'] = selected_volume
        await msg.answer("Введите адрес доставки:", reply_markup=ReplyKeyboardRemove())
        return

    if 'volume' in user_data.get(uid, {}) and 'address' not in user_data[uid]:
        user_data[uid]['address'] = text
        await msg.answer("Введите номер телефона:")
        return

    if 'address' in user_data.get(uid, {}) and 'phone' not in user_data[uid]:
        user_data[uid]['phone'] = text
        await msg.answer("Выберите скидку:", reply_markup=discount_types)
        return

    if text in discount_map and 'phone' in user_data.get(uid, {}):
        data = user_data[uid]
        data['discount'] = text
        data['discount_rate'] = discount_map[text]

        to_coords = get_coords(data['address'])
        if not to_coords:
            await msg.answer("Не удалось определить координаты. Проверь адрес.")
            return

        distance = get_distance_km(WAREHOUSE_COORDS, to_coords)
        base_price = firewood_prices[data['wood']][data['volume']]
        delivery_price = 1 * distance
        discounted_price = base_price * (1 - data['discount_rate'])
        discount_value = base_price * data['discount_rate']
        total = discounted_price + delivery_price

        summary = (
            f"📦 Заказ:\n"
            f"Вид дров: {data['wood']}\n"
            f"Объем: {data['volume']} кубов\n"
            f"Адрес: {data['address']}\n"
            f"Телефон: {data['phone']}\n"
            f"Скидка: {data['discount']} ({int(data['discount_rate']*100)}%)\n"
            f"Расстояние: {distance:.2f} км\n"
            f"💰 Цена дров (со скидкой): {discounted_price:.2f} руб.\n"
            f"🔻 Скидка на дрова: -{discount_value:.2f} руб.\n"
            f"🚚 Доставка: {delivery_price:.2f} руб.\n"
            f"💵 Итоговая цена: {total:.2f} руб."
        )

        await msg.answer(summary, reply_markup=restart_keyboard)
        await bot.send_message(ADMIN_ID, f"🛒 Новый заказ:\n{summary}")
        return

# 🚀 Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
