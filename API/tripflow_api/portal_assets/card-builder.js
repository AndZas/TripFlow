import { element, preferenceAttempts, preferenceInterpretation, preferencePath, scopes } from "./preference-view.js";

const labels = { hotels: scopes.hotels, attractions: scopes.attractions };
const money = new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 });
const expenses = {
  foodTotalRub: "Питание", localTransportTotalRub: "Городской транспорт",
  otherExpensesTotalRub: "Прочие расходы", reserveTotalRub: "Резерв",
};
const pollTimeoutMs = 120_000;

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
  if (typeof item.price === "number") return money.format(item.price) + " за проживание группы";
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
  let selectedHotel = null;
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
      destinationId: fields.destinationId.value,
      startDate: fields.startDate.value,
      endDate: fields.endDate.value,
      travelers: fields.travelers.valueAsNumber,
      budgetRub: fields.budgetRub.valueAsNumber,
      preferences: fields.preferences.value.trim() || null,
    };
  }

  function resetEstimate() {
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
    form.reset();
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
    byId("builder-inputs").disabled = working || !initialized;
    estimate.disabled = working;
    for (const group of groups) {
      group.more.disabled = working;
      for (const choice of group.panel.querySelectorAll("input")) choice.disabled = working;
    }
  }

  async function open() {
    if (initialized) return;
    const signal = controller.signal;
    try {
      const { payload } = await request("/builder/destinations", undefined, signal);
      if (signal.aborted) return;
      fields.destinationId.replaceChildren(...payload.map((destination) => {
        const option = element("option", destination.city);
        option.value = destination.id;
        return option;
      }));
      initialized = true;
      fillExample();
      updateControls();
    } catch (error) {
      if (!signal.aborted) throw error;
    }
  }

  function reset() {
    controller.abort();
    controller = new AbortController();
    initialized = false;
    working = false;
    form.reset();
    fields.destinationId.replaceChildren();
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

  async function runTask(panel, operation, body, signal) {
    status(panel, "Отправка");
    updateTrace(panel, operation, body);
    try {
      const accepted = await request("/builder/" + operation, body, signal);
      if (signal.aborted) return null;
      showResponse(panel, accepted.payload);
      status(panel, "В обработке");
      const deadline = Date.now() + pollTimeoutMs;
      while (!signal.aborted) {
        const reply = await request("/builder/tasks/" + encodeURIComponent(body.taskId), undefined, signal);
        if (signal.aborted) return null;
        showResponse(panel, reply.payload);
        if (reply.payload.status === "completed") return reply.payload.result;
        if (Date.now() >= deadline) throw new Error("Задача ещё выполняется. Статус можно проверить позже в журнале задач.");
        const retry = Number(reply.response.headers.get("Retry-After")) || 2;
        await pause(retry * 1000, signal);
      }
    } catch (error) {
      if (!signal.aborted) {
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
      const details = [item.category, item.stars ? item.stars + " ★" : null, formatPrice(item)].filter(Boolean);
      info.append(element("span", details.join(" · "), "metadata"));
    }
    label.append(input, info);
    return label;
  }

  async function find(group, trip, signal) {
    const limit = group.settings.querySelector("[data-builder-limit]");
    const body = {
      taskId: crypto.randomUUID(), trip, targets: group.kind,
      count: group.settings.querySelector("[data-builder-count]").valueAsNumber,
      maxTotalRub: limit.value ? limit.valueAsNumber : null,
      refinement: group.settings.querySelector("[data-builder-refinement]").value.trim() || null,
      excludedObjectIds: [...group.items.keys()],
    };
    const submission = { body, analysis: { status: "pending", stages: [] } };
    group.submission = submission;
    renderPreferences();
    const result = await runTask(group.panel, "recommendations", body, signal);
    if (signal.aborted || group.submission !== submission) return;
    void readPreferences(group, submission, signal);
    if (!result) return;
    const batch = result.results?.[group.kind];
    if (!batch || batch.status === "failed") {
      status(group.panel, "Ошибка", batch?.error?.message ?? "Подбор завершился ошибкой.", "bad");
      return;
    }
    for (const item of batch.items) group.items.set(item.objectId, item);
    const choices = [...group.items.values()].map((item) => choice(group, item));
    if (group.kind === "hotels" && choices.length) choices.unshift(choice(group, null));
    group.panel.querySelector("[data-builder-candidates]").replaceChildren(...choices);
    group.more.hidden = batch.hasMore === false;
    const partial = batch.status === "partial";
    status(group.panel, partial ? "Частичный результат" : "Готово",
      batch.error?.message ?? (batch.items.length ? "" : "Подходящих вариантов в этой выдаче нет."), partial ? "" : "good");
  }

  byId("builder-example").addEventListener("click", fillExample);
  form.addEventListener("input", (event) => {
    if (!event.target.closest("[data-trip]")) return;
    fields.endDate.min = fields.startDate.value;
    resetResults();
  });
  form.addEventListener("invalid", (event) => {
    const options = event.target.closest(".builder-options");
    if (options) options.open = true;
  }, true);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
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
    resetEstimate();
    work(async (signal) => {
      const result = await runTask(budget, "budget", body, signal);
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
