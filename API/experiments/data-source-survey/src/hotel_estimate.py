"""Offline arithmetic for a sourced/explicit manual room-rate estimate; never an offer."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path
import re

from .survey import ROOT, moscow_today, public_url


def positive_integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name}: требуется целое число больше нуля")
    return value


def estimate(data):
    guests = positive_integer(data.get("guests"), "guests")
    capacity = positive_integer(data.get("guests_per_room"), "guests_per_room")
    nights = positive_integer(data.get("nights"), "nights")
    if data.get("price_basis") != "room_per_night":
        raise ValueError("price_basis: требуется room_per_night; цена за человека/весь период не поддерживается")
    value = data.get("price_per_room_night")
    if value is None or isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("price_per_room_night: задайте реальную исходную сумму строкой, например \"125.50\"; значение по умолчанию отсутствует")
    try:
        price = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError("price_per_room_night: некорректная сумма") from None
    if not price.is_finite() or price <= 0 or price > Decimal("1000000000") or price.as_tuple().exponent < -4:
        raise ValueError("price_per_room_night: нужна конечная положительная сумма до 1e9, максимум 4 знака после запятой")
    currency = data.get("currency")
    # Supported subset: these currency minor units are all two decimal places.
    if currency not in {"EUR", "RUB", "TRY", "USD", "GBP"}:
        raise ValueError("currency: поддерживаются EUR, RUB, TRY, USD, GBP; смешение валют и конвертация не выполняются")
    basis = data.get("basis")
    if not isinstance(basis, str) or not basis.strip() or len(basis) > 1000:
        raise ValueError("basis: опишите источник/смысл цены и вместимости (1..1000 символов)")
    source_type = data.get("source_type")
    if source_type not in {"official_published_rate", "historical_average", "manual_estimate"}:
        raise ValueError("source_type: official_published_rate, historical_average или manual_estimate")
    source = data.get("source_url")
    safe_source = public_url(source)
    if source_type != "manual_estimate" and not safe_source:
        raise ValueError("source_url: для опубликованной/исторической цены требуется публичная ссылка")
    if source and not safe_source:
        raise ValueError("source_url: некорректная публичная ссылка")
    try:
        observed = date.fromisoformat(data.get("observed_on", ""))
    except (TypeError, ValueError):
        raise ValueError("observed_on: укажите дату источника/оценки YYYY-MM-DD") from None
    if observed > moscow_today():
        raise ValueError("observed_on: дата наблюдения не может быть в будущем")
    taxes = data.get("taxes_included")
    if taxes is not None and not isinstance(taxes, bool):
        raise ValueError("taxes_included: true, false или null")
    rooms = (guests + capacity - 1) // capacity
    total = (price * rooms * nights).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"evidence": "user_supplied_estimate", "is_live_offer": False, "availability": None,
            "guests": guests, "guests_per_room": capacity, "nights": nights, "rooms": rooms,
            "price_per_room_night": str(price), "estimated_total": str(total), "currency": currency,
            "formula": "ceil(guests / guests_per_room) * nights * price_per_room_night",
            "source_type": source_type, "source_url": safe_source, "observed_on": observed.isoformat(),
            "basis": basis.strip(), "taxes_included": taxes,
            "assumptions": ["Все номера одного типа и с одинаковой вместимостью и ценой",
                            "Цена за номер за ночь, не за человека и не за весь период",
                            "Гости распределяются по номерам без дополнительных ограничений; детские тарифы не моделируются",
                            "Не подтверждены даты, наличие номеров и итоговые дополнительные платежи"],
            "rounding": "Итог до 0.01, ROUND_HALF_UP; наценка и конвертация не добавляются"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline hotel estimate from your explicitly sourced room rate")
    parser.add_argument("--input", required=True, help="JSON file inside the experiment directory")
    args = parser.parse_args(argv)
    path = Path(args.input)
    path = path if path.is_absolute() else ROOT / path
    path = path.resolve()
    if not path.is_relative_to(ROOT):
        parser.error("Input must be inside the experiment directory")
    try:
        # Decimal parsing avoids introducing float rounding before arithmetic.
        data = json.loads(path.read_text(encoding="utf-8-sig"), parse_float=Decimal)
        if not isinstance(data, dict):
            raise ValueError("JSON должен быть объектом")
        result = estimate(data)
    except (OSError, ValueError, TypeError):
        # File paths and contents can contain sensitive information; don't dump arbitrary errors.
        parser.error("Не удалось рассчитать оценку. Проверьте обязательные поля по EXTENDED.md; шаблон с null нужно заполнить. Содержимое файла не выводится.")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = ROOT / "reports" / "estimates" / run_id
    out.mkdir(parents=True, exist_ok=False)
    (out / "estimate.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    text = (f"# Оценка проживания по введённой цене\n\n**Это оценка, не подтверждённый оффер.**\n\n"
            f"{result['guests']} гостей / {result['guests_per_room']} мест в номере → {result['rooms']} номера(ов).\n\n"
            f"{result['rooms']} × {result['nights']} ночей × {result['price_per_room_night']} {result['currency']} = "
            f"**{result['estimated_total']} {result['currency']}**.\n\n"
            f"Смысл цены и источника: {result['basis']}\n\nДата наблюдения: {result['observed_on']}. "
            f"Налоги включены: {result['taxes_included']}. Наличие номера неизвестно.\n\n"
            "Все допущения и ссылка — в [estimate.json](estimate.json).\n")
    (out / "estimate.md").write_text(text, encoding="utf-8")
    print("Оценка сохранена:", out / "estimate.md")
    return 0
