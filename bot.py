import os
import time
import json
import random
from datetime import datetime, timedelta
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

TOKEN = os.environ["VK_TOKEN"]
GROUP_ID = int(os.environ["VK_GROUP_ID"])

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, group_id=GROUP_ID)

ROLES_FILE = "bot/roles.json"
STATS_FILE = "bot/stats.json"
WARNS_FILE = "bot/warns.json"
RULES_FILE = "bot/rules.txt"
EVENTS_FILE = "bot/events.json"
RIDDLES_FILE = "bot/riddles.json"
CROCODILE_WORDS_FILE = "bot/crocodile_words.json"
GARDEN_FILE = "bot/garden.json"  # НОВЫЙ ФАЙЛ

# ── Роли ──────────────────────────────────────────────────────────────────────

def load_roles():
    if os.path.exists(ROLES_FILE):
        with open(ROLES_FILE, "r", encoding="utf-8") as f:
            return {int(k): v for k, v in json.load(f).items()}
    return {}

def save_roles():
    with open(ROLES_FILE, "w", encoding="utf-8") as f:
        json.dump(roles, f, ensure_ascii=False)

ROLE_LIST = {
    1: "Младший модератор",
    2: "Модератор",
    3: "Старший модератор",
    4: "Куратор",
    5: "Зам главного модератора",
    6: "Главный модератор",
    7: "Руководитель Вселенной",
}
ADMIN_ROLES = {5, 6, 7}

# Минимальный уровень роли для каждой команды
CMD_MIN_ROLE = {
    "!пред":          1,
    "!разпред":       1,
    "!мут":           1,
    "!размут":        1,
    "!кик":           2,
    "!бан":           3,
    "!повыс":         4,
    "!пониз":         4,
    "!мероприятия":   4,
    "!роль":          5,
    "!разроль":       5,
}

def role_level(user_id):
    """Возвращает числовой уровень роли пользователя (0 — нет роли)."""
    role_name = roles.get(user_id)
    if not role_name:
        return 0
    return next((k for k, v in ROLE_LIST.items() if v == role_name), 0)

def has_perm(user_id, cmd):
    """True, если у пользователя достаточно прав для команды."""
    min_lvl = CMD_MIN_ROLE.get(cmd, 99)
    return role_level(user_id) >= min_lvl

# ── Загадки ──────────────────────────────────────────────────────────────────

def load_riddles():
    if os.path.exists(RIDDLES_FILE):
        with open(RIDDLES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# active_riddle[peer_id] = {"q": ..., "a": ...}
active_riddle = {}

def load_crocodile_words():
    if os.path.exists(CROCODILE_WORDS_FILE):
        with open(CROCODILE_WORDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# active_crocodile[peer_id] = {"word": ..., "leader": user_id}
active_crocodile = {}

# ── Мероприятия ──────────────────────────────────────────────────────────────

def load_events():
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_events():
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False)

# ── Предупреждения ────────────────────────────────────────────────────────────

def load_warns():
    if os.path.exists(WARNS_FILE):
        with open(WARNS_FILE, "r", encoding="utf-8") as f:
            return {int(k): v for k, v in json.load(f).items()}
    return {}

def save_warns():
    with open(WARNS_FILE, "w", encoding="utf-8") as f:
        json.dump(warns, f, ensure_ascii=False)

# ── Статистика сообщений ──────────────────────────────────────────────────────
# Структура: { "user_id": { "2026-07-11": 5, "2026-07-10": 12, ... } }

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return {int(k): v for k, v in json.load(f).items()}
    return {}

def save_stats():
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False)

def record_message(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id not in stats:
        stats[user_id] = {}
    stats[user_id][today] = stats[user_id].get(today, 0) + 1
    save_stats()

def get_top(days):
    """Собрать топ за последние `days` дней. Возвращает список (user_id, count)."""
    if days == 1:
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        cutoff = datetime.now() - timedelta(days=days)
    totals = {}
    for uid, daily in stats.items():
        total = 0
        for date_str, count in daily.items():
            try:
                if datetime.strptime(date_str, "%Y-%m-%d") >= cutoff:
                    total += count
            except ValueError:
                pass
        if total > 0:
            totals[uid] = total
    return sorted(totals.items(), key=lambda x: x[1], reverse=True)[:10]

def format_top(top_list, period_label):
    if not top_list:
        return f"📊 Топ {period_label}: пока нет данных."

    user_ids = [uid for uid, _ in top_list]
    try:
        users_info = vk.users.get(user_ids=user_ids, fields="first_name,last_name")
        names = {u["id"]: f"{u['first_name']} {u['last_name']}" for u in users_info}
    except Exception:
        names = {}

    medals = ["🥇", "🥈", "🥉"]
    lines = [f"📊 Топ сообщений ({period_label}):"]
    for i, (uid, count) in enumerate(top_list):
        prefix = medals[i] if i < 3 else f"{i + 1}."
        name = names.get(uid, f"id{uid}")
        lines.append(f"{prefix} {name} — {count} сообщ.")
    return "\n".join(lines)

# ── Огород ────────────────────────────────────────────────────────────────────

# Конфигурация растений
PLANTS = {
    "морковь": {
        "seed_cost": 10,
        "sell_price": 20,
        "stages": 4,  # 0-посажено, 1-росток, 2-зелень, 3-урожай
        "grow_time": 3600,  # секунд на полный рост (1 час)
        "emoji": ["🌱", "🌿", "🥕"],
        "water_bonus": 0.3,  # ускорение при поливе
    },
    "помидор": {
        "seed_cost": 15,
        "sell_price": 30,
        "stages": 4,
        "grow_time": 5400,  # 1.5 часа
        "emoji": ["🌱", "🌿", "🍅"],
        "water_bonus": 0.3,
    },
    "огурец": {
        "seed_cost": 12,
        "sell_price": 25,
        "stages": 4,
        "grow_time": 4500,  # 1.25 часа
        "emoji": ["🌱", "🌿", "🥒"],
        "water_bonus": 0.3,
    },
    "клубника": {
        "seed_cost": 20,
        "sell_price": 40,
        "stages": 4,
        "grow_time": 7200,  # 2 часа
        "emoji": ["🌱", "🌿", "🍓"],
        "water_bonus": 0.3,
    },
}

def load_garden():
    if os.path.exists(GARDEN_FILE):
        with open(GARDEN_FILE, "r", encoding="utf-8") as f:
            return {int(k): v for k, v in json.load(f).items()}
    return {}

def save_garden():
    with open(GARDEN_FILE, "w", encoding="utf-8") as f:
        json.dump(garden, f, ensure_ascii=False)

def init_garden(user_id):
    """Создать огород для нового игрока."""
    if user_id not in garden:
        garden[user_id] = {
            "cells": [None] * 6,
            "coins": 50,  # стартовый капитал
            "inventory": {},
            "last_check": int(time.time())
        }
        save_garden()

def get_plant_stage(cell, current_time):
    """Рассчитать текущую стадию растения с учётом времени."""
    if cell is None:
        return None

    plant = cell["plant"]
    planted_at = cell["planted_at"]
    grow_time = PLANTS[plant]["grow_time"]
    water_bonus = 1.0
    if cell.get("watered", False):
        water_bonus = 1.0 - PLANTS[plant]["water_bonus"]

    elapsed = (current_time - planted_at) / (grow_time * water_bonus)
    stage = min(int(elapsed), PLANTS[plant]["stages"] - 1)
    return stage

def format_garden(user_id):
    """Вернуть красивую строку с состоянием огорода."""
    init_garden(user_id)
    data = garden[user_id]
    cells = data["cells"]
    coins = data["coins"]

    current_time = int(time.time())
    lines = [f"🌻 **Огород** | Монет: {coins} 💰\n"]
    lines.append("```")

    emojis = []
    for i, cell in enumerate(cells, 1):
        if cell is None:
            emojis.append(f"{i}. ⬜ пусто")
        else:
            plant = cell["plant"]
            stage = get_plant_stage(cell, current_time)
            max_stage = PLANTS[plant]["stages"] - 1

            if stage >= max_stage:
                emoji = "✅ " + PLANTS[plant]["emoji"][-1] + " ГОТОВО!"
            else:
                emoji = PLANTS[plant]["emoji"][stage] if stage < len(PLANTS[plant]["emoji"]) else "🌱"
                progress = "█" * (stage + 1) + "░" * (max_stage - stage - 1)
                emoji += f" {progress}"

            watered = "💧" if cell.get("watered", False) else ""
            emojis.append(f"{i}. {emoji} {plant} {watered}")

    lines.extend(emojis)
    lines.append("```")
    lines.append("\n📋 **Команды огорода:**")
    lines.append("!огород — посмотреть огород")
    lines.append("!посадить <клетка> <растение> — посадить (клетка 1-6)")
    lines.append("!полить <клетка> — полить растение")
    lines.append("!собрать <клетка> — собрать урожай")
    lines.append("!магазин — купить семена")
    lines.append("!купить <растение> <кол-во> — купить семена")
    lines.append("!инвентарь — посмотреть инвентарь")

    return "\n".join(lines)

# ── Инициализация ─────────────────────────────────────────────────────────────

muted = {}
roles = load_roles()
stats = load_stats()
warns = load_warns()
events = load_events()
riddles = load_riddles()
crocodile_words = load_crocodile_words()
garden = load_garden()  # НОВАЯ ИНИЦИАЛИЗАЦИЯ

print("Бот-модератор (группа) запущен!", flush=True)

# ── Основной цикл ─────────────────────────────────────────────────────────────

for event in longpoll.listen():
  try:
    if event.type == VkBotEventType.MESSAGE_NEW:
        msg = event.obj.message
        chat_id = msg.get('peer_id')
        user_id = msg.get('from_id')
        text = msg.get('text', '').lower().strip()
        message_id = msg.get('id')
        print(f"[MSG] peer={chat_id} user={user_id} text={text!r}", flush=True)

        # Работаем только с беседами (peer_id > 2000000000)
        if not chat_id or chat_id <= 2000000000:
            continue

        # --- МУТ: удаление сообщений заглушенных ---
        if user_id in muted:
            if time.time() < muted[user_id]:
                try:
                    vk.messages.delete(message_ids=[message_id], delete_for_all=1)
                except Exception:
                    pass
                continue
            else:
                del muted[user_id]

        # --- Считаем все сообщения участников (кроме самого бота) ---
        if user_id and user_id > 0 and user_id != -GROUP_ID:  # ИСПРАВЛЕНО
            record_message(user_id)

        # --- Проверка ответа на загадку ---
        if chat_id in active_riddle and not text.startswith("!"):
            correct = active_riddle[chat_id]["a"].lower().strip()
            if text.lower().strip() == correct:
                riddle_ans = active_riddle.pop(chat_id)["a"]
                try:
                    user_info = vk.users.get(user_ids=[user_id])
                    name = user_info[0]["first_name"]
                except Exception:
                    name = f"id{user_id}"
                vk.messages.send(peer_id=chat_id, message=f"🎉 {name} угадал(а)! Правильный ответ: {riddle_ans}", random_id=get_random_id())

        # --- Игра «Крокодил» ---
        if chat_id in active_crocodile and not text.startswith("!"):
            game = active_crocodile[chat_id]
            if user_id != game["leader"] and text.strip().lower() == game["word"].lower():  # ИСПРАВЛЕНО
                active_crocodile.pop(chat_id)
                try:
                    user_info = vk.users.get(user_ids=[user_id, game["leader"]])
                    winner_name = user_info[0]["first_name"]
                    leader_name = user_info[1]["first_name"] if len(user_info) > 1 else f"id{game['leader']}"
                except Exception:
                    winner_name = f"id{user_id}"
                    leader_name = f"id{game['leader']}"
                vk.messages.send(
                    peer_id=chat_id,
                    message=f"🎉 [id{user_id}|{winner_name}] угадал(а) слово «{game['word']}»! "
                            f"Ведущим был(а) [id{game['leader']}|{leader_name}].",
                    random_id=get_random_id()
                )

        # --- КОМАНДЫ ---
        if text == "!помощь":
            lvl = role_level(user_id)
            role_name = roles.get(user_id, "нет роли")

            header = f"👤 Ваша роль: {role_name}\n\n📋 Доступные команды:"

            general_lines = [
                "\n🎮 Развлечения:",
                "!крокодил — начать игру с ведущим и секретным словом",
                "!крокодил стоп — остановить текущую игру",
                "!загадка / !загадка ответ — загадка и ответ",
                "!браки, !переспать — случайные истории",
                "!обнять, !укусить, !пнуть — действие над участником",
                "!правила — правила беседы",
                "!мероприятия — список мероприятий",
                "!мояроль — ваша роль",
                "!топ день / !топ неделя — статистика активности",
                "\n🌱 Огород:",
                "!огород — посмотреть огород",
                "!посадить <клетка> <растение> — посадить",
                "!полить <клетка> — полить",
                "!собрать <клетка> — собрать урожай",
                "!магазин — купить семена",
                "!купить <растение> <кол-во> — купить семена",
                "!инвентарь — посмотреть инвентарь",
            ]

            mod_lines = []
            if lvl >= 1:
                mod_lines.append(f"\n🛡 [{ROLE_LIST[1]}+]")
                mod_lines.append("!пред / !разпред — предупреждение (ответом)")
                mod_lines.append("!мут N / !размут — мут на N мин (ответом)")
            if lvl >= 2:
                mod_lines.append(f"\n🛡 [{ROLE_LIST[2]}+]")
                mod_lines.append("!кик — исключить (ответом)")
            if lvl >= 3:
                mod_lines.append("!бан — исключить + бан (ответом)")
            if lvl >= 4:
                mod_lines.append(f"\n🛡 [{ROLE_LIST[4]}+]")
                mod_lines.append("!повыс / !пониз — изменить ступень (ответом)")
                mod_lines.append("!мероприятия добавить/удалить/очистить")
            if lvl >= 5:
                mod_lines.append(f"\n🛡 [{ROLE_LIST[5]}+]")
                mod_lines.append("!роль N / !разроль — выдать/снять роль (ответом)")

            full_text = header + "\n" + "\n".join(general_lines)
            if mod_lines:
                full_text += "\n" + "\n".join(mod_lines)
            vk.messages.send(peer_id=chat_id, message=full_text, random_id=get_random_id())

        elif text == "!огород":
            vk.messages.send(peer_id=chat_id, message=format_garden(user_id), random_id=get_random_id())

        elif text == "!магазин":
            shop_lines = ["🛒 Магазин семян:"]
            for plant_name, plant_data in PLANTS.items():
                shop_lines.append(
                    f"🌱 {plant_name} — {plant_data['seed_cost']} 💰 "
                    f"(урожай: {plant_data['sell_price']} 💰)"
                )
            shop_lines.append("\nКупить: !купить <растение> <количество>")
            vk.messages.send(peer_id=chat_id, message="\n".join(shop_lines), random_id=get_random_id())

        elif text == "!инвентарь":
            init_garden(user_id)
            player = garden[user_id]
            inventory_lines = [
                f"🌱 {plant}: {count} шт."
                for plant, count in player["inventory"].items()
                if count > 0
            ]
            inventory_text = "\n".join(inventory_lines) if inventory_lines else "Пусто"
            vk.messages.send(
                peer_id=chat_id,
                message=f"🎒 Инвентарь семян:\n{inventory_text}\n💰 Монет: {player['coins']}",
                random_id=get_random_id()
            )

        elif text.startswith("!купить"):
            parts = text.split()
            if len(parts) != 3 or parts[1] not in PLANTS or not parts[2].isdigit():
                vk.messages.send(
                    peer_id=chat_id,
                    message="ℹ️ Формат: !купить <растение> <количество>\n"
                            "Пример: !купить морковь 3\n"
                            f"Растения: {', '.join(PLANTS)}",
                    random_id=get_random_id()
                )
            else:
                plant_name = parts[1]
                quantity = int(parts[2])
                init_garden(user_id)
                player = garden[user_id]
                if not 1 <= quantity <= 99:
                    vk.messages.send(peer_id=chat_id, message="❌ Количество должно быть от 1 до 99.", random_id=get_random_id())
                else:
                    total_cost = PLANTS[plant_name]["seed_cost"] * quantity
                    if player["coins"] < total_cost:
                        vk.messages.send(
                            peer_id=chat_id,
                            message=f"❌ Недостаточно монет. Нужно {total_cost} 💰, у вас {player['coins']} 💰.",
                            random_id=get_random_id()
                        )
                    else:
                        player["coins"] -= total_cost
                        player["inventory"][plant_name] = player["inventory"].get(plant_name, 0) + quantity
                        save_garden()
                        vk.messages.send(
                            peer_id=chat_id,
                            message=f"✅ Куплено семян: {plant_name} ×{quantity}. Осталось {player['coins']} 💰.",
                            random_id=get_random_id()
                        )

        elif text.startswith("!посадить"):
            parts = text.split()
            if len(parts) != 3 or not parts[1].isdigit() or parts[2] not in PLANTS:
                vk.messages.send(
                    peer_id=chat_id,
                    message="ℹ️ Формат: !посадить <клетка> <растение>\n"
                            "Пример: !посадить 1 морковь\n"
                            f"Растения: {', '.join(PLANTS)}",
                    random_id=get_random_id()
                )
            else:
                cell_number = int(parts[1])
                plant_name = parts[2]
                init_garden(user_id)
                player = garden[user_id]
                if not 1 <= cell_number <= len(player["cells"]):
                    vk.messages.send(peer_id=chat_id, message="❌ Номер клетки должен быть от 1 до 6.", random_id=get_random_id())
                elif player["cells"][cell_number - 1] is not None:
                    vk.messages.send(peer_id=chat_id, message="❌ Эта клетка уже занята.", random_id=get_random_id())
                elif player["inventory"].get(plant_name, 0) <= 0:
                    vk.messages.send(
                        peer_id=chat_id,
                        message=f"❌ Нет семян «{plant_name}». Купите их командой !купить {plant_name} 1.",
                        random_id=get_random_id()
                    )
                else:
                    player["inventory"][plant_name] -= 1
                    player["cells"][cell_number - 1] = {
                        "plant": plant_name,
                        "planted_at": int(time.time()),
                        "watered": False,
                    }
                    save_garden()
                    vk.messages.send(
                        peer_id=chat_id,
                        message=f"🌱 «{plant_name}» посажен в клетку {cell_number}.",
                        random_id=get_random_id()
                    )

        elif text.startswith("!полить"):
            parts = text.split()
            if len(parts) != 2 or not parts[1].isdigit():
                vk.messages.send(peer_id=chat_id, message="ℹ️ Формат: !полить <клетка>", random_id=get_random_id())
            else:
                cell_number = int(parts[1])
                init_garden(user_id)
                player = garden[user_id]
                if not 1 <= cell_number <= len(player["cells"]):
                    vk.messages.send(peer_id=chat_id, message="❌ Номер клетки должен быть от 1 до 6.", random_id=get_random_id())
                elif player["cells"][cell_number - 1] is None:
                    vk.messages.send(peer_id=chat_id, message="❌ Эта клетка пустая.", random_id=get_random_id())
                else:
                    cell = player["cells"][cell_number - 1]
                    plant_name = cell["plant"]
                    if get_plant_stage(cell, int(time.time())) >= PLANTS[plant_name]["stages"] - 1:
                        vk.messages.send(peer_id=chat_id, message="✅ Урожай уже созрел — его можно собрать.", random_id=get_random_id())
                    elif cell.get("watered", False):
                        vk.messages.send(peer_id=chat_id, message="💧 Вы уже полили это растение.", random_id=get_random_id())
                    else:
                        cell["watered"] = True
                        save_garden()
                        vk.messages.send(
                            peer_id=chat_id,
                            message=f"💧 «{plant_name}» в клетке {cell_number} полит. Рост ускорен на 30%.",
                            random_id=get_random_id()
                        )

        elif text.startswith("!собрать"):
            parts = text.split()
            if len(parts) != 2 or not parts[1].isdigit():
                vk.messages.send(peer_id=chat_id, message="ℹ️ Формат: !собрать <клетка>", random_id=get_random_id())
            else:
                cell_number = int(parts[1])
                init_garden(user_id)
                player = garden[user_id]
                if not 1 <= cell_number <= len(player["cells"]):
                    vk.messages.send(peer_id=chat_id, message="❌ Номер клетки должен быть от 1 до 6.", random_id=get_random_id())
                elif player["cells"][cell_number - 1] is None:
                    vk.messages.send(peer_id=chat_id, message="❌ Эта клетка пустая.", random_id=get_random_id())
                else:
                    cell = player["cells"][cell_number - 1]
                    plant_name = cell["plant"]
                    if get_plant_stage(cell, int(time.time())) < PLANTS[plant_name]["stages"] - 1:
                        vk.messages.send(peer_id=chat_id, message="⏳ Растение ещё не созрело.", random_id=get_random_id())
                    else:
                        reward = PLANTS[plant_name]["sell_price"]
                        player["coins"] += reward
                        player["cells"][cell_number - 1] = None
                        save_garden()
                        vk.messages.send(
                            peer_id=chat_id,
                            message=f"🎉 Урожай «{plant_name}» собран! Вы получили {reward} 💰.",
                            random_id=get_random_id()
                        )

        elif text == "!крокодил" or text.startswith("!крокодил "):
            subcommand = text[len("!крокодил"):].strip()

            if subcommand in ("стоп", "stop"):
                if active_crocodile.pop(chat_id, None):
                    vk.messages.send(peer_id=chat_id, message="🛑 Игра «Крокодил» остановлена.", random_id=get_random_id())
                else:
                    vk.messages.send(peer_id=chat_id, message="ℹ️ В этой беседе сейчас нет игры.", random_id=get_random_id())
            elif chat_id in active_crocodile:
                game = active_crocodile[chat_id]
                vk.messages.send(
                    peer_id=chat_id,
                    message=f"🐊 Игра уже идёт! Ведущий: [id{game['leader']}|ведущий]. "
                            "Попробуйте угадать слово.",
                    random_id=get_random_id()
                )
            elif not crocodile_words:
                vk.messages.send(peer_id=chat_id, message="❌ Список слов для игры пуст.", random_id=get_random_id())
            else:
                try:
                    members_data = vk.messages.getConversationMembers(peer_id=chat_id)
                    member_ids = [
                        member["member_id"]
                        for member in members_data.get("items", [])
                        if member["member_id"] > 0
                    ]
                    if len(member_ids) < 2:
                        vk.messages.send(peer_id=chat_id, message="😢 Для игры нужно минимум два участника.", random_id=get_random_id())
                    else:
                        random.shuffle(member_ids)
                        started = False

                        # Пробуем участников по очереди: часть пользователей
                        # может запретить сообщения от сообщества.
                        for candidate_id in member_ids:
                            word = random.choice(crocodile_words).lower()
                            try:
                                vk.messages.send(
                                    user_id=candidate_id,
                                    message=f"🐊 Вы ведущий в игре «Крокодил»!\n\nВаше слово: «{word}»\n"
                                            "Покажите его жестами или опишите без однокоренных слов. "
                                            "Не отправляйте слово в беседу.",
                                    random_id=get_random_id()
                                )
                            except Exception:
                                continue

                            leader_id = candidate_id
                            active_crocodile[chat_id] = {"word": word, "leader": leader_id}
                            try:
                                leader_info = vk.users.get(user_ids=[leader_id])
                                leader_name = leader_info[0]["first_name"]
                            except Exception:
                                leader_name = f"id{leader_id}"
                            vk.messages.send(
                                peer_id=chat_id,
                                message=f"🐊 Начинаем «Крокодила»! Ведущий: [id{leader_id}|{leader_name}]. "
                                        "Он получил секретное слово в личные сообщения. Угадывайте!",
                                random_id=get_random_id()
                            )
                            started = True
                            break

                        if not started:
                            vk.messages.send(
                                peer_id=chat_id,
                                message="❌ Не нашёл участника, который разрешил сообщения от сообщества. "
                                        "Откройте страницу группы, нажмите «Написать сообщение» и разрешите сообщения, "
                                        "затем повторите !крокодил.",
                                random_id=get_random_id()
                            )
                except Exception as e:
                    vk.messages.send(
                        peer_id=chat_id,
                        message=f"❌ Не удалось получить участников беседы: {e}",
                        random_id=get_random_id()
                    )

        elif text.startswith("!кик"):
            if not has_perm(user_id, "!кик"):
                vk.messages.send(peer_id=chat_id, message=f"⛔ Нет прав. Нужна роль: {ROLE_LIST[CMD_MIN_ROLE['!кик']]} или выше.", random_id=get_random_id())
            elif 'reply_message' in msg:
                target = msg['reply_message']['from_id']
                if target == -GROUP_ID:
                    vk.messages.send(peer_id=chat_id, message="⛔ Нельзя кикнуть бота.", random_id=get_random_id())
                else:
                    try:
                        local_chat_id = chat_id - 2000000000
                        vk.messages.removeChatUser(chat_id=local_chat_id, user_id=target)
                        vk.messages.send(peer_id=chat_id, message="✅ Пользователь исключён.", random_id=get_random_id())
                    except Exception as e:
                        vk.messages.send(peer_id=chat_id, message=f"❌ Ошибка: {e}", random_id=get_random_id())
            else:
                vk.messages.send(peer_id=chat_id, message="ℹ️ Ответьте на сообщение нарушителя командой !кик", random_id=get_random_id())

        elif text.startswith("!бан"):
            if not has_perm(user_id, "!бан"):
                vk.messages.send(peer_id=chat_id, message=f"⛔ Нет прав. Нужна роль: {ROLE_LIST[CMD_MIN_ROLE['!бан']]} или выше.", random_id=get_random_id())
            elif 'reply_message' in msg:
                target = msg['reply_message']['from_id']
                if target == -GROUP_ID:
                    vk.messages.send(peer_id=chat_id, message="⛔ Нельзя забанить бота.", random_id=get_random_id())
                else:
                    kicked = False
                    ban_err = None
                    # Исключаем из беседы
                    try:
                        local_chat_id = chat_id - 2000000000
                        vk.messages.removeChatUser(chat_id=local_chat_id, member_id=target)
                        kicked = True
                    except Exception as e:
                        ban_err = str(e)
                    # Баним в группе (отдельно, чтобы ошибка не мешала кику)
                    try:
                        vk.groups.ban(group_id=GROUP_ID, owner_id=target)
                    except Exception:
                        pass
                    if kicked:
                        vk.messages.send(peer_id=chat_id, message="🚫 Пользователь исключён из беседы и заблокирован в группе.", random_id=get_random_id())
                    else:
                        vk.messages.send(peer_id=chat_id, message=f"❌ Не удалось исключить: {ban_err}", random_id=get_random_id())
            else:
                vk.messages.send(peer_id=chat_id, message="ℹ️ Ответьте на сообщение нарушителя командой !бан", random_id=get_random_id())

        elif text.startswith("!мут"):
            if not has_perm(user_id, "!мут"):
                vk.messages.send(peer_id=chat_id, message=f"⛔ Нет прав. Нужна роль: {ROLE_LIST[CMD_MIN_ROLE['!мут']]} или выше.", random_id=get_random_id())
            elif 'reply_message' in msg:
                target = msg['reply_message']['from_id']
                if target == -GROUP_ID:
                    vk.messages.send(peer_id=chat_id, message="⛔ Нельзя замутить бота.", random_id=get_random_id())
                else:
                    parts = text.split()
                    try:
                        minutes = int(parts[1]) if len(parts) > 1 else 10
                    except ValueError:
                        minutes = 10
                    end_ts = time.time() + minutes * 60
                    muted[target] = end_ts
                    # Пробуем нативный мут VK, если нет — работает удаление сообщений
                    try:
                        vk.messages.setMemberRestrictions(peer_id=chat_id, member_id=target, mute=1, end_time=int(end_ts))
                    except Exception:
                        pass
                    vk.messages.send(peer_id=chat_id, message=f"🔇 Пользователь заглушен на {minutes} мин.", random_id=get_random_id())
            else:
                vk.messages.send(peer_id=chat_id, message="ℹ️ Ответьте на сообщение командой !мут <минуты>", random_id=get_random_id())

        elif text.startswith("!размут"):
            if not has_perm(user_id, "!размут"):
                vk.messages.send(peer_id=chat_id, message=f"⛔ Нет прав. Нужна роль: {ROLE_LIST[CMD_MIN_ROLE['!размут']]} или выше.", random_id=get_random_id())
            elif 'reply_message' in msg:
                target = msg['reply_message']['from_id']
                muted.pop(target, None)
                try:
                    vk.messages.setMemberRestrictions(peer_id=chat_id, member_id=target, mute=0)
                except Exception:
                    pass
                vk.messages.send(peer_id=chat_id, message="🔊 Мут снят.", random_id=get_random_id())
            else:
                vk.messages.send(peer_id=chat_id, message="ℹ️ Ответьте на сообщение командой !размут", random_id=get_random_id())

        elif text == "!мояроль":
            my_role = roles.get(user_id)
            if my_role:
                vk.messages.send(peer_id=chat_id, message=f"👤 Ваша роль: {my_role}", random_id=get_random_id())
            else:
                vk.messages.send(peer_id=chat_id, message="ℹ️ У вас нет роли.", random_id=get_random_id())

        elif text.startswith("!роль"):
            if not has_perm(user_id, "!роль"):
                vk.messages.send(peer_id=chat_id, message=f"⛔ Нет прав. Нужна роль: {ROLE_LIST[CMD_MIN_ROLE['!роль']]} или выше.", random_id=get_random_id())
            elif 'reply_message' in msg:
                target = msg['reply_message']['from_id']
                if target == -GROUP_ID:
                    vk.messages.send(peer_id=chat_id, message="⛔ Нельзя изменить роль бота.", random_id=get_random_id())
                else:
                    parts = text.split()
                    if len(parts) < 2 or not parts[1].isdigit():
                        vk.messages.send(peer_id=chat_id, message="ℹ️ Укажите номер роли: !роль 1–7\n1 — Младший модератор\n2 — Модератор\n3 — Старший модератор\n4 — Куратор\n5 — Зам главного модератора\n6 — Главный модератор\n7 — Руководитель Вселенной", random_id=get_random_id())
                    else:
                        role_num = int(parts[1])
                        if role_num not in ROLE_LIST:
                            vk.messages.send(peer_id=chat_id, message="❌ Номер роли должен быть от 1 до 7.", random_id=get_random_id())  # ИСПРАВЛЕНО
                        else:
                            role_name = ROLE_LIST[role_num]
                            roles[target] = role_name
                            save_roles()
                            if role_num in ADMIN_ROLES:
                                try:
                                    vk.messages.setMemberRole(peer_id=chat_id, member_id=target, role="admin")
                                except Exception:
                                    pass
                            else:
                                try:
                                    vk.messages.setMemberRole(peer_id=chat_id, member_id=target, role="member")
                                except Exception:
                                    pass
                            vk.messages.send(peer_id=chat_id, message=f"✅ Роль выдана: {role_name}", random_id=get_random_id())
            else:
                vk.messages.send(peer_id=chat_id, message="ℹ️ Ответьте на сообщение пользователя командой !роль N (где N — номер от 1 до 7)", random_id=get_random_id())  # ИСПРАВЛЕНО

        elif text.startswith("!разроль"):
            if not has_perm(user_id, "!разроль"):
                vk.messages.send(peer_id=chat_id, message=f"⛔ Нет прав. Нужна роль: {ROLE_LIST[CMD_MIN_ROLE['!разроль']]} или выше.", random_id=get_random_id())
            elif 'reply_message' in msg:
                target = msg['reply_message']['from_id']
                if target == -GROUP_ID:
                    vk.messages.send(peer_id=chat_id, message="⛔ Нельзя изменить роль бота.", random_id=get_random_id())
                else:
                    old_role = roles.pop(target, None)
                    save_roles()
                    try:
                        vk.messages.setMemberRole(peer_id=chat_id, member_id=target, role="member")
                    except Exception:
                        pass
                    if old_role:
                        vk.messages.send(peer_id=chat_id, message=f"🔽 Роль «{old_role}» снята.", random_id=get_random_id())
                    else:
                        vk.messages.send(peer_id=chat_id, message="ℹ️ У пользователя не было роли.", random_id=get_random_id())
            else:
                vk.messages.send(peer_id=chat_id, message="ℹ️ Ответьте на сообщение пользователя командой !разроль", random_id=get_random_id())

        elif text.startswith("!пред"):
            if not has_perm(user_id, "!пред"):
                vk.messages.send(peer_id=chat_id, message=f"⛔ Нет прав. Нужна роль: {ROLE_LIST[CMD_MIN_ROLE['!пред']]} или выше.", random_id=get_random_id())
            elif 'reply_message' in msg:
                target = msg['reply_message']['from_id']
                if target == -GROUP_ID:
                    vk.messages.send(peer_id=chat_id, message="⛔ Нельзя выдать предупреждение боту.", random_id=get_random_id())
                else:
                    count = warns.get(target, 0) + 1
                    warns[target] = count
                    save_warns()
                    vk.messages.send(peer_id=chat_id, message=f"⚠️ Предупреждение выдано! ({count}/3)\n{'🔇 Автомут на 10 мин за 3 предупреждения!' if count >= 3 else ''}", random_id=get_random_id())
                    if count >= 3:
                        warns[target] = 0
                        save_warns()
                        end_ts = time.time() + 10 * 60
                        muted[target] = end_ts
                        try:
                            vk.messages.setMemberRestrictions(peer_id=chat_id, member_id=target, mute=1, end_time=int(end_ts))
                        except Exception:
                            pass
            else:
                vk.messages.send(peer_id=chat_id, message="ℹ️ Ответьте на сообщение нарушителя командой !пред", random_id=get_random_id())

        elif text.startswith("!разпред"):
            if not has_perm(user_id, "!разпред"):
                vk.messages.send(peer_id=chat_id, message=f"⛔ Нет прав. Нужна роль: {ROLE_LIST[CMD_MIN_ROLE['!разпред']]} или выше.", random_id=get_random_id())
            elif 'reply_message' in msg:
                target = msg['reply_message']['from_id']
                count = warns.get(target, 0)
                if count == 0:
                    vk.messages.send(peer_id=chat_id, message="ℹ️ У пользователя нет предупреждений.", random_id=get_random_id())
                else:
                    warns[target] = count - 1
                    save_warns()
                    vk.messages.send(peer_id=chat_id, message=f"✅ Предупреждение снято. Осталось: {count - 1}/3", random_id=get_random_id())
            else:
                vk.messages.send(peer_id=chat_id, message="ℹ️ Ответьте на сообщение пользователя командой !разпред", random_id=get_random_id())

        elif text.startswith("!повыс"):
            if not has_perm(user_id, "!повыс"):
                vk.messages.send(peer_id=chat_id, message=f"⛔ Нет прав. Нужна роль: {ROLE_LIST[CMD_MIN_ROLE['!повыс']]} или выше.", random_id=get_random_id())
            elif 'reply_message' in msg:
                target = msg['reply_message']['from_id']
                if target == -GROUP_ID:
                    vk.messages.send(peer_id=chat_id, message="⛔ Нельзя изменить роль бота.", random_id=get_random_id())
                else:
                    current_role = roles.get(target)
                    current_num = next((k for k, v in ROLE_LIST.items() if v == current_role), 0)
                    if current_num >= 7:
                        vk.messages.send(peer_id=chat_id, message="⛔ Выше некуда — уже Руководитель Вселенной.", random_id=get_random_id())
                    else:
                        new_num = current_num + 1
                        new_role = ROLE_LIST[new_num]
                        roles[target] = new_role
                        save_roles()
                        if new_num in ADMIN_ROLES:
                            try:
                                vk.messages.setMemberRole(peer_id=chat_id, member_id=target, role="admin")
                            except Exception:
                                pass
                        else:
                            try:
                                vk.messages.setMemberRole(peer_id=chat_id, member_id=target, role="member")
                            except Exception:
                                pass
                        old_label = f"«{current_role}»" if current_role else "без роли"
                        vk.messages.send(peer_id=chat_id, message=f"⬆️ Повышен: {old_label} → «{new_role}»", random_id=get_random_id())
            else:
                vk.messages.send(peer_id=chat_id, message="ℹ️ Ответьте на сообщение пользователя командой !повыс", random_id=get_random_id())

        elif text.startswith("!пониз"):
            if not has_perm(user_id, "!пониз"):
                vk.messages.send(peer_id=chat_id, message=f"⛔ Нет прав. Нужна роль: {ROLE_LIST[CMD_MIN_ROLE['!пониз']]} или выше.", random_id=get_random_id())
            elif 'reply_message' in msg:
                target = msg['reply_message']['from_id']
                if target == -GROUP_ID:
                    vk.messages.send(peer_id=chat_id, message="⛔ Нельзя изменить роль бота.", random_id=get_random_id())
                else:
                    current_role = roles.get(target)
                    current_num = next((k for k, v in ROLE_LIST.items() if v == current_role), 0)
                    if current_num <= 1:
                        msg_text = "ℹ️ У пользователя нет роли." if current_num == 0 else "⛔ Ниже некуда — уже Младший модератор."
                        vk.messages.send(peer_id=chat_id, message=msg_text, random_id=get_random_id())
                    else:
                        new_num = current_num - 1
                        new_role = ROLE_LIST[new_num]
                        roles[target] = new_role
                        save_roles()
                        try:
                            vk.messages.setMemberRole(peer_id=chat_id, member_id=target, role="member")
                        except Exception:
                            pass
                        vk.messages.send(peer_id=chat_id, message=f"⬇️ Понижен: «{current_role}» → «{new_role}»", random_id=get_random_id())
            else:
                vk.messages.send(peer_id=chat_id, message="ℹ️ Ответьте на сообщение пользователя командой !пониз", random_id=get_random_id())

        elif text == "!топ день":
            top = get_top(days=1)
            vk.messages.send(peer_id=chat_id, message=format_top(top, "за сегодня"), random_id=get_random_id())

        elif text == "!топ неделя":
            top = get_top(days=7)
            vk.messages.send(peer_id=chat_id, message=format_top(top, "за 7 дней"), random_id=get_random_id())

        elif text == "!правила":
            if os.path.exists(RULES_FILE):
                with open(RULES_FILE, "r", encoding="utf-8") as f:
                    rules_text = f.read()
                chunks = []
                current = ""
                for line in rules_text.splitlines(keepends=True):
                    if len(current) + len(line) > 4000:
                        chunks.append(current.strip())
                        current = line
                    else:
                        current += line
                if current.strip():
                    chunks.append(current.strip())
                for chunk in chunks:
                    vk.messages.send(peer_id=chat_id, message=chunk, random_id=get_random_id())
            else:
                vk.messages.send(peer_id=chat_id, message="ℹ️ Правила не заданы.", random_id=get_random_id())
  except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}", flush=True)