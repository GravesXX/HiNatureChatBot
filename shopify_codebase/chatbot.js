(function () {
  // ------- DOM helpers & references -------
  const $ = (id) => document.getElementById(id);
  const root     = $('gw-chatbot');
  const panel    = $('gwcb-panel');   // panel container (hidden via .gwcb-hidden)
  const toggle   = $('gwcb-toggle');  // bubble icon
  const closeBtn = $('gwcb-close');   // header "X"
  const log      = $('gwcb-log');
  const form     = $('gwcb-form');
  const input    = $('gwcb-input');

  // ------- Config with robust fallbacks -------
  function resolveEndpoint() {
    // 1) data-endpoint from DOM
    const fromData = root?.dataset?.endpoint?.trim();
    if (fromData) return fromData;
    // 2) global object (if snippet populates it)
    const fromGlobal = (window.GWCB_CFG && window.GWCB_CFG.endpoint || '').trim?.();
    if (fromGlobal) return fromGlobal;
    // 3) no endpoint
    return '';
  }

  const getCfg = () => ({
    endpoint   : resolveEndpoint(),
    shop       : root?.dataset.shop,
    customerId : root?.dataset.customerId || null
  });

  // ------- Session id -------
  const SID_KEY = 'gwcb_session_id';
  let sessionId = localStorage.getItem(SID_KEY);
  if (!sessionId) {
    sessionId = (crypto?.randomUUID?.() || String(Date.now()));
    localStorage.setItem(SID_KEY, sessionId);
  }

  // ------- Welcome bubble (always first in log) -------
  const WELCOME_ID   = 'gwcb-welcome-msg';
  const WELCOME_TEXT = 'Hi This is Hi Nature Pet Chat Bot! How can I help you today? I am always here willing to help!';

  function ensureWelcomeAtTop() {
    if (!log) return;
    let welcome = document.getElementById(WELCOME_ID);
    if (!welcome) {
      welcome = document.createElement('div');
      welcome.id = WELCOME_ID;
      welcome.className = 'gwcb-msg bot';
      welcome.textContent = WELCOME_TEXT;
    } else {
      welcome.className = 'gwcb-msg bot';
      welcome.textContent = WELCOME_TEXT;
    }
    if (log.firstChild !== welcome) {
      log.insertBefore(welcome, log.firstChild);
    }
  }

  // ------- UI helpers -------
  function appendMsg(role, text) {
    if (!log) return;
    // keep welcome at top
    ensureWelcomeAtTop();

    const el = document.createElement('div');
    el.className = `gwcb-msg ${role}`;
    // el.textContent = text;
    el.innerHTML = text;   // ✅ allows clickable links
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }

  function setTyping(on) {
    if (!log) return;
    const existing = log.querySelector('.gwcb-typing');
    if (on && !existing) appendMsg('bot gwcb-typing', 'Typing…');
    if (!on && existing) existing.remove();
  }

  // ------- Minimize / Expand via class -------
  function minimize() { // show icon, hide panel
    panel?.classList.add('gwcb-hidden');
    if (toggle) toggle.style.display = '';
    toggle?.setAttribute('aria-expanded', 'false');
  }

  function expand() {   // hide icon, show panel
    panel?.classList.remove('gwcb-hidden');
    if (toggle) toggle.style.display = 'none';
    toggle?.setAttribute('aria-expanded', 'true');
    ensureWelcomeAtTop();
    input?.focus();
  }

  // Initial visibility
  if (panel?.classList.contains('gwcb-hidden')) {
    if (toggle) toggle.style.display = '';
  } else {
    if (toggle) toggle.style.display = 'none';
  }
  // Ensure welcome exists on load
  ensureWelcomeAtTop();

  // Click handlers
  toggle?.addEventListener('click', expand);
  closeBtn?.addEventListener('click', minimize);

  // ESC to collapse
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !panel?.classList.contains('gwcb-hidden')) {
      minimize();
    }
  });

  // ------- If endpoint missing, show hint & disable form -------
  (function guardConfig() {
    const cfg = getCfg();
    if (!cfg.endpoint) {
      console.error('[chatbot] Missing endpoint config');
      appendMsg('bot', 'Chat not configured.');
      // prevent submits
      if (form) form.addEventListener('submit', (ev) => ev.preventDefault(), { once: true });
    }
  })();

  // ------- Reply shape tolerance -------
  function pickReply(data) {
    return (
      data?.response ??
      data?.reply ??
      data?.message ??
      data?.answer ??
      ''
    );
  }

  // ------- Send message flow -------
  async function sendMessage(text) {
    const cfg = getCfg();
    if (!cfg?.endpoint) {
      console.error('[chatbot] Missing endpoint config');
      appendMsg('bot', 'Chat not configured.');
      return;
    }
    if (!text || !text.trim()) return;

    appendMsg('user', text.trim());
    setTyping(true);
    if (input) input.value = '';

    try {
      const res = await fetch(cfg.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include', // remove if you don't need cookies
        body: JSON.stringify({
          message: text.trim(),
          session_id: sessionId,   // <<< use snake_case to match backend
          customerId: cfg.customerId,
          shop: cfg.shop
        })
      });

      const raw = await res.text();
      console.log('[chatbot] status', res.status, 'raw:', raw);

      let data;
      try { data = JSON.parse(raw); }
      catch { data = { response: 'Invalid JSON from server' }; }

      const reply = pickReply(data);
      setTyping(false);
      appendMsg('bot', reply || '…');
    } catch (err) {
      console.error('[chatbot] network error', err);
      setTyping(false);
      appendMsg('bot', 'Connection error. Please try again.');
    }
  }

  // Submit handler
  form?.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = input?.value || '';
    if (text.trim()) sendMessage(text);
  });
})();
