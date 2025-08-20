(function () {
    const $ = (id) => document.getElementById(id);
    const root     = $('gw-chatbot');
    const panel    = $('gwcb-panel');   // has/doesn't have .gwcb-hidden
    const toggle   = $('gwcb-toggle');  // bubble
    const closeBtn = $('gwcb-close');   // X
    const log      = $('gwcb-log');
    const form     = $('gwcb-form');
    const input    = $('gwcb-input');
  
    const getCfg = () => ({
      endpoint   : root?.dataset.endpoint,
      shop       : root?.dataset.shop,
      customerId : root?.dataset.customerId || null
    });
  
    // Session id
    const SID_KEY = 'gwcb_session_id';
    let sessionId = localStorage.getItem(SID_KEY);
    if (!sessionId) {
      sessionId = (crypto?.randomUUID?.() || String(Date.now()));
      localStorage.setItem(SID_KEY, sessionId);
    }
  
    function appendMsg(role, text) {
      const el = document.createElement('div');
      el.className = `gwcb-msg ${role}`;
      el.textContent = text;
      log.appendChild(el);
      log.scrollTop = log.scrollHeight;
      return el;
    }
  
    function setTyping(on) {
      const existing = log.querySelector('.gwcb-typing');
      if (on && !existing) appendMsg('bot gwcb-typing', 'Typing…');
      if (!on && existing) existing.remove();
    }
  
    // === Minimize / Expand using a CSS class ===
    function minimize() {                 // show icon, hide panel
      panel?.classList.add('gwcb-hidden');
      if (toggle) toggle.style.display = '';       // visible
      toggle?.setAttribute('aria-expanded', 'false');
    }
  
    function expand() {                   // hide icon, show panel
      panel?.classList.remove('gwcb-hidden');
      if (toggle) toggle.style.display = 'none';   // hidden
      toggle?.setAttribute('aria-expanded', 'true');
      input?.focus();
    }
  
    // Initial state from HTML: if panel has .gwcb-hidden, start minimized
    if (panel?.classList.contains('gwcb-hidden')) {
      if (toggle) toggle.style.display = '';
    } else {
      if (toggle) toggle.style.display = 'none';
    }
  
    // Click handlers
    toggle?.addEventListener('click', expand);  // icon opens panel
    closeBtn?.addEventListener('click', minimize); // X collapses
  
    // ESC to collapse
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !panel?.classList.contains('gwcb-hidden')) {
        minimize();
      }
    });
  
    function pickReply(data) {
      return (
        data?.response ??
        data?.reply ??
        data?.message ??
        data?.answer ??
        ''
      );
    }
  
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
            sessionId,
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
  
    form?.addEventListener('submit', (e) => {
      e.preventDefault();
      const text = input?.value || '';
      if (text.trim()) sendMessage(text);
    });
  })();
  