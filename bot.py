import logging
from time import sleep
from aiogram import Bot, Dispatcher, executor, types
from aiogram.utils.exceptions import BotBlocked, NetworkError
import auxiliary_functions as af
from time import sleep
import spacy

# Bot object

bot = Bot(token="your token")
dp = Dispatcher(bot)

# Turning on logging
logging.basicConfig(level=logging.INFO)

# Bot supports Rus and Eng, so we need to detect input languge
nlp_en = spacy.load("en_core_web_sm")
nlp_ru = spacy.load("ru_core_news_sm")


@dp.message_handler(commands='start')
async def send_welcome(message: types.Message):
    """
    This handler will be called when user sends `/start` command
    """
    # write the msg info to DB
    af.write_to_db(message, type_of_query='start')
    await message.answer(af.get_start_msg(message.from_user.full_name))


@dp.message_handler(commands='help')
async def send_welcome(message: types.Message):
    """
    This handler will be called when user sends `/help` command
    """
    # write the msg info to DB
    af.write_to_db(message, type_of_query='help')
    await message.answer(af.get_help_msg(message.from_user.full_name))


@dp.message_handler(commands='stats')
async def send_stats(message: types.Message):
    """
    This handler will be called when user sends `/stats` command
    """
    # Get data from DB and write the msg info
    data = af.write_to_db(message, type_of_query='stats')
    await bot.send_message(message.chat.id, f"Hi, {message.from_user.full_name}!")
    ans = af.user_stats(data)
    await message.answer(ans)


@dp.message_handler(commands="lucky")
async def lucky_command(message: types.Message):
    # generate random coords
    lat, lon = af.lucky_coords(0, 60, 0, 60)

    #Notify user that processing is started
    ans = f"Fine! Your lucky coordinates are are {float(lat):.2f}, {float(lon):.2f}\
    \nLet me look around ...\
    \nI'll answer in a few seconds)\n"
    await bot.send_message(message.chat.id, ans)

    # write the msg info to DB
    af.write_to_db(message, type_of_query='lucky')

    # run processing of query
    await af.process_lucky_query(lat, lon, message, bot)


@dp.message_handler()
async def read_coords(message: types.Message):
    af.write_to_db(message, type_of_query='text')
    # generate coords without assumptions about imput
    # it yet can be teext of coords
    direct_coords =  af.coords_matcher(message.text)
    adress_coords = af.get_coords(message.text)

    # check whether text imput includes any location describing words  
    GPE_tick_en = bool([f for f in nlp_en(message.text).ents if f.label_ == 'GPE'])
    GPE_tick_ru = bool([f for f in nlp_ru(message.text).ents if f.label_ == 'LOC'])

    # if we didn't find coords or adress - finish processing and notify user
    # elif we have direct coords - work with them and finish
    # elif we have adress coords - work with them and finish
    # else bot received improper imput
    if not (GPE_tick_en or GPE_tick_ru or af.coords_matcher(message.text)):
        await bot.answer("I'm not sure that that's a right adress...")
    elif direct_coords:
        lat, lon = direct_coords
        await af.process_query(lat, lon, message, bot)
    elif adress_coords:
        lat, lon, _ = adress_coords
        await af.process_query(lat, lon, message, bot)
    else:
        # If bot 
        await bot.send_message(message.chat.id, 'Hmm ... Let me think!')
        sleep(3)
        await message.answer("I don't see any coordinates or adress\nI can't help you, sorry!")
        sleep(1)


# SOme error handlers
@dp.errors_handler(exception=BotBlocked)
async def error_bot_blocked(update: types.Update, exception: BotBlocked):
    print(f"I'm blocked by user!\nMessage: {update}\nError: {exception}")
    return True


@dp.errors_handler(exception=NetworkError)
async def error_network_error(update: types.Update, exception: NetworkError):
    print(f"NetworkError!\nMessage: {update}\nError: {exception}")
    await bot.send_message(update.message.chat.id, 'Currently netwok is overloaded')
    return True


dp.register_message_handler(send_welcome, commands=['start', 'help'])
dp.register_message_handler(lucky_command, commands="lucky")
dp.register_message_handler(read_coords)

if __name__ == "__main__":
    # bot launch
    executor.start_polling(dp, skip_updates=True)
