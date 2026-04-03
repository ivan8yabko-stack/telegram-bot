print("🔥 NEW VERSION 123")
import asyncio
import logging
import calendar
import threading
import time
import json
import os
import csv
import re
import sys
import io
from datetime import datetime
from zoneinfo import ZoneInfo

# Исправляем кодировку для Windows (для вывода эмодзи и Unicode)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=options)
    return driver

# ================= ТВОИ НАСТРОЙКИ =================
import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 1045871640 # тут уже твой ID стоит

ACCOUNTS = [
    {"name": "AlinaShylife"},
    {"name": "AlinaShy_Vip"},
    {"name": "Alina_Shy"} 
]

CHATTERS = {
    70354: "Назар",
    139130: "Андрей", 
    160016: "Макс",
    163475: "Георгий",
    167593: "Никита",
    134895: "Начальник"
}

MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
    7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}

MONTHS_EN = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
}

DB_FILE = "om_database.json"
FOLLOWERS_FILE = "followers.json"
# ==================================================

# Часовой пояс Польши
POLAND_TZ = ZoneInfo("Europe/Warsaw")

def get_poland_now():
    """Возвращает текущее время по Польскому часовому поясу"""
    return datetime.now(POLAND_TZ)

logging.basicConfig(level=logging.ERROR)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# --- ЛОКАЛЬНАЯ БАЗА ДАННЫХ ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                db_changed = False
                
                # Миграция 1: "Назар 2" → "Назар"
                for sale_id, t in data.items():
                    if t.get("chatter") == "Назар 2":
                        t["chatter"] = "Назар"
                        db_changed = True
                
                # Миграция 2: добавляем "type" для старых записей
                for sale_id, t in data.items():
                    # Если есть "amount" и нет "type" - это старая транзакция
                    if "amount" in t and "type" not in t:
                        t["type"] = "transaction"
                        db_changed = True
                    # Если есть "subscriber" и нет "type" - это старый подписчик
                    elif "subscriber" in t and "type" not in t:
                        t["type"] = "follower"
                        db_changed = True
                    # Если есть "count" и нет "type" - это dashboard данные
                    elif "count" in t and "type" not in t:
                        t["type"] = "dashboard_fans"
                        db_changed = True
                
                # Миграция 3: удаляем служебные строки "Average" и "Total"
                keys_to_remove = []
                for sale_id, t in data.items():
                    account = t.get("account", "").lower()
                    if account in ("average", "total", "avg"):
                        keys_to_remove.append(sale_id)
                        db_changed = True
                
                for key in keys_to_remove:
                    del data[key]
                    print(f"🗑️  Удалена служебная строка: {key}")

                # Миграция 4: удаляем дубли транзакций (по нормализованному ключу)
                seen_trx = set()
                dup_keys = []
                for key, t in data.items():
                    if t.get("type") == "transaction":
                        tx_key = _canonical_transaction_key(
                            t.get("date", ""),
                            t.get("account", ""),
                            t.get("amount", 0),
                            t.get("chatter", "")
                        )
                        if tx_key in seen_trx:
                            dup_keys.append(key)
                        else:
                            seen_trx.add(tx_key)

                for key in dup_keys:
                    del data[key]
                    db_changed = True
                    print(f"🗑️  Дублированная транзакция удалена: {key}")

                # Миграция 5: переименовываем Озира на Георгия
                for sale_id, t in data.items():
                    if t.get("chatter") == "Озир":
                        t["chatter"] = "Георгий"
                        db_changed = True

                if db_changed:
                    with open(DB_FILE, "w", encoding="utf-8") as fw:
                        json.dump(data, fw, ensure_ascii=False, indent=4)
                        print("♻️ База данных обновлена (миграция структуры)")

                return data
        except:
            return {}
    return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_followers_db():
    if os.path.exists(FOLLOWERS_FILE):
        try:
            with open(FOLLOWERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    # fallback на старый файл, если он есть
    if os.path.exists("march_followers.json"):
        try:
            with open("march_followers.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                with open(FOLLOWERS_FILE, "w", encoding="utf-8") as fw:
                    json.dump(data, fw, ensure_ascii=False, indent=4)
                return data
        except:
            return {}

    return {}


def save_followers_db(data):
    with open(FOLLOWERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def import_transactions_from_csv(csv_file):
    """Импортирует транзакции из CSV файла в om_database.json"""
    if not os.path.exists(csv_file):
        print(f"❌ Файл {csv_file} не найден")
        return 0
    
    imported_count = 0
    existing_count = 0
    
    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                status = row.get("Status", "").strip()
                # Пропускаем refunded транзакции
                if status == "Refunded":
                    continue
                
                date_text = row.get("Date", "").strip()
                account_raw = row.get("Account", "").strip()
                amount_str = row.get("Net", "").strip()
                assignee_raw = row.get("Assignee", "").strip()
                
                if not all([date_text, account_raw, amount_str, assignee_raw]):
                    continue
                
                # Извлекаем имя аккаунта "alinashylife (id: 47639)" → "alinashylife"
                account_match = re.match(r"([\w\-]+)\s*\(", account_raw)
                account_text = account_match.group(1) if account_match else account_raw
                
                # Извлекаем имя чатера "Никита (id: 167593)" → "Никита"
                chatter_match = re.match(r"([\w\s]+)\s*\(", assignee_raw)
                chatter_raw = chatter_match.group(1).strip() if chatter_match else assignee_raw
                
                # Пытаемся найти в CHATTERS по ID
                chatter_id_match = re.search(r"id:\s*(\d+)", assignee_raw)
                if chatter_id_match:
                    chatter_id = int(chatter_id_match.group(1))
                    chatter = CHATTERS.get(chatter_id, chatter_raw)
                else:
                    chatter = chatter_raw
                
                try:
                    amount = float(amount_str)
                except ValueError:
                    continue
                
                # Создаём ключ транзакции
                canonical_key = (
                    date_text.strip(),
                    account_text.lower().strip(),
                    round(amount, 2),
                    chatter.lower().strip()
                )
                
                # Проверяем, есть ли уже такая транзакция
                found = False
                for existing_tx in LOCAL_DB.values():
                    if existing_tx.get("type") != "transaction":
                        continue
                    
                    existing_key = (
                        existing_tx.get("date", "").strip(),
                        existing_tx.get("account", "").lower().strip(),
                        round(float(existing_tx.get("amount", 0)), 2),
                        existing_tx.get("chatter", "").lower().strip()
                    )
                    
                    if existing_key == canonical_key:
                        found = True
                        existing_count += 1
                        break
                
                if not found:
                    tx_id = f"csv_txn:{date_text}|{account_text}|{amount:.2f}|{chatter}"
                    LOCAL_DB[tx_id] = {
                        "type": "transaction",
                        "date": date_text,
                        "account": account_text,
                        "amount": amount,
                        "chatter": chatter
                    }
                    imported_count += 1
    
    except Exception as e:
        print(f"❌ Ошибка при импорте CSV: {e}")
        return 0
    
    if imported_count > 0:
        save_db(LOCAL_DB)
        print(f"✅ Загружено {imported_count} новых транзакций из {csv_file}")
    
    if existing_count > 0:
        print(f"⏭️  {existing_count} транзакций уже были в БД (дубли пропущены)")
    
    return imported_count


LOCAL_DB = load_db()
FOLLOWERS_DB = load_followers_db()

# Импортируем CSV при старте
CSV_FILE = "cm_t_onlymonster_04_02_2026.csv"
if os.path.exists(CSV_FILE):
    import_transactions_from_csv(CSV_FILE)

# --- УМНЫЙ ПАРСЕР ДАТЫ (ДЛЯ СОРТИРОВКИ) ---
def parse_tx_date(date_str):
    import re
    
    month_map = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, 
        "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
        "January": 1, "February": 2, "March": 3, "April": 4, "June": 6,
        "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12
    }
    
    try:
        # Очищаем строку
        date_str = date_str.replace(',', '').replace('\n', ' ').strip()
        parts = date_str.split()
        
        if len(parts) < 2:
            return datetime.min
        
        # Попытка 1: "14 Mar 2026" или "14 Mar" формат
        try:
            day = int(parts[0])
            month = month_map.get(parts[1], 0)
            
            if month > 0:
                year = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else get_poland_now().year
                
                hour = minute = 0
                if len(parts) > 3:
                    time_match = re.search(r'(\d+):(\d+)', parts[3])
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2))
                        if len(parts) > 4 and parts[4].upper() == 'PM' and hour < 12:
                            hour += 12
                        elif len(parts) > 4 and parts[4].upper() == 'AM' and hour == 12:
                            hour = 0
                
                return datetime(year, month, day, hour, minute)
        except:
            pass
        
        # Попытка 2: поиск через регулярное выражение "DD MMM YYYY"
        match = re.search(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', date_str)
        if match:
            day = int(match.group(1))
            month_str = match.group(2)
            year = int(match.group(3))
            month = month_map.get(month_str, 0)
            
            if month > 0:
                return datetime(year, month, day)
        
        # Попытка 3: формат "MMM DD, YYYY"
        match = re.search(r'([A-Za-z]+)\s+(\d{1,2})\s*,?\s+(\d{4})', date_str)
        if match:
            month_str = match.group(1)
            day = int(match.group(2))
            year = int(match.group(3))
            month = month_map.get(month_str, 0)
            
            if month > 0:
                return datetime(year, month, day)
        
        return datetime.min
        
    except Exception as e:
        print(f"❌ Ошибка парсинга даты '{date_str}': {e}")
        return datetime.min


def _canonical_transaction_key(date_text, account_text, amount, chatter):
    # Стабильное формирование ключа для детекции дублей.
    tx_date = parse_tx_date(date_text)
    if tx_date == datetime.min:
        date_norm = "".join(date_text.strip().split())
    else:
        # Обрезаем до минут, чтобы одинаковые сделки с секундами воспринимались как один
        date_norm = tx_date.strftime("%d %b %Y %H:%M")

    account_norm = " ".join(account_text.strip().lower().split())
    chatter_norm = " ".join(chatter.strip().lower().split())
    amount_norm = round(float(amount), 2)

    return (date_norm, account_norm, amount_norm, chatter_norm)

DASHBOARD_URL = "https://onlymonster.ai/panel/dashboard"
FOLLOWERS_URL = None  # old path не работает в текущей версии
TRANSACTIONS_URL = "https://onlymonster.ai/panel/chatter-metrics/transactions"

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ПАРСЕРА ---
def _extract_chatter_name(chatter_raw):
    chatter_id = None
    if "(id" in chatter_raw:
        try:
            chatter_id = int(chatter_raw.split("(id")[1].replace(")", "").strip())
        except:
            chatter_id = None
    base_name = chatter_raw.split("(id")[0].strip()
    return CHATTERS.get(chatter_id, base_name)


def _process_transaction_row(row, loop):
    try:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) < 5:
            return False

        date_text = " ".join(cols[0].text.strip().split())
        account_text = " ".join(cols[1].text.strip().split())
        amount_text = cols[2].text.strip()
        chatter_raw = cols[4].text.strip() if len(cols) > 4 else "Неизвестно"

        chatter = _extract_chatter_name(chatter_raw)

        if "$" not in amount_text:
            return False

        amount_raw = amount_text.replace("$", "").strip()
        if not amount_raw.replace(".", "").isdigit():
            return False

        amount = float(amount_raw)
        canonical_key = _canonical_transaction_key(date_text, account_text, amount, chatter)
        tx_id = f"txn:{canonical_key[0]}|{canonical_key[1]}|{canonical_key[2]:.2f}|{canonical_key[3]}"

        # ✅ ПРОВЕРКА 1: Быстрая проверка по tx_id (очень часто совпадает точно)
        if tx_id in LOCAL_DB:
            return False  # Уже есть такая транзакция

        # ✅ ПРОВЕРКА 2: Проверка по canonical_key (для случаев с разными форматами даты)
        for existing_id, existing in LOCAL_DB.items():
            if existing.get("type") != "transaction":
                continue
            
            existing_key = _canonical_transaction_key(
                existing.get("date", ""),
                existing.get("account", ""),
                existing.get("amount", 0),
                existing.get("chatter", "")
            )
            
            if existing_key == canonical_key:
                return False  # Уже есть такая транзакция

        # ✅ НОВАЯ ТРАНЗАКЦИЯ - добавляем в БД
        LOCAL_DB[tx_id] = {
            "type": "transaction",
            "date": date_text,
            "account": account_text,
            "amount": amount,
            "chatter": chatter
        }

        print(f"✅ Добавлено: {account_text} | ${amount:.2f} | 👨‍💻 {chatter}")
        try:
            msg_text = (
                f"💰 <b>НОВАЯ ПРОДАЖА!</b>\n\n"
                f"🖥 Аккаунт: <b>{account_text}</b>\n"
                f"💵 Сумма: <b>${amount:.2f}</b>\n"
                f"👨‍💻 Чатер: <b>{chatter}</b>\n"
                f"📅 {date_text}"
            )
            asyncio.run_coroutine_threadsafe(bot.send_message(chat_id=ADMIN_ID, text=msg_text), loop)
        except Exception as e:
            print(f"Ошибка отправки уведомления: {e}")

        return True

    except Exception as e:
        print(f"⚠️ Ошибка обработки транзакции: {e}")
        return False


def _process_follower_row(row, loop):
    try:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) < 3:
            return False

        date_text = cols[0].text.strip()
        account_text = cols[1].text.strip()
        follower_name = cols[2].text.strip()

        if not follower_name:
            return False

        follow_id = f"follower:{date_text}|{account_text}|{follower_name}"

        if follow_id not in LOCAL_DB:
            LOCAL_DB[follow_id] = {
                "type": "follower",
                "date": date_text,
                "account": account_text,
                "subscriber": follower_name
            }

            print(f"👤 Новый подписчик: {account_text} | {follower_name}")
            try:
                msg_text = (
                    f"👤 <b>НОВЫЙ ПОДПИСЧИК!</b>\n\n"
                    f"🖥 Аккаунт: <b>{account_text}</b>\n"
                    f"👥 Подписчик: <b>{follower_name}</b>\n"
                    f"📅 {date_text}"
                )
                asyncio.run_coroutine_threadsafe(bot.send_message(chat_id=ADMIN_ID, text=msg_text), loop)
            except Exception as e:
                print(f"Ошибка отправки уведомления подписчика: {e}")

            return True

    except Exception:
        return False

    return False


def _process_dashboard_row(row, loop):
    try:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) < 2:
            return False

        account_text = cols[0].text.strip()
        fans_text = cols[1].text.strip()
        
        # Обрабатываем ТОЛЬКО строку "Total" (игнорируем данные по отдельным моделям)
        if account_text.lower() != "total":
            return False
        
        if not fans_text:
            return False

        # Извлекаем количество подписчиков из "Total"
        import re
        m = re.search(r"(\d+)", fans_text)
        if not m:
            return False

        fans_count = int(m.group(1))
        stat_id = "fans:total"  # Константный ID для общего итога

        # Получаем предыдущее значение
        old = LOCAL_DB.get(stat_id)
        old_count = old.get("count", 0) if old else 0

        # Вычисляем дельту (изменение)
        delta = fans_count - old_count

        # Сохраняем текущее значение для будущего сравнения
        LOCAL_DB[stat_id] = {
            "type": "dashboard_fans",
            "date": get_poland_now().strftime("%d %b %Y %H:%M"),
            "account": "TOTAL",
            "count": fans_count
        }

        # Сохраняем в отдельный файл для всех фанов
        FOLLOWERS_DB[stat_id] = {
            "type": "dashboard_fans",
            "date": get_poland_now().strftime("%d %b %Y %H:%M"),
            "account": "TOTAL",
            "count": fans_count
        }
        save_followers_db(FOLLOWERS_DB)

        # Отправляем уведомление ТОЛЬКО если произошло изменение (дельта ≠ 0)
        if delta != 0:
            current_date = get_poland_now().strftime('%d %b %Y')
            
            if delta > 0:
                # Подписчики добавились
                print(f"👤 TOTAL: +{delta} новых подписчиков (всего {fans_count})")
                msg_text = (
                    f"👤 <b>НОВЫЕ ПОДПИСЧИКИ!</b>\n\n"
                    f"➕ Новых: <b>+{delta}</b>\n"
                    f"👥 Всего подписчиков: <b>{fans_count}</b> за {current_date}\n"
                    f"📅 {get_poland_now().strftime('%d %b %Y %H:%M')}"
                )
            else:
                # Подписчики отписались
                print(f"👤 TOTAL: -{abs(delta)} отписалось (осталось {fans_count})")
                msg_text = (
                    f"👤 <b>ОТПИСКИ!</b>\n\n"
                    f"➖ Отписалось: <b>{abs(delta)}</b>\n"
                    f"👥 Всего подписчиков: <b>{fans_count}</b> за {current_date}\n"
                    f"📅 {get_poland_now().strftime('%d %b %Y %H:%M')}"
                )
            
            try:
                asyncio.run_coroutine_threadsafe(bot.send_message(chat_id=ADMIN_ID, text=msg_text), loop)
            except Exception as e:
                print(f"Ошибка отправки уведомления фанов: {e}")
            return True

    except Exception:
        return False

    return False


# --- ФОНОВЫЙ ПАРСЕР С ПЕРЕЗАПУСКОМ КАЖДЫЕ 15 МИНУТ ---
def run_parser(loop): # <--- Передаем цикл сюда
    while True: 
        driver = None
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--start-maximized")
            
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--remote-debugging-port=9222")
            options.add_argument("--headless=new") # РАСКОММЕНТИРУЙ НА СЕРВЕРЕ!
            
            profile_path = os.path.abspath("chrome_profile")
            options.add_argument(f"user-data-dir={profile_path}")

            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

            print("🚀 Запуск сессии Chrome...")
            driver.get("https://onlymonster.ai/panel/chatter-metrics/transactions")
            time.sleep(4) 

            if "login" in driver.current_url.lower() or "auth" in driver.current_url.lower():
                print("\n" + "="*50)
                print("🛑 СЕССИЯ ПУСТАЯ.")
                print("👉 ВОЙДИ В АККАУНТ ONLYMONSTER ОДИН РАЗ И НАЖМИ ENTER!")
                input("👉 ЖДУ ENTER В КОНСОЛИ...")
                print("="*50 + "\n")
                driver.get("https://onlymonster.ai/panel/chatter-metrics/transactions")
            else:
                print("✅ Успешный автовход!")

            print("🕒 Парсер запущен. Будет проверять новые транзакции и подписчиков каждую минуту...")
            print("Браузер перезагружается каждые 30 минут для очистки памяти\n")
            
            cycle_count = 0
            BROWSER_RELOAD_INTERVAL = 1800  # Перезагружаем браузер каждые 30 минут (1800 сек)

            while True:
                cycle_count += 1
                new_data_found = False

                # Сканируем только активные URL (без None)
                urls_to_scan = [
                    ("dashboard", DASHBOARD_URL),
                    ("transactions", TRANSACTIONS_URL),
                ]
                if FOLLOWERS_URL:
                    urls_to_scan.append(("followers", FOLLOWERS_URL))

                for url_type, url in urls_to_scan:
                    try:
                        driver.get(url)
                        time.sleep(4)

                        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                        if not rows:
                            print(f"⚠️  {url_type}: таблица не найдена или пуста")
                            continue

                        print(f"📊 {url_type}: найдено {len(rows)} строк | Цикл #{cycle_count}")

                        for row in rows:
                            try:
                                if url_type == "dashboard":
                                    if _process_dashboard_row(row, loop):
                                        new_data_found = True
                                        save_db(LOCAL_DB)  # Сохраняем сразу после новых данных
                                elif url_type == "transactions":
                                    if _process_transaction_row(row, loop):
                                        new_data_found = True
                                        save_db(LOCAL_DB)  # Сохраняем сразу после новой транзакции
                                elif url_type == "followers":
                                    if _process_follower_row(row, loop):
                                        new_data_found = True
                                        save_db(LOCAL_DB)  # Сохраняем сразу после новых подписчиков
                            except Exception as row_err:
                                print(f"⚠️ Ошибка при обработке строки таблицы: {row_err}")
                    except Exception as e:
                        print(f"⚠️ Ошибка при обработке {url_type}: {e}")

                # Перезагружаем браузер каждый час для очистки памяти
                if cycle_count % (BROWSER_RELOAD_INTERVAL // 60) == 0:
                    print("♻️ Перезагружаю браузер для очистки памяти...")
                    try:
                        driver.quit()
                    except:
                        pass
                    time.sleep(2)
                    
                    options = webdriver.ChromeOptions()
                    options.add_argument("--start-maximized")
                    options.add_argument("--no-sandbox")
                    options.add_argument("--disable-dev-shm-usage")
                    options.add_argument("--remote-debugging-port=9222")
                    profile_path = os.path.abspath("chrome_profile")
                    options.add_argument(f"user-data-dir={profile_path}")
                    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
                    driver.get("https://onlymonster.ai/panel/chatter-metrics/transactions")
                    time.sleep(4)
                    print("✅ Браузер перезагружен")

                print("⏳ Ожидание 60 сек перед следующей проверкой...")
                time.sleep(60)
                    
        except Exception as e:
            print("❌ Ошибка парсера:", e)
        finally:
            if driver:
                try: driver.quit() 
                except: pass
            print("♻️ Парсер остановлен. Браузер закрыт.")
            time.sleep(3)

# --- КЛАВИАТУРЫ ГЛАВНОГО МЕНЮ ---
def get_reply_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="🖥 Статистика"))
    builder.add(types.KeyboardButton(text="📈 Общая статистика"))
    builder.add(types.KeyboardButton(text="👥 ЗП чатеров"))
    builder.add(types.KeyboardButton(text="💰 Последние транзакции"))

    builder.add(types.KeyboardButton(text="👤 Новые подписчики"))
    builder.add(types.KeyboardButton(text="⚙️ Разработчик")) 
    builder.adjust(2, 2, 2) 
    return builder.as_markup(resize_keyboard=True)

# --- ОБРАБОТЧИКИ БОТА (СТАТИСТИКА ПО ОДНОЙ МОДЕЛИ) ---
@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer("🚀 <b>Бот запущен!</b> База данных загружена.", reply_markup=get_reply_menu())

@dp.callback_query(F.data == "cancel")
async def cancel_action(callback: types.CallbackQuery):
    await callback.message.delete()

@dp.message(F.text == "🖥 Статистика")
async def show_stats_menu(message: types.Message):
    builder = InlineKeyboardBuilder()
    for acc in ACCOUNTS:
        builder.row(types.InlineKeyboardButton(text=f"🖥 {acc['name']}", callback_data=f"select_month:{acc['name']}"))
    await message.answer("<b>Выберите аккаунт для отчета:</b>", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("select_month:"))
async def select_month(callback: types.CallbackQuery, state: FSMContext):
    acc_name = callback.data.split(":")[1]
    await state.update_data(stats_acc=acc_name)
    builder = InlineKeyboardBuilder()
    for num, name in MONTHS_RU.items():
        builder.add(types.InlineKeyboardButton(text=name, callback_data=f"select_start_day:{num}"))
    builder.adjust(3)
    builder.row(types.InlineKeyboardButton(text="⬅️ Отмена", callback_data="cancel"))
    await callback.message.edit_text(f"🖥 <b>{acc_name}</b>\nВыберите месяц начала периода:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("select_start_day:"))
async def select_start_day(callback: types.CallbackQuery, state: FSMContext):
    start_m = int(callback.data.split(":")[1])
    await state.update_data(stats_start_m=start_m)

    builder = InlineKeyboardBuilder()
    days_in_month = calendar.monthrange(get_poland_now().year, start_m)[1]
    for day in range(1, days_in_month + 1):
        builder.add(types.InlineKeyboardButton(text=str(day), callback_data=f"select_end_month:{day}"))
    builder.adjust(5)
    builder.row(types.InlineKeyboardButton(text="⬅️ К месяцам", callback_data=f"select_month:{(await state.get_data()).get('stats_acc')}"))
    await callback.message.edit_text(f"🖥 <b>{(await state.get_data()).get('stats_acc')}</b> > {MONTHS_RU[start_m]}\nВыберите день начала периода:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("select_end_month:"))
async def select_end_month(callback: types.CallbackQuery, state: FSMContext):
    start_d = int(callback.data.split(":")[1])
    await state.update_data(stats_start_d=start_d)

    builder = InlineKeyboardBuilder()
    for num, name in MONTHS_RU.items():
        builder.add(types.InlineKeyboardButton(text=name, callback_data=f"select_end_day:{num}"))
    builder.adjust(3)
    await callback.message.edit_text("Отлично! Теперь выберите месяц окончания периода:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("select_end_day:"))
async def select_end_day(callback: types.CallbackQuery, state: FSMContext):
    end_m = int(callback.data.split(":")[1])
    await state.update_data(stats_end_m=end_m)

    builder = InlineKeyboardBuilder()
    days_in_month = calendar.monthrange(get_poland_now().year, end_m)[1]
    for day in range(1, days_in_month + 1):
        builder.add(types.InlineKeyboardButton(text=str(day), callback_data=f"show_report_range:{day}"))
    builder.adjust(5)
    await callback.message.edit_text(f"Выберите день окончания периода ({MONTHS_RU[end_m]}):", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("show_report_range:"))
async def show_report_range(callback: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    acc_name = user_data.get("stats_acc")
    start_m = user_data.get("stats_start_m")
    start_d = user_data.get("stats_start_d")
    end_m = user_data.get("stats_end_m")
    end_d = int(callback.data.split(":")[1])
    year = get_poland_now().year

    # ✅ Проверка на отсутствие данных
    if not all([acc_name, start_m, start_d, end_m]):
        await state.clear()
        return await callback.message.edit_text(
            "❌ Ошибка: потеряны данные выбора.\n\n"
            "Пожалуйста, нажми 'Статистика' заново и полностью пройди все шаги выбора."
        )

    try:
        start_date = datetime(year, start_m, start_d)
        end_date = datetime(year, end_m, end_d, 23, 59, 59)
    except (ValueError, TypeError):
        try:
            return await callback.message.edit_text("❌ Ошибка в датах. Начни заново.")
        except:
            pass  # Игнорируем ошибки редактирования

    if start_date > end_date:
        try:
            return await callback.message.edit_text("❌ Дата начала не может быть позже окончания! Нажми 'Статистика' заново.")
        except:
            pass  # Игнорируем ошибки редактирования

    transactions, total_sum = [], 0.0
    month_map = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

    for sale_id, t in LOCAL_DB.items():
        if t.get("type") != "transaction":
            continue

        if acc_name.lower().replace("_", "") not in t.get("account", "").lower().replace("_", ""):
            continue

        tx_date = parse_tx_date(t.get("date", ""))
        if start_date <= tx_date <= end_date:
            transactions.append(t)
            total_sum += t.get("amount", 0.0)

    followers = []
    for sale_id, t in LOCAL_DB.items():
        if t.get("type") != "dashboard_fans":
            continue

        # Берем только TOTAL записи
        if t.get("account") != "TOTAL":
            continue

        fans_date = parse_tx_date(t.get("date", ""))
        if start_date <= fans_date <= end_date:
            followers.append(t)

    start_fans = min(followers, key=lambda x: parse_tx_date(x.get("date", "")), default=None)
    end_fans = max(followers, key=lambda x: parse_tx_date(x.get("date", "")), default=None)

    report = f"📅 <b>Отчет по {acc_name}</b>\n" \
             f"Период: <b>{start_d:02d} {MONTHS_RU[start_m]} — {end_d:02d} {MONTHS_RU[end_m]}</b>\n" \
             f"💵 Доход: <b>${total_sum:.2f}</b>\n\n"

    report += "<b>Транзакции:</b>\n"
    if not transactions:
        report += "└ Нет транзакций за этот период.\n"
    else:
        for t in transactions[:20]:
            report += f"└ <b>${t['amount']:.2f}</b> | 👨‍💻 {t.get('chatter')} | {t.get('date')}\n"
        if len(transactions) > 20:
            report += f"└ еще {len(transactions)-20} транзакций...\n"

    report += "\n<b>👥 Подписчики:</b>\n"
    if not followers:
        report += "└ Нет данных за этот период.\n"
    else:
        report += f"└ Начало: {start_fans.get('count') if start_fans else '?'}\n"
        report += f"└ Конец: {end_fans.get('count') if end_fans else '?'}\n"
        if start_fans and end_fans:
            report += f"└ Приращение: {end_fans.get('count',0)-start_fans.get('count',0)}\n"

    await state.clear()
    await callback.message.edit_text(report)

# ================= ОБЩАЯ СТАТИСТИКА ЗА ПЕРИОД =================
@dp.message(F.text == "📈 Общая статистика")
async def all_stats_start(message: types.Message, state: FSMContext):
    await state.clear()
    builder = InlineKeyboardBuilder()
    for num, name in MONTHS_RU.items():
        builder.add(types.InlineKeyboardButton(text=name, callback_data=f"all_sm:{num}"))
    builder.adjust(3)
    builder.row(types.InlineKeyboardButton(text="⚡ Быстрый отчет за СЕГОДНЯ", callback_data="all_today"))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    await message.answer("<b>📈 Общая статистика по всем моделям</b>\n\nВыберите <b>МЕСЯЦ НАЧАЛА</b> периода:", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "all_today")
async def all_today_stats(callback: types.CallbackQuery):
    now = get_poland_now()
    today_str, en_month = f"{now.day:02d}", MONTHS_EN[now.month]
    
    total_sum = 0.0
    models_income = {acc["name"]: 0.0 for acc in ACCOUNTS}

    for sale_id, t in LOCAL_DB.items():
        if t.get("type") != "transaction":
            continue

        if today_str in t["date"] and en_month in t["date"]:
            amount = t["amount"]
            total_sum += amount
            for acc in ACCOUNTS:
                target_acc = acc["name"].lower().replace("_", "")
                db_acc = t["account"].lower().replace("_", "")
                if target_acc in db_acc:
                    models_income[acc["name"]] += amount
                    break

    report = f"<b>📅 ОБЩАЯ КАССА ЗА СЕГОДНЯ</b>\n━━━━━━━━━━━━━━━━━━\n💵 ИТОГО: <b>${total_sum:.2f}</b>\n━━━━━━━━━━━━━━━━━━\n\n<b>Разбивка по моделям:</b>\n"
    if total_sum == 0:
         report += "└ Нет транзакций за сегодня.\n"
    else:
        for m_name, m_sum in models_income.items():
            report += f"🖥 {m_name}: <b>${m_sum:.2f}</b>\n"

    await callback.message.edit_text(report)

@dp.callback_query(F.data.startswith("all_sm:"))
async def all_ask_start_day(callback: types.CallbackQuery, state: FSMContext):
    month = int(callback.data.split(":")[1])
    await state.update_data(all_start_m=month)
    builder = InlineKeyboardBuilder()
    days_in_month = calendar.monthrange(get_poland_now().year, month)[1]
    for day in range(1, days_in_month + 1):
        builder.add(types.InlineKeyboardButton(text=str(day), callback_data=f"all_sd:{day}"))
    builder.adjust(5)
    await callback.message.edit_text(f"Месяц: {MONTHS_RU[month]}\nВыберите <b>ДЕНЬ НАЧАЛА</b> периода:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("all_sd:"))
async def all_ask_end_month(callback: types.CallbackQuery, state: FSMContext):
    day = int(callback.data.split(":")[1])
    await state.update_data(all_start_d=day)
    builder = InlineKeyboardBuilder()
    for num, name in MONTHS_RU.items():
        builder.add(types.InlineKeyboardButton(text=name, callback_data=f"all_em:{num}"))
    builder.adjust(3)
    await callback.message.edit_text("Отлично!\n\nТеперь выберите <b>МЕСЯЦ ОКОНЧАНИЯ</b> периода:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("all_em:"))
async def all_ask_end_day(callback: types.CallbackQuery, state: FSMContext):
    month = int(callback.data.split(":")[1])
    await state.update_data(all_end_m=month)
    builder = InlineKeyboardBuilder()
    days_in_month = calendar.monthrange(get_poland_now().year, month)[1]
    for day in range(1, days_in_month + 1):
        builder.add(types.InlineKeyboardButton(text=str(day), callback_data=f"all_ed:{day}"))
    builder.adjust(5)
    await callback.message.edit_text(f"Месяц: {MONTHS_RU[month]}\nВыберите <b>ДЕНЬ ОКОНЧАНИЯ</b> периода:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("all_ed:"))
async def all_calculate(callback: types.CallbackQuery, state: FSMContext):
    end_d = int(callback.data.split(":")[1])
    data = await state.get_data()
    
    start_m, start_d = data.get("all_start_m"), data.get("all_start_d")
    end_m = data.get("all_end_m")
    year = get_poland_now().year

    # ✅ Проверка на отсутствие данных
    if not all([start_m, start_d, end_m]):
        await state.clear()
        try:
            return await callback.message.edit_text(
                "❌ Ошибка: потеряны данные выбора.\n\n"
                "Пожалуйста, нажми 'Общая статистика' заново и полностью пройди все шаги выбора."
            )
        except:
            pass  # Игнорируем ошибки редактирования

    try:
        start_date = datetime(year, start_m, start_d)
        end_date = datetime(year, end_m, end_d, 23, 59, 59)
    except (ValueError, TypeError):
        try:
            return await callback.message.edit_text("❌ Ошибка в датах. Начни заново.")
        except:
            pass  # Игнорируем ошибки редактирования

    if start_date > end_date:
        try:
            return await callback.message.edit_text("❌ Дата начала не может быть позже окончания! Нажми 'Общая статистика' заново.")
        except:
            pass  # Игнорируем ошибки редактирования

    total_sum = 0.0
    models_income = {acc["name"]: 0.0 for acc in ACCOUNTS}
    month_map = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

    for sale_id, t in LOCAL_DB.items():
        if t.get("type") != "transaction":
            continue

        try:
            parts = t["date"].replace(",", "").split()
            db_d = int(parts[0])
            db_m = month_map[parts[1]]
            db_y = int(parts[2])
            db_date = datetime(db_y, db_m, db_d)

            if start_date <= db_date <= end_date:
                amount = t["amount"]
                total_sum += amount
                
                for acc in ACCOUNTS:
                    target_acc = acc["name"].lower().replace("_", "")
                    db_acc = t["account"].lower().replace("_", "")
                    if target_acc in db_acc:
                        models_income[acc["name"]] += amount
                        break
        except:
            continue

    start_str = f"{start_d:02d} {MONTHS_RU[start_m]}"
    end_str = f"{end_d:02d} {MONTHS_RU[end_m]}"

    report = f"📈 <b>ОБЩАЯ СТАТИСТИКА ПО ВСЕМ МОДЕЛЯМ</b>\n"
    report += f"📅 Период: <b>{start_str} — {end_str}</b>\n"
    report += f"━━━━━━━━━━━━━━━━━━\n"
    report += f"💵 ОБЩАЯ КАССА: <b>${total_sum:.2f}</b>\n"
    report += f"━━━━━━━━━━━━━━━━━━\n\n"
    report += "<b>Разбивка по моделям:</b>\n"
    
    if total_sum == 0:
         report += "└ Нет транзакций за этот период.\n"
    else:
        for m_name, m_sum in models_income.items():
            report += f"🖥 {m_name}: <b>${m_sum:.2f}</b>\n"

    await state.clear()
    await callback.message.edit_text(report)


# ================= ПОСЛЕДНИЕ ТРАНЗАКЦИИ =================
@dp.message(F.text == "💰 Последние транзакции")
async def show_latest_transactions(message: types.Message):
    txs = [t for t in LOCAL_DB.values() if t.get("type") == "transaction"]
    if not txs:
        return await message.answer("📭 База транзакций пока пуста.")

    txs.sort(key=lambda t: parse_tx_date(t["date"]), reverse=True)
    latest_txs = txs[:15]

    report = "<b>💰 15 самых свежих транзакций:</b>\n\n"
    for t in latest_txs:
        report += f"📅 {t['date']} | 🖥 <b>{t['account'][:15]}...</b>\n└ <b>${t['amount']:.2f}</b> | 👨‍💻 {t['chatter']}\n\n"
    await message.answer(report)


@dp.message(F.text == "👤 Новые подписчики")
async def show_latest_followers(message: types.Message):
    # Показываем только Total подписчиков
    followers = [t for t in LOCAL_DB.values() if t.get("type") == "dashboard_fans" and t.get("account") == "TOTAL"]
    
    if not followers:
        return await message.answer("📭 Пока нет данных о подписчиках.")

    # Берем последнюю запись (самую свежую)
    followers.sort(key=lambda f: parse_tx_date(f.get("date", "")), reverse=True)
    latest = followers[0]

    report = "<b>👤 ВСЕГО ПОДПИСЧИКОВ</b>\n\n"
    report += f"👥 Текущий баланс: <b>{latest['count']}</b>\n"
    report += f"📅 Последнее обновление: <b>{latest['date']}</b>\n"

    await message.answer(report)

# ================= КАЛЬКУЛЯТОР ЗП ЧАТЕРОВ ЗА ПЕРИОД =================
@dp.message(F.text == "👥 ЗП чатеров")
async def zp_chatter_menu(message: types.Message, state: FSMContext):
    await state.clear()
    builder = InlineKeyboardBuilder()
    unique_chatters = list(set(CHATTERS.values()))
    
    for c in unique_chatters:
        builder.add(types.InlineKeyboardButton(text=f"👨‍💻 {c}", callback_data=f"zp_chatter:{c}"))
    builder.adjust(2) 
    
    builder.row(types.InlineKeyboardButton(text="⚡ Быстрый отчет за СЕГОДНЯ", callback_data="zp_today_all"))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    
    await message.answer("<b>Выберите чатера для расчета ЗП:</b>", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "zp_today_all")
async def zp_today_all(callback: types.CallbackQuery):
    now = get_poland_now()
    today_str = f"{now.day:02d} {MONTHS_EN[now.month]}"
    chatters_income = {}
    for sale_id, t in LOCAL_DB.items():
        if t.get("type") != "transaction":
            continue

        if today_str in t["date"]:
            chatters_income[t["chatter"]] = chatters_income.get(t["chatter"], 0) + t["amount"]

    report = "<b>👥 Доход чатеров за СЕГОДНЯ:</b>\n\n"
    if not chatters_income:
        report += "Парсер еще не увидел продаж за сегодня."
    else:
        for c_name, amount in sorted(chatters_income.items(), key=lambda x: x[1], reverse=True):
            report += f"👨‍💻 <b>{c_name}</b>: ${amount:.2f} (ЗП 20%: ${(amount*0.2):.2f})\n"
    await callback.message.edit_text(report)

@dp.callback_query(F.data.startswith("zp_chatter:"))
async def zp_ask_start_month(callback: types.CallbackQuery, state: FSMContext):
    chatter_name = callback.data.split(":")[1]
    await state.update_data(zp_chatter=chatter_name)

    builder = InlineKeyboardBuilder()
    for num, name in MONTHS_RU.items():
        builder.add(types.InlineKeyboardButton(text=name, callback_data=f"zp_sm:{num}"))
    builder.adjust(3)
    await callback.message.edit_text(f"👨‍💻 Чатер: <b>{chatter_name}</b>\n\nВыберите <b>МЕСЯЦ НАЧАЛА</b> периода:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("zp_sm:"))
async def zp_ask_start_day(callback: types.CallbackQuery, state: FSMContext):
    month = int(callback.data.split(":")[1])
    await state.update_data(zp_start_m=month)

    builder = InlineKeyboardBuilder()
    days_in_month = calendar.monthrange(get_poland_now().year, month)[1]
    for day in range(1, days_in_month + 1):
        builder.add(types.InlineKeyboardButton(text=str(day), callback_data=f"zp_sd:{day}"))
    builder.adjust(5)
    await callback.message.edit_text(f"Месяц: {MONTHS_RU[month]}\nВыберите <b>ДЕНЬ НАЧАЛА</b> периода:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("zp_sd:"))
async def zp_ask_end_month(callback: types.CallbackQuery, state: FSMContext):
    day = int(callback.data.split(":")[1])
    await state.update_data(zp_start_d=day)

    builder = InlineKeyboardBuilder()
    for num, name in MONTHS_RU.items():
        builder.add(types.InlineKeyboardButton(text=name, callback_data=f"zp_em:{num}"))
    builder.adjust(3)
    await callback.message.edit_text("Отлично!\n\nТеперь выберите <b>МЕСЯЦ ОКОНЧАНИЯ</b> периода:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("zp_em:"))
async def zp_ask_end_day(callback: types.CallbackQuery, state: FSMContext):
    month = int(callback.data.split(":")[1])
    await state.update_data(zp_end_m=month)

    builder = InlineKeyboardBuilder()
    days_in_month = calendar.monthrange(get_poland_now().year, month)[1]
    for day in range(1, days_in_month + 1):
        builder.add(types.InlineKeyboardButton(text=str(day), callback_data=f"zp_ed:{day}"))
    builder.adjust(5)
    await callback.message.edit_text(f"Месяц: {MONTHS_RU[month]}\nВыберите <b>ДЕНЬ ОКОНЧАНИЯ</b> периода:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("zp_ed:"))
async def zp_calculate(callback: types.CallbackQuery, state: FSMContext):
    end_d = int(callback.data.split(":")[1])
    data = await state.get_data()
    
    chatter_name = data.get("zp_chatter")
    start_m, start_d = data.get("zp_start_m"), data.get("zp_start_d")
    end_m = data.get("zp_end_m")
    year = get_poland_now().year

    # ✅ Проверка на отсутствие данных
    if not all([chatter_name, start_m, start_d, end_m]):
        await state.clear()
        try:
            return await callback.message.edit_text(
                "❌ Ошибка: потеряны данные выбора.\n\n"
                "Пожалуйста, нажми 'ЗП чатеров' заново и полностью пройди все шаги выбора."
            )
        except:
            pass  # Игнорируем ошибки редактирования сообщения

    try:
        start_date = datetime(year, start_m, start_d)
        end_date = datetime(year, end_m, end_d, 23, 59, 59)
    except (ValueError, TypeError) as e:
        try:
            return await callback.message.edit_text("❌ Ошибка в датах. Начни заново.")
        except:
            pass  # Игнорируем ошибки редактирования

    if start_date > end_date:
        return await callback.message.edit_text("❌ Дата начала не может быть позже окончания! Нажми 'ЗП чатеров' заново.")

    total_sum = 0.0
    month_map = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

    for sale_id, t in LOCAL_DB.items():
        if t.get("type") != "transaction":
            continue

        if t.get("chatter") != chatter_name:
            continue
            
        try:
            parts = t["date"].replace(",", "").split()
            db_d = int(parts[0])
            db_m = month_map[parts[1]]
            db_y = int(parts[2])
            db_date = datetime(db_y, db_m, db_d)

            if start_date <= db_date <= end_date:
                total_sum += t["amount"]
        except:
            continue

    salary = total_sum * 0.20 
    
    start_str = f"{start_d:02d} {MONTHS_RU[start_m]}"
    end_str = f"{end_d:02d} {MONTHS_RU[end_m]}"

    report = f"👨‍💻 <b>Расчет ЗП: {chatter_name}</b>\n"
    report += f"📅 Период: <b>{start_str} — {end_str}</b>\n"
    report += f"━━━━━━━━━━━━━━━━━━\n"
    report += f"💵 Общая касса: <b>${total_sum:.2f}</b>\n"
    report += f"💎 Процент (20%): <b>${salary:.2f}</b>\n"
    report += f"━━━━━━━━━━━━━━━━━━\n"

    await callback.message.answer(report)

# ================= ТРАНЗАКЦИИ ЗА ПЕРИОД =================
# Удален отдельный модуль "Транзакции за период" — теперь используется общий путь "🖥 Статистика" с выбором начальной и конечной даты.

@dp.callback_query(F.data.startswith("txp_sm:"))
async def txp_ask_start_day(callback: types.CallbackQuery, state: FSMContext):
    month = int(callback.data.split(":")[1])
    await state.update_data(txp_start_m=month)
    builder = InlineKeyboardBuilder()
    days_in_month = calendar.monthrange(get_poland_now().year, month)[1]
    for day in range(1, days_in_month + 1):
        builder.add(types.InlineKeyboardButton(text=str(day), callback_data=f"txp_sd:{day}"))
    builder.adjust(5)
    await callback.message.edit_text(f"Месяц: {MONTHS_RU[month]}\nВыберите <b>ДЕНЬ НАЧАЛА</b> периода:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("txp_sd:"))
async def txp_ask_end_month(callback: types.CallbackQuery, state: FSMContext):
    day = int(callback.data.split(":")[1])
    await state.update_data(txp_start_d=day)
    builder = InlineKeyboardBuilder()
    for num, name in MONTHS_RU.items():
        builder.add(types.InlineKeyboardButton(text=name, callback_data=f"txp_em:{num}"))
    builder.adjust(3)
    await callback.message.edit_text("Отлично!\n\nТеперь выберите <b>МЕСЯЦ ОКОНЧАНИЯ</b> периода:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("txp_em:"))
async def txp_ask_end_day(callback: types.CallbackQuery, state: FSMContext):
    month = int(callback.data.split(":")[1])
    await state.update_data(txp_end_m=month)
    builder = InlineKeyboardBuilder()
    days_in_month = calendar.monthrange(get_poland_now().year, month)[1]
    for day in range(1, days_in_month + 1):
        builder.add(types.InlineKeyboardButton(text=str(day), callback_data=f"txp_ed:{day}"))
    builder.adjust(5)
    await callback.message.edit_text(f"Месяц: {MONTHS_RU[month]}\nВыберите <b>ДЕНЬ ОКОНЧАНИЯ</b> периода:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("txp_ed:"))
async def txp_calculate(callback: types.CallbackQuery, state: FSMContext):
    end_d = int(callback.data.split(":")[1])
    data = await state.get_data()
    
    start_m, start_d = data.get("txp_start_m"), data.get("txp_start_d")
    end_m = data.get("txp_end_m")
    year = get_poland_now().year

    # ✅ Проверка на отсутствие данных
    if not all([start_m, start_d, end_m]):
        await state.clear()
        try:
            return await callback.message.edit_text(
                "❌ Ошибка: потеряны данные выбора.\n\n"
                "Пожалуйста, нажми 'Транзакции за период' заново и полностью пройди все шаги выбора."
            )
        except:
            pass  # Игнорируем ошибки редактирования

    try:
        start_date = datetime(year, start_m, start_d)
        end_date = datetime(year, end_m, end_d, 23, 59, 59)
    except (ValueError, TypeError):
        try:
            return await callback.message.edit_text("❌ Ошибка в датах. Начни заново.")
        except:
            pass  # Игнорируем ошибки редактирования

    if start_date > end_date:
        try:
            return await callback.message.edit_text("❌ Дата начала не может быть позже окончания! Нажми 'Транзакции за период' заново.")
        except:
            pass  # Игнорируем ошибки редактирования

    transactions = []
    total_sum = 0.0
    month_map = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

    for sale_id, t in LOCAL_DB.items():
        if t.get("type") != "transaction":
            continue
            
        try:
            parts = t["date"].replace(",", "").split()
            db_d = int(parts[0])
            db_m = month_map[parts[1]]
            db_y = int(parts[2])
            db_date = datetime(db_y, db_m, db_d)

            if start_date <= db_date <= end_date:
                transactions.append(t)
                total_sum += t["amount"]
        except:
            continue

    start_str = f"{start_d:02d} {MONTHS_RU[start_m]}"
    end_str = f"{end_d:02d} {MONTHS_RU[end_m]}"

    report = f"📅 <b>ТРАНЗАКЦИИ ЗА ПЕРИОД</b>\n"
    report += f"📅 Период: <b>{start_str} — {end_str}</b>\n"
    report += f"━━━━━━━━━━━━━━━━━━\n"
    report += f"💰 Всего транзакций: <b>{len(transactions)}</b>\n"
    report += f"💵 Общая сумма: <b>${total_sum:.2f}</b>\n"
    report += f"━━━━━━━━━━━━━━━━━━\n\n"
    
    if not transactions:
        report += "└ Нет транзакций за этот период.\n"
    else:
        # Группируем по аккаунтам
        by_account = {}
        for t in transactions:
            acc = t["account"]
            if acc not in by_account:
                by_account[acc] = []
            by_account[acc].append(t)
        
        for acc, txs in by_account.items():
            acc_sum = sum(t["amount"] for t in txs)
            report += f"🖥 <b>{acc}</b>: {len(txs)} шт (${acc_sum:.2f})\n"
            for t in txs[:5]:  # Показываем первые 5
                report += f"  └ ${t['amount']:.2f} | 👨‍💻 {t['chatter']} | 📅 {t['date']}\n"
            if len(txs) > 5:
                report += f"  └ ... и ещё {len(txs)-5} транзакций\n"
            report += "\n"

    await state.clear()
    await callback.message.edit_text(report)

# ================= КНОПКА РАЗРАБОТЧИКА =================
@dp.message(F.text == "⚙️ Разработчик")
async def show_developer_info(message: types.Message):
    # Диагностика: показать все даты и аккаунты в БД
    report = "<b>🔧 ДИАГНОСТИКА БД:</b>\n\n"
    
    # Группируем транзакции по месяцам
    txs = [t for t in LOCAL_DB.values() if t.get("type") == "transaction"]
    months_txs = {}
    
    for t in txs:
        try:
            parsed_date = parse_tx_date(t.get("date", ""))
            key = f"{parsed_date.year}-{parsed_date.month:02d}"
            if key not in months_txs:
                months_txs[key] = []
            months_txs[key].append(t)
        except:
            pass
    
    report += f"💾 <b>Транзакции по месяцам:</b>\n"
    for month_key in sorted(months_txs.keys(), reverse=True)[:12]:  # Последние 12 месяцев
        count = len(months_txs[month_key])
        total = sum(t.get("amount", 0) for t in months_txs[month_key])
        report += f"  • {month_key}: {count} шт (${total:.2f})\n"
    
    report += f"\n👥 <b>Подписчики:</b> {len([t for t in LOCAL_DB.values() if t.get('type') in ('follower', 'dashboard_fans')])}\n"
    report += f"📊 <b>Всего записей в БД:</b> {len(LOCAL_DB)}\n"
    report += f"\n💡 <i>Используй 'Экспорт месяца' для сохранения данных в JSON</i>"
    
    await message.answer(report)

async def main():
    loop = asyncio.get_running_loop()

    # 🔥 запускаем Selenium-парсер в отдельном потоке
    threading.Thread(target=run_parser, args=(loop,), daemon=True).start()

    # 🤖 запускаем Telegram-бота
    await dp.start_polling(bot)
if __name__ == "__main__":
    asyncio.run(main())
