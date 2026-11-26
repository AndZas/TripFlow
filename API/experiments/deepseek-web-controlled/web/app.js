"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("trip");
const searchStatus = byId("search-status");
const budgetStatus = byId("budget-status");
const budgetPanel = byId("budget");
const calcButton = byId("calculate");
const format = new Intl.NumberFormat("ru-RU");
const rub = (value) => `${format.format(value)} ₽`;
const units = {room_night: "за номер / ночь", group_stay: "за группу / поездку",
  person_admission: "за человека", group_admission: "за группу"};
const categories = {foodRub: "Питание", transportRub: "Городской транспорт",
  otherRub: "Прочие расходы", reserveRub: "Резерв"};
const estimateBasis = {hotel_rate: "По опубликованной ставке отеля", hotel_proxy: "Ориентир по тарифу для нескольких гостей",
  comparable_rates: "По тарифам похожих отелей",
  model_only: "Грубая оценка Flash без тарифов", budget_reference: "Резервный ориентир из бюджета поездки"};

let searchId = null;
let busy = false;

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function link(url, text, className) {
  const node = el("a", text, className);
  node.href = url;
  node.target = "_blank";
  node.rel = "noopener noreferrer";
  return node;
}

function status(node, text, kind = "") {
  node.textContent = text;
  node.className = `status ${kind}`;
}

async function request(path, data) {
  const response = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.message || "Запрос не выполнен.");
  return result;
}

function localDate(offset) {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  return [date.getFullYear(), date.getMonth() + 1, date.getDate()].map((n) => String(n).padStart(2, "0")).join("-");
}

function niceDate(value) {
  return new Intl.DateTimeFormat("ru-RU", {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"})
    .format(new Date(`${value}T00:00:00Z`));
}

function selection() {
  return {hotelId: document.querySelector("input[name=hotel]:checked")?.value,
    placeIds: [...document.querySelectorAll("input[name=place]:checked")].map((node) => node.value)};
}

function refreshControls() {
  const {hotelId, placeIds} = selection();
  for (const control of form.elements) control.disabled = busy;
  for (const control of document.querySelectorAll("input[name=hotel], input[name=place]")) control.disabled = busy;
  calcButton.disabled = busy || !hotelId;
  byId("selected").textContent = hotelId ? `Отель выбран · мест: ${placeIds.length}` : "Выбери один отель";
}

function priceLabel(price) {
  if (!price) return "Цена не найдена";
  if (price.basis === "free") return "Бесплатный вход";
  const value = new Intl.NumberFormat("ru-RU", {style: "currency", currency: price.currency}).format(price.amount);
  return `${price.from ? "от " : ""}${value} ${units[price.basis]}`;
}

function usageLabel(usage) {
  const input = usage.tokens.cacheHit + usage.tokens.cacheMiss;
  const {search, fetch} = usage.billed;
  return `Расход по пиковому тарифу ¥${usage.peakCny.toFixed(4)} · поиск ${search} · загрузки ${fetch} · ` +
    `${format.format(input)} входных и ${format.format(usage.tokens.output)} выходных токенов`;
}

function card(option, isHotel) {
  const article = el("article", "", "panel option");
  const top = link(option.mapUrl, "", `visual ${isHotel ? "hotel" : "place"}`);
  top.setAttribute("aria-label", `${option.name} на карте`);
  const fallback = el("span", isHotel ? "⌂" : "◇", "placeholder");
  fallback.setAttribute("aria-hidden", "true");
  top.append(fallback);
  if (option.image) {
    const image = el("img");
    image.alt = option.name;
    image.loading = "lazy";
    image.referrerPolicy = "no-referrer";
    image.addEventListener("error", () => image.remove());
    image.src = option.image.url;
    top.append(image);
  }
  top.append(el("span", "На карте ↗", "map-badge"));
  article.append(top);

  const body = el("div", "", "option-body");
  body.append(el("h4", option.name));
  const price = option.price ? link(option.price.url, priceLabel(option.price), "price") : el("p", priceLabel(), "muted");
  if (isHotel && option.estimate) {
    const estimate = option.estimate;
    body.append(el("p", `≈ ${rub(estimate.totalRub)} за проживание`, "lodging-total"),
      el("p", `${rub(estimate.totalLowRub)} – ${rub(estimate.totalHighRub)} на всю группу`, "lodging-range"),
      el("p", `${rub(estimate.nightlyRub)} за номер / ночь · ${estimate.rooms} ном. × ${estimate.nights} ноч.`, "muted"),
      el("p", estimateBasis[estimate.basis], "estimate-basis"));
    if (option.price) {
      if (option.price.occupancy) price.append(` · гостей по тарифу: ${option.price.occupancy}`);
      body.append(price);
    }
  } else body.append(price);
  if (option.description) body.append(el("p", option.description));
  const facts = el("dl", "", "facts");
  for (const [label, field] of [["Адрес", option.address], [isHotel ? "Заезд и выезд" : "Часы работы", option.hours]]) {
    facts.append(el("dt", label));
    const value = el("dd");
    if (field) value.append(link(field.url, field.value));
    else value.textContent = "Не найдено";
    facts.append(value);
  }
  body.append(facts);
  if (option.fit) body.append(el("p", option.fit, "fit"));
  if (option.note) body.append(el("p", option.note, "muted note"));
  if (option.facts?.length) {
    const extras = el("details");
    extras.append(el("summary", "Дополнительные сведения"));
    const facts = el("dl", "", "facts");
    for (const fact of option.facts) {
      const value = el("dd");
      value.append(link(fact.url, fact.value));
      facts.append(el("dt", fact.label), value);
    }
    extras.append(facts);
    body.append(extras);
  }
  if (option.estimate?.reason || option.estimate?.sources.length) {
    const basis = el("details");
    basis.append(el("summary", "Основание оценки проживания"));
    if (option.estimate.reason) basis.append(el("p", option.estimate.reason));
    for (const source of option.estimate.sources) {
      const line = el("p");
      line.append(link(source.url, `${source.name} · ${source.from ? "от " : ""}${rub(source.nightlyRub)} за ночь`));
      basis.append(line);
    }
    body.append(basis);
  }
  const sources = el("details");
  sources.append(el("summary", "Источники"));
  const list = el("ul");
  for (const source of option.sources) {
    const row = el("li");
    row.append(link(source.url, source.title || source.url));
    list.append(row);
  }
  if (option.imageSource) {
    const row = el("li");
    row.append(link(option.imageSource, "Источник изображения"));
    list.append(row);
  }
  sources.append(list);
  if (option.coordinates) sources.append(el("p", `${option.coordinates.lat}, ${option.coordinates.lon}`, "muted"));
  if (option.price?.quote) sources.append(el("blockquote", option.price.quote));
  body.append(sources);

  const choose = el("label", "", "choose");
  const input = el("input");
  input.type = isHotel ? "radio" : "checkbox";
  input.name = isHotel ? "hotel" : "place";
  input.value = option.id;
  input.addEventListener("change", () => {
    budgetPanel.hidden = true;
    status(budgetStatus, "");
    refreshControls();
  });
  choose.append(input, el("span", isHotel ? "Выбрать отель" : "Добавить в поездку"));
  article.append(body, choose);
  return article;
}

function row(name, value, note) {
  const line = el("div", "", "budget-row");
  const label = el("div", name);
  if (note) label.append(el("small", note));
  line.append(label, el("strong", value === null ? "Неизвестно" : rub(value)));
  return line;
}

function renderBudget(data) {
  const title = el("h2", "Бюджет поездки");
  title.id = "budget-title";
  const amount = el("p", rub(data.totalRub), "total");
  const summary = data.incomplete ? "Учтённые расходы · некоторые цены неизвестны" : "Оценка расходов на всю группу";
  const gap = data.remainingRub >= 0 ? `До целевого бюджета ${rub(data.remainingRub)}` :
    `Выше целевого бюджета на ${rub(-data.remainingRub)}`;
  budgetPanel.replaceChildren(title, amount, el("p", summary, "muted"),
    el("p", `${rub(data.perPersonRub)} на человека · ${data.incomplete ? "по учтённым расходам: " : ""}${gap}`, "budget-summary"));
  for (const item of data.items) budgetPanel.append(row(item.name, item.rub, item.note));
  for (const [key, label] of Object.entries(categories)) budgetPanel.append(row(label, data.additional[key], "Оценка модели"));
  if (data.assumptions) budgetPanel.append(el("p", data.assumptions, "assumptions"));
  if (data.fx) budgetPanel.append(link(data.fx.url, `Курс Банка России от ${data.fx.date}`, "muted"));
  if (data.usage) budgetPanel.append(el("p", usageLabel(data.usage), "muted usage"));
  budgetPanel.hidden = false;
  budgetPanel.scrollIntoView({block: "nearest", behavior: "smooth"});
}

byId("example").addEventListener("click", () => {
  for (const [key, value] of Object.entries({destination: "Санкт-Петербург", startDate: localDate(14), endDate: localDate(16),
    travelers: 2, budgetRub: 45000, preferences: "Отель недалеко от метро, желательно с завтраком. Хотим художественные музеи."})) {
    form.elements[key].value = value;
  }
  form.elements.endDate.min = form.elements.startDate.value;
});

form.elements.startDate.addEventListener("change", () => { form.elements.endDate.min = form.elements.startDate.value; });

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(form));
  data.travelers = Number(data.travelers);
  data.budgetRub = Number(data.budgetRub);
  if (data.startDate >= data.endDate) {
    status(searchStatus, "Дата окончания должна быть позже даты начала.", "error");
    return;
  }
  busy = true;
  refreshControls();
  searchId = null;
  byId("results").hidden = true;
  budgetPanel.hidden = true;
  status(budgetStatus, "");
  status(searchStatus, "Ищем отели и места, проверяем сведения и оцениваем проживание…", "working");
  try {
    const result = await request("/api/search", data);
    searchId = result.searchId;
    byId("trip-title").textContent = result.trip.destination;
    byId("trip-summary").textContent = `${niceDate(result.trip.startDate)} — ${niceDate(result.trip.endDate)} · ${rub(result.trip.budgetRub)} на группу`;
    const spend = byId("search-usage");
    spend.textContent = usageLabel(result.usage);
    if (result.fx) spend.append(" · ", link(result.fx.url, `Курс Банка России от ${result.fx.date}`));
    for (const key of ["hotels", "places"]) {
      byId(key).replaceChildren(...(result[key].length ? result[key].map((option) => card(option, key === "hotels")) :
        [el("p", result.errors[key] || "Подходящих вариантов с источниками не нашлось.", "muted")]));
    }
    byId("results").hidden = false;
    status(searchStatus, "");
  } catch (error) {
    status(searchStatus, error.message || "Поиск прервался. Попробуй ещё раз.", "error");
  } finally {
    busy = false;
    refreshControls();
  }
});

calcButton.addEventListener("click", async () => {
  const selected = selection();
  if (!searchId || !selected.hotelId) return;
  busy = true;
  refreshControls();
  status(budgetStatus, "Считаем расходы на выбранную поездку…", "working");
  try {
    renderBudget(await request("/api/budget", {searchId, ...selected}));
    status(budgetStatus, "");
  } catch (error) {
    status(budgetStatus, error.message || "Бюджет не рассчитан. Попробуй ещё раз.", "error");
  } finally {
    busy = false;
    refreshControls();
  }
});
