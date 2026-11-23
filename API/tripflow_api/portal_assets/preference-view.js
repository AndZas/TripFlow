export const preferencePath = (taskId) => "/preferences/tasks/" + encodeURIComponent(taskId);

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
