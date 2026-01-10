import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import telebot
import telebot.apihelper as apihelper
import time

from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

# Environment o'qish
load_dotenv()

# Bot tokenini environmentdan olish
BOT_TOKEN = os.getenv('BOT_TOKEN', '8468261643:AAFlCy7RQRsGBuBMpm3mtItH-bQCrEPxXNE')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '@GarajHub_test')
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
    get_rejected_startups, get_all_startup_members,
    get_startups_by_category, get_all_categories,
    get_user_joined_startups, get_startups_by_ids,
    update_user_specialization, update_user_experience
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

# Asosiy menyu tugmalari
def create_main_menu(user_id: int):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton('🌐 Startaplar'),
        KeyboardButton('🚀 Startup yaratish'),
        KeyboardButton('📌 Startaplarim'),
        KeyboardButton('👤 Profil')
    ]
    markup.add(*buttons)
    
    if user_id == ADMIN_ID:
        markup.add(KeyboardButton('⚙️ Admin panel'))
    
    return markup

# 1. START - BOSHLASH
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
        InlineKeyboardButton('🔗 Kanalga otish', url=f'https://t.me/{CHANNEL_USERNAME[1:]}'),
        InlineKeyboardButton('✅ Tekshirish', callback_data='check_subscription')
    )
    bot.send_message(
        message.chat.id,
        "🤖 <b>GarajHub</b>\n\n"
        "Davom etish uchun rasmiy kanalimizga obuna bo'ling:\n"
        f"👉 {CHANNEL_USERNAME}",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == 'check_subscription')
def check_subscription_callback(call):
    user_id = call.from_user.id
    try:
        chat_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if chat_member.status in ['member', 'administrator', 'creator']:
            show_main_menu(call)
            bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi")
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
    
    text = "🚀 <b>GarajHub</b> — startaplar platformasiga xush kelibsiz!\n\n➡️ <b>Asosiy menyu:</b>"
    
    bot.send_message(chat_id, text, reply_markup=create_main_menu(user_id))

# 2. STARTAPLAR BO'LIMI
@bot.message_handler(func=lambda message: message.text == '🌐 Startaplar')
def show_startups_menu(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'in_startups_menu')
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton('🎯 Tavsiyalar'),
        KeyboardButton('🔎 Kategoriya bo\'yicha'),
        KeyboardButton('🔙 Asosiy menyu')
    )
    
    bot.send_message(message.chat.id, "🌐 <b>Startaplar bo'limi:</b>", reply_markup=markup)

# 2.1 TAVSIYALAR
@bot.message_handler(func=lambda message: message.text == '🎯 Tavsiyalar')
def show_recommended_startups(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'viewing_recommended')
    
    show_recommended_page(message.chat.id, 1)

def show_recommended_page(chat_id, page):
    per_page = 1
    startups, total = get_active_startups(page, per_page=per_page)
    
    if not startups:
        bot.send_message(chat_id, 
                        "📭 <b>Hozircha startup mavjud emas.</b>", 
                        reply_markup=create_back_button())
        return
    
    startup = startups[0]
    user = get_user(startup['owner_id'])
    owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
    
    members_count = len(get_all_startup_members(startup['_id']))
    
    total_pages = max(1, (total + per_page - 1) // per_page)
    
    text = (
        f"💡 <b>Tavsiya {page}/{total_pages}</b>\n\n"
        f"🎯 <b>{startup['name']}</b>\n"
        f"📌 {startup['description'][:200]}{'...' if len(startup['description']) > 200 else ''}\n\n"
        f"👤 <b>Muallif:</b> {owner_name}\n"
        f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
        f"🔧 <b>Kerak:</b> {startup.get('required_skills', '—')}\n"
        f"👥 <b>A'zolar:</b> {members_count} / {startup.get('max_members', '—')}"
    )
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton('🤝 Qo\'shilish', callback_data=f'join_startup_{startup["_id"]}'))
    
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton('⏮️ Oldingi', callback_data=f'rec_page_{page-1}'))
    
    nav_buttons.append(InlineKeyboardButton(f'{page}/{total_pages}', callback_data='current_page'))
    
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton('⏭️ Keyingi', callback_data=f'rec_page_{page+1}'))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_startups_menu'))
    
    try:
        if startup.get('logo'):
            bot.send_photo(chat_id, startup['logo'], caption=text, reply_markup=markup)
        else:
            bot.send_message(chat_id, text, reply_markup=markup)
    except Exception as e:
        logging.error(f"Xabar yuborishda xatolik: {e}")
        bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('rec_page_'))
def handle_recommended_page(call):
    try:
        page = int(call.data.split('_')[2])
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_recommended_page(call.message.chat.id, page)
        bot.answer_callback_query(call.id)
    except:
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

# 2.2 KATEGORIYA BO'YICHA
@bot.message_handler(func=lambda message: message.text == '🔎 Kategoriya bo\'yicha')
def show_categories(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'choosing_category')
    
    categories = get_all_categories()
    
    markup = InlineKeyboardMarkup(row_width=2)
    
    if categories:
        for category in categories:
            category_emojis = {
                'Biznes': '💼',
                'Sog\'liq': '🏥',
                'Texnologiya': '📱',
                'Ekologiya': '🌿',
                'Ta\'lim': '🎓',
                'Dizayn': '🎨',
                'Dasturlash': '💻',
                'Savdo': '🛒',
                'Media': '🎬',
                'Karyera': '💼'
            }
            emoji = category_emojis.get(category, '🏷️')
            markup.add(InlineKeyboardButton(f'{emoji} {category}', callback_data=f'category_{category}'))
    else:
        markup.add(InlineKeyboardButton('💼 Biznes', callback_data='category_Biznes'))
        markup.add(InlineKeyboardButton('🏥 Sog\'liq', callback_data='category_Sog\'liq'))
        markup.add(InlineKeyboardButton('📱 Texnologiya', callback_data='category_Texnologiya'))
        markup.add(InlineKeyboardButton('🌿 Ekologiya', callback_data='category_Ekologiya'))
        markup.add(InlineKeyboardButton('🎓 Ta\'lim', callback_data='category_Ta\'lim'))
        markup.add(InlineKeyboardButton('🎨 Dizayn', callback_data='category_Dizayn'))
        markup.add(InlineKeyboardButton('💻 Dasturlash', callback_data='category_Dasturlash'))
        markup.add(InlineKeyboardButton('🛒 Savdo', callback_data='category_Savdo'))
        markup.add(InlineKeyboardButton('🎬 Media', callback_data='category_Media'))
        markup.add(InlineKeyboardButton('💼 Karyera', callback_data='category_Karyera'))
    
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_startups_menu'))
    
    bot.send_message(message.chat.id, "🏷️ <b>Kategoriya tanlang:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('category_'))
def handle_category_selection(call):
    try:
        category_name = call.data.split('_')[1]
        show_category_startups(call.message.chat.id, category_name, 1)
        bot.answer_callback_query(call.id)
    except:
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

def show_category_startups(chat_id, category_name, page):
    startups = get_startups_by_category(category_name)
    
    if not startups:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_categories'))
        
        bot.send_message(chat_id, 
                        f"🏷️ <b>{category_name}</b> kategoriyasida hozircha startup mavjud emas.",
                        reply_markup=markup)
        return
    
    per_page = 5
    total = len(startups)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(1, page), total_pages)
    
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total)
    page_startups = startups[start_idx:end_idx]
    
    category_emojis = {
        'Biznes': '💼',
        'Sog\'liq': '🏥',
        'Texnologiya': '📱',
        'Ekologiya': '🌿',
        'Ta\'lim': '🎓',
        'Dizayn': '🎨',
        'Dasturlash': '💻',
        'Savdo': '🛒',
        'Media': '🎬',
        'Karyera': '💼'
    }
    emoji = category_emojis.get(category_name, '🏷️')
    
    text = f"{emoji} <b>{category_name} startaplari</b>\n📄 <b>Sahifa:</b> {page}/{total_pages}\n\n"
    
    for i, startup in enumerate(page_startups, start=start_idx+1):
        user = get_user(startup['owner_id'])
        owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
        text += f"{i}. <b>{startup['name']}</b> – {owner_name}\n"
    
    markup = InlineKeyboardMarkup(row_width=5)
    
    # Raqamli tugmalar
    numbers = []
    for i in range(start_idx+1, start_idx+len(page_startups)+1):
        numbers.append(InlineKeyboardButton(f'{i}️⃣', callback_data=f'cat_startup_{startups[i-1]["_id"]}'))
    
    if numbers:
        markup.row(*numbers)
    
    # Navigatsiya
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton('⏮️ Oldingi', callback_data=f'cat_page_{category_name}_{page-1}'))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton('⏭️ Keyingi', callback_data=f'cat_page_{category_name}_{page+1}'))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_categories'))
    
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_page_'))
def handle_category_page(call):
    try:
        parts = call.data.split('_')
        category_name = parts[2]
        page = int(parts[3])
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_category_startups(call.message.chat.id, category_name, page)
        bot.answer_callback_query(call.id)
    except:
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_startup_'))
def handle_category_startup_view(call):
    try:
        startup_id = call.data.split('_')[2]
        startup = get_startup(startup_id)
        
        if not startup:
            bot.answer_callback_query(call.id, "❌ Startup topilmadi!", show_alert=True)
            return
        
        user = get_user(startup['owner_id'])
        owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
        
        members_count = len(get_all_startup_members(startup_id))
        
        text = (
            f"🎯 <b>{startup['name']}</b>\n\n"
            f"📌 <b>Tavsif:</b> {startup['description']}\n\n"
            f"👤 <b>Muallif:</b> {owner_name}\n"
            f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
            f"🔧 <b>Kerak:</b> {startup.get('required_skills', '—')}\n"
            f"👥 <b>A'zolar:</b> {members_count} / {startup.get('max_members', '—')}"
        )
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('🤝 Startupga Qo\'shilish', callback_data=f'join_startup_{startup_id}'))
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_categories'))
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        if startup.get('logo'):
            bot.send_photo(call.message.chat.id, startup['logo'], caption=text, reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, text, reply_markup=markup)
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"Category startup view xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

# Qo'shilish jarayoni
@bot.callback_query_handler(func=lambda call: call.data.startswith('join_startup_'))
def handle_join_startup(call):
    try:
        startup_id = call.data.split('_')[2]
        user_id = call.from_user.id
        
        # Startup egasi ekanligini tekshirish
        startup = get_startup(startup_id)
        if startup and startup['owner_id'] == user_id:
            bot.answer_callback_query(call.id, "❌ Siz bu startupning egasisiz!", show_alert=True)
            return
        
        # Avval so'rov yuborilganligini tekshirish
        request_id = get_join_request_id(startup_id, user_id)
        
        if request_id:
            # So'rov holatini tekshirish
            from db import db, STARTUP_MEMBERS_COLLECTION
            from bson import ObjectId
            
            member_request = db[STARTUP_MEMBERS_COLLECTION].find_one({'_id': ObjectId(request_id)})
            if member_request:
                if member_request['status'] == 'pending':
                    bot.answer_callback_query(call.id, "📩 Sizning so'rovingiz hali ko'rib chiqilmoqda!", show_alert=True)
                elif member_request['status'] == 'accepted':
                    bot.answer_callback_query(call.id, "✅ Siz allaqachon bu startupda a'zosiz!", show_alert=True)
                elif member_request['status'] == 'rejected':
                    bot.answer_callback_query(call.id, "❌ So'rovingiz avval rad etilgan.", show_alert=True)
            return
        
        # Yangi so'rov yaratish
        add_startup_member(startup_id, user_id)
        request_id = get_join_request_id(startup_id, user_id)
        
        # Foydalanuvchiga xabar
        bot.answer_callback_query(call.id, "✅ So'rovingiz muvaffaqiyatli yuborildi.", show_alert=True)
        
        # Startup egasiga xabar yuborish
        if startup:
            user = get_user(user_id)
            
            if user:
                user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                if not user_name:
                    user_name = f"User {user_id}"
                
                text = (
                    f"🆕 <b>Qo'shilish so'rovi</b>\n\n"
                    f"👤 <b>Foydalanuvchi:</b> {user_name}\n"
                    f"📞 <b>Telefon:</b> {user.get('phone', '—')}\n"
                    f"🔧 <b>Mutaxassislik:</b> {user.get('specialization', '—')}\n"
                    f"📈 <b>Tajriba:</b> {user.get('experience', '—')}\n"
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
    except Exception as e:
        logging.error(f"Join startup xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

# Qo'shilish so'rovini tasdiqlash
@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_join_'))
def approve_join_request(call):
    try:
        request_id = call.data.split('_')[2]
        
        # So'rov holatini yangilash
        update_join_request(request_id, 'accepted')
        
        # So'rov ma'lumotlarini olish
        from db import db, STARTUP_MEMBERS_COLLECTION, STARTUPS_COLLECTION
        from bson import ObjectId
        
        member = db[STARTUP_MEMBERS_COLLECTION].find_one({'_id': ObjectId(request_id)})
        if member:
            startup_id = member['startup_id']
            user_id = member['user_id']
            
            startup = get_startup(startup_id)
            
            if startup:
                # Foydalanuvchiga xabar
                try:
                    bot.send_message(
                        user_id,
                        f"🎉 <b>Tabriklaymiz!</b>\n\n"
                        f"✅ Sizning so'rovingiz qabul qilindi.\n\n"
                        f"🎯 <b>Startup:</b> {startup['name']}\n"
                        f"🔗 <b>Guruhga qo'shilish:</b> {startup.get('group_link', '—')}"
                    )
                except Exception as e:
                    logging.error(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")
        
        # Egaga xabar
        bot.edit_message_text(
            "✅ <b>So'rov tasdiqlandi va foydalanuvchiga havola yuborildi.</b>",
            call.message.chat.id,
            call.message.message_id
        )
        bot.answer_callback_query(call.id, "✅ Tasdiqlandi!")
        
    except Exception as e:
        logging.error(f"Approve join xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

# Qo'shilish so'rovini rad etish
@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_join_'))
def reject_join_request(call):
    try:
        request_id = call.data.split('_')[2]
        
        # So'rov holatini yangilash
        update_join_request(request_id, 'rejected')
        
        # So'rov ma'lumotlarini olish
        from db import db, STARTUP_MEMBERS_COLLECTION
        from bson import ObjectId
        
        member = db[STARTUP_MEMBERS_COLLECTION].find_one({'_id': ObjectId(request_id)})
        if member:
            user_id = member['user_id']
            
            # Foydalanuvchiga xabar
            try:
                bot.send_message(
                    user_id,
                    "❌ <b>Afsus, so'rovingiz rad etildi.</b>\n\n"
                    "Boshqa startaplarga qo'shilishingiz mumkin."
                )
            except:
                pass
        
        # Egaga xabar
        bot.edit_message_text(
            "❌ <b>So'rov rad etildi.</b>",
            call.message.chat.id,
            call.message.message_id
        )
        bot.answer_callback_query(call.id, "✅ Rad etildi!")
        
    except Exception as e:
        logging.error(f"Reject join xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

# 3. PROFIL
@bot.message_handler(func=lambda message: message.text == '👤 Profil')
def show_profile(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'in_profile')
    
    user = get_user(user_id)
    if not user:
        save_user(user_id, message.from_user.username or "", message.from_user.first_name or "")
        user = get_user(user_id)
    
    profile_text = (
        "👤 <b>Profil ma'lumotlari:</b>\n\n"
        f"🧑 <b>Ism:</b> {user.get('first_name', '—')}\n"
        f"🧾 <b>Familiya:</b> {user.get('last_name', '—')}\n"
        f"⚧️ <b>Jins:</b> {user.get('gender', '—')}\n"
        f"📞 <b>Telefon:</b> {user.get('phone', '—')}\n"
        f"🎂 <b>Tug'ilgan sana:</b> {user.get('birth_date', '—')}\n"
        f"🔧 <b>Mutaxassislik:</b> {user.get('specialization', '—')}\n"
        f"📈 <b>Tajriba:</b> {user.get('experience', '—')}\n"
        f"📝 <b>Bio:</b> {user.get('bio', '—')}\n\n"
        "🛠 <b>Tahrirlash uchun tugmalardan birini tanlang:</b>"
    )
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton('✏️ Ism', callback_data='edit_first_name'),
        InlineKeyboardButton('✏️ Familiya', callback_data='edit_last_name'),
        InlineKeyboardButton('📞 Telefon', callback_data='edit_phone'),
        InlineKeyboardButton('⚧️ Jins', callback_data='edit_gender'),
        InlineKeyboardButton('🎂 Tug\'ilgan sana', callback_data='edit_birth_date'),
        InlineKeyboardButton('🔧 Mutaxassislik', callback_data='edit_specialization'),
        InlineKeyboardButton('📈 Tajriba', callback_data='edit_experience'),
        InlineKeyboardButton('📝 Bio', callback_data='edit_bio')
    )
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_main_menu'))

    bot.send_message(message.chat.id, profile_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def handle_edit_profile(call):
    user_id = call.from_user.id
    
    if call.data == 'edit_first_name':
        set_user_state(user_id, 'editing_first_name')
        msg = bot.send_message(call.message.chat.id, "📝 <b>Ismingizni kiriting:</b>", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_first_name)
    
    elif call.data == 'edit_last_name':
        set_user_state(user_id, 'editing_last_name')
        msg = bot.send_message(call.message.chat.id, "📝 <b>Familiyangizni kiriting:</b>", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_last_name)
    
    elif call.data == 'edit_phone':
        set_user_state(user_id, 'editing_phone')
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
        set_user_state(user_id, 'editing_birth_date')
        msg = bot.send_message(call.message.chat.id, 
                              "🎂 <b>Tug'ilgan sanangizni kiriting (kun-oy-yil)</b>\n"
                              "Masalan: <code>30-04-2000</code>", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_birth_date)
    
    elif call.data == 'edit_specialization':
        set_user_state(user_id, 'editing_specialization')
        msg = bot.send_message(call.message.chat.id, 
                              "🔧 <b>Mutaxassisligingizni kiriting:</b>\n\n"
                              "Masalan: <code>Python, AI, ML</code>", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_specialization)
    
    elif call.data == 'edit_experience':
        set_user_state(user_id, 'editing_experience')
        msg = bot.send_message(call.message.chat.id, 
                              "📈 <b>Tajribangizni kiriting:</b>\n\n"
                              "Masalan: <code>5 yil</code>", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_experience)
    
    elif call.data == 'edit_bio':
        set_user_state(user_id, 'editing_bio')
        msg = bot.send_message(call.message.chat.id, "📝 <b>Bio kiriting:</b>", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_bio)
    
    bot.answer_callback_query(call.id)

def process_first_name(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_profile(message)
        return
    
    update_user_field(user_id, 'first_name', message.text)
    bot.send_message(message.chat.id, "✅ <b>Ismingiz muvaffaqiyatli saqlandi</b>")
    clear_user_state(user_id)
    show_profile(message)

def process_last_name(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_profile(message)
        return
    
    update_user_field(user_id, 'last_name', message.text)
    bot.send_message(message.chat.id, "✅ <b>Familiyangiz muvaffaqiyatli saqlandi</b>")
    clear_user_state(user_id)
    show_profile(message)

def process_phone(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_profile(message)
        return
    
    update_user_field(user_id, 'phone', message.text)
    bot.send_message(message.chat.id, "✅ <b>Telefon raqami muvaffaqiyatli saqlandi</b>")
    clear_user_state(user_id)
    show_profile(message)

@bot.callback_query_handler(func=lambda call: call.data in ['gender_male', 'gender_female'])
def process_gender(call):
    user_id = call.from_user.id
    gender = 'Erkak' if call.data == 'gender_male' else 'Ayol'
    update_user_field(user_id, 'gender', gender)
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "✅ <b>Jins muvaffaqiyatli saqlandi</b>")
    
    show_profile(call.message)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_profile')
def back_to_profile(call):
    show_profile(call.message)
    bot.answer_callback_query(call.id)

def process_birth_date(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_profile(message)
        return
    
    update_user_field(user_id, 'birth_date', message.text)
    bot.send_message(message.chat.id, "✅ <b>Tug'ilgan sana muvaffaqiyatli saqlandi</b>")
    clear_user_state(user_id)
    show_profile(message)

def process_specialization(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_profile(message)
        return
    
    update_user_specialization(user_id, message.text)
    bot.send_message(message.chat.id, "✅ <b>Mutaxassislik muvaffaqiyatli saqlandi</b>")
    clear_user_state(user_id)
    show_profile(message)

def process_experience(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_profile(message)
        return
    
    update_user_experience(user_id, message.text)
    bot.send_message(message.chat.id, "✅ <b>Tajriba muvaffaqiyatli saqlandi</b>")
    clear_user_state(user_id)
    show_profile(message)

def process_bio(message):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_profile(message)
        return
    
    update_user_field(user_id, 'bio', message.text)
    bot.send_message(message.chat.id, "✅ <b>Bio saqlandi</b>")
    clear_user_state(user_id)
    show_profile(message)

# 4. STARTUP YARATISH
@bot.message_handler(func=lambda message: message.text == '🚀 Startup yaratish')
def start_creation(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'creating_startup')
    
    msg = bot.send_message(message.chat.id, 
                          "🚀 <b>Yangi startup yaratamiz!</b>\n\n"
                          "📝 <b>Startup nomini kiriting:</b>", 
                          reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_startup_name, {'owner_id': user_id})

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
    else:
        data['logo'] = None
    
    msg = bot.send_message(message.chat.id,
                          "🔗 <b>Guruh yoki kanal havolasini kiriting:</b>\n\n"
                          "Masalan: https://t.me/group_name yoki @group_name",
                          reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_startup_group_link, data)

def process_startup_group_link(message, data):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_main_menu(message)
        return
    
    if not ('t.me/' in message.text or 'telegram.me/' in message.text or message.text.startswith('@')):
        msg = bot.send_message(message.chat.id,
                              "⚠️ <b>Noto'g'ri havola format!</b>\n\n"
                              "Iltimos, Telegram guruh yoki kanal havolasini kiriting:\n"
                              "• https://t.me/groupname\n"
                              "• @groupname\n\n"
                              "Yoki '🔙 Orqaga' tugmasini bosing:",
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_group_link, data)
        return
    
    data['group_link'] = message.text
    
    msg = bot.send_message(message.chat.id,
                          "🔧 <b>Kerakli mutaxassislarni kiriting:</b>\n\n"
                          "Masalan: Python, Designer, Manager",
                          reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_startup_skills, data)

def process_startup_skills(message, data):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_main_menu(message)
        return
    
    data['required_skills'] = message.text
    
    # Kategoriya tanlash
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton('💼 Biznes', callback_data='create_cat_business'),
        InlineKeyboardButton('🏥 Sog\'liq', callback_data='create_cat_health'),
        InlineKeyboardButton('📱 Texnologiya', callback_data='create_cat_tech'),
        InlineKeyboardButton('🌿 Ekologiya', callback_data='create_cat_eco'),
        InlineKeyboardButton('🎓 Ta\'lim', callback_data='create_cat_edu'),
        InlineKeyboardButton('🎨 Dizayn', callback_data='create_cat_design'),
        InlineKeyboardButton('💻 Dasturlash', callback_data='create_cat_programming'),
        InlineKeyboardButton('🛒 Savdo', callback_data='create_cat_sales'),
        InlineKeyboardButton('🎬 Media', callback_data='create_cat_media'),
        InlineKeyboardButton('💼 Karyera', callback_data='create_cat_career')
    )
    
    bot.send_message(message.chat.id, "🏷️ <b>Kategoriya tanlang:</b>", reply_markup=markup)
    
    # Kategoriya callback handler
    @bot.callback_query_handler(func=lambda call: call.data.startswith('create_cat_'))
    def handle_create_category(call):
        if call.data == 'create_cat_business':
            data['category'] = 'Biznes'
        elif call.data == 'create_cat_health':
            data['category'] = 'Sog\'liq'
        elif call.data == 'create_cat_tech':
            data['category'] = 'Texnologiya'
        elif call.data == 'create_cat_eco':
            data['category'] = 'Ekologiya'
        elif call.data == 'create_cat_edu':
            data['category'] = 'Ta\'lim'
        elif call.data == 'create_cat_design':
            data['category'] = 'Dizayn'
        elif call.data == 'create_cat_programming':
            data['category'] = 'Dasturlash'
        elif call.data == 'create_cat_sales':
            data['category'] = 'Savdo'
        elif call.data == 'create_cat_media':
            data['category'] = 'Media'
        elif call.data == 'create_cat_career':
            data['category'] = 'Karyera'
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        msg = bot.send_message(call.message.chat.id,
                              "👥 <b>Maksimal a'zolar sonini kiriting:</b>\n\n"
                              "Masalan: 10",
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_max_members, data)
        bot.answer_callback_query(call.id)

def process_startup_max_members(message, data):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        show_main_menu(message)
        return
    
    try:
        max_members = int(message.text)
        if max_members <= 0:
            raise ValueError
    except ValueError:
        msg = bot.send_message(message.chat.id,
                              "⚠️ <b>Iltimos, musbat raqam kiriting!</b>\n\n"
                              "Masalan: 10",
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_max_members, data)
        return
    
    data['max_members'] = max_members
    
    # Startup yaratish
    startup_id = create_startup(
        name=data['name'],
        description=data['description'],
        logo=data.get('logo'),
        group_link=data['group_link'],
        owner_id=data['owner_id'],
        required_skills=data.get('required_skills', ''),
        category=data.get('category', 'Boshqa'),
        max_members=data['max_members']
    )
    
    if not startup_id:
        bot.send_message(message.chat.id,
                        "❌ <b>Startup yaratishda xatolik yuz berdi!</b>\n\n"
                        "Iltimos, keyinroq qayta urinib ko'ring.",
                        reply_markup=create_back_button())
        clear_user_state(user_id)
        show_main_menu(message)
        return
    
    # Foydalanuvchiga xabar
    bot.send_message(message.chat.id,
                    "✅ <b>Startup yaratildi!</b>\n\n"
                    "⏳ Administrator tasdig'ini kutmoqda.",
                    reply_markup=create_back_button())
    
    # Adminga xabar
    startup = get_startup(startup_id)
    user = get_user(data['owner_id'])
    owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
    
    text = (
        f"🆕 <b>Yangi startup yaratildi!</b>\n\n"
        f"🎯 <b>Nomi:</b> {startup['name']}\n"
        f"📌 <b>Tavsif:</b> {startup['description'][:200]}...\n"
        f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
        f"🔧 <b>Kerak:</b> {startup.get('required_skills', '—')}\n"
        f"👥 <b>Maksimal a'zolar:</b> {startup.get('max_members', '—')}\n\n"
        f"👤 <b>Muallif:</b> {owner_name}\n"
        f"📱 <b>Aloqa:</b> @{user.get('username', '—')}"
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
    
    clear_user_state(user_id)
    show_main_menu(message)

# 5. STARTAPLARIM BO'LIMI
@bot.message_handler(func=lambda message: message.text == '📌 Startaplarim')
def show_my_startups_main(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'in_my_startups')
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton('📋 Mening startaplarim'),
        KeyboardButton('🤝 Qo\'shilgan startaplar'),
        KeyboardButton('🔙 Asosiy menyu')
    )
    
    bot.send_message(message.chat.id, "📌 <b>Startaplarim bo'limi:</b>", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '📋 Mening startaplarim' and get_user_state(message.from_user.id) == 'in_my_startups')
def show_my_startups_list(message):
    user_id = message.from_user.id
    startups = get_startups_by_owner(user_id)
    
    if not startups:
        bot.send_message(message.chat.id,
                        "📭 <b>Sizda hali startup mavjud emas.</b>",
                        reply_markup=create_back_button())
        return
    
    show_my_startups_page(message.chat.id, user_id, 1)

def show_my_startups_page(chat_id, user_id, page):
    startups = get_startups_by_owner(user_id)
    
    per_page = 5
    total = len(startups)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(1, page), total_pages)
    
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total)
    page_startups = startups[start_idx:end_idx]
    
    text = f"📋 <b>Mening startaplarim</b>\n📄 <b>Sahifa:</b> {page}/{total_pages}\n\n"
    
    for i, startup in enumerate(page_startups, start=start_idx + 1):
        status_emoji = {
            'pending': '⏳',
            'active': '▶️',
            'completed': '✅',
            'rejected': '❌'
        }.get(startup['status'], '❓')
        text += f"{i}. {startup['name']} – {status_emoji}\n"
    
    markup = InlineKeyboardMarkup(row_width=5)
    
    # Raqamli tugmalar
    buttons = []
    for i in range(start_idx + 1, start_idx + len(page_startups) + 1):
        buttons.append(InlineKeyboardButton(f'{i}️⃣', callback_data=f'my_startup_num_{i-1}'))
    
    if buttons:
        markup.row(*buttons)
    
    # Navigatsiya
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton('⏮️ Oldingi', callback_data=f'my_startup_page_{page-1}'))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton('⏭️ Keyingi', callback_data=f'my_startup_page_{page+1}'))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_my_startups'))
    
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

@bot.callback_query_handler(func=lambda call: call.data.startswith('my_startup_num_'))
def handle_my_startup_number(call):
    try:
        idx = int(call.data.split('_')[3])
        user_id = call.from_user.id
        startups = get_startups_by_owner(user_id)
        
        if idx < 0 or idx >= len(startups):
            bot.answer_callback_query(call.id, "❌ Startup topilmadi!", show_alert=True)
            return
        
        startup = startups[idx]
        view_my_startup_details(call.message.chat.id, call.message.message_id, startup)
        bot.answer_callback_query(call.id)
    except:
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

def view_my_startup_details(chat_id, message_id, startup):
    user = get_user(startup['owner_id'])
    owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
    
    # A'zolar soni
    members_count = len(get_all_startup_members(startup['_id']))
    
    status_texts = {
        'pending': '⏳ Kutilmoqda',
        'active': '▶️ Faol',
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
        f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
        f"👥 <b>A'zolar:</b> {members_count} / {startup.get('max_members', '—')}\n"
        f"📌 <b>Tavsif:</b> {startup['description']}"
    )
    
    markup = InlineKeyboardMarkup()
    
    if startup['status'] == 'pending':
        markup.add(InlineKeyboardButton('⏳ Admin tasdig\'ini kutyapti', callback_data='waiting_approval'))
    elif startup['status'] == 'active':
        markup.add(InlineKeyboardButton('👥 A\'zolar', callback_data=f'view_members_{startup["_id"]}_1'))
        markup.add(InlineKeyboardButton('⏹️ Yakunlash', callback_data=f'complete_startup_{startup["_id"]}'))
    elif startup['status'] == 'completed':
        markup.add(InlineKeyboardButton('👥 A\'zolar', callback_data=f'view_members_{startup["_id"]}_1'))
        if startup.get('results'):
            markup.add(InlineKeyboardButton('📊 Natijalar', callback_data=f'view_results_{startup["_id"]}'))
    elif startup['status'] == 'rejected':
        markup.add(InlineKeyboardButton('❌ Rad etilgan', callback_data='rejected_info'))
    
    markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_my_startups_list'))
    
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass
    
    if startup.get('logo'):
        bot.send_photo(chat_id, startup['logo'], caption=text, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('view_members_'))
def view_startup_members(call):
    try:
        parts = call.data.split('_')
        startup_id = parts[2]
        page = int(parts[3])
        
        members, total = get_startup_members(startup_id, page)
        total_pages = max(1, (total + 4) // 5)
        
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        if not members:
            text = "👥 <b>A'zolar</b>\n\n📭 <b>Hozircha a'zolar yo'q.</b>"
            markup = InlineKeyboardMarkup()
        else:
            text = f"👥 <b>A'zolar</b>\n📄 <b>Sahifa:</b> {page}/{total_pages}\n\n"
            for i, member in enumerate(members, start=(page-1)*5+1):
                member_name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip()
                if not member_name:
                    member_name = f"User {member.get('user_id', '')}"
                text += f"{i}. <b>{member_name}</b>\n"
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
        
        markup.add(InlineKeyboardButton('🔙 Orqaga', callback_data=f'back_to_my_startup_{startup_id}'))
        
        bot.send_message(call.message.chat.id, text, reply_markup=markup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"View members xatosi: {e}")
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('complete_startup_'))
def complete_startup(call):
    try:
        startup_id = call.data.split('_')[2]
        user_id = call.from_user.id
        set_user_state(user_id, f'completing_startup_{startup_id}')
        
        msg = bot.send_message(call.message.chat.id, 
                              "📝 <b>Nimalarga erishdingiz?</b>\nMatn yozing:", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_results, startup_id)
        
        bot.answer_callback_query(call.id)
    except:
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

def process_startup_results(message, startup_id):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        # Startup ko'rinishiga qaytish
        startups = get_startups_by_owner(user_id)
        for startup in startups:
            if startup['_id'] == startup_id:
                view_my_startup_details(message.chat.id, message.message_id, startup)
                break
        return
    
    results_text = message.text
    
    msg = bot.send_message(message.chat.id, 
                          "🖼 <b>Natijalar rasmini yuboring:</b>", 
                          reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_startup_photo, startup_id, results_text)

def process_startup_photo(message, startup_id, results_text):
    user_id = message.from_user.id
    
    if message.text == '🔙 Orqaga':
        clear_user_state(user_id)
        msg = bot.send_message(message.chat.id, 
                              "📝 <b>Nimalarga erishdingiz?</b>\nMatn yozing:", 
                              reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_results, startup_id)
        return
    
    if message.photo:
        photo_id = message.photo[-1].file_id
        
        # Startup holati va natijalarini yangilash
        update_startup_status(startup_id, 'completed')
        update_startup_results(startup_id, results_text, datetime.now())
        
        # Barcha a'zolarni olish
        members = get_all_startup_members(startup_id)
        
        startup = get_startup(startup_id)
        
        # Barcha a'zolarga xabar yuborish
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
                        f"📤 Xabar yuborildi: {success_count} ta a'zoga")
        
        clear_user_state(user_id)
        
        # Yangilangan startup ma'lumotlarini ko'rsatish
        startups = get_startups_by_owner(user_id)
        for startup in startups:
            if startup['_id'] == startup_id:
                view_my_startup_details(message.chat.id, message.message_id, startup)
                break
    else:
        bot.send_message(message.chat.id, "⚠️ <b>Iltimos, rasm yuboring!</b>", reply_markup=create_back_button())
        msg = bot.send_message(message.chat.id, "🖼 <b>Natijalar rasmini yuboring:</b>", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_startup_photo, startup_id, results_text)

@bot.message_handler(func=lambda message: message.text == '🤝 Qo\'shilgan startaplar' and get_user_state(message.from_user.id) == 'in_my_startups')
def show_joined_startups(message):
    user_id = message.from_user.id
    joined_startup_ids = get_user_joined_startups(user_id)
    
    if not joined_startup_ids:
        bot.send_message(message.chat.id,
                        "🤝 <b>Qo'shilgan startaplar:</b>\n\n"
                        "🔜 Hozircha qo'shilgan startapingiz yo'q.",
                        reply_markup=create_back_button())
        return
    
    startups = get_startups_by_ids(joined_startup_ids)
    
    text = "🤝 <b>Qo'shilgan startaplar:</b>\n\n"
    
    for i, startup in enumerate(startups, 1):
        status_emoji = {
            'pending': '⏳',
            'active': '▶️',
            'completed': '✅',
            'rejected': '❌'
        }.get(startup['status'], '❓')
        text += f"{i}. {startup['name']} – {status_emoji}\n"
    
    bot.send_message(message.chat.id, text, reply_markup=create_back_button())

# 6. ADMIN PANEL
@bot.message_handler(func=lambda message: message.text == '⚙️ Admin panel' and message.chat.id == ADMIN_ID)
def admin_panel(message):
    user_id = message.from_user.id
    set_user_state(user_id, 'in_admin_panel')
    
    stats = get_statistics()
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton('📊 Dashboard'),
        KeyboardButton('🚀 Startaplar'),
        KeyboardButton('👥 Foydalanuvchilar'),
        KeyboardButton('📢 Xabar yuborish'),
        KeyboardButton('🔙 Asosiy menyu')
    )
    
    welcome_text = (
        f"👨‍💼 <b>Admin Panel</b>\n\n"
        f"📊 <b>Dashboard:</b>\n"
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
    
    dashboard_text = (
        f"📊 <b>Dashboard</b>\n\n"
        f"📈 <b>Umumiy statistikalar:</b>\n"
        f"├ 👥 Foydalanuvchilar: <b>{stats['total_users']}</b>\n"
        f"├ 🚀 Startaplar: <b>{stats['total_startups']}</b>\n"
        f"├ ⏳ Kutilayotgan: <b>{stats['pending_startups']}</b>\n"
        f"├ ▶️ Faol: <b>{stats['active_startups']}</b>\n"
        f"└ ✅ Yakunlangan: <b>{stats['completed_startups']}</b>\n\n"
    )
    
    if recent_users:
        dashboard_text += f"👥 <b>So'nggi foydalanuvchilar:</b>\n"
        for i, user in enumerate(recent_users, 1):
            dashboard_text += f"{i}. {user.get('first_name', '')} {user.get('last_name', '')}\n"
        dashboard_text += "\n"
    
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
        InlineKeyboardButton('📈 Toʻliq statistikalar', callback_data='full_stats'),
        InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_admin_panel')
    )
    
    bot.send_message(message.chat.id, dashboard_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '🚀 Startaplar' and message.chat.id == ADMIN_ID)
def admin_startups_menu(message):
    stats = get_statistics()
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton('⏳ Kutilayotgan', callback_data='pending_startups_1'),
        InlineKeyboardButton('▶️ Faol', callback_data='active_startups_1'),
        InlineKeyboardButton('✅ Yakunlangan', callback_data='completed_startups_1'),
        InlineKeyboardButton('❌ Rad etilgan', callback_data='rejected_startups_1'),
        InlineKeyboardButton('🔙 Orqaga', callback_data='back_to_admin_panel')
    )
    
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
        text = f"⏳ <b>Kutilayotgan startaplar</b>\n📄 <b>Sahifa:</b> {page}/{total_pages}\n\n"
        
        for i, startup in enumerate(startups, start=(page-1)*5+1):
            user = get_user(startup['owner_id'])
            owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
            text += f"{i}. <b>{startup['name']}</b> – {owner_name}\n\n"
        
        markup = InlineKeyboardMarkup()
        
        # Sahifa navigatsiyasi
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton('⏮️', callback_data=f'pending_startups_{page-1}'))
        
        nav_buttons.append(InlineKeyboardButton(f'{page}/{total_pages}', callback_data='current_page'))
        
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton('⏭️', callback_data=f'pending_startups_{page+1}'))
        
        if nav_buttons:
            markup.row(*nav_buttons)
        
        # Startup tanlash
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
            f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
            f"🔧 <b>Kerak:</b> {startup.get('required_skills', '—')}\n"
            f"👥 <b>Maksimal a'zolar:</b> {startup.get('max_members', '—')}\n"
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
        
        # Egaga xabar
        startup = get_startup(startup_id)
        if startup:
            try:
                bot.send_message(
                    startup['owner_id'],
                    f"🎉 <b>Tabriklaymiz!</b>\n\n"
                    f"✅ '<b>{startup['name']}</b>' startupingiz tasdiqlandi va kanalga joylandi!"
                )
            except:
                pass
        
        # Kanalga post
        try:
            user = get_user(startup['owner_id'])
            owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
            
            channel_text = (
                f"🚀 <b>{startup['name']}</b>\n\n"
                f"📝 {startup['description']}\n\n"
                f"👤 <b>Muallif:</b> {owner_name}\n"
                f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
                f"🔧 <b>Kerakli mutaxassislar:</b>\n{startup.get('required_skills', '—')}\n\n"
                f"👥 <b>A'zolar:</b> 0 / {startup.get('max_members', '—')}\n\n"
                f"👉 <b>Startupga qo'shilish uchun pastdagi tugmani bosing.</b>\n"
                f"➕ <b>O'z startupingizni yaratish uchun:</b> @{bot.get_me().username}"
            )
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton('🤝 Startupga qo\'shilish', callback_data=f'join_startup_{startup_id}'))
            
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
        
        # Kutilayotgan startaplarga qaytish
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
        
        # Egaga xabar
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
        
        # Kutilayotgan startaplarga qaytish
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
            # Xabar turini tekshirish
            if message.photo:
                bot.send_photo(user_id, message.photo[-1].file_id, caption=text if text else None)
            elif message.video:
                bot.send_video(user_id, message.video.file_id, caption=text if text else None)
            elif message.document:
                bot.send_document(user_id, message.document.file_id, caption=text if text else None)
            else:
                bot.send_message(user_id, f"📢 <b>Yangilik!</b>\n\n{text}")
            
            success += 1
            time.sleep(0.05)  # Flood limitdan qochish uchun
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

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_startups_menu')
def handle_back_to_startups_menu(call):
    show_startups_menu(call.message)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_categories')
def handle_back_to_categories(call):
    show_categories(call.message)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_my_startups')
def handle_back_to_my_startups(call):
    show_my_startups_main(call.message)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_my_startups_list')
def handle_back_to_my_startups_list(call):
    user_id = call.from_user.id
    show_my_startups_page(call.message.chat.id, user_id, 1)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('back_to_my_startup_'))
def handle_back_to_my_startup(call):
    try:
        startup_id = call.data.split('_')[4]
        user_id = call.from_user.id
        startups = get_startups_by_owner(user_id)
        
        # Startupni topish
        for idx, startup in enumerate(startups):
            if startup['_id'] == startup_id:
                view_my_startup_details(call.message.chat.id, call.message.message_id, startup)
                break
        
        bot.answer_callback_query(call.id)
    except:
        bot.answer_callback_query(call.id, "⚠️ Xatolik yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data in ['already_active', 'already_completed', 'already_rejected', 
                                                          'rejected_info', 'waiting_approval', 'current_page'])
def handle_info_callbacks(call):
    bot.answer_callback_query(call.id)

# Orqaga tugmasi uchun umumiy handler
@bot.message_handler(func=lambda message: message.text == '🔙 Orqaga')
def handle_back_button(message):
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    
    if user_state in ['in_profile', 'editing_first_name', 'editing_last_name', 'editing_phone',
                     'editing_birth_date', 'editing_specialization', 'editing_experience', 'editing_bio']:
        clear_user_state(user_id)
        show_main_menu(message)
    
    elif user_state in ['in_startups_menu', 'viewing_recommended', 'choosing_category']:
        clear_user_state(user_id)
        show_main_menu(message)
    
    elif user_state in ['in_my_startups', 'creating_startup', 'completing_startup_']:
        clear_user_state(user_id)
        show_main_menu(message)
    
    elif user_state == 'in_admin_panel' or user_state == 'broadcasting_message':
        clear_user_state(user_id)
        show_main_menu(message)
    
    else:
        show_main_menu(message)

@bot.message_handler(func=lambda message: message.text == '🔙 Asosiy menyu')
def handle_back_to_main_menu_button(message):
    show_main_menu(message)

# To'liq umumiy handler
@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    try:
        if message.chat.id == ADMIN_ID and message.text not in ('🔙 Orqaga', '🔙 Asosiy menyu', '⚙️ Admin panel'):
            admin_panel(message)
            return

        if message.text == '🔙 Orqaga':
            handle_back_button(message)
            return
        
        if message.text == '🔙 Asosiy menyu':
            show_main_menu(message)
            return

        show_main_menu(message)
    except Exception as e:
        logging.error(f"Unhandled message error: {e}")

# Botni ishga tushirish
if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("🚀 GarajHub Bot ishga tushdi...")
    print(f"👨‍💼 Admin ID: {ADMIN_ID}")
    print(f"📢 Kanal: {CHANNEL_USERNAME}")
    try:
        bot_info = bot.get_me()
        print(f"🤖 Bot: @{bot_info.username}")
    except:
        print("🤖 Bot: (get_me() failed)")
    print("🗄️ Database: MongoDB")
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
            continue # pyright: ignore[reportUndefinedVariable]
