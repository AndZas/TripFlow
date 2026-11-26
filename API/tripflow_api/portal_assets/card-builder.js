import { element, hotelAvailability, hotelCoverage, hotelDiagnostics, hotelPriceBasis, preferenceAttempts, preferenceInterpretation, preferencePath, scopes } from "./preference-view.js";

const labels = { hotels: scopes.hotels, attractions: scopes.attractions };
const money = new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 });
const expenses = {
  foodTotalRub: "Питание", localTransportTotalRub: "Городской транспорт",
  otherExpensesTotalRub: "Прочие расходы", reserveTotalRub: "Резерв",
};
const pollTimeoutMs = 300_000;

function status(panel, label, message = "", style = "") {
  const badge = panel.querySelector("[data-builder-status]");
  badge.hidden = !label;
  badge.textContent = label;
  badge.className = style ? "pill " + style : "pill";
  const description = panel.querySelector("[data-builder-message]");
  description.hidden = !message;
  description.textContent = message;
}

function updateTrace(panel, operation, body) {
  const details = panel.querySelector("[data-builder-trace]");
  details.hidden = !body;
  if (!body) {
    details.open = false;
    for (const field of details.querySelectorAll("code")) field.textContent = "";
    return;
  }
  details.querySelector("[data-builder-endpoint]").textContent = "POST /v1/" + operation;
  details.querySelector("[data-builder-id]").textContent = body.taskId;
  details.querySelector("[data-builder-request]").textContent = JSON.stringify(body, null, 2);
  details.querySelector("[data-builder-response]").textContent = "Запрос отправляется…";
}

function showResponse(panel, body) {
  panel.querySelector("[data-builder-response]").textContent = JSON.stringify(body, null, 2);
}

function failureMessage(error) {
  const detail = error.payload?.error;
  return Object.entries(detail?.fields ?? {}).map(([field, issues]) => field + " — " + issues.join(", ")).join(". ")
    || detail?.message || error.message;
}

function formatPrice(item) {
  if (item.price == null) return "Цена неизвестна";
  if (typeof item.price === "number") return money.format(item.price) + " · ориентир за всю группу и все ночи";
  const units = item.price.basis === "person_admission" ? " с человека" : " за группу";
  return (item.price.isFromPrice ? "от " : "") + money.format(item.price.amountRub) + units;
}

function dateText(date) {
  return [
    date.getFullYear(), String(date.getMonth() + 1).padStart(2, "0"), String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

function pause(milliseconds, signal) {
  return new Promise((resolve) => {
    if (signal.aborted) return resolve();
    const timer = setTimeout(finish, milliseconds);
    signal.addEventListener("abort", finish, { once: true });
    function finish() {
      clearTimeout(timer);
      signal.removeEventListener("abort", finish);
      resolve();
    }
  });
}

export function setupCardBuilder(request) {
  const byId = (id) => document.getElementById(id);
  const form = byId("builder-form");
  const fields = form.elements;
  const cityOptions = byId("builder-city-options");
  const cityMessage = byId("builder-city-message");
  const recommendations = byId("builder-recommendations");
  const budget = byId("builder-budget");
  const estimate = byId("builder-estimate");
  const expenseList = byId("builder-expenses");
  const tabs = [...byId("builder-tabs").querySelectorAll("[role=tab]")];
  const preferencePanel = byId("builder-preferences");
  const groups = Object.entries(labels).map(([kind, label]) => {
    const settings = byId("builder-settings-template").content.firstElementChild.cloneNode(true);
    const panel = byId("builder-result-template").content.firstElementChild.cloneNode(true);
    for (const node of [settings, panel]) node.querySelector("[data-builder-label]").textContent = label;
    panel.querySelector("[data-builder-mock]").hidden = kind === "hotels";
    if (kind === "hotels") {
      settings.querySelector("[data-builder-money-label]").textContent = "Желаемая сумма проживания на всю группу, ₽";
      const target = settings.querySelector("[data-builder-limit]");
      target.min = "1";
      target.dataset.builderTarget = "";
    }
    byId("builder-settings").append(settings);
    recommendations.append(panel);
    const more = panel.querySelector("[data-builder-more]");
    more.addEventListener("click", () => {
      if (form.reportValidity()) work((signal) => find(group, tripSnapshot(), signal));
    });
    const group = { kind, settings, panel, more, items: new Map() };
    return group;
  });

  let controller = new AbortController();
  let initialized = false;
  let working = false;
  let destination = null;
  let cityLookup;
  let cityTimer;
  let selectedHotel = null;
  let estimateSubmission = null;
  const selectedAttractions = new Set();

  function selectTab(tab) {
    for (const button of tabs) {
      const active = button === tab;
      button.setAttribute("aria-selected", active);
      button.tabIndex = active ? 0 : -1;
      byId(button.getAttribute("aria-controls")).hidden = !active;
    }
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectTab(tab));
    tab.addEventListener("keydown", (event) => {
      const keys = { ArrowRight: 1 - index, ArrowLeft: 1 - index, Home: 0, End: 1 };
      if (!Object.hasOwn(keys, event.key)) return;
      event.preventDefault();
      const next = tabs[keys[event.key]];
      selectTab(next);
      next.focus();
    });
  });

  function renderPreferences() {
    const submissions = groups.map((group) => group.submission).filter(Boolean);
    const interpretation = preferenceInterpretation(submissions.map(({ body, analysis }) => ({
      category: body.targets, preferences: body.trip.preferences, refinement: body.refinement, analysis,
    })));
    for (const { body, analysis } of submissions) {
      if (analysis.stages.length) interpretation.append(preferenceAttempts(analysis, body.taskId));
      if (analysis.hotels) interpretation.append(hotelDiagnostics(analysis.hotels));
    }
    preferencePanel.replaceChildren(interpretation);
  }

  async function readPreferences(group, submission, signal) {
    try {
      const { payload } = await request(preferencePath(submission.body.taskId), undefined, signal);
      submission.analysis = payload;
    } catch {
      submission.analysis = { status: "unavailable", stages: [] };
    }
    if (!signal.aborted && group.submission === submission) renderPreferences();
  }

  function tripSnapshot() {
    return {
      destination,
      startDate: fields.startDate.value,
      endDate: fields.endDate.value,
      travelers: fields.travelers.valueAsNumber,
      budgetRub: fields.budgetRub.valueAsNumber,
      preferences: fields.preferences.value.trim() || null,
    };
  }

  function resetEstimate() {
    estimateSubmission = null;
    status(budget, "");
    updateTrace(budget, "", null);
    expenseList.replaceChildren();
    expenseList.hidden = true;
    const hotel = groups[0].items.get(selectedHotel);
    byId("builder-selection").textContent = (hotel ? hotel.name : "Отель не выбран")
      + " · Мест выбрано: " + selectedAttractions.size;
  }

  function resetResults() {
    for (const group of groups) {
      group.items.clear();
      group.proofs?.clear();
      group.submission = null;
      group.more.hidden = true;
      group.panel.querySelector("[data-builder-candidates]").replaceChildren();
      status(group.panel, "");
      updateTrace(group.panel, "", null);
    }
    selectedHotel = null;
    selectedAttractions.clear();
    resetEstimate();
    byId("builder-empty").hidden = false;
    byId("builder-tabs").hidden = true;
    for (const tab of tabs) byId(tab.getAttribute("aria-controls")).hidden = true;
    renderPreferences();
  }

  function fillExample() {
    const city = fields.city.value;
    form.reset();
    fields.city.value = city;
    const start = new Date();
    start.setDate(start.getDate() + 7);
    const end = new Date(start);
    end.setDate(end.getDate() + 3);
    fields.startDate.value = dateText(start);
    fields.endDate.value = dateText(end);
    fields.endDate.min = fields.startDate.value;
    fields.travelers.value = "2";
    fields.budgetRub.value = "85000";
    fields.preferences.value = "Отель рядом с метро, музеи и прогулки";
    resetResults();
  }

  function updateControls() {
    const inputs = byId("builder-inputs");
    inputs.disabled = !initialized;
    for (const input of inputs.querySelectorAll("input, textarea, button")) {
      if (input !== fields.city && !cityOptions.contains(input)) input.disabled = working;
    }
    estimate.disabled = working;
    for (const group of groups) {
      group.more.disabled = working;
      for (const choice of group.panel.querySelectorAll("input")) choice.disabled = working;
    }
  }

  function clearCityLookup() {
    clearTimeout(cityTimer);
    cityLookup?.abort();
    cityOptions.replaceChildren();
  }

  function suggestCity() {
    clearCityLookup();
    const query = fields.city.value.trim();
    cityMessage.textContent = query ? "Поиск города…" : "Введите название города.";
    if (!query) return;
    cityLookup = new AbortController();
    const signal = cityLookup.signal;
    cityTimer = setTimeout(async () => {
      try {
        const { payload } = await request("/builder/cities?q=" + encodeURIComponent(query), undefined, signal);
        if (signal.aborted) return;
        const messages = { unconfigured: "Для подсказок нужен ключ Geoapify.",
          unavailable: "Сервис подсказок недоступен. Попробуйте снова.", empty: "Введите название города." };
        cityMessage.textContent = messages[payload.status] || (payload.items.length ? "Выберите город из списка." : "Города не найдены.");
        cityOptions.replaceChildren(...payload.items.map(({ label, ...value }) => {
          const button = element("button", label, "button secondary");
          button.type = "button";
          button.addEventListener("click", () => {
            destination = value;
            fields.city.value = label;
            fields.city.setCustomValidity("");
            clearCityLookup();
            cityMessage.textContent = "";
            fields.city.focus();
          });
          return button;
        }));
      } catch {
        if (!signal.aborted) cityMessage.textContent = "Не удалось загрузить подсказки. Попробуйте снова.";
      }
    }, 300);
  }

  function open() {
    if (initialized) return;
    initialized = true;
    fillExample();
    updateControls();
  }

  function reset() {
    controller.abort();
    controller = new AbortController();
    initialized = false;
    working = false;
    form.reset();
    destination = null;
    clearCityLookup();
    fields.city.setCustomValidity("");
    resetResults();
    updateControls();
  }

  async function work(action) {
    if (working || !initialized) return;
    const signal = controller.signal;
    working = true;
    updateControls();
    try {
      await action(signal);
    } finally {
      if (!signal.aborted) {
        working = false;
        updateControls();
      }
    }
  }

  async function runTask(panel, operation, submission, signal) {
    const { body } = submission;
    updateTrace(panel, operation, body);
    submission.retry = false;
    try {
      if (!submission.accepted) {
        status(panel, "Отправка");
        let accepted;
        try {
          accepted = await request("/builder/" + operation, body, signal);
        } catch (error) {
          if (signal.aborted || error.payload && error.status < 500) throw error;
          await pause(700, signal);
          if (signal.aborted) return null;
          accepted = await request("/builder/" + operation, body, signal);
        }
        if (signal.aborted) return null;
        submission.accepted = accepted.payload;
      }
      showResponse(panel, submission.accepted);
      status(panel, "В обработке");
      const deadline = Date.now() + pollTimeoutMs;
      while (!signal.aborted) {
        if (Date.now() >= deadline) throw new Error("Задача ещё выполняется. Продолжите опрос или откройте журнал задач.");
        let reply;
        try {
          reply = await request("/builder/tasks/" + encodeURIComponent(body.taskId), undefined, signal);
        } catch (error) {
          if (signal.aborted || error.payload && error.status < 500) throw error;
          await pause(2000, signal);
          continue;
        }
        if (signal.aborted) return null;
        showResponse(panel, reply.payload);
        if (reply.payload.status === "completed") return reply.payload.result;
        const retry = Number(reply.response.headers.get("Retry-After")) || 2;
        await pause(retry * 1000, signal);
      }
    } catch (error) {
      if (!signal.aborted) {
        submission.retry = !error.payload || error.status >= 500;
        if (error.payload) showResponse(panel, error.payload);
        status(panel, "Ошибка", failureMessage(error), "bad");
      }
    }
    return null;
  }

  function choice(group, item) {
    const hotel = group.kind === "hotels";
    const input = element("input");
    input.type = hotel ? "radio" : "checkbox";
    input.name = hotel ? "builder-hotel" : "builder-attraction";
    input.checked = hotel ? selectedHotel === (item?.objectId ?? null) : selectedAttractions.has(item.objectId);
    input.disabled = working;
    input.addEventListener("change", () => {
      if (hotel) selectedHotel = item?.objectId ?? null;
      else if (input.checked) selectedAttractions.add(item.objectId);
      else selectedAttractions.delete(item.objectId);
      resetEstimate();
    });
    const label = element("label", undefined, "builder-choice");
    const info = element("span");
    info.append(element("strong", item?.name ?? "Без отеля"));
    if (item) {
      const proof = group.proofs?.get(item.objectId);
      const price = proof?.price;
      const estimate = price
        ? (["from", "range"].includes(price.type) ? "От " : "") + money.format(item.price)
            + " за " + price.rooms + " ном. и " + price.nights + " ноч."
        : formatPrice(item);
      const details = [item.category, item.stars ? item.stars + " ★" : null, estimate].filter(Boolean);
      info.append(element("span", details.join(" · "), "metadata"));
      if (hotel) {
        const availability = proof?.availability ?? { state: "unknown" };
        const difference = price?.differenceRub;
        const targetText = difference == null ? "" : difference === 0 ? "Совпадает с желаемой суммой"
          : money.format(Math.abs(difference)) + (difference > 0 ? " выше цели" : " ниже цели");
        for (const text of [price?.roomCategory, hotelPriceBasis(price), hotelAvailability(availability), targetText].filter(Boolean)) {
          info.append(element("span", text, "metadata"));
        }
      }
      if (hotel && item.address) info.append(element("span", item.address, "metadata"));
    }
    label.append(input, info);
    if (!hotel || !item?.sourceUrl) return label;
    const card = element("div", undefined, "builder-hotel-card");
    const photo = item.imageUrl;
    if (photo) {
      const image = document.createElement("img");
      image.className = "builder-hotel-photo";
      image.alt = item.name;
      image.loading = "lazy";
      image.referrerPolicy = "no-referrer";
      image.addEventListener("error", () => image.remove(), { once: true });
      image.src = photo;
      card.append(image);
    }
    const links = element("div", undefined, "builder-hotel-links");
    const proof = group.proofs?.get(item.objectId);
    const website = proof?.metadata?.website?.value;
    const source = proof?.price?.level === "market" ? "Источник сведений об отеле" : "Источник цены";
    for (const [href, title] of [[item.sourceUrl, source], [website, "Сайт гостиницы"]]) {
      if (!href) continue;
      const link = element("a", title, "metadata");
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      links.append(link);
    }
    card.append(label, links);
    return card;
  }

  async function find(group, trip, signal) {
    const limit = group.settings.querySelector("[data-builder-limit]");
    const body = {
      taskId: crypto.randomUUID(), trip, targets: group.kind,
      count: group.settings.querySelector("[data-builder-count]").valueAsNumber,
      maxTotalRub: group.kind === "hotels" || !limit.value ? null : limit.valueAsNumber,
      ...(group.kind === "hotels" ? { targetHotelTotalRub: limit.value ? limit.valueAsNumber : null } : {}),
      refinement: group.settings.querySelector("[data-builder-refinement]").value.trim() || null,
      excludedObjectIds: [...group.items.keys()],
    };
    const previous = group.submission;
    const submission = repeatSubmission(previous, body);
    submission.analysis ??= { status: "pending", stages: [] };
    group.submission = submission;
    renderPreferences();
    const result = await runTask(group.panel, "recommendations", submission, signal);
    if (signal.aborted || group.submission !== submission) return;
    if (result && group.kind === "hotels") {
      await readPreferences(group, submission, signal);
      if (signal.aborted || group.submission !== submission) return;
    } else {
      void readPreferences(group, submission, signal);
    }
    if (!result) {
      group.more.hidden = false;
      group.more.textContent = submission.accepted && submission.retry ? "Продолжить опрос" : "Повторить подбор";
      return;
    }
    const batch = result.results?.[group.kind];
    const hotelReport = group.kind === "hotels" ? submission.analysis.hotels : null;
    const coverage = hotelReport && batch ? hotelCoverage(hotelReport, batch) : "";
    if (!batch || batch.status === "failed") {
      group.more.hidden = false;
      group.more.textContent = "Повторить подбор";
      status(group.panel, "Ошибка", coverage || (batch?.error?.message ?? "Подбор завершился ошибкой."), "bad");
      return;
    }
    group.proofs ??= new Map();
    for (const proof of hotelReport?.hotels ?? []) group.proofs.set(proof.item.objectId, proof);
    for (const item of batch.items) group.items.set(item.objectId, item);
    const choices = [...group.items.values()].map((item) => choice(group, item));
    if (group.kind === "hotels" && choices.length) choices.unshift(choice(group, null));
    group.panel.querySelector("[data-builder-candidates]").replaceChildren(...choices);
    group.more.hidden = batch.hasMore === false;
    group.more.textContent = "Подобрать ещё";
    const partial = batch.status === "partial";
    status(group.panel, partial ? "Частичный результат" : "Готово",
      coverage || (batch.error?.message ?? (batch.items.length ? "" : "Подходящих вариантов в этой выдаче нет.")), partial ? "" : "good");
  }

  byId("builder-example").addEventListener("click", fillExample);
  form.addEventListener("input", (event) => {
    if (event.target.matches("[data-builder-target]")) {
      const group = groups[0];
      const hadResults = group.submission !== null || group.items.size > 0 || !group.more.hidden;
      group.items.clear();
      group.proofs?.clear();
      group.submission = null;
      group.panel.querySelector("[data-builder-candidates]").replaceChildren();
      group.more.hidden = !hadResults;
      group.more.textContent = "Подобрать с новой суммой";
      status(group.panel, "");
      updateTrace(group.panel, "", null);
      selectedHotel = null;
      resetEstimate();
      renderPreferences();
      return;
    }
    if (!event.target.closest("[data-trip]")) return;
    if (event.target === fields.city) {
      destination = null;
      fields.city.setCustomValidity(fields.city.value.trim() ? "Выберите город из подсказок." : "");
      if (working) {
        controller.abort();
        controller = new AbortController();
        working = false;
        updateControls();
      }
      suggestCity();
    }
    fields.endDate.min = fields.startDate.value;
    resetResults();
  });
  form.addEventListener("invalid", (event) => {
    const options = event.target.closest(".builder-options");
    if (options) options.open = true;
  }, true);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!destination) return;
    const trip = tripSnapshot();
    resetResults();
    byId("builder-empty").hidden = true;
    byId("builder-tabs").hidden = false;
    selectTab(tabs[0]);
    work((signal) => Promise.all(groups.map((group) => find(group, trip, signal))));
  });
  estimate.addEventListener("click", () => {
    const trip = tripSnapshot();
    const hotel = groups[0].items.get(selectedHotel);
    const items = [...selectedAttractions].map((id) => groups[1].items.get(id));
    const selected = ({ objectId, price }) => ({ objectId, price });
    const body = {
      taskId: crypto.randomUUID(), trip, selectedHotel: hotel ? selected(hotel) : null,
      selectedAttractions: items.map(selected),
    };
    const submission = repeatSubmission(estimateSubmission, body);
    resetEstimate();
    estimateSubmission = submission;
    work(async (signal) => {
      const result = await runTask(budget, "budget", submission, signal);
      if (signal.aborted || !result) return;
      if (result.status !== "succeeded") {
        status(budget, "Ошибка", result.error?.message ?? "Расчёт завершился ошибкой.", "bad");
        return;
      }
      expenseList.replaceChildren(...Object.entries(expenses).map(([key, label]) => {
        const item = element("div");
        item.append(element("dt", label), element("dd", money.format(result.expenses[key])));
        return item;
      }));
      expenseList.hidden = false;
      status(budget, "Готово", "", "good");
    });
  });

  updateControls();
  return { open, reset };
}

function repeatSubmission(previous, body) {
  if (previous?.retry && JSON.stringify(previous.body) === JSON.stringify({ ...body, taskId: previous.body.taskId })) {
    return previous;
  }
  return { body };
}
