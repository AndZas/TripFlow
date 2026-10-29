const $ = id => document.getElementById(id);
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = value => new Intl.NumberFormat('ru-RU', {maximumFractionDigits:2}).format(Number(value)) + ' ₽';
const map = item => `https://www.openstreetmap.org/?mlat=${encodeURIComponent(item.lat)}&mlon=${encodeURIComponent(item.lon)}#map=15/${encodeURIComponent(item.lat)}/${encodeURIComponent(item.lon)}`;
let selected = null, selectionQuery = '', result = null, tab = 'hotels', timer, searchVersion = 0, busy = false;

async function api(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || data.error || 'Не удалось получить данные.');
  return data;
}
function choose(city, query) {
  selected = city; selectionQuery = query;
  $('city').value = city.city;
  $('suggestions').hidden = true;
  $('city').setAttribute('aria-expanded', 'false');
  $('explore').disabled = busy;
  $('notice').textContent = '';
}
async function search(query, automatic = false) {
  const version = ++searchVersion;
  if (query.length < 2) { $('suggestions').hidden = true; return; }
  try {
    const response = await api('/api/cities?q=' + encodeURIComponent(query));
    if (version !== searchVersion) return;
    const items = response.data;
    if (automatic && items.length) {
      choose(items.find(x => x.city.toLocaleLowerCase('ru') === query.toLocaleLowerCase('ru')) || items[0], query);
      return explore();
    }
    $('suggestions').replaceChildren();
    if (!items.length) {
      const p = document.createElement('p'); p.style.padding = '0 20px'; p.textContent = 'Город не найден. Попробуйте другое название.';
      $('suggestions').append(p);
    }
    items.forEach(city => {
      const button = document.createElement('button'); button.className = 'suggestion'; button.setAttribute('role','option');
      button.innerHTML = `<strong>${escape(city.city)}</strong><small>${escape(city.region)} · Россия · ${escape(city.source)}</small>`;
      button.onclick = () => choose(city, query);
      $('suggestions').append(button);
    });
    $('suggestions').hidden = false; $('city').setAttribute('aria-expanded', 'true');
  } catch (e) { if (version === searchVersion) $('notice').textContent = e.message; }
}
$('city').addEventListener('input', () => {
  selected = null; $('explore').disabled = true; ++searchVersion; clearTimeout(timer);
  timer = setTimeout(() => search($('city').value.trim()), 450);
});
$('city').addEventListener('keydown', e => {
  if (e.key === 'Escape') { $('suggestions').hidden = true; $('city').setAttribute('aria-expanded','false'); }
  if (e.key === 'ArrowDown') { e.preventDefault(); $('suggestions').querySelector('button')?.focus(); }
  if (e.key === 'Enter' && selected) explore();
});
$('suggestions').addEventListener('keydown', e => {
  if (e.key === 'ArrowDown') { e.preventDefault(); document.activeElement.nextElementSibling?.focus(); }
  if (e.key === 'ArrowUp') { e.preventDefault(); (document.activeElement.previousElementSibling || $('city')).focus(); }
});
document.addEventListener('click', e => { if (!e.target.closest('.search-panel')) $('suggestions').hidden = true; });
document.querySelectorAll('[data-city]').forEach(button => button.onclick = () => { if (!busy) search(button.dataset.city, true); });
$('explore').onclick = explore;

async function explore() {
  if (!selected || busy) return;
  busy = true; $('explore').disabled = true; $('city').disabled = true;
  $('empty').hidden = true; $('results').hidden = true;
  $('notice').innerHTML = '<div class="loading"><span class="spinner"></span><span>Ищем отели и места, читаем справочники… Обычно это занимает несколько секунд.</span></div>';
  try {
    result = await api(`/api/explore?q=${encodeURIComponent(selectionQuery)}&id=${encodeURIComponent(selected.id)}`);
    render(); $('notice').textContent = '';
  } catch(e) { $('notice').textContent = e.message; $('empty').hidden = false; }
  finally { busy = false; $('explore').disabled = !selected; $('city').disabled = false; }
}
function render() {
  const {city, blocks} = result;
  $('results').hidden = false;
  $('city-title').textContent = city.city;
  $('city-subtitle').textContent = `${city.region || 'Россия'} · ${city.lat.toFixed(4)}° N, ${city.lon.toFixed(4)}° E · география: ${city.source}`;
  $('city-map').href = map(city);
  const meta = blocks.metadata.data || {};
  $('metadata').innerHTML = [['Страна',meta.country || 'Россия'],['Часовой пояс',meta.timezone || city.timezone || 'Нет данных'],['Валюта',meta.currency || 'Нет данных'],['Языки страны',meta.languages || 'Нет данных']].map(([label,value]) => `<div class="meta"><small>${escape(label)}</small><strong>${escape(value)}</strong></div>`).join('');
  $('sources').innerHTML = Object.values(blocks).map(block => `<div class="source ${block.status === 'ok' ? '' : 'error'}"><span class="status">${block.status === 'ok' ? '✓' : '!'}</span><strong>${escape(block.source)}</strong><small>${block.status === 'ok' ? `Получено · ${block.durationMs} мс` : escape(block.message)}</small></div>`).join('');
  $('fetch-time').textContent = `Данные: ${new Date(result.fetchedAt).toLocaleTimeString('ru-RU')} · кеш до 10 минут`;
  [['hotels','hotel-count'],['places','place-count'],['rates','rate-count']].forEach(([name,id]) => $(id).textContent = blocks[name].data?.length || 0);
  $('json').textContent = JSON.stringify(result,null,2);
  renderTab();
}
document.querySelectorAll('[data-tab]').forEach(button => button.onclick = () => {tab = button.dataset.tab; renderTab();});
function renderTab() {
  if (!result) return;
  document.querySelectorAll('[data-tab]').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  const block = result.blocks[tab], items = block.data || [];
  $('tab-description').textContent = {
    hotels:'Реальные объекты Russhotels. Показанные тарифы опубликованы поставщиком; актуальность, единица цены и наличие на даты требуют отдельной проверки. Это не предложения бронирования.',
    places:'Музеи и достопримечательности в радиусе 7 км от центра. Сведения Geoapify на основе OpenStreetMap; неизвестная стоимость билета не означает бесплатный вход.',
    rates:'Справочные средние цены Росстата за сентябрь 2026 года. Для каждой ставки указан город, регион или страна. Это ориентиры услуг, а не итоговый бюджет поездки.'
  }[tab];
  if (!items.length) {
    $('content').innerHTML = `<div class="block-empty">${escape(block.message || 'Подходящих данных в этом запросе не найдено.')}<br>Другие источники доступны независимо.</div>`;
    return;
  }
  if (tab === 'rates') {
    const scopes = {city:'Город',region:'Регион',country:'Страна'};
    $('content').innerHTML = '<div class="rates">' + items.map(r => `<div class="rate"><div>${escape(r.source_label_with_unit)}<small>Период: ${escape(r.reference_period)}</small></div><strong>${money(r.amount_rub)}</strong><div class="scope">${escape(scopes[r.scope])}<br>${escape(r.territory_name)}</div></div>`).join('') + '</div>';
    return;
  }
  $('content').innerHTML = '<div class="cards">' + items.map((item,index) => {
    const rooms = item.rooms || [];
    const website = /^https?:\/\//i.test(item.website || '') ? `<a href="${escape(item.website)}" target="_blank" rel="noreferrer">Сайт ↗</a>` : '';
    return `<article class="card"><div class="card-top"><span class="number">${String(index+1).padStart(2,'0')}</span><span class="badge">${tab === 'hotels' ? 'Проживание' : 'Достопримечательность'}</span></div><h3>${escape(item.name)}</h3><div class="address">${escape(item.address || 'Адрес не указан')}</div>${item.description ? `<p class="description">${escape(item.description.slice(0,220))}${item.description.length>220 ? "…" : ""}</p>${item.description.length>220 ? `<details><summary>Полное описание</summary><p class="description">${escape(item.description)}</p></details>` : ""}` : ''}${item.openingHours ? `<p class="description">Часы: ${escape(item.openingHours)}</p>` : ''}${tab === 'hotels' ? `<details><summary>${rooms.length ? 'Опубликованные тарифы ('+rooms.length+')' : 'Тарифы не получены'}</summary>${rooms.map(r => `<div class="room">${escape(r.name)}<br>${escape(r.placement)}<br><strong>${money(r.priceRub)}</strong>${r.updatedAt ? `<br>Обновление тарифа: ${escape(formatTimestamp(r.updatedAt))}` : ''}</div>`).join('')}<p>Единица и применимость тарифа не подтверждены для поездки.</p></details>${item.checkIn ? `<p class="address">Заезд: ${escape(item.checkIn)} · выезд: ${escape(item.checkOut || '—')}</p>` : ''}` : '<p class="address">Стоимость билета: нет подтверждённых данных</p>'}<div class="card-footer"><span>${escape(item.source)}</span><span>${website} <a href="${escape(map(item))}" target="_blank" rel="noreferrer">На карте ↗</a></span></div></article>`;
  }).join('') + '</div>';
}
function formatTimestamp(value) {
  const timestamp = Number(value);
  return Number.isFinite(timestamp) && timestamp > 0 ? new Date(timestamp*1000).toLocaleDateString('ru-RU') : String(value);
}
