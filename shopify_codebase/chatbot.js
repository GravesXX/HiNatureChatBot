(function () {
    // ------- DOM helpers & config -------
    const $ = (id) => document.getElementById(id);
    const root     = $('gw-chatbot'); // wrapper
    const panel    = $('gwcb-panel');  // full chat panel
    const toggle   = $('gwcb-toggle'); // floating icon/bubble
    const closeBtn = $('gwcb-close');  // "X" inside header
    const log      = $('gwcb-log');
    const form     = $('gwcb-form');
    const input    = $('gwcb-input');
  
    const getCfg = () => ({
      endpoint   : root?.dataset.endpoint,
      shop       : root?.dataset.shop,
      customerId : root?.dataset.customerId || null
    });
  
    // ------- Session id for guests -------
    const SID_KEY = 'gwcb_session_id';
    let sessionId = localStorage.getItem(SID_KEY);
    if (!sessionId) {
      sessionId = (crypto?.randomUUID?.() || String(Date.now()));
      localStorage.setItem(SID_KEY, sessionId);
    }
  
    // ------- UI helpers -------
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
  
    // === REQUIRED BEHAVIOR ===
    // openPanel = MINIMIZE (hide panel, show icon)
    function openPanel() {
      if (!panel) return;
      panel.hidden = true;                           // hide whole panel
      toggle?.setAttribute('aria-expanded', 'false');
      if (toggle) toggle.style.display = '';         // show icon
    }
  
    // closePanel = EXPAND (show panel, hide icon)
    function closePanel() {
      if (!panel) return;
      panel.hidden = false;                          // show whole panel
      toggle?.setAttribute('aria-expanded', 'true');
      if (toggle) toggle.style.display = 'none';     // hide icon
      input?.focus();
    }
  
    // Initial state: if panel has the "hidden" attribute in HTML, show icon
    if (panel?.hidden) {
      if (toggle) toggle.style.display = '';
    } else {
      if (toggle) toggle.style.display = 'none';
    }
  
    // ------- Events (open/close) -------
    toggle?.addEventListener('click', () => closePanel()); // icon expands
    closeBtn?.addEventListener('click', () => openPanel()); // X collapses
  
    // ESC to collapse
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !panel?.hidden) openPanel();
    });
  
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
          credentials: 'include', // remove to simplify CORS if not using cookies
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
  
    // Submit handler
    form?.addEventListener('submit', (e) => {
      e.preventDefault();
      const text = input?.value || '';
      if (text.trim()) sendMessage(text);
    });
  })();
  