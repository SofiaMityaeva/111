"""Генератор СИНТЕТИЧЕСКИХ обращений.

Тексты собираются из шаблонов: приветствие + суть проблемы + подробность + концовка,
с опечатками, разговорными оборотами и примесью фраз из других категорий.
Реальных данных компаний здесь нет: всё придумано для учебной демонстрации.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

import pandas as pd

from core.classifier import predict_many
from core.config import (
    CHANNELS,
    STATUS_IN_PROGRESS,
    STATUS_NEW,
    STATUS_RESOLVED,
    STATUS_REVIEW,
)
from core.routing import route
from core.sla import compute_deadline

PROBLEMS = {
    "tech": [
        "не работает интернет",
        "пропал интернет",
        "интернет очень медленный",
        "скорость упала до {speed} мбит",
        "роутер мигает красным",
        "постоянно отваливается wi-fi",
        "на телевизоре нет каналов",
        "тв-приставка пишет нет сигнала",
        "большой пинг, игры лагают",
        "интернет пропадает каждые полчаса",
        "не открываются сайты",
        "горит лампочка los на роутере",
        "соединение есть, но страницы не грузятся",
        "видео постоянно зависает и буферизуется",
        "не работает интернет на всех устройствах",
    ],
    "billing": [
        "деньги списали два раза",
        "не прошёл платёж",
        "оплатил, но баланс не пополнился",
        "почему такая большая сумма в счёте",
        "нужен акт сверки",
        "не пришёл чек об оплате",
        "хочу вернуть деньги за неиспользованный период",
        "баланс отрицательный, хотя я платил",
        "как настроить автоплатёж",
        "списали абонентскую плату за отключённую услугу",
        "не получается оплатить картой в личном кабинете",
        "нужна справка об оплате для бухгалтерии",
        "непонятное списание {sum} рублей",
        "пришёл счёт за прошлый месяц повторно",
    ],
    "connect": [
        "хочу подключить интернет по адресу {address}",
        "когда придёт монтажник",
        "перенесите визит мастера на {day}",
        "переезжаю, нужно перенести подключение на новый адрес",
        "есть ли техническая возможность подключения в моём доме",
        "нужно протянуть кабель в другую комнату",
        "оставлял заявку на подключение, никто не перезвонил",
        "хочу подключить интернет в офис",
        "сколько ждать подключения частного дома",
        "нужна установка и настройка роутера мастером",
        "запишите на подключение на {day}",
        "можно ли подключить интернет на даче",
    ],
    "tariff": [
        "хочу сменить тариф на более быстрый",
        "какие есть тарифы дешевле",
        "добавьте пакет каналов кино",
        "отключите услугу антивирус",
        "хочу подключить статический ip",
        "как перейти на тариф с телевидением",
        "интересует акция для новых абонентов",
        "хочу добавить мобильную связь в пакет",
        "уберите платную подписку на онлайн-кинотеатр",
        "какая скорость на тарифе {plan}",
        "можно ли приостановить договор на время отпуска",
        "хочу подключить второй тв-приставку к тарифу",
    ],
    "complaint": [
        "очень недоволен качеством обслуживания",
        "оператор нагрубил мне в чате",
        "третий раз обращаюсь и никто не решает проблему",
        "хочу оставить жалобу на мастера",
        "монтажник опоздал на три часа и оставил мусор",
        "обещали перезвонить и не перезвонили",
        "буду писать жалобу в контролирующие органы",
        "требую компенсацию за простой",
        "мне никто не отвечает уже неделю",
        "ужасный сервис, хочу расторгнуть договор",
        "сотрудник поддержки бросил трубку",
        "прошу разобраться с отношением ваших сотрудников",
    ],
}

DETAILS = {
    "tech": ["со вчерашнего вечера", "уже второй день", "с утра", "после грозы",
             "перезагружал роутер, не помогло", "кабель проверил, всё подключено", "у соседей тоже"],
    "billing": ["в личном кабинете", "по выписке из банка", "платил через приложение банка",
                "в прошлом месяце было меньше", "оплата была {date}"],
    "connect": ["дом новый", "квартира на {floor} этаже", "удобно после 18:00",
                "в выходные удобнее", "договор уже подписан"],
    "tariff": ["пользуюсь услугами пять лет", "сейчас тариф базовый", "скорости не хватает",
               "дома работаем вдвоём", "видел рекламу на сайте"],
    "complaint": ["это уже не первый раз", "очень разочарован", "время потрачено зря",
                  "так с клиентами не работают", "жду извинений"],
}

# Общие фразы без явной темы: модель по ним не может уверенно понять категорию
GENERIC = [
    "у меня проблема, перезвоните",
    "ничего не работает, что происходит",
    "разберитесь пожалуйста с моим договором",
    "вопрос по услугам",
    "помогите решить вопрос",
    "проблема с личным кабинетом",
]

OPENINGS = ["Здравствуйте!", "Добрый день.", "Добрый вечер,", "Привет.", "Помогите пожалуйста,",
            "Подскажите,", "Алло,", "", "", ""]
CLOSINGS = ["Спасибо.", "Жду ответа.", "Срочно!", "Договор {contract}.", "Номер договора {contract}.",
            "Заранее спасибо!", "", "", ""]

# Размеры категорий различаются, как в жизни: технических обращений больше, жалоб меньше
CATEGORY_WEIGHTS = {"tech": 0.27, "billing": 0.23, "connect": 0.2, "tariff": 0.17, "complaint": 0.13}

PRIORITY_WEIGHTS = {"Высокий": 0.2, "Средний": 0.5, "Низкий": 0.3}


def _fill(template: str, rnd: random.Random) -> str:
    return template.format(
        speed=rnd.choice([1, 2, 5, 10]),
        address=f"ул. Садовая, д. {rnd.randint(1, 120)}",
        day=rnd.choice(["понедельник", "вторник", "среду", "пятницу", "субботу"]),
        sum=rnd.choice([150, 299, 450, 700, 1200]),
        plan=rnd.choice(["Старт", "Оптима", "Максимум"]),
        date=f"{rnd.randint(1, 28)}.{rnd.randint(1, 12):02d}",
        floor=rnd.randint(1, 25),
        contract=rnd.randint(100000, 999999),
    )


def _add_typos(text: str, rnd: random.Random, probability: float = 0.06) -> str:
    """Меняет местами две соседние буквы в некоторых словах — как при быстром наборе."""
    words = text.split()
    for i, word in enumerate(words):
        if len(word) > 4 and rnd.random() < probability:
            pos = rnd.randint(1, len(word) - 3)
            words[i] = word[:pos] + word[pos + 1] + word[pos] + word[pos + 2:]
    return " ".join(words)


def make_text(category: str, rnd: random.Random) -> str:
    """Собирает один синтетический текст обращения заданной категории."""
    parts = [rnd.choice(OPENINGS)]
    # Часть клиентов пишет общими словами, а суть — только в подробностях или вовсе без неё
    if rnd.random() < 0.15:
        parts.append(rnd.choice(GENERIC))
        if rnd.random() < 0.5:
            parts.append(_fill(rnd.choice(DETAILS[category]), rnd))
    else:
        parts.append(_fill(rnd.choice(PROBLEMS[category]), rnd))
        if rnd.random() < 0.6:
            parts.append(_fill(rnd.choice(DETAILS[category]), rnd))
    # Примерно в каждом пятом обращении есть фраза из другой категории — так бывает в жизни
    if rnd.random() < 0.2:
        other = rnd.choice([c for c in PROBLEMS if c != category])
        parts.append("ещё " + _fill(rnd.choice(PROBLEMS[other]), rnd))
    parts.append(_fill(rnd.choice(CLOSINGS), rnd))
    text = " ".join(p for p in parts if p).strip()
    if rnd.random() < 0.3:
        text = text.lower()
    return _add_typos(text, rnd)


def _pick_weighted(weights: dict, rnd: random.Random) -> str:
    return rnd.choices(list(weights), weights=list(weights.values()))[0]


def generate_training_set(n: int = 1500, seed: int = 42) -> pd.DataFrame:
    """Размеченный синтетический набор для обучения модели: text, category."""
    rnd = random.Random(seed)
    rows = []
    for _ in range(n):
        category = _pick_weighted(CATEGORY_WEIGHTS, rnd)
        rows.append({"text": make_text(category, rnd), "category": category})
    return pd.DataFrame(rows)


def generate_demo_tickets(model, groups, sla_rules, threshold, now: datetime, n: int = 300, days: int = 14, seed: int = 7):
    """Синтетическая история обращений за последние days дней.

    Каждое обращение проходит настоящую обработку моделью, а затем «проживает»
    жизненный цикл: диспетчер проверяет неуверенные, исправляет часть ошибок модели,
    специалисты решают — большинство в срок, часть с нарушением SLA.
    Возвращает (список обращений, список правок с индексом обращения).
    """
    rnd = random.Random(seed)
    true_categories, texts, created = [], [], []
    for _ in range(n):
        category = _pick_weighted(CATEGORY_WEIGHTS, rnd)
        true_categories.append(category)
        texts.append(make_text(category, rnd))
        # Треть обращений — за последние сутки, чтобы в очереди были открытые
        horizon = 24 * 60 if rnd.random() < 0.33 else days * 24 * 60
        offset = timedelta(minutes=rnd.randint(0, horizon))
        created.append((now - offset).replace(second=0, microsecond=0))

    predictions = predict_many(model, texts)
    tickets, corrections = [], []
    for i, (text, true_category, created_at, (predicted, confidence)) in enumerate(
        zip(texts, true_categories, created, predictions)
    ):
        priority = _pick_weighted(PRIORITY_WEIGHTS, rnd)
        group, status, auto = route(predicted, confidence, groups, threshold)
        ticket = {
            "created_at": created_at,
            "channel": rnd.choice(CHANNELS),
            "priority": priority,
            "text": text,
            "predicted_category": predicted,
            "confidence": round(confidence, 4),
            "category": predicted,
            "group_name": group,
            "status": status,
            "auto_assigned": int(auto),
            "assigned_at": created_at if auto else None,
            "deadline": compute_deadline(created_at, predicted, priority, sla_rules),
            "resolved_at": None,
            "is_synthetic": 1,
        }
        age = now - created_at

        # Диспетчер разбирает неуверенные обращения через 10–300 минут
        if not auto:
            review_delay = timedelta(minutes=rnd.randint(10, 300))
            if age > review_delay:
                ticket["assigned_at"] = created_at + review_delay
                ticket["status"] = STATUS_NEW
                if true_category != predicted:
                    corrections.append((i, predicted, true_category, ticket["assigned_at"]))
                ticket["category"] = true_category
        # Ошибку автоназначения в 70% случаев замечает группа и возвращает обращение
        elif true_category != predicted and rnd.random() < 0.7:
            fix_delay = timedelta(minutes=rnd.randint(30, 240))
            if age > fix_delay:
                corrections.append((i, predicted, true_category, created_at + fix_delay))
                ticket["category"] = true_category

        ticket["group_name"] = groups[ticket["category"]]
        ticket["deadline"] = compute_deadline(created_at, ticket["category"], priority, sla_rules)

        # Решение: 80% в пределах норматива, 20% с нарушением
        if ticket["status"] != STATUS_REVIEW:
            sla_hours = (ticket["deadline"] - created_at).total_seconds() / 3600
            share = rnd.uniform(0.2, 0.95) if rnd.random() < 0.8 else rnd.uniform(1.05, 1.8)
            resolved_at = created_at + timedelta(hours=sla_hours * share)
            if resolved_at < now and resolved_at > (ticket["assigned_at"] or created_at):
                ticket["status"] = STATUS_RESOLVED
                ticket["resolved_at"] = resolved_at.replace(microsecond=0)
            elif rnd.random() < 0.6:
                ticket["status"] = STATUS_IN_PROGRESS
        tickets.append(ticket)
    return tickets, corrections


def create_demo_environment(now: datetime, groups, sla_rules, threshold, paths) -> dict:
    """Первый запуск (сценарий US-01): синтетика → обучение модели → демо-история в базе.

    paths — объект с полями synthetic, model, metrics, db (по умолчанию core.config).
    """
    from core import db
    from core.classifier import save_model, train_and_evaluate

    training = generate_training_set()
    paths.synthetic.parent.mkdir(parents=True, exist_ok=True)
    training.to_csv(paths.synthetic, index=False, encoding="utf-8")

    model, metrics = train_and_evaluate(training["text"], training["category"])
    metrics["n_corrections_used"] = 0
    save_model(model, metrics, paths.model, paths.metrics)

    db.reset_db(paths.db)
    tickets, corrections = generate_demo_tickets(model, groups, sla_rules, threshold, now)
    ids = [db.insert_ticket(t, paths.db) for t in tickets]
    for index, old, new, corrected_at in corrections:
        db.insert_correction(ids[index], old, new, corrected_at, paths.db)
    return {"tickets": len(ids), "corrections": len(corrections), "metrics": metrics}
