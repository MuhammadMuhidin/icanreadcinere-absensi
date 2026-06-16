(() => {
  const profile = document.querySelector('.profile-row');
  const todayCard = document.querySelector('.today-card');
  const timelineCard = document.getElementById('timelineHeading')?.closest('.card');
  const monthCard = document.getElementById('summaryHeading')?.closest('.card');
  const leaveCards = document.querySelectorAll('section[aria-label="Leave overview"] > a.card');
  const announcementCard = document.getElementById('newsHeading')?.closest('.card');

  if (!profile && !todayCard && !timelineCard && !monthCard && !announcementCard) return;

  function text(element, selector) {
    return element?.querySelector(selector)?.textContent?.trim() || '—';
  }

  function activate(element, handler, className = 'home-detail-card') {
    if (!element) return;
    element.classList.add(className);
    if (element.tagName !== 'A') {
      element.setAttribute('role', 'button');
      element.tabIndex = 0;
    }

    element.addEventListener('click', (event) => {
      if (event.target.closest('button, input, textarea, select, a:not(.home-detail-link), .profile-photo')) return;
      if (element.tagName === 'A') event.preventDefault();
      handler(event);
    });

    element.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      if (event.target.closest('button, input, textarea, select')) return;
      event.preventDefault();
      handler(event);
    });
  }

  activate(profile, async () => {
    const name = text(profile, 'h1');
    const title = [...profile.querySelectorAll('.profile-copy p')].at(-1)?.textContent?.trim() || 'Team Member';
    const changePhoto = await window.appDialog.confirm({
      title: name,
      message: `Account: ${name}\nRole: ${title}\n\nYour profile photo is used across the attendance interface.`,
      tone: 'info',
      icon: 'info',
      confirmText: 'Change photo',
      cancelText: 'Close'
    });
    if (changePhoto) document.getElementById('profilePhoto')?.click();
  }, 'home-detail-card');

  activate(todayCard, async () => {
    const status = text(todayCard, '#todayHeading');
    const date = text(todayCard, '#todayDate');
    const rows = [...document.querySelectorAll('.timeline-row')];
    const checkIn = rows[0]?.querySelector('.timeline-time')?.textContent?.trim() || '—';
    const checkOut = rows[1]?.querySelector('.timeline-time')?.textContent?.trim() || '—';
    const punctuality = rows[0]?.querySelector('.timeline-label span')?.textContent?.trim() || '—';
    const duration = document.getElementById('liveDuration')?.textContent?.trim()
      || [...todayCard.querySelectorAll('.today-status p')].at(-1)?.textContent?.trim()
      || '—';

    await window.appDialog.alert({
      title: 'Today’s attendance',
      message: `${date}\n\nStatus: ${status}\nCheck in: ${checkIn}\nCheck out: ${checkOut}\nPunctuality: ${punctuality}\nDuration: ${duration}`,
      tone: status.toLowerCase().includes('completed') ? 'success' : 'info',
      icon: status.toLowerCase().includes('completed') ? 'success' : 'info',
      confirmText: 'Close'
    });
  });

  activate(timelineCard, async () => {
    const rows = [...timelineCard.querySelectorAll('.timeline-row')];
    const details = rows.map((row) => {
      const label = text(row, '.timeline-label strong');
      const note = text(row, '.timeline-label span');
      const time = text(row, '.timeline-time');
      return `${label}: ${time}\n${note}`;
    }).join('\n\n');

    await window.appDialog.alert({
      title: 'Today’s timeline',
      message: details,
      tone: 'info',
      icon: 'info',
      confirmText: 'Close'
    });
  });

  activate(monthCard, async () => {
    const period = text(monthCard, '.section-heading p').split('·')[0].trim();
    const metrics = [...monthCard.querySelectorAll('.metric')].map((metric) => {
      return `${text(metric, '.metric-label')}: ${text(metric, '.metric-value')}`;
    }).join('\n');

    const openHistory = await window.appDialog.confirm({
      title: `Attendance summary · ${period}`,
      message: `${metrics}\n\nOpen the detailed attendance history to review each recorded day.`,
      tone: 'info',
      icon: 'info',
      confirmText: 'Open history',
      cancelText: 'Close'
    });
    if (openHistory) window.location.href = monthCard.querySelector('a[href^="/history"]')?.href || '/history';
  });

  leaveCards.forEach((card, index) => {
    activate(card, async () => {
      const label = text(card, '.metric-label');
      const value = text(card, '.metric-value');
      const message = index === 0
        ? `Available paid leave: ${value}.\n\nOpen the leave page to submit a request and review your leave history.`
        : `Requests waiting for approval: ${value}.\n\nOpen the leave page to review, edit, or cancel pending requests.`;
      const openLeave = await window.appDialog.confirm({
        title: label,
        message,
        tone: 'info',
        icon: 'info',
        confirmText: 'Open leave',
        cancelText: 'Close'
      });
      if (openLeave) window.location.href = card.href;
    }, 'home-detail-link');
  });

  activate(announcementCard, async () => {
    const content = text(announcementCard, '.news-content');
    const published = announcementCard.querySelector('.news-date')?.textContent?.trim();
    await window.appDialog.alert({
      title: 'Latest announcement',
      message: `${content}${published ? `\n\n${published}` : ''}`,
      tone: 'info',
      icon: 'info',
      confirmText: 'Close'
    });
  });
})();
