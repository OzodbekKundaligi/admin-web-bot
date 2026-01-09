import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import telebot
import telebot.apihelper as apihelper
import time

from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from dotenv import load_dotenv

# Environment o'qish
load_dotenv()

# Bot tokenini environmentdan olish
BOT_TOKEN = os.getenv('BOT_TOKEN', '8545746982:AAHZ6hFQZgvDsqhGyAV7gt-og2BjXtSOfDc')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '@GarajHub_uz')
ADMIN_ID = int(os.getenv('ADMIN_ID', '7903688837'))

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# MongoDB import
from db import (
    init_db,
    get_user, save_user, update_user_field,
    create_startup, get_startup, get_startups_by_owner,
    get_pending_startups, get_active_startups, update_startup_status, update_startup_results,
    add_startup_member, get_join_request_id, update_join_request,
    get_startup_members, get_statistics, get_all_users,
    get_recent_users, get_recent_startups, get_completed_startups,
    get_rejected_startups, get_all_startup_members
)

# Database initialization
init_db()

# User state management
user_states = {}

def set_user_state(user_id: int, state: str):
    user_states[user_id] = state

def get_user_state(user_id: int) -> str:
    return user_states.get(user_id, '')

def clear_user_state(user_id: int):
    if user_id in user_states:
        del user_states[user_id]

# Orqaga tugmasini yaratish
def create_back_button():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton('🔙 Orqaga'))
    return markup

# Asosiy menyu tugmalari - MATNLAR O'ZGARTIRILDI
def create_main_menu(user_id: int):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton('🌐 Startaplar'),
        KeyboardButton('📌 Mening startaplarim'),
        KeyboardButton('➕ Startup yaratish'),
        KeyboardButton('👤 Profil')
    ]
    markup.add(*buttons)
    
    if user_id == ADMIN_ID:
        markup.add(KeyboardButton('⚙️ Admin panel'))
    
    return markup

# 1. START - KANALGA OBUNA TEKSHIRISH
@bot.message_handler(commands=['start', 'help', 'boshlash'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    
    save_user(user_id, username, first_name)
    
    # Kanalga obuna tekshirish
    try:
        chat_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if chat_member.status in ['member', 'administrator', 'creator']:
            show_main_menu(message)
        else:
            ask_for_subscription(message)
    except Exception as e:
        logging.error(f"Obuna tekshirishda xatolik: {e}")
        ask_for_subscription(message)

def ask_for_subscription(message):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton('🔗 Kanalga o\'tish', url=f'https://t.me/{CHANNEL_USERNAME[1:]}'),
        InlineKeyboardButton('✅ Tekshirish', callback_data='check_subscription')
    )
    bot.send_message(
        message.chat.id,
        "🤖 <b>GarajHub Bot</b>\n\n"
        "Botdan foydalanish uchun avval kanalimizga obuna bo'ling 👇",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == 'check_subscription')
def check_subscription_callback(call):
    user_id = call.from_user.id
    try:
        chat_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if chat_member.status in ['member', 'administrator', 'creator']:
            show_main_menu(call)
            bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
        else:
            bot.answer_callback_query(call.id, "❌ Iltimos, kanalga obuna bo'ling!", show_alert=True)
    except Exception as e:
        logging.error(f"Obuna tekshirishda xatolik: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

def show_main_menu(message_or_call):
    if isinstance(message_or_call, types.CallbackQuery):
        chat_id = message_or_call.message.chat.id
        message_id = message_or_call.message.message_id
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass
    else:
        chat_id = message_or_call.chat.id
    
    user_id = message_or_call.from_user.id if isinstance(message_or_call, types.CallbackQuery) else message_or_call.from_user.id
    clear_user_state(user_id)
    
    text = "👋 <b>Assalomu alaykum!</b>\n\n🚀 <b>GarajHub</b> — startaplar uchun platforma.\n\nQuyidagilardan birini tanlang:"
    
    bot.send_message(chat_id, text, reply_markup=create_main_menu(user_id))

# 2. PROFIL (Yangilangan)
@bot.message_handler(func=lambda message: message.text == '👤 Profil')
def show_profile(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'in_profile')
    
    markup = create_back_button()
    
    user = get_user(user_id)
    if not user:
        save_user(user_id, message.from_user.username or "", message.from_user.first_name or "")
        user = get_user(user_id)
    
    profile_text = (
        "👤 <b>Profil ma'lumotlari:</b>\n\n"
        f"🧑 <b>Ism:</b> {user.get('first_name', '—')}\n"
        f"🧾 <b>Familiya:</b> {user.get('last_name', '—')}\n"
        f"⚧️ <b>Jins:</b> {user.get('gender', '—')}\n"
        f"📞 <b>Telefon:</b> {user.get('phone', '+998*')}\n"
        f"🎂 <b>Tug'ilgan sana:</b> {user.get('birth_date', '—')}\n"
        f"📝 <b>Bio:</b> {user.get('bio', '—')}\n\n"
        "🛠 <b>Tahrirlash uchun tugmalardan birini tanlang:</b>"
    )
    
    markup_inline = InlineKeyboardMarkup(row_width=2)
    markup_inline.add(
        InlineKeyboardButton('✏️ Ism', callback_data='edit_first_name'),
        InlineKeyboardButton('✏️ Familiya', callback_data='edit_last_name'),
        InlineKeyboardButton('📞 Telefon', callback_data='edit_phone'),
        InlineKeyboardButton('⚧️ Jins', callback_data='edit_gender'),
        InlineKeyboardButton('🎂 Tug\'ilgan sana', callback_data='edit_birth_date'),
        InlineKeyboardButton('📝 Bio', callback_data='edit_bio')
    )
    # Add inline back button to avoid sending an extra message with reply keyboard
    markup_inline.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_main_menu'))

    # Faqat bitta xabar yuborish
    bot.send_message(message.chat.id, profile_text, reply_markup=markup_inline)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def handle_edit_profile(call):
    user_id = call.from_user.id
    set_user_state(user_id, f'editing_{call.data}')
    
    if call.data == 'edit_first_name':
        msg = bot.send_message(call.message.chat.id, "📝 <b>Ismingizni kiriting:</b>", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_first_name)
    
    elif call.data == 'edit_last_name':
        msg = bot.send_message(call.message.chat.id, "📝 <b>Familiyangizni kiriting:</b>", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_last_name)
    
    elif call.data == 'edit_phone':
        msg = bot.send_message(call.message.chat.id, 
                              "📱 <b>Telefon raqamingizni kiriting:</b>\n\n"
                              "Masalan: <code>+998901234567</code>", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_phone)
    
    elif call.data == 'edit_gender':
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton('👨 Erkak', callback_data='gender_male'),
            InlineKeyboardButton('👩 Ayol', callback_data='gender_female'),
            InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_profile')
        )
        bot.edit_message_text("⚧️ <b>Jinsingizni tanlang:</b>", call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    elif call.data == 'edit_birth_date':
        msg = bot.send_message(call.message.chat.id, 
                              "🎂 <b>Tug'ilgan sanangizni kiriting (kun-oy-yil)</b>\n"
                              "Masalan: <code>30-04-2010</code>", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_birth_date)
    
    elif call.data == 'edit_bio':
        msg = bot.send_message(call.message.chat.id, "📝 <b>Bio kiriting:</b>", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_bio)
    
    bot.answer_callback_query(call.id)

def process_first_name(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        show_profile(message)
        clear_user_state(user_id)
        return
    
    update_user_field(user_id, 'first_name', message.text)
    bot.send_message(message.chat.id, "✅ <b>Ismingiz muvaffaqiyatli saqlandi</b>", reply_markup=create_back_button())
    show_profile(message)

def process_last_name(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        show_profile(message)
        clear_user_state(user_id)
        return
    
    update_user_field(user_id, 'last_name', message.text)
    bot.send_message(message.chat.id, "✅ <b>Familiyangiz muvaffaqiyatli saqlandi</b>", reply_markup=create_back_button())
    show_profile(message)

def process_phone(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        show_profile(message)
        clear_user_state(user_id)
        return
    
    update_user_field(user_id, 'phone', message.text)
    bot.send_message(message.chat.id, "✅ <b>Telefon raqami muvaffaqiyatli saqlandi</b>", reply_markup=create_back_button())
    show_profile(message)

@bot.callback_query_handler(func=lambda call: call.data in ['gender_male', 'gender_female'])
def process_gender(call):
    user_id = call.from_user.id
    gender = 'Erkak' if call.data == 'gender_male' else 'Ayol'
    update_user_field(user_id, 'gender', gender)
    
    # O'rniga yangi xabar yuborish
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "✅ <b>Jins muvaffaqiyatli saqlandi</b>", reply_markup=create_back_button())
    
    # Profilni qayta ko'rsatish
    show_profile(call.message)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_profile')
def back_to_profile(call):
    show_profile(call.message)
    bot.answer_callback_query(call.id)

def process_birth_date(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        show_profile(message)
        clear_user_state(user_id)
        return
    
    update_user_field(user_id, 'birth_date', message.text)
    bot.send_message(message.chat.id, "✅ <b>Tug'ilgan sana muvaffaqiyatli saqlandi</b>", reply_markup=create_back_button())
    show_profile(message)

def process_bio(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        show_profile(message)
        clear_user_state(user_id)
        return
    
    update_user_field(user_id, 'bio', message.text)
    bot.send_message(message.chat.id, "✅ <b>Bio saqlandi</b>", reply_markup=create_back_button())
    show_profile(message)

# 3. STARTUPLAR (To'g'rilangan)
@bot.message_handler(func=lambda message: message.text == '🌐 Startaplar')
def show_startups(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'viewing_startups')
    
    markup = create_back_button()
    bot.send_message(message.chat.id, "🌐 <b>Startaplar ro'yxati:</b>", reply_markup=markup)
    show_startup_page(message.chat.id, 1)

def show_startup_page(chat_id, page):
    per_page = 1  # show one startup per page
    startups, total = get_active_startups(page, per_page=per_page)
    
    if not startups:
        bot.send_message(chat_id, "📭 <b>Hozircha startup mavjud emas.</b>", reply_markup=create_back_button())
        return
    
    startup = startups[0]
    user = get_user(startup['owner_id'])
    owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
    
    total_pages = max(1, (total + per_page - 1) // per_page)
    
    text = (
        f"<b>🌐 Startaplar</b>\n"
        f"📄 Sahifa: <b>{page}/{total_pages}</b>\n\n"
        f"🎯 <b>{startup['name']}</b>\n"
        f"📌 {startup['description'][:200]}...\n"
        f"👤 <b>Muallif:</b> {owner_name}"
    )
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton('🤝 Startupga qo\'shilish',
                               callback_data=f'join_startup_{startup["_id"]}'))


    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton('⏮️ Oldingi', callback_data=f'startup_page_{page-1}'))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton('⏭️ Keyingi', callback_data=f'startup_page_{page+1}'))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_main_menu'))
    
    # Send photo if exists, else send text
    try:
        if startup.get('logo'):
            bot.send_photo(chat_id, startup['logo'], caption=text, reply_markup=markup)
        else:
            bot.send_message(chat_id, text, reply_markup=markup)
    except Exception as e:
        logging.error(f"Xabar yuborishda xatolik: {e}")
        bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('startup_page_'))
def handle_startup_page(call):
    try:
        page = int(call.data.split('_')[2])
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_startup_page(call.message.chat.id, page)
        bot.answer_callback_query(call.id)
    except:
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('join_startup_'))
def handle_join_startup(call):
    try:
        startup_id = call.data.split('_')[2]
        user_id = call.from_user.id
        
        # Check if already joined
        request_id = get_join_request_id(startup_id, user_id)
        
        if request_id:
            bot.answer_callback_query(call.id, "📩 Sizning so'rovingiz hali ko'rib chiqilmoqda!", show_alert=True)
        else:
            add_startup_member(startup_id, user_id)
            request_id = get_join_request_id(startup_id, user_id)
            
            # Foydalanuvchiga xabar
            bot.answer_callback_query(call.id, "✅ So'rov yuborildi. Startup egasi tasdiqlasa, sizga xabar yuboriladi.", show_alert=True)
            
            # Send notification to startup owner
            startup = get_startup(startup_id)
            user = get_user(user_id)
            
            if startup and user:
                text = (
                    f"🆕 <b>Startupga qo'shilish so'rovi</b>\n\n"
                    f"👤 <b>Foydalanuvchi:</b> {user.get('first_name', '')} {user.get('last_name', '')}\n"
                    f"📱 <b>Telefon:</b> {user.get('phone', '—')}\n"
                    f"📝 <b>Bio:</b> {user.get('bio', '—')}\n\n"
                    f"🎯 <b>Startup:</b> {startup['name']}"
                )
                
                markup = InlineKeyboardMarkup()
                markup.add(
                    InlineKeyboardButton('✅ Tasdiqlash', callback_data=f'approve_join_{request_id}'),
                    InlineKeyboardButton('❌ Rad etish', callback_data=f'reject_join_{request_id}')
                )
                
                try:
                    bot.send_message(startup['owner_id'], text, reply_markup=markup)
                except Exception as e:
                    logging.error(f"Egaga xabar yuborishda xatolik: {e}")
                    # Notify admin if owner cannot be messaged (owner may not have started bot)
                    try:
                        bot.send_message(ADMIN_ID, f"⚠️ Ownerga xabar yuborilmadi (ID: {startup['owner_id']}) for join request {request_id}. Error: {e}")
                    except:
                        pass
    except Exception as e:
        logging.error(f"Join startup xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_join_'))
def approve_join_request(call):
    try:
        request_id = call.data.split('_')[2]
        update_join_request(request_id, 'accepted')
        
        # Get startup details
        from db import db, STARTUP_MEMBERS_COLLECTION, STARTUPS_COLLECTION
        from bson import ObjectId # type: ignore
        
        member = db[STARTUP_MEMBERS_COLLECTION].find_one({'_id': ObjectId(request_id)})
        if member:
            startup_id = member['startup_id']
            user_id = member['user_id']
            
            startup = db[STARTUPS_COLLECTION].find_one({'_id': ObjectId(startup_id)})
            
            if startup:
                try:
                    bot.send_message(
                        user_id,
                        f"🎉 <b>Tabriklaymiz!</b>\n\n"
                        f"✅ Sizning so'rovingiz qabul qilindi.\n\n"
                        f"🎯 <b>Startup:</b> {startup['name']}\n"
                        f"🔗 <b>Guruhga qo'shilish:</b> {startup['group_link']}"
                    )
                except Exception as e:
                    logging.error(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")
        
        bot.edit_message_text(
            "✅ <b>So'rov tasdiqlandi va foydalanuvchiga havola yuborildi.</b>",
            call.message.chat.id,
            call.message.message_id
        )
        bot.answer_callback_query(call.id, "✅ Tasdiqlandi!")
        
    except Exception as e:
        logging.error(f"Approve join xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_join_'))
def reject_join_request(call):
    try:
        request_id = call.data.split('_')[2]
        
        from db import db, STARTUP_MEMBERS_COLLECTION
        from bson import ObjectId # type: ignore
        
        member = db[STARTUP_MEMBERS_COLLECTION].find_one({'_id': ObjectId(request_id)})
        if member:
            user_id = member['user_id']
            update_join_request(request_id, 'rejected')
            
            try:
                bot.send_message(user_id, "❌ <b>So'rovingiz rad etildi.</b>")
            except:
                pass
        
        bot.edit_message_text(
            "❌ <b>So'rov rad etildi.</b>",
            call.message.chat.id,
            call.message.message_id
        )
        bot.answer_callback_query(call.id, "✅ Rad etildi!")
        
    except Exception as e:
        logging.error(f"Reject join xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

# 4. MENING STARTUPLARIM (To'g'rilangan)
@bot.message_handler(func=lambda message: message.text == '📌 Mening startaplarim')
def show_my_startups(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'viewing_my_startups')
    
    markup = create_back_button()
    bot.send_message(message.chat.id, "📌 <b>Mening startaplarim:</b>", reply_markup=markup)
    show_my_startups_page(message.chat.id, user_id, 1)

def show_my_startups_page(chat_id, user_id, page):
    startups = get_startups_by_owner(user_id)
    
    if not startups:
        bot.send_message(chat_id, "📭 <b>Sizda hali startup mavjud emas.</b>", reply_markup=create_back_button())
        return
    
    per_page = 5
    total = len(startups)
    total_pages = (total + per_page - 1) // per_page
    page = min(max(1, page), total_pages)
    
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total)
    page_startups = startups[start_idx:end_idx]
    
    text = f"<b>📌 Mening startaplarim</b>\n📄 Sahifa: <b>{page}/{total_pages}</b>\n\n"
    for i, startup in enumerate(page_startups, start=start_idx + 1):
        status_emoji = {
            'pending': '⏳',
            'active': '▶️',
            'completed': '✅',
            'rejected': '❌'
        }.get(startup['status'], '❓')
        text += f"{i}. {startup['name']} {status_emoji}\n"
    
    markup = InlineKeyboardMarkup(row_width=5)
    
    # Page numbers
    buttons = []
    start_page = max(1, page - 2)
    end_page = min(total_pages, start_page + 4)
    
    for i in range(start_page, end_page + 1):
        buttons.append(InlineKeyboardButton(f'{i}', callback_data=f'my_startup_page_{i}'))
    
    if buttons:
        markup.row(*buttons)
    
    # Navigation
    if page > 1:
        markup.add(InlineKeyboardButton('⏮️ Oldingi', callback_data=f'my_startup_page_{page-1}'))
    if page < total_pages:
        markup.add(InlineKeyboardButton('⏭️ Keyingi', callback_data=f'my_startup_page_{page+1}'))
    
    # Startup selection
    if page_startups:
        for i, startup in enumerate(page_startups):
            markup.add(InlineKeyboardButton(f'{start_idx + i + 1}. {startup["name"][:15]}...', 
                                           callback_data=f'view_startup_{startup["_id"]}'))
    
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_main_menu'))
    
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('my_startup_page_'))
def handle_my_startup_page(call):
    try:
        page = int(call.data.split('_')[3])
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_my_startups_page(call.message.chat.id, call.from_user.id, page)
        bot.answer_callback_query(call.id)
    except:
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('view_startup_'))
def view_startup_details(call):
    try:
        startup_id = call.data.split('_')[2]
        startup = get_startup(startup_id)
        
        if not startup:
            bot.answer_callback_query(call.id, "❌ Startup topilmadi!", show_alert=True)
            return
        
        user = get_user(startup['owner_id'])
        owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
        
        # Get member count
        members, total_members = get_startup_members(startup_id, 1, 1)
        
        status_texts = {
            'pending': '⏳ Kutilmoqda',
            'active': '▶️ Boshlangan',
            'completed': '✅ Yakunlangan',
            'rejected': '❌ Rad etilgan'
        }
        
        status_text = status_texts.get(startup['status'], startup['status'])
        
        start_date = startup.get('started_at', '—')
        if start_date and start_date != '—' and isinstance(start_date, datetime):
            start_date = start_date.strftime('%d-%m-%Y')
        
        text = (
            f"🎯 <b>Nomi:</b> {startup['name']}\n"
            f"📊 <b>Holati:</b> {status_text}\n"
            f"📅 <b>Boshlanish sanasi:</b> {start_date}\n"
            f"👤 <b>Muallif:</b> {owner_name}\n"
            f"👥 <b>A'zolar:</b> {total_members} ta\n"
            f"📌 <b>Tavsif:</b> {startup['description']}"
        )
        
        markup = InlineKeyboardMarkup()
        
        if startup['status'] == 'pending':
            markup.add(InlineKeyboardButton('⏳ Admin tasdigini kutyapti', callback_data='waiting_approval'))
        elif startup['status'] == 'active':
            markup.add(InlineKeyboardButton('👥 A\'zolar', callback_data=f'view_members_{startup_id}_1'))
            markup.add(InlineKeyboardButton('⏹️ Yakunlash', callback_data=f'complete_startup_{startup_id}'))
        elif startup['status'] == 'completed':
            markup.add(InlineKeyboardButton('👥 A\'zolar', callback_data=f'view_members_{startup_id}_1'))
            if startup.get('results'):
                markup.add(InlineKeyboardButton('📊 Natijalar', callback_data=f'view_results_{startup_id}'))
        elif startup['status'] == 'rejected':
            markup.add(InlineKeyboardButton('❌ Rad etilgan', callback_data='rejected_info'))
        
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_my_startups'))
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        if startup.get('logo'):
            bot.send_photo(call.message.chat.id, startup['logo'], caption=text, reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, text, reply_markup=markup)
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"View startup xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_my_startups')
def back_to_my_startups(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_my_startups_page(call.message.chat.id, call.from_user.id, 1)
        bot.answer_callback_query(call.id)
    except:
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('view_members_'))
def view_startup_members(call):
    try:
        parts = call.data.split('_')
        startup_id = parts[2]
        page = int(parts[3])
        
        members, total = get_startup_members(startup_id, page)
        total_pages = max(1, (total + 4) // 5)
        
        # Avvalgi xabarni o'chirish
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        if not members:
            text = "👥 <b>A'zolar</b>\n\n📭 <b>Hozircha a'zolar yo'q.</b>"
            markup = InlineKeyboardMarkup()
        else:
            text = f"👥 <b>A'zolar</b>\n📄 Sahifa: <b>{page}/{total_pages}</b>\n\n"
            for i, member in enumerate(members, start=(page-1)*5+1):
                member_name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip()
                if not member_name:
                    member_name = f"User {member.get('user_id', '')}"
                text += f"{i}. {member_name}\n"
                if member.get('phone'):
                    text += f"   📱 {member.get('phone')}\n"
                if member.get('bio'):
                    bio_short = member.get('bio', '')[:30] + '...' if len(member.get('bio', '')) > 30 else member.get('bio', '')
                    text += f"   📝 {bio_short}\n"
                text += "\n"
        
        markup = InlineKeyboardMarkup()
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton('⏮️ Oldingi', callback_data=f'view_members_{startup_id}_{page-1}'))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton('⏭️ Keyingi', callback_data=f'view_members_{startup_id}_{page+1}'))
        
        if nav_buttons:
            markup.row(*nav_buttons)
        
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data=f'view_startup_{startup_id}'))
        
        bot.send_message(call.message.chat.id, text, reply_markup=markup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"View members xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('view_results_'))
def view_startup_results(call):
    try:
        startup_id = call.data.split('_')[2]
        startup = get_startup(startup_id)
        
        if not startup or not startup.get('results'):
            bot.answer_callback_query(call.id, "📭 Natijalar mavjud emas!", show_alert=True)
            return
        
        text = (
            f"📊 <b>Startup natijalari</b>\n\n"
            f"🎯 <b>Nomi:</b> {startup['name']}\n"
            f"📝 <b>Natijalar:</b> {startup['results']}\n"
            f"📅 <b>Yakunlangan sana:</b> {startup['ended_at'][:10] if startup.get('ended_at') else '—'}"
        )
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data=f'view_startup_{startup_id}'))
        
        bot.send_message(call.message.chat.id, text, reply_markup=markup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"View results xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('complete_startup_'))
def complete_startup(call):
    try:
        startup_id = call.data.split('_')[2]
        user_id = call.from_user.id
        set_user_state(user_id, f'completing_startup_{startup_id}')
        
        msg = bot.send_message(call.message.chat.id, "📝 <b>Nimalarga erishdingiz?</b>\nMatn yozing:", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_results, startup_id)
        
        bot.answer_callback_query(call.id)
    except:
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

def process_startup_results(message, startup_id):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        # Go back to startup view
        startup = get_startup(startup_id)
        if startup:
            user = get_user(startup['owner_id'])
            owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
            
            text = (
                f"🎯 <b>Nomi:</b> {startup['name']}\n"
                f"📊 <b>Holati:</b> ▶️ Boshlangan\n"
                f"👤 <b>Muallif:</b> {owner_name}\n"
                f"📌 <b>Tavsif:</b> {startup['description']}"
            )
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton('👥 A\'zolar', callback_data=f'view_members_{startup_id}_1'))
            markup.add(InlineKeyboardButton('⏹️ Yakunlash', callback_data=f'complete_startup_{startup_id}'))
            markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_my_startups'))
            
            bot.send_message(message.chat.id, text, reply_markup=markup)
        return
    
    results_text = message.text
    
    msg = bot.send_message(message.chat.id, "🖼 <b>Natijalar rasmini yuboring:</b>", reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_startup_photo, startup_id, results_text)

def process_startup_photo(message, startup_id, results_text):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        msg = bot.send_message(message.chat.id, "📝 <b>Nimalarga erishdingiz?</b>\nMatn yozing:", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_results, startup_id)
        return
    
    if message.photo:
        photo_id = message.photo[-1].file_id
        
        # Update startup status and results
        update_startup_status(startup_id, 'completed')
        update_startup_results(startup_id, results_text, datetime.now())
        
        # Get all members
        members = get_all_startup_members(startup_id)
        
        startup = get_startup(startup_id)
        
        # Send notification to all members
        end_date = datetime.now().strftime('%d-%m-%Y')
        success_count = 0
        
        for member_id in members:
            try:
                bot.send_photo(
                    member_id,
                    photo_id,
                    caption=(
                        f"🏁 <b>Startup yakunlandi</b>\n\n"
                        f"🎯 <b>{startup['name']}</b>\n"
                        f"📅 <b>Yakunlangan sana:</b> {end_date}\n"
                        f"📝 <b>Natijalar:</b> {results_text}"
                    )
                )
                success_count += 1
            except:
                pass
        
        bot.send_message(message.chat.id, 
                        f"✅ <b>Startup muvaffaqiyatli yakunlandi!</b>\n\n"
                        f"📤 Xabar yuborildi: {success_count} ta a'zoga", 
                        reply_markup=create_back_button())
        
        clear_user_state(user_id)
        
        # Show updated startup details
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data=f'view_startup_{startup_id}'))
        
        startup = get_startup(startup_id)
        user = get_user(startup['owner_id'])
        owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
        
        text = (
            f"🎯 <b>Nomi:</b> {startup['name']}\n"
            f"📊 <b>Holati:</b> ✅ Yakunlangan\n"
            f"📅 <b>Yakunlangan sana:</b> {end_date}\n"
            f"👤 <b>Muallif:</b> {owner_name}\n"
            f"📌 <b>Tavsif:</b> {startup['description']}\n\n"
            f"📝 <b>Natijalar:</b> {startup.get('results', '—')}"
        )
        
        bot.send_message(message.chat.id, text, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "⚠️ <b>Iltimos, rasm yuboring!</b>", reply_markup=create_back_button())
        msg = bot.send_message(message.chat.id, "🖼 <b>Natijalar rasmini yuboring:</b>", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_photo, startup_id, results_text)

# 5. STARTUP YARATISH
@bot.message_handler(func=lambda message: message.text == '➕ Startup yaratish')
def start_creation(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'creating_startup')
    
    markup = create_back_button()
    bot.send_message(message.chat.id, "🚀 <b>Yangi startup yaratamiz!</b>\n\n📝 <b>Startup nomini kiriting:</b>", reply_markup=markup)
    bot.register_next_step_handler(message, process_startup_name, {'owner_id': user_id})

def process_startup_name(message, data):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_main_menu(message)
        return
    
    data['name'] = message.text
    msg = bot.send_message(message.chat.id, "📝 <b>Startup tavsifini kiriting:</b>", reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_startup_description, data)

def process_startup_description(message, data):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_main_menu(message)
        return
    
    data['description'] = message.text
    msg = bot.send_message(message.chat.id, "🖼 <b>Logo (rasm) yuboring:</b>", reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_startup_logo, data)

def process_startup_logo(message, data):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_main_menu(message)
        return
    
    if message.photo:
        data['logo'] = message.photo[-1].file_id
        msg = bot.send_message(message.chat.id, 
                              "🔗 <b>Guruh yoki kanal havolasini kiriting (majburiy):</b>\n\n"
                              "Masalan: <code>https://t.me/group_name</code>", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_group_link, data)
    else:
        msg = bot.send_message(message.chat.id, "⚠️ <b>Iltimos, rasm yuboring!</b>", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_logo, data)

def process_startup_group_link(message, data):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_main_menu(message)
        return
    
    if not ('t.me/' in message.text or 'telegram.me/' in message.text):
        msg = bot.send_message(message.chat.id, 
                              "⚠️ <b>Noto'g'ri havola format!</b>\n\n"
                              "Iltimos, Telegram guruh yoki kanal havolasini kiriting:\n"
                              "<code>https://t.me/groupname</code>\n\n"
                              "Yoki '🔙 Orqaga' tugmasini bosing:", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_group_link, data)
        return
    
    data['group_link'] = message.text
    startup_id = create_startup(
        data['name'],
        data['description'],
        data.get('logo'),
        data['group_link'],
        data['owner_id']
    )
    
    if not startup_id:
        bot.send_message(message.chat.id, 
                        "❌ <b>Startup yaratishda xatolik yuz berdi!</b>\n\n"
                        "Iltimos, keyinroq qayta urinib ko'ring.", 
                        reply_markup=create_back_button())
        clear_user_state(user_id)
        show_main_menu(message)
        return
    
    # Send to admin for approval
    startup = get_startup(startup_id)
    user = get_user(data['owner_id'])
    owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
    
    text = (
        f"🆕 <b>Yangi startup yaratildi!</b>\n\n"
        f"🎯 <b>Nomi:</b> {startup['name']}\n"
        f"📌 <b>Tavsif:</b> {startup['description'][:200]}...\n"
        f"👤 <b>Muallif:</b> {owner_name}\n"
        f"👤 <b>Muallif ID:</b> {data['owner_id']}"
    )
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton('✅ Tasdiqlash', callback_data=f'admin_approve_{startup_id}'),
        InlineKeyboardButton('❌ Rad etish', callback_data=f'admin_reject_{startup_id}')
    )
    
    try:
        if startup.get('logo'):
            bot.send_photo(ADMIN_ID, startup['logo'], caption=text, reply_markup=markup)
        else:
            bot.send_message(ADMIN_ID, text, reply_markup=markup)
    except Exception as e:
        logging.error(f"Adminga xabar yuborishda xatolik: {e}")
    
    bot.send_message(message.chat.id, 
                    "✅ <b>Startup yaratildi va tekshiruvga yuborildi!</b>\n\n"
                    "⏳ <i>Administrator tekshirgandan so'ng kanalga joylanadi.</i>", 
                    reply_markup=create_back_button())
    
    clear_user_state(user_id)
    show_main_menu(message)

# ADMIN PANEL (Yangilangan)
@bot.message_handler(func=lambda message: message.text == '⚙️ Admin panel' and message.chat.id == ADMIN_ID)
def admin_panel(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'in_admin_panel')
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton('📊 Dashboard'),
        KeyboardButton('🚀 Startaplar'),
        KeyboardButton('👥 Foydalanuvchilar'),
        KeyboardButton('📢 Xabar yuborish'),
        KeyboardButton('⚙️ Sozlamalar'),
        KeyboardButton('🔙 Orqaga')
    )
    
    # Welcome message with statistics
    stats = get_statistics()
    
    welcome_text = (
        f"👨‍💼 <b>Admin Panel</b>\n\n"
        f"📊 <b>Dashboard statistikasi:</b>\n"
        f"├ 👥 Foydalanuvchilar: <b>{stats['total_users']}</b>\n"
        f"├ 🚀 Startaplar: <b>{stats['total_startups']}</b>\n"
        f"├ ⏳ Kutilayotgan: <b>{stats['pending_startups']}</b>\n"
        f"├ ▶️ Faol: <b>{stats['active_startups']}</b>\n"
        f"└ ✅ Yakunlangan: <b>{stats['completed_startups']}</b>"
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '📊 Dashboard' and message.chat.id == ADMIN_ID)
def admin_dashboard(message):
    stats = get_statistics()
    recent_users = get_recent_users(5)
    recent_startups = get_recent_startups(5)
    
    # Dashboard text
    dashboard_text = (
        f"📊 <b>Dashboard</b>\n\n"
        f"📈 <b>Umumiy statistikalar:</b>\n"
        f"├ 👥 Foydalanuvchilar: <b>{stats['total_users']}</b>\n"
        f"├ 🚀 Startaplar: <b>{stats['total_startups']}</b>\n"
        f"├ ⏳ Kutilayotgan: <b>{stats['pending_startups']}</b>\n"
        f"├ ▶️ Faol: <b>{stats['active_startups']}</b>\n"
        f"└ ✅ Yakunlangan: <b>{stats['completed_startups']}</b>\n\n"
    )
    
    # Recent users
    if recent_users:
        dashboard_text += f"👥 <b>So'nggi foydalanuvchilar:</b>\n"
        for i, user in enumerate(recent_users, 1):
            dashboard_text += f"{i}. {user.get('first_name', '')} {user.get('last_name', '')}\n"
        dashboard_text += "\n"
    
    # Recent startups
    if recent_startups:
        dashboard_text += f"🚀 <b>So'nggi startaplar:</b>\n"
        for i, startup in enumerate(recent_startups, 1):
            status_emoji = {
                'pending': '⏳',
                'active': '▶️',
                'completed': '✅',
                'rejected': '❌'
            }.get(startup['status'], '❓')
            dashboard_text += f"{i}. {startup['name']} {status_emoji}\n"
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton('🔄 Yangilash', callback_data='refresh_dashboard'),
        InlineKeyboardButton('📈 Toliq statistikalar', callback_data='full_stats'),
        InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_admin_panel')
    )
    
    bot.send_message(message.chat.id, dashboard_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '🚀 Startaplar' and message.chat.id == ADMIN_ID)
def admin_startups_menu(message):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton('⏳ Kutilayotgan', callback_data='pending_startups_1'),
        InlineKeyboardButton('▶️ Faol', callback_data='active_startups_1'),
        InlineKeyboardButton('✅ Yakunlangan', callback_data='completed_startups_1'),
        InlineKeyboardButton('❌ Rad etilgan', callback_data='rejected_startups_1'),
        InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_admin_panel')
    )
    
    stats = get_statistics()
    text = (
        f"🚀 <b>Startaplar boshqaruvi</b>\n\n"
        f"📊 <b>Statistikalar:</b>\n"
        f"├ ⏳ Kutilayotgan: <b>{stats['pending_startups']}</b>\n"
        f"├ ▶️ Faol: <b>{stats['active_startups']}</b>\n"
        f"├ ✅ Yakunlangan: <b>{stats['completed_startups']}</b>\n"
        f"└ ❌ Rad etilgan: <b>{stats['rejected_startups']}</b>"
    )
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pending_startups_'))
def show_pending_startups(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!", show_alert=True)
        return
    
    page = int(call.data.split('_')[2])
    startups, total = get_pending_startups(page)
    
    if not startups:
        text = "⏳ <b>Kutilayotgan startaplar yo'q.</b>"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_admin_startups'))
    else:
        total_pages = max(1, (total + 4) // 5)
        text = f"⏳ <b>Kutilayotgan startaplar</b>\n📄 Sahifa: <b>{page}/{total_pages}</b>\n\n"
        
        for i, startup in enumerate(startups, start=(page-1)*5+1):
            user = get_user(startup['owner_id'])
            owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
            text += f"{i}. <b>{startup['name']}</b>\n   👤 {owner_name}\n\n"
        
        markup = InlineKeyboardMarkup()
        
        # Page navigation
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton('⏮️', callback_data=f'pending_startups_{page-1}'))
        
        nav_buttons.append(InlineKeyboardButton(f'{page}/{total_pages}', callback_data='current_page'))
        
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton('⏭️', callback_data=f'pending_startups_{page+1}'))
        
        if nav_buttons:
            markup.row(*nav_buttons)
        
        # Startup selection
        for i, startup in enumerate(startups):
            markup.add(InlineKeyboardButton(f'{i+1}. {startup["name"][:20]}...', 
                                           callback_data=f'admin_view_startup_{startup["_id"]}'))
        
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_admin_startups'))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=markup)
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_view_startup_'))
def admin_view_startup_details(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!", show_alert=True)
        return
    
    try:
        startup_id = call.data.split('_')[3]
        startup = get_startup(startup_id)
        
        if not startup:
            bot.answer_callback_query(call.id, "❌ Startup topilmadi!", show_alert=True)
            return
        
        user = get_user(startup['owner_id'])
        owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
        owner_contact = f"@{user.get('username', '')}" if user and user.get('username') else f"ID: {startup['owner_id']}"
        
        text = (
            f"🖼 <b>Startup ma'lumotlari</b>\n\n"
            f"🎯 <b>Nomi:</b> {startup['name']}\n"
            f"📌 <b>Tavsif:</b> {startup['description']}\n\n"
            f"👤 <b>Muallif:</b> {owner_name}\n"
            f"📱 <b>Aloqa:</b> {owner_contact}\n"
            f"🔗 <b>Guruh havolasi:</b> {startup['group_link']}\n"
            f"📅 <b>Yaratilgan sana:</b> {startup['created_at'][:10] if startup.get('created_at') else '—'}\n"
            f"📊 <b>Holati:</b> {startup['status']}"
        )
        
        markup = InlineKeyboardMarkup()
        
        if startup['status'] == 'pending':
            markup.add(
                InlineKeyboardButton('✅ Tasdiqlash', callback_data=f'admin_approve_{startup_id}'),
                InlineKeyboardButton('❌ Rad etish', callback_data=f'admin_reject_{startup_id}')
            )
        elif startup['status'] == 'active':
            markup.add(InlineKeyboardButton('✅ Faol', callback_data='already_active'))
        elif startup['status'] == 'completed':
            markup.add(InlineKeyboardButton('✅ Yakunlangan', callback_data='already_completed'))
        elif startup['status'] == 'rejected':
            markup.add(InlineKeyboardButton('❌ Rad etilgan', callback_data='already_rejected'))
        
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='pending_startups_1'))
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        if startup.get('logo'):
            bot.send_photo(call.message.chat.id, startup['logo'], caption=text, reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, text, reply_markup=markup)
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"Admin view startup xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_approve_'))
def admin_approve_startup(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!", show_alert=True)
        return
    
    try:
        startup_id = call.data.split('_')[2]
        update_startup_status(startup_id, 'active')
        
        # Notify owner
        startup = get_startup(startup_id)
        if startup:
            try:
                bot.send_message(
                    startup['owner_id'],
                    f"🎉 <b>Tabriklaymiz!</b>\n\n"
                    f"✅ Sizning '<b>{startup['name']}</b>' startupingiz tasdiqlandi va kanalga joylandi!"
                )
            except:
                pass
        
        # Post to channel (TO'G'RILANGAN - inline tugma bilan)
        try:
            user = get_user(startup['owner_id'])
            owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
            
            channel_text = (
                f"🚀 <b>{startup['name']}</b>\n\n"
                f"📝 {startup['description']}\n\n"
                f"👤 <b>Muallif:</b> {owner_name}\n\n"
                f"👉 <b>Startupga qo'shilish uchun pastdagi tugmani bosing.</b>\n"
                f"➕ <b>O'z startupingizni yaratish uchun:</b> @{bot.get_me().username}"
            )
            
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton('🤝 Startupga qo\'shilish', callback_data=f'join_startup_{startup_id}'),
        
            )
            
            if startup.get('logo'):
                bot.send_photo(CHANNEL_USERNAME, startup['logo'], caption=channel_text, reply_markup=markup)
            else:
                bot.send_message(CHANNEL_USERNAME, channel_text, reply_markup=markup)
        except Exception as e:
            logging.error(f"Kanalga post yuborishda xatolik: {e}")
        
        try:
            bot.send_message(call.message.chat.id, "✅ <b>Startup tasdiqlandi va kanalga joylandi!</b>")
        except:
            pass
        
        bot.answer_callback_query(call.id, "✅ Startup tasdiqlandi!")
        
        # Go back to pending startups
        show_pending_startups(call)
        
    except Exception as e:
        logging.error(f"Admin approve xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_reject_'))
def admin_reject_startup(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!", show_alert=True)
        return
    
    try:
        startup_id = call.data.split('_')[2]
        update_startup_status(startup_id, 'rejected')
        
        # Notify owner
        startup = get_startup(startup_id)
        if startup:
            try:
                bot.send_message(
                    startup['owner_id'],
                    f"❌ <b>Xabar!</b>\n\n"
                    f"Sizning '<b>{startup['name']}</b>' startupingiz rad etildi."
                )
            except:
                pass
        
        try:
            bot.send_message(call.message.chat.id, "❌ <b>Startup rad etildi.</b>")
        except:
            pass
        
        bot.answer_callback_query(call.id, "❌ Startup rad etildi!")
        
        # Go back to pending startups
        show_pending_startups(call)
        
    except Exception as e:
        logging.error(f"Admin reject xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.message_handler(func=lambda message: message.text == '👥 Foydalanuvchilar' and message.chat.id == ADMIN_ID)
def admin_users(message):
    stats = get_statistics()
    recent_users = get_recent_users(10)
    
    text = (
        f"👥 <b>Foydalanuvchilar boshqaruvi</b>\n\n"
        f"📊 <b>Umumiy foydalanuvchilar:</b> <b>{stats['total_users']}</b> ta\n\n"
        f"📋 <b>So'nggi foydalanuvchilar:</b>\n"
    )
    
    for i, user in enumerate(recent_users, 1):
        joined_date = user.get('joined_at', '—')
        if joined_date and joined_date != '—':
            try:
                if isinstance(joined_date, str):
                    joined_date = joined_date[:10]
            except:
                pass
        
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        if not name:
            name = "Noma'lum"
        
        text += f"{i}. <b>{name}</b>\n"
        text += f"   👤 @{user.get('username', '—')} | 📅 {joined_date}\n\n"
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton('📥 Foydalanuvchilar ro\'yxati', callback_data='users_list_1'),
        InlineKeyboardButton('📊 Statistika', callback_data='users_stats'),
        InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_admin_panel')
    )
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '📢 Xabar yuborish' and message.chat.id == ADMIN_ID)
def broadcast_message_start(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'broadcasting_message')
    
    msg = bot.send_message(message.chat.id, 
                          "📢 <b>Xabaringizni yozing:</b>\n\n"
                          "<i>Barcha foydalanuvchilarga yuboriladi.</i>",
                          reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_broadcast_message)

def process_broadcast_message(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        admin_panel(message)
        return
    
    text = message.text
    users = get_all_users()
    
    bot.send_message(message.chat.id, f"📤 <b>Xabar yuborilmoqda...</b>\n\nFoydalanuvchilar: {len(users)} ta")
    
    success = 0
    fail = 0
    
    for user_id in users:
        try:
            # Check message type and send accordingly
            if message.photo:
                bot.send_photo(user_id, message.photo[-1].file_id, caption=text if text else None)
            elif message.video:
                bot.send_video(user_id, message.video.file_id, caption=text if text else None)
            elif message.document:
                bot.send_document(user_id, message.document.file_id, caption=text if text else None)
            else:
                bot.send_message(user_id, f"📢 <b>Yangilik!</b>\n\n{text}")
            
            success += 1
            time.sleep(0.05)  # To avoid flood limit
        except Exception as e:
            fail += 1
    
    bot.send_message(
        message.chat.id,
        f"✅ <b>Xabar yuborish yakunlandi!</b>\n\n"
        f"✅ Yuborildi: {success} ta\n"
        f"❌ Yuborilmadi: {fail} ta\n\n"
        f"📊 Umumiy foiz: {success/(success+fail)*100:.1f}%"
    )
    
    clear_user_state(message.from_user.id)
    admin_panel(message)

@bot.message_handler(func=lambda message: message.text == '⚙️ Sozlamalar' and message.chat.id == ADMIN_ID)
def admin_settings(message):
    text = (
        f"⚙️ <b>Admin sozlamalari</b>\n\n"
        f"🔧 <b>Bot ma'lumotlari:</b>\n"
        f"├ 🤖 Bot: @{bot.get_me().username}\n"
        f"├ 👨‍💼 Admin ID: {ADMIN_ID}\n"
        f"├ 📢 Kanal: {CHANNEL_USERNAME}\n"
        f"└ 🗄️ Database: MongoDB\n\n"
        f"📊 <b>Texnik ma'lumotlar:</b>\n"
        f"├ 📁 Database: {os.getenv('DATABASE_NAME', 'garajhub')}\n"
        f"├ 🚀 Versiya: 3.0 (MongoDB)\n"
        f"└ 🔄 Oxirgi yangilanish: {datetime.now().strftime('%d/%m/%Y')}"
    )
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton('🔄 Database yangilash', callback_data='refresh_db'),
        InlineKeyboardButton('💾 Backup olish', callback_data='backup_db'),
        InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_admin_panel')
    )
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

# Callback query handlers
@bot.callback_query_handler(func=lambda call: call.data == 'back_to_admin_panel')
def handle_back_to_admin_panel(call):
    admin_panel(call.message)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_admin_startups')
def handle_back_to_admin_startups(call):
    admin_startups_menu(call.message)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'refresh_dashboard')
def handle_refresh_dashboard(call):
    admin_dashboard(call.message)
    bot.answer_callback_query(call.id, "🔄 Dashboard yangilandi!")

@bot.callback_query_handler(func=lambda call: call.data == 'full_stats')
def handle_full_stats(call):
    stats = get_statistics()
    bot.answer_callback_query(call.id, 
                             f"👥 Foydalanuvchilar: {stats['total_users']}\n"
                             f"🚀 Startaplar: {stats['total_startups']}\n"
                             f"⏳ Kutilayotgan: {stats['pending_startups']}\n"
                             f"▶️ Faol: {stats['active_startups']}\n"
                             f"✅ Yakunlangan: {stats['completed_startups']}\n"
                             f"❌ Rad etilgan: {stats['rejected_startups']}", 
                             show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'refresh_db')
def handle_refresh_db(call):
    init_db()
    bot.answer_callback_query(call.id, "✅ Database indexlari yangilandi!")

@bot.callback_query_handler(func=lambda call: call.data == 'backup_db')
def handle_backup_db(call):
    bot.answer_callback_query(call.id, "⏳ Backup tayyorlanmoqda...")

@bot.callback_query_handler(func=lambda call: call.data == 'users_list_1')
def handle_users_list(call):
    bot.answer_callback_query(call.id, "⏳ Foydalanuvchilar ro'yxati tuzilmoqda...")

@bot.callback_query_handler(func=lambda call: call.data == 'users_stats')
def handle_users_stats(call):
    stats = get_statistics()
    bot.answer_callback_query(call.id, 
                             f"👥 Foydalanuvchilar: {stats['total_users']}\n"
                             f"🚀 Startaplar: {stats['total_startups']}", 
                             show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_main_menu')
def handle_back_to_main_menu(call):
    show_main_menu(call)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data in ['already_active', 'already_completed', 'already_rejected', 
                                                          'rejected_info', 'waiting_approval', 'current_page',
                                                          'show_charts', 'activity_stats', 'view_logs',
                                                          'admin_review_', 'admin_view_members_', 'admin_view_user_'])
def handle_info_callbacks(call):
    bot.answer_callback_query(call.id)

# Orqaga tugmasi uchun umumiy handler
@bot.message_handler(func=lambda message: message.text == '🔙 Orqaga')
def handle_back_button(message):
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    
    if user_state == 'in_profile' or user_state.startswith('editing_'):
        clear_user_state(user_id)
        show_main_menu(message)
    
    elif user_state == 'viewing_startups':
        clear_user_state(user_id)
        show_main_menu(message)
    
    elif user_state == 'viewing_my_startups':
        clear_user_state(user_id)
        show_main_menu(message)
    
    elif user_state.startswith('completing_startup_'):
        startup_id = user_state.split('_')[2]
        clear_user_state(user_id)
        
        # Go back to startup view
        startup = get_startup(startup_id)
        if startup:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton('🔙 Startupga qaytish', callback_data=f'view_startup_{startup_id}'))
            bot.send_message(message.chat.id, f"🔙 <b>Startupga qaytish:</b> {startup['name']}", reply_markup=markup)
    
    elif user_state == 'creating_startup':
        clear_user_state(user_id)
        show_main_menu(message)
    
    elif user_state == 'in_admin_panel' or user_state == 'broadcasting_message':
        clear_user_state(user_id)
        show_main_menu(message)
    
    else:
        show_main_menu(message)

# To'liq umumiy handler
@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    try:
        if message.chat.id == ADMIN_ID and message.text not in ('🔙 Orqaga', '⚙️ Admin panel'):
            admin_panel(message)
            return

        if message.text == '🔙 Orqaga':
            handle_back_button(message)
            return

        show_main_menu(message)
    except Exception as e:
        logging.error(f"Unhandled message error: {e}")

# Botni ishga tushirish
if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("🚀 GarajHub Bot (MongoDB versiyasi) ishga tushdi...")
    print(f"👨‍💼 Admin ID: {ADMIN_ID}")
    print(f"📢 Kanal: {CHANNEL_USERNAME}")
    try:
        print(f"🤖 Bot: @{bot.get_me().username}")
    except:
        print("🤖 Bot: (get_me() failed)")
    print(f"🗄️ Database: MongoDB")
    print("=" * 60)
    
    while True:
        try:
            try:
                bot.remove_webhook()
            except:
                pass
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except apihelper.ApiTelegramException as e:
            if hasattr(e, 'result_json') and isinstance(e.result_json, dict) and e.result_json.get('error_code') == 409 or '409' in str(e):
                logging.error(f"Telegram 409 conflict: {e}. Removing webhook and retrying...")
                try:
                    bot.remove_webhook()
                except:
                    pass
                time.sleep(5)
                continue
            else:
                logging.error(f"TeleBot ApiTelegramException: {e}")
                time.sleep(5)
                continue
        except Exception as e:
            logging.error(f"Botda xatolik: {e}")
            time.sleep(5)
            continue
        
 
