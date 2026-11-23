import { setupCardBuilder } from "./card-builder.js";
import { element, preferenceAttempts, preferenceInterpretation, preferencePath, preferenceSummary } from "./preference-view.js";

const $ = (id) => document.getElementById(id);
const app = $("app");
const access = $("access");
const form = $("access-form");
const dialog = $("secret-dialog");
const dates = new Intl.DateTimeFormat("ru", { dateStyle: "medium", timeStyle: "short" });
const roles = {owner: "Владелец", admin: "Администратор", developer: "Разработчик"};
let account = null;
let registration = false;
let noticeTimer;
const builder = setupCardBuilder(portalRequest);
let selectedPreference = null;

function showNotice(message, error = false) {
  const notice = $("notice");
  notice.textContent = message;
  notice.classList.toggle("error", error);
  notice.hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { notice.hidden = true; }, 6500);
}

async function portalRequest(path, body, signal) {
  const options = { cache: "no-store", signal };
  if (body !== undefined) {
    options.method = "POST";
    options.headers = { "Content-Type": "application/json", "X-Portal-Request": "1" };
    options.body = JSON.stringify(body);
  }
  const response = await fetch("/portal/data" + path, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && account) {
      showAccess(true);
    }
    const message = typeof payload.detail === "string" ? payload.detail : "Проверьте поля формы и повторите действие.";
    const error = new Error(message);
    error.payload = payload;
    throw error;
  }
  return { payload, response };
}

async function call(path, body) {
  return (await portalRequest(path, body)).payload;
}

async function busy(button, action) {
  button.disabled = true;
  try {
    await action();
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    button.disabled = false;
  }
}

function formatDate(seconds) {
  return seconds ? dates.format(new Date(seconds * 1000)) : "—";
}

function setAccessMode(register) {
  registration = register;
  $("access-title").textContent = register ? "Запрос доступа" : "Вход в кабинет";
  $("access-description").textContent = register ? "Для нового аккаунта задайте пароль от 12 символов. Для повторной заявки используйте прежний пароль." : "Войдите, чтобы управлять ключом и видеть свои задачи.";
  $("access-submit").textContent = register ? "Отправить заявку" : "Войти";
  $("access-switch").textContent = register ? "Уже есть аккаунт" : "Запросить доступ";
  $("request-feedback").hidden = true;
  form.elements.password.autocomplete = register ? "new-password" : "current-password";
  form.elements.password.value = "";
}

function showAccess(enabled) {
  account = null;
  builder.reset();
  if (dialog.open) dialog.close();
  $("task-rows").replaceChildren();
  $("preference-summary").replaceChildren();
  $("preference-summary-panel").hidden = true;
  clearPreferenceTask();
  $("accounts").replaceChildren();
  $("requests").replaceChildren();
  form.reset();
  setAccessMode(false);
  app.hidden = true;
  $("boot").hidden = true;
  access.hidden = false;
  form.hidden = !enabled;
  $("unconfigured").hidden = enabled;
}

function renderKeys() {
  for (const card of document.querySelectorAll("[data-key]")) {
    const key = account.keys[card.dataset.key];
    const active = Boolean(key.hint);
    const status = card.querySelector("[data-key-status]");
    status.textContent = active ? "Активен" : "Не выпущен";
    status.classList.toggle("good", active);
    card.querySelector("[data-key-hint]").textContent = active ? "•••• " + key.hint : "—";
    card.querySelector("[data-key-issued]").textContent = active ? "Выпущен " + formatDate(key.issuedAt) : "";
    card.querySelector('[data-key-action="issue"]').textContent = active ? "Перевыпустить" : "Выпустить ключ";
    card.querySelector('[data-key-action="revoke"]').hidden = !active;
  }
  $("base-url").textContent = window.location.origin;
}

function renderAccount() {
  $("account-role").textContent = roles[account.role];
  $("admin-nav").hidden = account.role === "developer";
  renderKeys();
}

function showApp(current) {
  account = current;
  $("boot").hidden = true;
  access.hidden = true;
  app.hidden = false;
  $("account-email").textContent = account.email;
  $("initials").textContent = account.email.slice(0, 2).toUpperCase();
  renderAccount();
  selectView("keys");
}

async function refreshAccount() {
  const status = await call("/session");
  if (!status.account) {
    showAccess(status.enabled);
    return;
  }
  account = status.account;
  renderAccount();
}

function showSecret(title, description, secret) {
  $("secret-title").textContent = title;
  $("secret-description").textContent = description;
  $("secret-value").value = secret;
  $("copy-secret").textContent = "Копировать";
  dialog.showModal();
}

dialog.addEventListener("close", () => { $("secret-value").value = ""; });
$("copy-secret").addEventListener("click", async () => {
  const input = $("secret-value");
  try {
    await navigator.clipboard.writeText(input.value);
    $("copy-secret").textContent = "Скопировано";
  } catch {
    input.focus();
    input.select();
    $("copy-secret").textContent = "Скопируйте выделенное";
  }
});

function selectView(view) {
  for (const button of document.querySelectorAll("[data-view]")) {
    if (button.dataset.view === view) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  for (const section of document.querySelectorAll("[data-section]")) {
    section.hidden = section.dataset.section !== view;
  }
}

function renderActivity(tasks, table, empty, openPreferences) {
  const rows = tasks.map((task) => {
    const row = document.createElement("tr");
    const id = document.createElement("code");
    id.textContent = task.taskId;
    row.insertCell().append(id);
    row.insertCell().textContent = task.operation === "budget" ? "Смета" : "Подбор";
    row.insertCell().textContent = formatDate(task.createdAt);
    const status = document.createElement("span");
    status.className = "pill";
    status.classList.toggle("good", task.status === "completed");
    status.textContent = task.status === "completed" ? "Завершена" : "В обработке";
    row.insertCell().append(status);
    if (openPreferences) {
      const cell = row.insertCell();
      if (task.operation === "recommendations") {
        const button = element("button", "Детали", "text-button");
        button.type = "button";
        button.setAttribute("aria-label", "Разбор задачи " + task.taskId);
        button.addEventListener("click", () => openPreferences(task.taskId));
        cell.append(button);
      }
    }
    return row;
  });
  table.querySelector("tbody").replaceChildren(...rows);
  table.hidden = !rows.length;
  empty.hidden = Boolean(rows.length);
}

function clearPreferenceTask() {
  selectedPreference = null;
  $("preference-task").replaceChildren();
  $("preference-task").hidden = true;
}

async function openPreferenceTask(taskId) {
  const selection = { taskId };
  selectedPreference = selection;
  const panel = $("preference-task");
  const heading = element("h2", "Разбор пожеланий в задаче");
  const task = element("code", taskId);
  panel.replaceChildren(heading, task, element("p", "Загрузка…"));
  panel.hidden = false;
  panel.focus();
  try {
    const record = await call(preferencePath(taskId));
    if (selectedPreference !== selection) return;
    const interpretation = preferenceInterpretation([{
      category: record.category, preferences: record.preferences, refinement: record.refinement, analysis: record,
    }]);
    if (record.status !== "historical") {
      const attempts = preferenceAttempts(record, taskId);
      attempts.open = true;
      interpretation.append(attempts);
    }
    panel.replaceChildren(heading, task, interpretation);
  } catch (error) {
    if (selectedPreference === selection) panel.replaceChildren(heading, task, element("p", error.message));
  }
}

async function loadActivity() {
  const current = account?.id;
  const { tasks, summary, preferences } = await call("/activity");
  if (account?.id !== current) return;
  $("activity-summary").textContent = "Всего задач · " + summary.total + "　 В обработке · " + summary.pending + "　 Завершено · " + (summary.total - summary.pending);
  $("preference-summary").replaceChildren(preferenceSummary(preferences));
  $("preference-summary-panel").hidden = false;
  renderActivity(tasks, $("task-table"), $("tasks-empty"), openPreferenceTask);
  if (selectedPreference) await openPreferenceTask(selectedPreference.taskId);
}

async function loadAccounts() {
  await refreshAccount();
  if (!account) return;
  if (account.role === "developer") {
    selectView("keys");
    return;
  }
  const { accounts } = await call("/admin/accounts");
  const isOwner = account.role === "owner";
  $("accounts").replaceChildren();
  $("requests").replaceChildren();
  const labels = {pending: "Ожидает", rejected: "Отклонено", approved: "Доступ открыт", disabled: "Отключено"};
  for (const person of accounts) {
    const node = $("account-template").content.cloneNode(true);
    const role = roles[person.role];
    node.querySelector("[data-email]").textContent = person.email;
    node.querySelector("[data-role]").textContent = role + " · " + formatDate(person.createdAt);
    const status = node.querySelector("[data-status]");
    status.textContent = person.status === "pending" && person.ownerReview ? "Повторная заявка · владельцу" : labels[person.status];
    status.classList.toggle("good", person.active);
    node.querySelector("[data-keys]").textContent = person.keys.api.hint ? "Ключ · •••• " + person.keys.api.hint : "";
    const actions = node.querySelector("[data-actions]");
    const path = "/admin/accounts/" + encodeURIComponent(person.id);
    function addAction(label, action) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = action === "approve" ? "button primary" : "button secondary";
      button.textContent = label;
      button.addEventListener("click", () => busy(button, async () => {
        if (action === "disable" && !confirm("Завершить сессии и отозвать ключ? Для восстановления доступа понадобится новая заявка.")) return;
        await call(path, {action});
        await loadAccounts();
      }));
      actions.append(button);
    }
    if (person.status === "pending" && (isOwner || !person.ownerReview)) {
      addAction("Одобрить", "approve");
      addAction("Отклонить", "reject");
    } else if (person.role !== "owner" && person.status === "approved") {
      if (isOwner) {
        addAction("Отключить доступ", "disable");
        if (person.role === "developer") addAction("Назначить администратором", "promote");
        else addAction("Снять роль администратора", "demote");
      }
    }
    const activity = node.querySelector("details");
    activity.addEventListener("toggle", async () => {
      if (!activity.open) return;
      try {
        const { tasks, summary, usage } = await call(path + "/activity");
        for (const item of activity.querySelectorAll("[data-metric]")) {
          const name = item.dataset.metric;
          item.textContent = name === "lastRequestHour" ? formatDate(usage[name]) : usage[name].toLocaleString("ru");
        }
        activity.querySelector("[data-task-total]").textContent = "Всего задач · " + summary.total;
        renderActivity(tasks, activity.querySelector("table"), activity.querySelector("[data-empty]"));
      } catch (error) {
        showNotice(error.message, true);
      }
    });
    $(person.status === "pending" ? "requests" : "accounts").append(node);
  }
  if (!$("requests").children.length) $("requests").textContent = "Новых заявок нет.";
}

$("access-switch").addEventListener("click", () => setAccessMode(!registration));
form.addEventListener("submit", (event) => {
  event.preventDefault();
  busy($("access-submit"), async () => {
    const values = Object.fromEntries(new FormData(form));
    const result = await call(registration ? "/register" : "/login", values);
    if (result.status === "pending") {
      setAccessMode(false);
      $("request-feedback").textContent = "Заявка отправлена. После одобрения войдите с этим email и паролем.";
      $("request-feedback").hidden = false;
      return;
    }
    form.reset();
    showApp(result.account);
  });
});

$("logout").addEventListener("click", () => busy($("logout"), async () => {
  await call("/logout", {});
  showAccess(true);
}));

for (const button of document.querySelectorAll("[data-view]")) {
  button.addEventListener("click", () => {
    const view = button.dataset.view;
    selectView(view);
    if (view === "builder") busy(button, builder.open);
    if (view === "activity") busy(button, loadActivity);
    if (view === "admin") busy(button, loadAccounts);
  });
}

for (const button of document.querySelectorAll("[data-key-action]")) {
  button.addEventListener("click", () => {
    const kind = button.closest("[data-key]").dataset.key;
    const action = button.dataset.keyAction;
    if (account.keys[kind].hint && !confirm("Текущий ключ перестанет действовать. Продолжить?")) return;
    busy(button, async () => {
      const result = await call("/keys/" + kind + "/" + action, {});
      if (action === "issue") {
        const title = "Новый X-API-Key";
        showSecret(title, "Скопируйте значение в конфигурацию сервиса. В кабинете останутся последние символы.", result.key);
      } else {
        showNotice("Ключ отозван.");
      }
      await refreshAccount();
    });
  });
}

$("refresh-tasks").addEventListener("click", () => busy($("refresh-tasks"), loadActivity));
$("refresh-accounts").addEventListener("click", () => busy($("refresh-accounts"), loadAccounts));

try {
  const initial = await call("/session");
  if (initial.account) showApp(initial.account);
  else showAccess(initial.enabled);
} catch {
  $("boot").textContent = "Кабинет недоступен. Обновите страницу.";
}
