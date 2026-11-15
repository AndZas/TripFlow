"use strict";

const get = (id) => document.getElementById(id);
const form = get("trip-form");
const inputs = form.elements;
const currency = new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 });
const dateFormat = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short", year: "numeric" });
const expenses = { food: "Питание", transport: "Городской транспорт", other: "Прочие расходы", reserve: "Резерв" };
const filters = { restaurant: "Ресторан отеля", parking: "Парковка", wifi: "Wi-Fi",
  museums: "Музеи", parks: "Парки", historic: "Исторические места" };
const statuses = { confirmed: "Подтверждено", contradicted: "Опровергнуто", unknown: "Не удалось подтвердить" };
const example = "Из достопримечательностей только музеи. Каждый день один обед в недорогом кафе, другие приёмы пищи не планируем. По городу две поездки на метро в день на человека. На сувениры потратим 1 250 ₽ на человека за поездку. Резерв ровно 6 000 ₽ на всю группу за поездку.";
const state = { token: null, searching: false, calculating: false, stopped: false,
  selectionId: null, recommendations: null, hotelIndex: 0, hotelId: null, placeIndex: 0,
  placeIds: [], placesDone: false };

function node(tag, text, css) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (css) element.className = css;
  return element;
}

function announce(message, error = false) {
  get("activity").textContent = message;
  get("activity").classList.toggle("error", error);
}

function setStep(section) {
  for (const link of document.querySelectorAll(".steps a")) {
    if (link.hash === "#" + section) link.setAttribute("aria-current", "step");
    else link.removeAttribute("aria-current");
  }
}

function moveTo(section) {
  setStep(section);
  get(section).scrollIntoView({ block: "start" });
}

function picks() {
  return { hotelId: state.hotelId, placeIds: state.placeIds };
}

function refresh() {
  const ready = Boolean(state.token) && !state.stopped;
  const selection = picks();
  const busy = state.searching || state.calculating;
  get("trip-fields").disabled = busy || state.stopped;
  get("example").disabled = busy || state.stopped;
  get("search").disabled = !ready || busy;
  get("calculate").disabled = !ready || state.calculating || !selection.hotelId || !state.placesDone;
  get("stop").disabled = !ready;
  get("activity").classList.toggle("busy", busy);
  for (const button of document.querySelectorAll("#hotels button, #places button")) {
    button.disabled = !ready || state.calculating;
  }
  get("overview-city").textContent = inputs.destination.selectedOptions[0]?.textContent || "—";
  const dates = [inputs.startDate.value, inputs.endDate.value].filter(Boolean)
    .map((value) => dateFormat.format(new Date(value + "T12:00:00")));
  get("overview-dates").textContent = dates.join(" — ") || "Укажи даты поездки";
  get("overview-travelers").textContent = inputs.travelers.value || "—";
  get("overview-target").textContent = inputs.budgetRub.value ? currency.format(inputs.budgetRub.value) : "—";
  get("overview-hotel").textContent = state.recommendations?.hotels.find((hotel) => hotel.id === selection.hotelId)?.name || "—";
  get("overview-places").textContent = selection.placeIds.length;
}

function resetBudget() {
  get("budget-content").hidden = true;
  get("budget-content").replaceChildren();
  get("budget-placeholder").hidden = false;
}

function resetChoices() {
  state.selectionId = null;
  state.recommendations = null;
  Object.assign(state, { hotelIndex: 0, hotelId: null, placeIndex: 0, placeIds: [], placesDone: false });
  get("choice-count").textContent = "";
  get("choice-content").hidden = true;
  get("choice-placeholder").hidden = false;
  get("hotels").replaceChildren();
  get("places").replaceChildren();
  resetBudget();
}

async function request(path, data) {
  const options = data === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json", "X-Stand-Token": state.token },
    body: JSON.stringify(data),
  };
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.message);
  return result;
}

async function backgroundJob(path, data, onResult) {
  const { jobId } = await request(path, data);
  let previous = "";
  let lastView = "";
  while (!state.stopped) {
    const job = await request("/api/job/" + jobId);
    if (onResult && job.result) {
      const view = job.result.hotels.length + "/" + job.state;
      if (view !== lastView) {
        onResult(jobId, job.result);
        lastView = view;
      }
    }
    if (job.state === "done") return job.result;
    if (job.state === "error") throw new Error(job.message);
    if (job.message !== previous) {
      if (!onResult || !state.calculating) announce(job.message + "…");
      previous = job.message;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("Стенд остановлен.");
}

function safeLink(url, text) {
  try {
    if (!["https:", "http:"].includes(new URL(url).protocol)) return null;
  } catch {
    return null;
  }
  const link = node("a", text);
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

function showCheck(check) {
  const line = node("p");
  const status = statuses[check.status];
  line.append(node("span", status, "tag " + check.status),
    document.createTextNode(check.label || check.requirement.question));
  if (check.supportQuote || check.quote) line.append(node("small", "«" + (check.supportQuote || check.quote) + "»"));
  if (check.requirement.excluded) line.append(node("small", "Условие применяется как исключение."));
  if (check.source) {
    const link = safeLink(check.source, check.page ? "Источник · страница " + check.page : "Источник");
    if (link) {
      const source = node("small");
      source.append(link);
      line.append(source);
    }
  }
  return line;
}

function optionCard(item, hotel) {
  const block = node("article", undefined, "option");
  const price = hotel ? currency.format(item.indicativeGroupRub) + " за группу · ориентир" :
    item.price === 0 ? "Вход бесплатный" : item.price ? currency.format(item.price) + " за человека" :
    item.priceReference ? "Цена билета неизвестна · ориентир Росстата " + currency.format(item.priceReference.amount_rub) + " на человека" :
    item.feeStatus === "paid" ? "Платный вход · сумма неизвестна" : "Цена посещения неизвестна";
  block.append(node("h4", item.name), node("p", price, "card-price"));
  if (item.address) block.append(node("small", item.address));
  if (hotel) {
    const hours = [item.checkIn && "Заезд с " + item.checkIn, item.checkOut && "Выезд до " + item.checkOut];
    block.append(node("p", [item.room, item.meal || "Питание не указано"].filter(Boolean).join(" · ")),
      node("small", hours.filter(Boolean).join(" · ")));
    if (item.nightlyPersonRub) {
      block.append(node("small", currency.format(item.nightlyPersonRub) +
        " на человека за ночь по тарифу поставщика. Наличие на даты не проверено."));
    }
  } else if (item.openingHours) {
    block.append(node("small", "Часы работы · " + item.openingHours));
  }
  if (item.description) block.append(node("p", String(item.description).slice(0, 460), "option-description"));
  if (item.website) {
    const link = safeLink(item.website, "Сайт места");
    if (link) block.append(link);
  }
  if (item.checks?.length) {
    const detail = node("details");
    detail.append(node("summary", "Результаты проверки"), ...item.checks.map(showCheck));
    block.append(detail);
  }
  return block;
}

function action(label, callback, secondary = false) {
  const button = node("button", label, secondary ? "quiet" : undefined);
  button.type = "button";
  button.addEventListener("click", () => {
    callback();
    resetBudget();
    setStep("choices");
    showQueues();
    refresh();
  });
  return button;
}

function showQueues() {
  const { hotels, attractions } = state.recommendations;
  const chosen = hotels.find((hotel) => hotel.id === state.hotelId);
  const pendingHotel = hotels[state.hotelIndex];
  const hotelBlock = get("hotels");
  if (chosen) {
    hotelBlock.replaceChildren(optionCard(chosen, true),
      action("Посмотреть следующий отель", () => { state.hotelId = null; state.hotelIndex += 1; }, true));
  } else if (pendingHotel) {
    hotelBlock.replaceChildren(optionCard(pendingHotel, true), node("div", undefined, "selection-actions"));
    hotelBlock.lastChild.append(action("Выбрать отель", () => { state.hotelId = pendingHotel.id; }),
      action("Пропустить", () => { state.hotelIndex += 1; }, true));
  } else {
    hotelBlock.replaceChildren(node("p", state.searching ? "Ищем следующий подходящий отель…" :
      "Подходящие варианты закончились. Можно пересмотреть пропущенные или изменить пожелания.", "muted"));
    if (!state.searching && hotels.length) {
      hotelBlock.append(action("Показать отели сначала", () => { state.hotelIndex = 0; }, true));
    }
  }

  const placeBlock = get("places");
  const pendingPlace = attractions[state.placeIndex];
  placeBlock.replaceChildren();
  if (state.placeIds.length) {
    const chosenPlaces = node("ul", undefined, "chosen-places");
    for (const id of state.placeIds) {
      const item = attractions.find((place) => place.id === id);
      const row = node("li", item.name);
      row.append(action("Убрать", () => { state.placeIds = state.placeIds.filter((value) => value !== id); }, true));
      chosenPlaces.append(row);
    }
    placeBlock.append(chosenPlaces);
  }
  if (!state.placesDone && pendingPlace) {
    const actions = node("div", undefined, "selection-actions");
    actions.append(action("Добавить место", () => { state.placeIds.push(pendingPlace.id); state.placeIndex += 1; }),
      action("Пропустить", () => { state.placeIndex += 1; }, true),
      action("Достаточно мест", () => { state.placesDone = true; }, true));
    placeBlock.append(optionCard(pendingPlace, false), actions);
  } else if (!state.placesDone) {
    placeBlock.append(node("p", "Больше мест в подборке нет.", "muted"),
      action("Завершить выбор мест", () => { state.placesDone = true; }));
  } else if (pendingPlace) {
    placeBlock.append(action("Продолжить выбор мест", () => { state.placesDone = false; }, true));
  }
}

function showRecommendations(result, first, waitingForHotel) {
  if (first) showInterpretation(result);
  if (first || waitingForHotel) showQueues();
  get("choice-count").textContent = "Отелей " + result.hotels.length + " · мест " + result.attractions.length;
  get("choice-placeholder").hidden = true;
  get("choice-content").hidden = false;
}

function showInterpretation(result) {
  const { parsed } = result;
  const interpretation = get("interpretation");
  const lines = parsed.filters.map((rule) =>
    node("p", filters[rule.value] + " · " + (rule.excluded ? "исключить" :
      rule.strength === "required" ? "обязательно" : "желательно")));
  for (const rule of parsed.extra) {
    lines.push(node("p", rule.label + " · " + (rule.strength === "required" ? "обязательно" : "желательно")));
  }
  for (const [key, note] of Object.entries(parsed.expenses)) {
    if (note) lines.push(node("p", expenses[key] + " — " + note));
  }
  interpretation.replaceChildren(...(lines.length ? lines : [node("p", "Отдельных условий и расходных заметок нет.")]));
  get("hotel-limit").textContent = "До " + currency.format(result.card.hotelBudgetRub) + " на группу";
}

function showBudget(result) {
  const content = get("budget-content");
  const { knownTotalRub, unpricedPlaces, remainingRub, ticketLines } = result;
  const total = node("div", undefined, "total");
  total.append(node("p", unpricedPlaces.length ? "Оценка без неизвестных цен посещений" : "Ориентир на всю группу"),
    node("strong", currency.format(knownTotalRub)),
    node("p", (remainingRub >= 0 ? "До целевого бюджета " : "Выше целевого бюджета на ") + currency.format(Math.abs(remainingRub))));
  const amounts = node("dl", undefined, "amounts");
  const addRow = (label, amount) => {
    const row = node("div");
    row.append(node("dt", label), node("dd", currency.format(amount)));
    amounts.append(row);
  };
  addRow("Проживание · ориентир", result.lodgingRub);
  if (ticketLines.length) addRow("Посещения", result.ticketsRub);
  for (const [key, label] of Object.entries(expenses)) addRow(label, result.expenses[key].groupRub);
  content.replaceChildren(total, amounts);
  if (unpricedPlaces.length) content.append(node("p", "Цена неизвестна — " + unpricedPlaces.join(", "), "warn"));
  const breakfast = result.benefits.find((benefit) => benefit.kind === "breakfast");
  if (breakfast) content.append(node("p", "Завтрак по тарифу покрывает " + breakfast.coveredDays + " из " + result.days + " дней."));
  const other = result.expenses.other;
  if (other.reducedRub > 0) content.append(node("p", "Необязательные расходы уменьшены на " + currency.format(other.reducedRub) + ".", "warn"));
  const notes = node("details");
  notes.append(node("summary", "Ставки и допущения"));
  const meals = { breakfast: "Завтрак", lunch: "Обед", dinner: "Ужин", snacks: "Перекусы" };
  for (const [key, row] of Object.entries(result.expenses)) {
    if (row.meals) {
      for (const [meal, value] of Object.entries(row.meals)) {
        if (value.amountRub) notes.append(node("p", meals[meal] + " · " + currency.format(value.amountRub) +
          " на человека × " + value.paidDays + " платных дн. × " + result.travelers +
          " = " + currency.format(value.groupRub) + ". " + value.assumption));
      }
    } else {
      notes.append(node("p", expenses[key] + " — " + row.assumption));
    }
    if (row.overCapRub > 0) notes.append(node("p", "Сверх лимита на категорию " + currency.format(row.overCapRub), "warn"));
    for (const rate of result.sources[key]) {
      const line = node("p", rate.source_label_with_unit + " · " + currency.format(rate.amount_rub) + " · " + rate.reference_period);
      const link = rate.source_url && safeLink(rate.source_url, "Росстат");
      if (link) line.append(" · ", link);
      notes.append(line);
    }
  }
  for (const ticket of ticketLines) {
    const line = node("p", ticket.name + " · " + currency.format(ticket.groupRub) + " за группу · " + ticket.origin);
    const link = ticket.reference && safeLink(ticket.reference.source_url, "Источник ставки");
    if (link) line.append(" · ", link);
    notes.append(line);
  }
  content.append(notes);
  get("budget-placeholder").hidden = true;
  content.hidden = false;
}

function defaultDates() {
  const today = new Date();
  const localDate = (offset) => {
    const value = new Date(today.getFullYear(), today.getMonth(), today.getDate() + offset);
    return [value.getFullYear(), value.getMonth() + 1, value.getDate()]
      .map((part) => String(part).padStart(2, "0")).join("-");
  };
  inputs.startDate.value = localDate(30);
  inputs.endDate.value = localDate(32);
}

get("example").addEventListener("click", () => {
  defaultDates();
  inputs.travelers.value = "2";
  inputs.budgetRub.value = "85000";
  inputs.preferences.value = example;
  form.dispatchEvent(new Event("input"));
});

form.addEventListener("input", () => {
  if (state.selectionId) {
    resetChoices();
    announce("Параметры изменились. Запусти новый подбор.");
    setStep("trip");
  }
  refresh();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.searching || state.calculating || !state.token) return;
  const data = Object.fromEntries(new FormData(form));
  data.travelers = Number(data.travelers);
  data.budgetRub = Number(data.budgetRub);
  resetChoices();
  state.searching = true;
  announce("Запускаем подбор…");
  refresh();
  try {
    await backgroundJob("/api/select", data, (jobId, result) => {
      const first = state.selectionId === null;
      const waitingForHotel = !state.hotelId && !state.recommendations?.hotels[state.hotelIndex];
      state.selectionId = jobId;
      state.recommendations = result;
      showRecommendations(result, first, waitingForHotel);
      if (first) moveTo("choices");
      refresh();
    });
    if (!state.calculating) announce("Подбор завершён.");
  } catch (error) {
    if (!state.stopped) announce(error.message, true);
  } finally {
    state.searching = false;
    if (state.recommendations && !state.hotelId && !state.recommendations.hotels[state.hotelIndex]) showQueues();
    refresh();
  }
});

get("calculate").addEventListener("click", async () => {
  state.calculating = true;
  resetBudget();
  announce("Запускаем расчёт…");
  refresh();
  try {
    const result = await backgroundJob("/api/budget", { ...picks(), selectionId: state.selectionId });
    showBudget(result);
    moveTo("budget");
    announce("Расчёт завершён.");
  } catch (error) {
    if (!state.stopped) announce(error.message, true);
  } finally {
    state.calculating = false;
    refresh();
  }
});

get("stop").addEventListener("click", async () => {
  get("stop").disabled = true;
  try {
    await request("/api/stop", {});
    state.stopped = true;
    get("connection").textContent = "Остановка";
    announce("Стенд останавливается. Выгрузка модели завершится в окне запуска.");
  } catch (error) {
    announce(error.message, true);
  } finally {
    refresh();
  }
});

defaultDates();
request("/api/config").then(({ destinations, token }) => {
  state.token = token;
  for (const destination of destinations) {
    const option = node("option", destination.city);
    option.value = destination.id;
    inputs.destination.append(option);
  }
  get("connection").textContent = "LM Studio подключена";
  announce("Стенд готов к подбору.");
  refresh();
}).catch(() => {
  get("connection").textContent = "Стенд недоступен";
  announce("Запусти стенд и обнови страницу.", true);
});
