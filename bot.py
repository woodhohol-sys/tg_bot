import asyncio
import json
import logging
import os
import re
from datetime import datetime
from telethon import TelegramClient
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize clients
client = TelegramClient('user_session', Config.API_ID, Config.API_HASH)
bot = Bot(token=Config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Storage files
GROUPS_FILE = Config.GROUPS_FILE
SETTINGS_FILE = 'bot_settings.json'

# States
class BotStates(StatesGroup):
    waiting_for_group = State()
    waiting_for_delay = State()
    waiting_for_message = State()
    waiting_for_tag_user = State()

# Load data functions
def load_groups():
    if os.path.exists(GROUPS_FILE):
        try:
            with open(GROUPS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {
                "mailing_enabled": False, 
                "delay_seconds": 60, 
                "simultaneous_sending": True,
                "auto_repeat": False,
                "repeat_count": 0,
                "max_repeats": 10
            }
    return {
        "mailing_enabled": False, 
        "delay_seconds": 60, 
        "simultaneous_sending": True,
        "auto_repeat": False,
        "repeat_count": 0,
        "max_repeats": 10
    }

def save_groups(groups):
    try:
        with open(GROUPS_FILE, 'w') as f:
            json.dump(groups, f)
    except Exception as e:
        logger.error(f"Error saving groups: {e}")

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f)
    except Exception as e:
        logger.error(f"Error saving settings: {e}")

# Global variables
groups = load_groups()
bot_settings = load_settings()
pending_message = None
is_mailing_active = False
mailing_task = None

# Keyboard layouts - UKRAINIAN
def get_main_keyboard():
    mailing_status = "🟢 Запустити розсилку" if not is_mailing_active else "🔴 Зупинити розсилку"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Переглянути групи"), KeyboardButton(text="➕ Додати групу")],
            [KeyboardButton(text="🗑 Видалити групу"), KeyboardButton(text="⏰ Затримка")],
            [KeyboardButton(text="✏️ Створити повідомлення"), KeyboardButton(text=mailing_status)],
            [KeyboardButton(text="📤 Надіслати 1 раз"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="❓ Допомога")]
        ],
        resize_keyboard=True
    )

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Скасувати")]],
        resize_keyboard=True
    )

def get_compose_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Додати теги"), KeyboardButton(text="📤 Надіслати 1 раз")],
            [KeyboardButton(text="🔄 Авто-повтор"), KeyboardButton(text="❌ Скасувати")]
        ],
        resize_keyboard=True
    )

# Bot command handlers - UKRAINIAN
@dp.message(Command("start"))
async def start_command(message: types.Message):
    if message.from_user.id != Config.ADMIN_ID:
        await message.answer("❌ Неавторизований доступ. Цей бот приватний.")
        return
    
    welcome_text = """
🤖 **Персональний Telegram Бот для Розсилки**

Я відправляю ваші повідомлення в групи з вашего ОСОБИСТОГО акаунту.

**✨ Основні функції:**
• Ручне створення та відправка повідомлень  
• Автоматична розсилка з затримкою
• Підтримка текстів та фото (відразу видно)
• Одночасна відправка в усі групи
• Можливість тегувати користувачів
• Авто-повтор до зупинки
• Працює 24/7 навіть коли ви офлайн

**🚀 Швидкий старт:**
1. Створіть повідомлення через '✏️ Створити повідомлення'
2. Налаштуйте затримку через '⏰ Затримка'
3. Запустіть авто-розсилку через '🟢 Запустити розсилку'

Використовуйте кнопки нижче, щоб почати!
    """
    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode='Markdown')

@dp.message(F.text == "📋 Переглянути групи")
async def view_groups(message: types.Message):
    if not groups:
        await message.answer("❌ Групи ще не додані. Використовуйте '➕ Додати групу' щоб додати першу групу.")
        return
    
    groups_text = "📋 **Ваші групи:**\n\n"
    for i, group in enumerate(groups, 1):
        groups_text += f"{i}. {group['title']}\n   ID: `{group['id']}`\n\n"
    
    groups_text += f"**Всього:** {len(groups)} груп"
    await message.answer(groups_text, parse_mode='Markdown')

@dp.message(F.text == "➕ Додати групу")
async def add_group_start(message: types.Message, state: FSMContext):
    await state.set_state(BotStates.waiting_for_group)
    await message.answer(
        "🔍 **Як додати групу:**\n\n"
        "1. Відкрийте Telegram та перейдіть в цільову групу\n"
        "2. Скопіюйте посилання-запрошення групи\n"
        "3. Надішліть посилання сюди\n\n"
        "Або надішліть ID групи (якщо знаєте)\n\n"
        "Натисніть '❌ Скасувати' для відміни",
        reply_markup=get_cancel_keyboard(),
        parse_mode='Markdown'
    )

@dp.message(BotStates.waiting_for_group)
async def add_group_process(message: types.Message, state: FSMContext):
    if message.text == "❌ Скасувати":
        await state.clear()
        await message.answer("❌ Скасовано.", reply_markup=get_main_keyboard())
        return
    
    try:
        group_input = message.text.strip()
        
        # Try to get entity by username or invite link
        if 't.me/' in group_input:
            # Extract username from link
            username = group_input.split('t.me/')[-1].split('/')[-1]
            if '+' in username:
                username = username.replace('+', '')
            entity = await client.get_entity(username)
        else:
            # Try as group ID
            entity = await client.get_entity(int(group_input))
        
        group_info = {
            'id': entity.id,
            'title': entity.title,
            'username': getattr(entity, 'username', None)
        }
        
        # Check if group already exists
        if any(g['id'] == group_info['id'] for g in groups):
            await message.answer("❌ Ця група вже є у вашому списку.")
        else:
            groups.append(group_info)
            save_groups(groups)
            await message.answer(f"✅ **Групу успішно додано!**\n\n**Назва:** {entity.title}\n**ID:** `{entity.id}`", 
                               reply_markup=get_main_keyboard(), parse_mode='Markdown')
        
        await state.clear()
        
    except Exception as e:
        await message.answer(f"❌ Помилка: Не вдалося знайти групу. Будь ласка, перевірте посилання/ID та спробуйте ще раз.\n\nПомилка: {str(e)}")

@dp.message(F.text == "🗑 Видалити групу")
async def remove_group_start(message: types.Message):
    if not groups:
        await message.answer("❌ Немає груп для видалення.")
        return
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    for group in groups:
        keyboard.add(KeyboardButton(f"🗑 {group['title']}"))
    keyboard.add(KeyboardButton("❌ Скасувати"))
    
    await message.answer("Виберіть групу для видалення:", reply_markup=keyboard)

@dp.message(F.text.startswith("🗑 "))
async def remove_group_action(message: types.Message):
    if message.text == "❌ Скасувати":
        await message.answer("❌ Скасовано.", reply_markup=get_main_keyboard())
        return
    
    group_title = message.text.replace("🗑 ", "")
    global groups
    initial_count = len(groups)
    groups = [g for g in groups if g['title'] != group_title]
    
    if len(groups) < initial_count:
        save_groups(groups)
        await message.answer(f"✅ Групу '{group_title}' успішно видалено!", reply_markup=get_main_keyboard())
    else:
        await message.answer("❌ Групу не знайдено.", reply_markup=get_main_keyboard())

@dp.message(F.text == "⏰ Затримка")
async def change_delay_start(message: types.Message, state: FSMContext):
    await state.set_state(BotStates.waiting_for_delay)
    await message.answer(
        f"⏰ Поточна затримка: {bot_settings['delay_seconds']} секунд\n\n"
        "Введіть нову затримку в секундах між повідомленнями:\n"
        "60 = 1 хвилина\n"
        "120 = 2 хвилини\n"
        "300 = 5 хвилин\n"
        "600 = 10 хвилин",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(BotStates.waiting_for_delay)
async def change_delay_process(message: types.Message, state: FSMContext):
    if message.text == "❌ Скасувати":
        await state.clear()
        await message.answer("❌ Скасовано.", reply_markup=get_main_keyboard())
        return
    
    try:
        delay = int(message.text)
        if 1 <= delay <= 3600:  # Up to 1 hour
            bot_settings['delay_seconds'] = delay
            save_settings(bot_settings)
            minutes = delay // 60
            seconds = delay % 60
            time_text = f"{minutes} хв {seconds} сек" if minutes > 0 else f"{delay} сек"
            await message.answer(f"✅ Затримку встановлено на {time_text}!", reply_markup=get_main_keyboard())
        else:
            await message.answer("❌ Будь ласка, введіть число від 1 до 3600 секунд (1 година).")
            return
    except ValueError:
        await message.answer("❌ Будь ласка, введіть коректне число.")
        return
    
    await state.clear()

@dp.message(F.text == "✏️ Створити повідомлення")
async def compose_message_start(message: types.Message, state: FSMContext):
    await state.set_state(BotStates.waiting_for_message)
    await message.answer(
        "✏️ **Створіть ваше повідомлення:**\n\n"
        "Надішліть:\n"
        "• Текст повідомлення\n"
        "• Фото з підписом (відразу видно)\n\n"
        "Це повідомлення буде використовуватись для авто-розсилки.\n\n"
        "Натисніть '❌ Скасувати' для відміни",
        reply_markup=get_cancel_keyboard(),
        parse_mode='Markdown'
    )

# Handle text messages
@dp.message(BotStates.waiting_for_message, F.text)
async def compose_text_process(message: types.Message, state: FSMContext):
    global pending_message
    
    if message.text == "❌ Скасувати":
        await state.clear()
        await message.answer("❌ Скасовано.", reply_markup=get_main_keyboard())
        return
    
    # Store the composed message
    pending_message = {
        'text': message.text,
        'media': None,
        'message_type': 'text'
    }
    
    logger.info(f"Text message saved: {pending_message['text'][:50]}...")
    
    # Ask what to do next
    await message.answer(
        "✅ Текстове повідомлення створено!\n\n"
        "Що бажаєте зробити далі?",
        reply_markup=get_compose_keyboard()
    )
    await state.clear()

# Handle photo messages
@dp.message(BotStates.waiting_for_message, F.photo)
async def compose_photo_process(message: types.Message, state: FSMContext):
    global pending_message
    
    try:
        # Download and store the photo properly
        file_info = await bot.get_file(message.photo[-1].file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        photo_data = downloaded_file.read()
        
        # Store everything needed for proper photo sending
        pending_message = {
            'text': message.caption or "",
            'photo_data': photo_data,
            'message_type': 'photo',
            'file_extension': 'jpg'
        }
        
        logger.info(f"Photo message saved. Caption: '{pending_message['text']}', Size: {len(photo_data)} bytes")
        
        # Ask what to do next
        await message.answer(
            "✅ Фото з підписом створено!\n\n"
            "Що бажаєте зробити далі?",
            reply_markup=get_compose_keyboard()
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing photo: {e}")
        await message.answer("❌ Помилка при обробці фото. Спробуйте ще раз.")
        await state.clear()

@dp.message(F.text == "✅ Додати теги")
async def add_tags_start(message: types.Message, state: FSMContext):
    await state.set_state(BotStates.waiting_for_tag_user)
    await message.answer(
        "🔖 **Додати теги користувачів:**\n\n"
        "Надішліть Telegram імена користувачів для тегування (по одному на рядок, без @):\n\n"
        "Приклад:\n"
        "username1\n"
        "username2\n\n"
        "Напишіть 'готово' коли закінчите або '❌ Скасувати' для відміни",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(BotStates.waiting_for_tag_user)
async def add_tags_process(message: types.Message, state: FSMContext):
    if message.text == "❌ Скасувати":
        await state.clear()
        await message.answer("❌ Скасовано.", reply_markup=get_main_keyboard())
        return
    
    if message.text.lower() == 'готово':
        await state.clear()
        await send_composed_message(message)
        return
    
    # Process usernames
    usernames = [line.strip() for line in message.text.split('\n') if line.strip()]
    tags_text = "\n".join([f"@{username}" for username in usernames])
    
    if pending_message:
        if pending_message['text']:
            pending_message['text'] = f"{pending_message['text']}\n\n{tags_text}"
        else:
            pending_message['text'] = tags_text
    
    await message.answer(
        f"✅ Теги додано! Поточне повідомлення:\n\n{pending_message['text']}\n\n"
        "Надішліть ще імена користувачів або напишіть 'готово' щоб відправити повідомлення.",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(F.text == "📤 Надіслати 1 раз")
async def send_once_handler(message: types.Message):
    await send_composed_message(message)

@dp.message(F.text == "🔄 Авто-повтор")
async def auto_repeat_handler(message: types.Message):
    if not pending_message:
        await message.answer("❌ Спочатку створіть повідомлення.", reply_markup=get_main_keyboard())
        return
    
    bot_settings['auto_repeat'] = True
    save_settings(bot_settings)
    await message.answer("🔄 Авто-повтор увімкнено! Запустіть розсилку для початку.", reply_markup=get_main_keyboard())

async def send_composed_message(message: types.Message):
    global pending_message
    
    if not pending_message:
        await message.answer("❌ Немає повідомлення для відправки. Спочатку створіть повідомлення.", reply_markup=get_main_keyboard())
        return
    
    if not groups:
        await message.answer("❌ Групи не додані. Будь ласка, спочатку додайте групи.", reply_markup=get_main_keyboard())
        return
    
    await send_to_all_groups(message)

async def send_to_all_groups(message: types.Message):
    """Send to all groups simultaneously"""
    await message.answer(f"⚡ Відправляю в {len(groups)} груп...")
    
    tasks = []
    for group in groups:
        task = send_to_group(group)
        tasks.append(task)
    
    # Send to all groups simultaneously
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Count results
    sent_count = sum(1 for result in results if result is True)
    failed_count = len(groups) - sent_count
    
    # Update statistics
    bot_settings['repeat_count'] += 1
    save_settings(bot_settings)
    
    # Final result
    if failed_count == 0:
        await message.answer(f"✅ Відправлено в {sent_count} груп! (Всього відправок: {bot_settings['repeat_count']})", reply_markup=get_main_keyboard())
    else:
        await message.answer(f"⚠️ Відправлено в {sent_count} груп, не вдалося в {failed_count} груп (Всього відправок: {bot_settings['repeat_count']})", reply_markup=get_main_keyboard())

async def send_to_group(group):
    """Send message to a single group"""
    try:
        if pending_message['message_type'] == 'photo':
            # Save photo to temporary file
            temp_filename = f"temp_photo_{group['id']}.jpg"
            with open(temp_filename, 'wb') as f:
                f.write(pending_message['photo_data'])
            
            try:
                # Send as photo (not document)
                if pending_message['text']:
                    await client.send_file(
                        group['id'],
                        temp_filename,
                        caption=pending_message['text'],
                        force_document=False
                    )
                else:
                    await client.send_file(
                        group['id'],
                        temp_filename,
                        force_document=False
                    )
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                    
        else:
            # Send text message
            await client.send_message(group['id'], pending_message['text'])
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send to {group['title']}: {e}")
        return False

async def mailing_loop():
    """Main mailing loop that runs automatically"""
    global is_mailing_active
    
    while is_mailing_active:
        try:
            if pending_message and groups:
                # Send to all groups
                tasks = [send_to_group(group) for group in groups]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                sent_count = sum(1 for result in results if result is True)
                
                # Update statistics
                bot_settings['repeat_count'] += 1
                save_settings(bot_settings)
                
                logger.info(f"Auto-mailing sent: {sent_count}/{len(groups)} groups. Total sends: {bot_settings['repeat_count']}")
            
            # Wait for the delay
            delay = bot_settings['delay_seconds']
            minutes = delay // 60
            seconds = delay % 60
            delay_text = f"{minutes} хв {seconds} сек" if minutes > 0 else f"{delay} сек"
            
            logger.info(f"Waiting {delay_text} before next mailing...")
            await asyncio.sleep(delay)
            
        except Exception as e:
            logger.error(f"Error in mailing loop: {e}")
            await asyncio.sleep(10)  # Wait 10 seconds before retrying

# Mailing control buttons
@dp.message(F.text.in_(["🟢 Запустити розсилку", "🔴 Зупинити розсилку"]))
async def toggle_mailing(message: types.Message):
    global is_mailing_active, mailing_task
    
    if message.text == "🟢 Запустити розсилку":
        if not pending_message:
            await message.answer("❌ Спочатку створіть повідомлення через '✏️ Створити повідомлення'.", reply_markup=get_main_keyboard())
            return
        
        if not groups:
            await message.answer("❌ Групи не додані. Спочатку додайте групи.", reply_markup=get_main_keyboard())
            return
        
        is_mailing_active = True
        # Start mailing loop
        mailing_task = asyncio.create_task(mailing_loop())
        
        delay = bot_settings['delay_seconds']
        minutes = delay // 60
        seconds = delay % 60
        delay_text = f"{minutes} хв {seconds} сек" if minutes > 0 else f"{delay} сек"
        
        await message.answer(f"🟢 **Авто-розсилка запущена!**\n\n• Затримка: {delay_text}\n• Груп: {len(groups)}\n• Повідомлення буде відправлятись автоматично до зупинки.\n\nНатисніть '🔴 Зупинити розсилку' для зупинки.", reply_markup=get_main_keyboard())
        
    else:
        is_mailing_active = False
        if mailing_task:
            mailing_task.cancel()
            mailing_task = None
        
        await message.answer("🔴 **Розсилка зупинена!**\n\nВсього відправок: " + str(bot_settings['repeat_count']), reply_markup=get_main_keyboard())

# Cancel handler for all states
@dp.message(F.text == "❌ Скасувати")
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
    await message.answer("❌ Скасовано.", reply_markup=get_main_keyboard())

@dp.message(F.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    total_groups = len(groups)
    mailing_status = "Активна" if is_mailing_active else "Зупинена"
    delay = bot_settings['delay_seconds']
    minutes = delay // 60
    seconds = delay % 60
    delay_text = f"{minutes} хв {seconds} сек" if minutes > 0 else f"{delay} сек"
    
    stats_text = (
        f"📊 **Статистика бота**\n\n"
        f"• Всього груп: `{total_groups}`\n"
        f"• Затримка: `{delay_text}`\n"
        f"• Статус розсилки: `{mailing_status}`\n"
        f"• Всього відправок: `{bot_settings['repeat_count']}`\n"
        f"• Тип повідомлення: `{'Текст' if pending_message and pending_message['message_type'] == 'text' else 'Фото' if pending_message else 'Не створено'}`"
    )
    
    await message.answer(stats_text, parse_mode='Markdown')

@dp.message(F.text == "❓ Допомога")
async def show_help(message: types.Message):
    help_text = """
❓ **Довідка - Авто-розсилка**

**Як використовувати:**
1. **Створити повідомлення**: '✏️ Створити повідомлення' - текст або фото
2. **Налаштувати затримку**: '⏰ Затримка' - час між повідомленнями
3. **Запустити розсилку**: '🟢 Запустити розсилку' - почати авто-відправку
4. **Зупинити**: '🔴 Зупинити розсилку' - зупинити авто-відправку

**Функції:**
• **Авто-повтор** - відправляє повідомлення автоматично з вашою затримкою
• **Ручна відправка** - '📤 Надіслати 1 раз' для одноразової відправки
• **Статистика** - відстежує кількість відправок
• **Працює 24/7** - навіть коли ви офлайн

**Для фото:**
• Надішліть фото з підписом
• Фото відправляється відразу видно (не файл)
• Авто-розсилка працює з фото та текстом

**Важливо:**
• Повідомлення відправляється до ручної зупинки
• Затримка працює між кожним циклом розсилки
• Бот повинен бути запущений на комп'ютері
    """
    await message.answer(help_text, reply_markup=get_main_keyboard())

async def main():
    # Load data first
    if not os.path.exists(GROUPS_FILE):
        save_groups(groups)
    if not os.path.exists(SETTINGS_FILE):
        save_settings(bot_settings)
    
    # Start user client
    await client.start()
    logger.info("✅ User client started successfully")
    
    # Start bot polling
    await dp.start_polling(bot)
    logger.info("✅ Bot started polling - Auto-mailing READY!")

if __name__ == '__main__':
    # Run the bot
    asyncio.run(main())