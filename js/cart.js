/**
 * ООО «Альянс» — Cart Manager
 * localStorage-based shopping cart
 */

const Cart = {
  STORAGE_KEY: 'alliance_cart',

  getItems() {
    try {
      return JSON.parse(localStorage.getItem(this.STORAGE_KEY)) || [];
    } catch {
      return [];
    }
  },

  save(items) {
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(items));
    this.updateUI();
  },

  addItem(product) {
    // product: { id, title, category, price_rub, image, slug }
    const items = this.getItems();
    const existing = items.find(i => i.id === product.id);
    if (existing) {
      existing.qty = (existing.qty || 1) + 1;
    } else {
      items.push({ ...product, qty: 1 });
    }
    this.save(items);
    showToast('Товар добавлен в корзину');
  },

  removeItem(id) {
    const items = this.getItems().filter(i => i.id !== id);
    this.save(items);
  },

  updateQty(id, qty) {
    const items = this.getItems();
    const item = items.find(i => i.id === id);
    if (item) {
      item.qty = Math.max(1, parseInt(qty) || 1);
      this.save(items);
    }
  },

  getTotal() {
    return this.getItems().reduce((sum, i) => sum + (i.price_rub * (i.qty || 1)), 0);
  },

  getCount() {
    return this.getItems().reduce((sum, i) => sum + (i.qty || 1), 0);
  },

  clear() {
    localStorage.removeItem(this.STORAGE_KEY);
    this.updateUI();
  },

  updateUI() {
    // Update cart count badge
    const badge = document.querySelector('.cart-count');
    const count = this.getCount();
    if (badge) {
      badge.textContent = count;
      badge.style.display = count > 0 ? 'flex' : 'none';
    }
    // Re-render cart page if open
    if (document.getElementById('cart-container')) {
      renderCartPage();
    }
  }
};

// ── Toast notification ──
function showToast(msg) {
  let toast = document.querySelector('.toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2500);
}

// ── Render cart page ──
function renderCartPage() {
  const container = document.getElementById('cart-container');
  if (!container) return;
  const items = Cart.getItems();
  if (items.length === 0) {
    container.innerHTML = `
      <div class="cart-empty">
        <div class="cart-empty-icon">🛒</div>
        <h2>Корзина пуста</h2>
        <p>Добавьте товары из <a href="/products/">каталога</a></p>
      </div>`;
    return;
  }

  const itemsHtml = items.map(item => `
    <div class="cart-item" data-id="${item.id}">
      <img class="cart-item__img" src="${item.image || '/img/no-image.png'}" alt="${item.title}" loading="lazy">
      <div>
        <div class="cart-item__name">${item.title}</div>
        <div class="cart-item__cat">${item.category || ''}</div>
        <div class="cart-item__qty">
          <div class="qty-ctrl">
            <button class="qty-btn" onclick="Cart.updateQty('${item.id}', ${(item.qty||1)-1})">−</button>
            <input class="qty-input" type="number" value="${item.qty||1}" min="1"
              onchange="Cart.updateQty('${item.id}', this.value)">
            <button class="qty-btn" onclick="Cart.updateQty('${item.id}', ${(item.qty||1)+1})">+</button>
          </div>
        </div>
        <div class="cart-item__price">${formatPrice(item.price_rub * (item.qty||1))} ₽</div>
      </div>
      <button class="cart-item__remove" onclick="Cart.removeItem('${item.id}')" title="Удалить">✕</button>
    </div>`).join('');

  const total = Cart.getTotal();
  container.innerHTML = `
    <div id="cart-items">${itemsHtml}</div>
    <div class="cart-summary">
      <div class="cart-total">Итого: <span>${formatPrice(total)} ₽</span></div>
      <button class="btn-order" onclick="openOrderModal()">Оформить заказ →</button>
    </div>`;
}

// ── Order modal ──
function openOrderModal() {
  const items = Cart.getItems();
  if (!items.length) { showToast('Корзина пуста'); return; }
  const modal = document.getElementById('order-modal');
  if (!modal) return;

  // Fill preview
  const preview = modal.querySelector('.order-cart-preview');
  if (preview) {
    const rows = items.map(i =>
      `<div class="order-cart-item"><span>${i.title} × ${i.qty||1}</span><span>${formatPrice(i.price_rub*(i.qty||1))} ₽</span></div>`
    ).join('');
    preview.innerHTML = rows +
      `<div class="order-cart-total"><span>Итого</span><span>${formatPrice(Cart.getTotal())} ₽</span></div>`;
  }

  modal.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeOrderModal() {
  const modal = document.getElementById('order-modal');
  if (modal) modal.classList.remove('open');
  document.body.style.overflow = '';
}

// ── Order form submit ──
function submitOrder(event) {
  event.preventDefault();
  const form = event.target;
  const data = new FormData(form);
  const items = Cart.getItems();

  // Build order details string
  const orderLines = items.map(i => `${i.title} × ${i.qty||1} = ${formatPrice(i.price_rub*(i.qty||1))} ₽`).join('\n');
  const total = formatPrice(Cart.getTotal());

  // Append cart to form data
  data.set('order_items', orderLines);
  data.set('order_total', total + ' ₽');
  data.set('_subject', `Заказ от ${data.get('name')} — ${total} ₽`);

  const btn = form.querySelector('.form-submit');
  btn.disabled = true;
  btn.textContent = 'Отправляем...';

  fetch(form.action, {
    method: 'POST',
    body: data,
    headers: { 'Accept': 'application/json' }
  })
  .then(r => r.ok ? r.json() : Promise.reject(r))
  .then(() => {
    closeOrderModal();
    Cart.clear();
    showOrderSuccess(data.get('name'), total);
  })
  .catch(() => {
    btn.disabled = false;
    btn.textContent = 'Оформить заказ';
    showToast('Ошибка отправки. Позвоните нам: +7 (812) 936-74-60');
  });
}

function showOrderSuccess(name, total) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `
    <div class="modal" style="text-align:center">
      <div style="font-size:56px;margin-bottom:16px">✅</div>
      <h2>Заказ получен!</h2>
      <p class="sub">Спасибо, ${name}! Мы свяжемся с вами в ближайшее время и выставим счёт от ООО «Альянс» на сумму <strong>${total} ₽</strong>.</p>
      <button class="form-submit" onclick="this.closest('.modal-overlay').remove()" style="margin-top:24px">Закрыть</button>
    </div>`;
  document.body.appendChild(overlay);
}

// ── Print invoice ──
function printInvoice() {
  const items = Cart.getItems();
  if (!items.length) return;

  const now = new Date();
  const dateStr = now.toLocaleDateString('ru-RU');
  const invoiceNum = Math.floor(Math.random() * 9000) + 1000;

  const rows = items.map((i, idx) => `
    <tr>
      <td>${idx+1}</td>
      <td>${i.title}</td>
      <td>${i.qty||1}</td>
      <td>${formatPrice(i.price_rub)} ₽</td>
      <td>${formatPrice(i.price_rub*(i.qty||1))} ₽</td>
    </tr>`).join('');

  const total = Cart.getTotal();
  const win = window.open('', '_blank');
  win.document.write(`<!DOCTYPE html><html><head>
    <meta charset="utf-8"><title>Счёт №${invoiceNum}</title>
    <style>
      body { font-family: Arial, sans-serif; padding: 40px; color: #333; }
      h1 { font-size: 24px; margin-bottom: 4px; }
      .meta { font-size: 14px; color: #666; margin-bottom: 32px; }
      .parties { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }
      .party h3 { font-size: 14px; margin-bottom: 8px; color: #0260e8; }
      .party p { font-size: 13px; line-height: 1.7; }
      table { width: 100%; border-collapse: collapse; }
      th { background: #f1f6fb; padding: 10px; text-align: left; border: 1px solid #dce8f8; font-size: 13px; }
      td { padding: 9px 10px; border: 1px solid #dce8f8; font-size: 13px; }
      .total { font-size: 18px; font-weight: 700; text-align: right; margin-top: 16px; }
      .footer { margin-top: 40px; font-size: 12px; color: #999; }
      @media print { body { padding: 20px; } }
    </style>
  </head><body>
    <h1>Счёт на оплату №${invoiceNum}</h1>
    <div class="meta">Дата: ${dateStr}</div>
    <div class="parties">
      <div class="party">
        <h3>Поставщик</h3>
        <p><strong>ООО «Альянс»</strong><br>
        ИНН 7842104042<br>
        Россия, Санкт-Петербург,<br>ул. Бассейная, д. 21, офис 701<br>
        Тел: +7 (812) 936-74-60<br>
        info@alliance-llc.ru</p>
      </div>
      <div class="party">
        <h3>Покупатель</h3>
        <p>___________________________________<br>
        ИНН ___________________________________<br>
        Адрес: _____________________________</p>
      </div>
    </div>
    <table>
      <thead><tr><th>№</th><th>Наименование</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="total">ИТОГО: ${formatPrice(total)} ₽ (НДС не облагается)</div>
    <div class="footer">
      Оплата по настоящему счёту означает согласие с условиями поставки.<br>
      Счёт действителен 5 банковских дней.
    </div>
    <script>window.onload = function() { window.print(); }<\/script>
  </body></html>`);
  win.document.close();
}

// ── Helpers ──
function formatPrice(n) {
  return Math.round(n).toLocaleString('ru-RU');
}

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
  Cart.updateUI();
  renderCartPage();

  // Close modal on backdrop click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
      if (e.target === overlay) closeOrderModal();
    });
  });

  // Burger menu
  const burger = document.querySelector('.burger');
  const mobileNav = document.querySelector('.mobile-nav');
  if (burger && mobileNav) {
    burger.addEventListener('click', () => mobileNav.classList.toggle('open'));
  }

  // Category filter on catalog page
  document.querySelectorAll('.cat-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const cat = btn.dataset.cat;
      document.querySelectorAll('.product-card').forEach(card => {
        card.style.display = (cat === 'all' || card.dataset.cat === cat) ? '' : 'none';
      });
    });
  });

  // Search
  const searchInput = document.getElementById('product-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.toLowerCase();
      document.querySelectorAll('.product-card').forEach(card => {
        const text = card.dataset.title || card.textContent;
        card.style.display = text.toLowerCase().includes(q) ? '' : 'none';
      });
    });
  }
});
