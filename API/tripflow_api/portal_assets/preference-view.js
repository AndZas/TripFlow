export const preferencePath = (taskId) => "/preferences/tasks/" + encodeURIComponent(taskId);

export function hotelAvailability(availability) {
  return {
    available: "Источник подтвердил наличие номеров на выбранные даты",
    unavailable: "Источник сообщает, что на выбранные даты мест нет",
    unknown: "Доступность на выбранные даты не проверена",
  }[availability?.state];
}

export function hotelPriceBasis(price) {
  const observation = price?.rate?.observedOn;
  const period = price?.rate?.start && price?.rate?.end ? price.rate.start + " — " + price.rate.end : null;
  if (price?.level === "room_reference") {
    const reference = "Ориентир по цене отдельного номера в этой гостинице";
    return price.basis === "other_period" ? reference + " · другой период" + (observation || period ? " (" + (observation || period) + ")" : "") : reference;
  }
  if (price?.level === "market") return "Оценка по другим объектам города";
  return {
    dated: "Тариф для выбранных дат",
    published: price?.rate?.variableQuote ? "Оценка по изменяемому тарифу" : "Оценка по опубликованному прайсу",
    other_period: "Оценка по тарифу другого периода" + (observation || period ? " (" + (observation || period) + ")" : ""),
    analogs: "Оценка по сопоставимым отелям",
  }[price?.basis];
}

export function hotelCoverage(report, batch) {
  const messages = [];
  if (batch.error?.message) messages.push(batch.error.message);
  if (!batch.items.length && report?.considered != null) {
    if (report.coverage) {
      messages.push("Обнаружено " + report.coverage.discovered + ", подтверждён город у " + report.coverage.cityConfirmed + " объектов.");
    } else if (!report.stop) {
      messages.push("Проверено объектов: " + report.considered + ".");
    }
    if (report.considered && !report.priced) {
      const missingDonors = report.rejected?.some(item => item.priceGap === "insufficient_donors");
      messages.push(missingDonors ? "Не удалось подтвердить тариф или найти две сопоставимые местные цены."
        : "Не удалось обосновать стоимость проживания.");
    }
    if (!report.stop && report.priced) messages.push("С обоснованной оценкой: " + report.priced + ".");
    if (report.failedConditions) messages.push("Отсеяно обязательными условиями: " + report.failedConditions + ".");
    if (report.overCeiling) messages.push("Выше лимита отеля: " + report.overCeiling + ".");
  }
  if (report?.targetGap) messages.push("В текущих источниках не нашлось цены в пределах 30% от цели. Показаны ближайшие подходящие предложения.");
  if (batch.hasMore === null) messages.push("За пределами этой попытки число вариантов неизвестно.");
  return messages.join(" ");
}

export function hotelDiagnostics(report) {
  const details = element("details", undefined, "builder-json");
  const labels = { published: "Опубликованная ставка", from: "Ставка «от»", range: "Нижняя граница диапазона",
    analogs: "Оценка по аналогам" };
  const units = { room_night: "за номер за ночь", room_stay: "за номер за период",
    group_night: "за группу номеров за ночь", group_stay: "за группу за период" };
  const verdicts = { confirmed: "подтверждено", refuted: "опровергнуто", unknown: "неизвестно" };
  const link = (url, label = "Источник") => {
    const result = element("a", label);
    result.href = url;
    result.target = "_blank";
    result.rel = "noopener noreferrer";
    return result;
  };
  const rubles = (value) => new Intl.NumberFormat("ru-RU").format(value) + " ₽";
  details.append(element("summary", "Источники, расчёт и обращения к сервисам"));
  const calls = report.calls;
  const seconds = report.elapsedMs == null ? "выполняется" : (report.elapsedMs / 1000).toLocaleString("ru-RU") + " с";
  details.append(element("p", [
    seconds, "обращений к каталогу " + (report.catalogLookups ?? "—"), "вариантов из каталога " + (report.catalogMatches ?? "—"),
    "Search " + calls.search, "Fetch " + calls.fetch, "Flash " + calls.flash, "ЦБ " + calls.fx, "повторов " + report.retries,
  ].join(" · "), "metadata"));
  const tokens = report.usage;
  const usage = (value) => value == null ? "неизвестно" : String(value);
  details.append(element("p", "Токены гостиничного поиска · вход " + usage(tokens.inputTokens)
    + " · выход " + usage(tokens.outputTokens) + (report.usageIncomplete ? " · данные неполные" : ""), "metadata"));
  if (report.considered != null) {
    details.append(element("p", "В каталоге на старте " + report.catalogAtStart + " · новых объектов " + report.discovered
      + " · проверено " + report.considered + " · с обоснованной оценкой " + report.priced
      + " · отсеяно по условиям " + report.failedConditions + " · выше лимита " + report.overCeiling
      + " · выдано " + report.returned, "metadata"));
  }
  if (report.coverage) {
    const { discovered, cityConfirmed, priceLevels, returned } = report.coverage;
    details.append(element("p", "Обнаружено " + discovered + " · подтверждён город у " + cityConfirmed
      + " · тариф предложения " + (priceLevels.offer ?? 0) + " · ориентир по номеру " + (priceLevels.room_reference ?? 0)
      + " · оценка по городу " + (priceLevels.market ?? 0) + " · выдано " + returned, "metadata"));
  }
  if (report.profile && report.discoverySources) {
    const found = report.discoverySources;
    const sources = report.sourceCalls;
    const prices = report.priceSources ?? {};
    details.append(element("p", "Профиль " + report.profile + (report.usedExtension ? " · использован расширенный бюджет" : "")
      + (report.destinationRegion ? " · " + report.destinationRegion : ""), "metadata"));
    details.append(element("p", "Geoapify " + found.geoapify + " · Russhotels " + found.russhotels
      + " · новых из веба " + report.newWebObjects + " · пригодные цены по источникам "
      + Object.entries(prices).map(([source, count]) => source + " " + count).join(", "), "metadata"));
    if (sources) details.append(element("p", "Геокодирование " + sources.geocode
      + " · Places " + sources.places + " · Russhotels " + sources.russhotels, "metadata"));
  }
  if (report.error) {
    const stop = report.stop;
    const reasons = { input_bytes: "объём входного текста, байты", output_reserve: "резерв выходных токенов",
      calls: "число вызовов", time: "время, мс" };
    const provider = { authorization: "провайдер отклонил авторизацию", balance: "исчерпан баланс провайдера",
      invalid_response: "ответ провайдера не прошёл проверку", flash_response: "непригодный ответ модели",
      flash_truncated: "ответ модели оборвался", timeout: "провайдер не ответил вовремя",
      fx_unavailable: "курс валют недоступен" };
    const stage = report.attempts.findLast((attempt) => attempt.error === report.error)?.kind;
    const reason = stop ? stop.stage.toUpperCase() + " · " + reasons[stop.unit] + " · "
      + stop.used + " из " + stop.limit + (stop.requested ? " · следующий шаг требует " + stop.requested : "")
      : [stage?.toUpperCase(), provider[report.error] ?? report.error].filter(Boolean).join(" · ");
    details.append(element("p", "Причина остановки · " + reason, "metadata"));
  }
  if (report.reusedCalls && Object.values(report.reusedCalls).some(Boolean)) {
    const { search, fetch, flash } = report.reusedCalls;
    details.append(element("p", "Переиспользованы ответы прежней задачи · Search " + search + " · Fetch " + fetch
      + " · Flash " + flash, "metadata"));
  }
  const currencyReasons = { fx_unavailable: "сервис курса недоступен", fx_currency_missing: "валюта отсутствует в документе ЦБ",
    fx_invalid_rate: "курс или номинал не прошёл проверку", unknown_currency: "неизвестный код валюты" };
  for (const entry of report.currencyIssues ?? []) {
    details.append(element("p", entry.name + " · " + entry.currencies.map(({ currency, reason }) =>
      currency + " · " + (currencyReasons[reason] ?? reason)).join(", "), "metadata"));
  }
  if (report.enrichmentCalls) {
    const { search, fetch } = report.enrichmentCalls;
    details.append(element("p", "Обогащение карточек · Search " + search + " · страницы " + fetch, "metadata"));
  }
  for (const hotel of report.hotels ?? []) {
    const price = hotel.price;
    details.append(element("h3", hotel.item.name), link(hotel.item.sourceUrl,
      price.level === "market" ? "Источник сведений об отеле" : "Источник цены"));
    if (hotel.metadata?.website) details.append(link(hotel.metadata.website.value, "Сайт гостиницы"));
    if (hotel.metadata?.image) details.append(link(hotel.metadata.image.sourceUrl, "Источник фото"));
    if (price.roomCategory) details.append(element("p", price.roomCategory, "metadata"));
    if (price.targetRub != null) details.append(element("p", "Цель " + rubles(price.targetRub)
      + " · отклонение " + (price.differenceRub > 0 ? "+" : "") + rubles(price.differenceRub), "metadata"));
    details.append(element("p", labels[price.type] + " · " + price.rooms + " ном. × " + price.nights + " ноч. · " + rubles(price.totalRub)));
    for (const text of [hotelPriceBasis(price), hotelAvailability(hotel.availability)].filter(Boolean)) {
      details.append(element("p", text, "metadata"));
    }
    if (hotel.availability?.sourceUrl) {
      const proof = element("p");
      proof.append(element("q", hotel.availability.quote), document.createTextNode(" "), link(hotel.availability.sourceUrl));
      details.append(proof);
    }
    if (price.rate) {
      const rate = price.rate;
      const line = element("p", rate.amount + (rate.upper ? "–" + rate.upper : "") + " " + rate.currency + " " + units[rate.basis] + " · ");
      line.append(link(rate.sourceUrl, "Тариф"), document.createTextNode(" · "), element("q", rate.quote));
      details.append(line);
      if (rate.provider === "russhotels") {
        details.append(element("p", "Russhotels · " + rate.providerRoom + " · " + rate.providerPlacement
          + " · price_client " + rate.providerAmount, "metadata"), link(rate.documentationUrl, "Единица цены в API"));
      }
      for (const phrase of rate.support ?? []) details.append(element("q", phrase));
      if (rate.originalOccupancy) details.append(element("p", rate.originalOccupancy, "metadata"));
      if (rate.periodQuote) details.append(element("q", rate.periodQuote));
      if (rate.variableQuote) details.append(element("q", rate.variableQuote));
      if (rate.scope && !price.basis) {
        const period = rate.scope === "general" ? "Общий прайс" : (rate.scope === "offer" ? "Цена на выбранные даты" : "Период тарифа")
          + " · " + rate.start + " — " + rate.end;
        details.append(element("p", period, "metadata"));
      }
      const policies = { no_meals: "без питания", breakfast_included: "завтрак включён",
        breakfast_extra: "завтрак за доплату", nonrefundable: "невозвратный тариф", free_cancellation: "бесплатная отмена" };
      if (rate.policies?.length) details.append(element("p", rate.policies.map((policy) => policies[policy]).join(" · "), "metadata"));
      const fx = price.exchange;
      if (fx.sourceUrl) {
        const conversion = element("p", fx.nominal + " " + fx.currency + " = " + fx.valueRub + " ₽ · " + fx.date + " · ");
        conversion.append(link(fx.sourceUrl, "Банк России"));
        details.append(conversion);
      }
    } else {
      const spread = price.spreadRubPerRoomNight;
      details.append(element("p", "Медиана за номер за ночь " + rubles(price.rateRubPerRoomNight)
        + (spread ? " · диапазон " + rubles(spread[0]) + " — " + rubles(spread[1]) : "")
        + (price.zone === "nearby" ? " · близкие отели" : "")));
      for (const example of price.analogs) {
        const row = element("p");
        row.append(link(example.rate.sourceUrl, example.name), document.createTextNode(
          example.nightlyRub ? " · " + rubles(example.nightlyRub) + " за ночь · " : " · "), element("q", example.rate.quote));
        details.append(row);
      }
    }
    for (const check of hotel.conditions) {
      const row = element("p", check.travelerQuote + " · " + verdicts[check.verdict]);
      for (const evidence of check.evidence) {
        row.append(document.createTextNode(" · "), element("q", evidence.quote), document.createTextNode(" "), link(evidence.sourceUrl));
      }
      details.append(row);
    }
  }
  if (report.attempts.length || report.rejected?.length || report.sourceIssues?.length || report.focused?.length) {
    const raw = element("details", undefined, "builder-json");
    const pre = element("pre");
    pre.append(element("code", JSON.stringify({ attempts: report.attempts, focused: report.focused ?? [],
      rejected: report.rejected ?? [], sourceIssues: report.sourceIssues ?? [], marketSearch: report.marketSearch,
      budget: report.budget }, null, 2)));
    raw.append(element("summary", "Попытки и исключённые варианты"), pre);
    details.append(raw);
  }
  return details;
}

export const scopes = { hotels: "Отели", attractions: "Достопримечательности", budget: "Смета" };
const roles = { required: "Обязательно", preferred: "Желательно", excluded: "Исключение", note: "Заметка" };
const errors = {
  invalid_response: "Ответ модели не прошёл проверку формата.",
  invalid_quote: "Модель не подтвердила условие цитатой из текста.",
  numeric_conflict: "Число, единица расчёта или граница в условии не совпали с исходным текстом.",
  timeout: "Истекло время ожидания модели.",
  authorization: "DeepSeek отклонил ключ.",
  balance: "Недостаточно средств на балансе DeepSeek.",
  rate_limit: "DeepSeek ограничил частоту запросов.",
  network: "Не удалось связаться с DeepSeek.",
  provider_unavailable: "DeepSeek временно недоступен.",
  provider_rejected: "DeepSeek отклонил запрос.",
  input_too_long: "Текст превышает лимит анализа в 6000 символов на поле.",
  interrupted: "Разбор прерван. Его можно повторить в новой задаче.",
  internal: "Внутренняя ошибка разбора.",
};
const statusLabels = {
  pending: "Разбор выполняется…", succeeded: "Разбор готов.",
  empty: "Пожелания не указаны, модель не вызывалась.",
  unconfigured: "Ключ DeepSeek не настроен. Анализ недоступен.",
  historical: "Для этой задачи разбор не записывался.",
  unavailable: "Диагностика задачи пока недоступна.",
};
const usageFields = {
  inputTokens: "Входные", outputTokens: "Выходные", totalTokens: "Всего токенов",
  cachedInputTokens: "Из кэша DeepSeek", uncachedInputTokens: "Вне кэша DeepSeek",
};
const date = new Intl.DateTimeFormat("ru", { dateStyle: "short", timeStyle: "medium" });
const number = new Intl.NumberFormat("ru");

export function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function preferenceStatus(record) {
  return statusLabels[record.status] ?? (errors[record.error] || "Разбор завершился ошибкой.");
}

function preferenceText(label, text) {
  const section = element("div", undefined, "preference-text");
  section.append(element("h3", label), element("p", text || "Не указано"));
  return section;
}

function preferenceConditions(scope, conditions, message) {
  const section = element("div");
  section.append(element("h4", scopes[scope]));
  if (message) section.append(element("p", message, "metadata"));
  if (conditions === null) return section;
  const list = element("ul", undefined, "preference-conditions");
  for (const item of conditions.filter((condition) => condition.scope === scope)) {
    const line = element("li");
    const role = roles[item.role] + (item.ambiguous ? " · Нужно уточнить" : "");
    line.append(element("span", role, "pill"), element("p", item.meaning), element("q", item.quote, "metadata"));
    list.append(line);
  }
  section.append(list.children.length ? list : element("p", "Условий нет.", "metadata"));
  return section;
}

function preferenceChanges(changes) {
  const list = element("ul", undefined, "preference-conditions");
  for (const change of changes) {
    const item = element("li");
    const previous = change.previous.meaning;
    const message = change.replacement ? `Изменено условие «${previous}»` : `Снято условие «${previous}»`;
    item.append(element("p", message), element("q", change.quote, "metadata"));
    list.append(item);
  }
  return list;
}

export function preferenceInterpretation(submissions) {
  const fragment = document.createDocumentFragment();
  if (!submissions.length) return fragment;
  const [{ preferences }] = submissions;
  if (submissions[0].analysis.status === "historical") {
    fragment.append(element("p", preferenceStatus(submissions[0].analysis)));
    return fragment;
  }

  const base = submissions.flatMap(({ analysis }) => analysis.stages)
    .find((stage) => stage.stage === "preferences" && stage.result);
  const refinements = new Map(submissions.filter(({ refinement }) => refinement).map((submission) => [
    submission.category, { ...submission, stage: submission.analysis.stages.find((stage) => stage.stage === "refinement") },
  ]));
  const hasInterpretation = base?.status === "succeeded" || [...refinements.values()].some(({ stage }) => stage?.result);
  const current = element("section", undefined, "preference-stack");
  current.append(element("h3", "Актуальные условия"));
  const messages = new Set(submissions.filter(({ refinement, analysis }) => !refinement && analysis.status !== "succeeded")
    .map(({ analysis }) => preferenceStatus(analysis)));
  for (const message of messages) current.append(element("p", message));
  for (const scope of Object.keys(scopes)) {
    const refinement = refinements.get(scope);
    if (refinement?.stage?.result) {
      current.append(preferenceConditions(scope, refinement.stage.result.conditions));
    } else if (refinement) {
      const status = preferenceStatus(refinement.stage ?? refinement.analysis);
      const message = base ? `До уточнения. ${status}` : status;
      current.append(preferenceConditions(scope, base?.result.conditions ?? null, message));
    } else if (hasInterpretation && base) {
      current.append(preferenceConditions(scope, base.result.conditions));
    }
  }
  fragment.append(current);

  const history = element("details", undefined, "preference-history preference-attempts");
  history.append(element("summary", refinements.size ? "Исходный разбор и изменения" : "Отправленные пожелания"));
  const content = element("div", undefined, "preference-stack");
  content.append(preferenceText("Отправленные пожелания", preferences));
  for (const [scope, { refinement, stage }] of refinements) {
    content.append(preferenceText(`Отправленные уточнения · ${scopes[scope]}`, refinement));
    if (base) content.append(preferenceConditions(scope, base.result.conditions, "Исходные условия"));
    if (stage?.result?.changes.length) content.append(preferenceChanges(stage.result.changes));
  }
  history.append(content);
  fragment.append(history);
  return fragment;
}

function measurements(values) {
  const list = element("dl", undefined, "usage");
  for (const [label, value] of values) {
    const entry = element("div");
    entry.append(element("dt", label), element("dd", value));
    list.append(entry);
  }
  return list;
}

function usageText(usage) {
  return Object.entries(usageFields).map(([key, label]) =>
    `${label} ${usage?.[key] == null ? "не сообщено" : number.format(usage[key])}`).join(" · ");
}

export function preferenceSummary(summary) {
  const fragment = document.createDocumentFragment();
  const { tasks } = summary;
  const count = (status) => number.format(tasks[status] || 0);
  fragment.append(element("p", `Последние 7 суток · ${date.format(summary.start * 1000)} — ${date.format(summary.end * 1000)}`, "metadata"));
  fragment.append(measurements([
    ["Задач с разбором", number.format(Object.values(tasks).reduce((sum, value) => sum + value, 0))],
    ["Успешно", count("succeeded")], ["Пустой ввод", count("empty")], ["Ошибка", count("failed")],
    ["Без ключа", count("unconfigured")], ["В обработке", count("pending")],
    ["Попыток вызова", number.format(summary.attempts)], ["Этапов переиспользовано", number.format(summary.reused)],
    ["Среднее время вызова", summary.averageMs == null ? "—" : `${number.format(summary.averageMs)} мс`],
    ["Замеров времени", number.format(summary.durationObservations)],
  ]));
  if (summary.attempts) {
    fragment.append(element("p", usageText(summary.usage), "metadata"));
    if (summary.incompleteUsage) {
      fragment.append(element("p", `Показаны известные суммы. Попыток с неполным usage: ${summary.incompleteUsage}.`, "metadata"));
    }
    const cacheObservations = summary.usageObservations;
    if (cacheObservations.cachedInputTokens < summary.attempts || cacheObservations.uncachedInputTokens < summary.attempts) {
      fragment.append(element("p", "DeepSeek сообщил разбивку входных токенов по кэшу не для всех попыток.", "metadata"));
    }
  }
  fragment.append(element("p", "Стоимость не рассчитана.", "metadata"));
  return fragment;
}

export function preferenceAttempts(record, taskId) {
  const details = element("details", undefined, "preference-attempts");
  details.append(element("summary", "Расход и время задачи"), element("p", `Задача ${taskId}`, "metadata"));
  if (record.duration_ms != null) details.append(element("p", `Полное время разбора · ${number.format(record.duration_ms)} мс`));
  for (const stage of record.stages) {
    const title = stage.stage === "preferences" ? "Общий текст" : "Уточнение";
    details.append(element("h3", title));
    const source = { call: "Вызов модели", reused: stage.status === "pending" ? "Ожидание общего разбора" : "Использован общий разбор",
      empty: "Пустой ввод", unavailable: "Модель не вызвана" }[stage.source];
    details.append(element("p", `${source} · ${stage.model} · ${stage.version} · ${date.format(stage.started_at * 1000)}`, "metadata"));
    if (stage.initiatorTaskId && stage.initiatorTaskId !== taskId) {
      details.append(element("p", `Вызов инициирован задачей ${stage.initiatorTaskId}`, "metadata"));
    }
    if (stage.error) details.append(element("p", `${preferenceStatus(stage)} (${stage.error})`, "metadata"));
    for (const attempt of stage.attempts) {
      const time = attempt.duration_ms == null ? "время не сообщено" : `${attempt.duration_ms} мс`;
      const fields = [`Попытка ${attempt.number}`, date.format(attempt.started_at * 1000), time, attempt.model, attempt.error];
      details.append(element("p", fields.filter(Boolean).join(" · ")),
        element("p", attempt.usage ? usageText(attempt.usage) : "Токены не сообщены.", "metadata"));
    }
  }
  details.append(element("p", "Стоимость не рассчитана.", "metadata"));
  return details;
}
