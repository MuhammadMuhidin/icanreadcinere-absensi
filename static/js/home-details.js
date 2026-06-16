(() => {
  const targets = {
    profile: document.querySelector('.profile-row'),
    today: document.querySelector('.today-card'),
    timeline: document.getElementById('timelineHeading')?.closest('.card'),
    month: document.getElementById('summaryHeading')?.closest('.card'),
    announcement: document.getElementById('newsHeading')?.closest('.card')
  };
  const leaveCards = document.querySelectorAll('section[aria-label="Leave overview"] > a.card');
  if (!Object.values(targets).some(Boolean) && !leaveCards.length) return;

  targets.today?.classList.add('no-detail-arrow');
  targets.month?.classList.add('no-detail-arrow');

  let cache = null;
  let pending = null;

  const icons = {
    profile: '<path d="M20 21a8 8 0 0 0-16 0"></path><circle cx="12" cy="7" r="4"></circle>',
    today: '<circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path>',
    timeline: '<path d="M5 4v16"></path><circle cx="5" cy="7" r="2"></circle><circle cx="5" cy="17" r="2"></circle><path d="M9 7h10M9 17h10"></path>',
    month: '<rect x="3" y="5" width="18" height="16" rx="2"></rect><path d="M16 3v4M8 3v4M3 10h18"></path>',
    leave: '<rect x="3" y="5" width="18" height="16" rx="2"></rect><path d="M8 3v4M16 3v4M3 10h18M9 15l2 2 4-4"></path>',
    announcement: '<path d="M3 11v2a2 2 0 0 0 2 2h2l4 4V5L7 9H5a2 2 0 0 0-2 2Z"></path><path d="M15 9a4 4 0 0 1 0 6"></path>'
  };

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[character]);

  function formatDate(value, withTime = false) {
    if (!value) return '—';
    const parsed = new Date(String(value).includes('T') ? value : `${value}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return new Intl.DateTimeFormat('en-GB', {
      day: 'numeric', month: 'short', year: 'numeric',
      ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {})
    }).format(parsed);
  }

  function duration(minutes) {
    if (minutes === null || minutes === undefined) return '—';
    const value = Number(minutes) || 0;
    return `${Math.floor(value / 60)}h ${value % 60}m`;
  }

  const stat = (label, value) => `<div class="detail-stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? '—')}</strong></div>`;
  const row = (label, value) => `<div class="detail-row"><span class="detail-row-label">${escapeHtml(label)}</span><strong class="detail-row-value">${escapeHtml(value ?? '—')}</strong></div>`;
  const listItem = (title, description, value = '') => `<div class="detail-list-item"><div><strong>${escapeHtml(title)}</strong><span>${escapeHtml(description || '')}</span></div><div class="detail-list-value">${escapeHtml(value)}</div></div>`;

  function badge(value) {
    const text = String(value || 'Unknown').replaceAll('_', ' ');
    const lower = text.toLowerCase();
    const kind = lower.includes('approved') || lower.includes('complete') || lower.includes('on time')
      ? 'success'
      : lower.includes('waiting') || lower.includes('late') || lower.includes('checked in')
        ? 'warning'
        : 'muted';
    return `<span class="detail-badge detail-badge-${kind}">${escapeHtml(text)}</span>`;
  }

  function ensureDialog() {
    if (document.getElementById('dashboardDetailDialog')) return;
    document.body.insertAdjacentHTML('beforeend', `
      <dialog class="dialog detail-dialog" id="dashboardDetailDialog">
        <div class="dialog-body">
          <button type="button" class="app-dialog-close" data-form-dialog-close aria-label="Close dialog">×</button>
          <div class="detail-dialog-header">
            <div class="detail-dialog-icon"><svg viewBox="0 0 24 24" data-detail-icon></svg></div>
            <div><h2 class="detail-dialog-title" data-detail-title></h2><p class="detail-dialog-subtitle" data-detail-subtitle></p></div>
          </div>
          <div class="detail-dialog-content" data-detail-content></div>
          <div class="detail-dialog-actions" data-detail-actions></div>
        </div>
      </dialog>`);
  }

  function openDetail({ title, subtitle, icon, content, actions = [] }) {
    ensureDialog();
    const dialog = document.getElementById('dashboardDetailDialog');
    dialog.querySelector('[data-detail-title]').textContent = title;
    dialog.querySelector('[data-detail-subtitle]').textContent = subtitle || '';
    dialog.querySelector('[data-detail-icon]').innerHTML = icons[icon] || icons.profile;
    dialog.querySelector('[data-detail-content]').innerHTML = content;
    const actionsElement = dialog.querySelector('[data-detail-actions]');
    actionsElement.classList.toggle('three', actions.length === 3);
    actionsElement.innerHTML = actions.map((action) => `<button type="button" class="btn ${action.className || 'btn-ghost'}" data-detail-action="${escapeHtml(action.id)}">${escapeHtml(action.label)}</button>`).join('');
    if (!dialog.open) dialog.showModal();
  }

  function showLoading(type) {
    openDetail({
      title: 'Loading details',
      subtitle: 'Reading the latest records from the server.',
      icon: type,
      content: '<div class="detail-empty"><div class="spinner" aria-hidden="true"></div><p>Preparing a complete summary.</p></div>',
      actions: [{ id: 'close', label: 'Close' }]
    });
  }

  async function getData(force = false) {
    if (cache && !force) return cache;
    if (pending && !force) return pending;
    pending = fetch('/api/me/dashboard-details', { cache: 'no-store' })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.message || data.error || 'Could not load details');
        cache = data;
        return data;
      })
      .finally(() => { pending = null; });
    return pending;
  }

  async function show(type) {
    showLoading(type);
    try {
      render(type, await getData());
    } catch (error) {
      document.getElementById('dashboardDetailDialog')?.close();
      await window.appDialog.error({ title: 'Details could not be loaded', message: error.message });
    }
  }

  function render(type, data) {
    if (type === 'profile') {
      const item = data.profile;
      openDetail({
        title: item.user_id,
        subtitle: `${item.title} · ${item.role}`,
        icon: 'profile',
        content: `<div class="detail-section"><h3 class="detail-section-title">Account</h3>${row('User ID', item.user_id)}${row('Title', item.title)}${row('Role', item.role)}${row('Phone', item.phone || 'Not configured')}</div>`,
        actions: [
          { id: 'close', label: 'Close' },
          { id: 'photo', label: 'Change photo', className: 'btn-secondary' },
          { id: 'security', label: 'Change password', className: 'btn-primary' }
        ]
      });
      return;
    }

    if (type === 'today') {
      const item = data.today;
      openDetail({
        title: 'Today’s attendance',
        subtitle: item.date_label,
        icon: 'today',
        content: `
          <div class="detail-section"><h3 class="detail-section-title">Status</h3><div style="margin-bottom:12px">${badge(item.state)}</div><div class="detail-grid">${stat('Check in', item.checkin?.slice(0, 5) || '—')}${stat('Check out', item.checkout?.slice(0, 5) || '—')}${stat('Duration', duration(item.duration_minutes))}${stat('Expected start', item.expected_start)}</div></div>
          <div class="detail-section"><h3 class="detail-section-title">Recorded context</h3>${row('Punctuality', item.deviation === 'On time!' ? 'On time' : item.deviation ? `Late ${item.deviation.slice(0, 5)}` : 'Not recorded')}${row('Mood', item.mood || 'Not provided')}${row('Database records', item.events?.length || 0)}${item.notes ? `<p class="detail-note" style="margin-top:12px"><strong>Note</strong>\n${escapeHtml(item.notes)}</p>` : ''}</div>`,
        actions: [{ id: 'close', label: 'Close', className: 'btn-primary' }]
      });
      return;
    }

    if (type === 'timeline') {
      const events = data.today.events || [];
      const items = events.length
        ? events.map((event) => listItem(
            event.aksi,
            [event.deviation === 'On time!' ? 'On time' : event.deviation ? `Late ${event.deviation.slice(0, 5)}` : '', event.mood ? `Mood: ${event.mood}` : '', event.notes || ''].filter(Boolean).join(' · '),
            event.waktu?.slice(0, 5) || '—'
          )).join('')
        : '<div class="detail-empty">No attendance events have been recorded today.</div>';
      openDetail({
        title: 'Today’s timeline',
        subtitle: `${data.today.date_label} · ${events.length} database record${events.length === 1 ? '' : 's'}`,
        icon: 'timeline',
        content: `<div class="detail-section"><h3 class="detail-section-title">Recorded events</h3><div class="detail-list">${items}</div></div>`,
        actions: [{ id: 'close', label: 'Close', className: 'btn-primary' }]
      });
      return;
    }

    if (type === 'month') {
      const item = data.month;
      const summary = item.summary;
      openDetail({
        title: `Attendance · ${item.period}`,
        subtitle: 'Calculated from every stored attendance record in this period.',
        icon: 'month',
        content: `
          <div class="detail-section"><h3 class="detail-section-title">Performance</h3><div class="detail-grid">${stat('Recorded days', summary.recorded_days)}${stat('Completed days', summary.completed_days)}${stat('On time', summary.on_time_days)}${stat('Late', summary.late_days)}${stat('Incomplete', summary.incomplete_days)}${stat('Late minutes', summary.total_late_minutes)}${stat('Total work', duration(summary.total_work_minutes))}${stat('Average day', duration(summary.average_work_minutes))}</div></div>
          <div class="detail-section"><h3 class="detail-section-title">Highlights</h3>${row('Longest completed day', item.longest_day ? `${formatDate(item.longest_day.date)} · ${duration(item.longest_day.duration_minutes)}` : 'No completed day')}${row('Latest late arrival', item.latest_late ? `${formatDate(item.latest_late.date)} · ${item.latest_late.deviation.slice(0, 5)}` : 'None')}</div>
          <div class="detail-section"><h3 class="detail-section-title">Recent recorded days</h3><div class="detail-list">${item.recent_days.length ? item.recent_days.map((day) => listItem(formatDate(day.date), `${day.checkin?.slice(0, 5) || '—'}–${day.checkout?.slice(0, 5) || '—'} · ${day.state.replaceAll('_', ' ')}`, duration(day.duration_minutes))).join('') : '<div class="detail-empty">No records in this period.</div>'}</div></div>`,
        actions: [{ id: 'close', label: 'Close' }, { id: 'history', label: 'Open full history', className: 'btn-primary' }]
      });
      return;
    }

    if (type === 'leave') {
      const item = data.leave;
      openDetail({
        title: 'Paid leave overview',
        subtitle: item.next_approved ? `Next approved leave: ${formatDate(item.next_approved.leave_date)}` : 'No upcoming approved leave.',
        icon: 'leave',
        content: `
          <div class="detail-section"><h3 class="detail-section-title">Balance and requests</h3><div class="detail-grid">${stat('Balance', `${item.balance ?? '—'} days`)}${stat('Waiting', item.counts.waiting)}${stat('Approved', item.counts.approved)}${stat('Rejected', item.counts.rejected)}${stat('Canceled', item.counts.canceled)}${stat('All requests', item.counts.all)}</div></div>
          <div class="detail-section"><h3 class="detail-section-title">Recent requests</h3><div class="detail-list">${item.recent_requests.length ? item.recent_requests.map((entry) => listItem(formatDate(entry.leave_date), entry.reason || `Submitted ${formatDate(entry.created_at)}`, entry.status.replace('WAITING APPROVAL', 'Waiting'))).join('') : '<div class="detail-empty">No leave requests yet.</div>'}</div></div>`,
        actions: [{ id: 'close', label: 'Close' }, { id: 'leave', label: 'Open leave page', className: 'btn-primary' }]
      });
      return;
    }

    const item = data.announcements;
    openDetail({
      title: 'Announcements',
      subtitle: item.latest ? `Latest published ${formatDate(item.latest.published_at)}` : 'No published announcement.',
      icon: 'announcement',
      content: `
        <div class="detail-section"><h3 class="detail-section-title">Latest</h3>${item.latest ? `<p class="detail-note">${escapeHtml(item.latest.content)}</p>` : '<div class="detail-empty">No announcement available.</div>'}</div>
        <div class="detail-section"><h3 class="detail-section-title">Previous announcements</h3><div class="detail-list">${item.previous.length ? item.previous.map((entry) => listItem(formatDate(entry.published_at), entry.content)).join('') : '<div class="detail-empty">No previous announcements.</div>'}</div></div>`,
      actions: [{ id: 'close', label: 'Close', className: 'btn-primary' }]
    });
  }

  function activate(element, type, className = 'home-detail-card') {
    if (!element) return;
    element.classList.add(className);
    if (element.tagName !== 'A') {
      element.setAttribute('role', 'button');
      element.tabIndex = 0;
    }
    const open = (event) => {
      if (event.target.closest('button, input, textarea, select, a:not(.home-detail-link), .profile-photo')) return;
      if (element.tagName === 'A') event.preventDefault();
      show(type);
    };
    element.addEventListener('click', open);
    element.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      open(event);
    });
  }

  ensureDialog();
  activate(targets.profile, 'profile');
  activate(targets.today, 'today');
  activate(targets.timeline, 'timeline');
  activate(targets.month, 'month');
  leaveCards.forEach((card) => activate(card, 'leave', 'home-detail-link'));
  activate(targets.announcement, 'announcement');

  document.addEventListener('click', (event) => {
    const action = event.target.closest('[data-detail-action]')?.dataset.detailAction;
    if (!action) return;
    const dialog = document.getElementById('dashboardDetailDialog');
    if (action === 'close') dialog.close();
    if (action === 'photo') {
      dialog.close();
      document.getElementById('profilePhoto')?.click();
    }
    if (action === 'security') {
      dialog.close();
      document.dispatchEvent(new CustomEvent('open-account-security'));
    }
    if (action === 'history') window.location.href = `/history?period=${cache?.month?.period || ''}`;
    if (action === 'leave') window.location.href = '/paid_leave';
  });

  document.addEventListener('account-security-updated', () => { cache = null; });
})();
