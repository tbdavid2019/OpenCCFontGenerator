const STORAGE_KEY = 'opencc_font_jobs_v1';

const MODE_META = {
  convert: {
    heading: '單一字型簡繁轉換與 GSUB 規則編譯',
    subtitle: '上傳來源字型並編譯詞彙級 OpenCC OpenType 查找表（支援備用字型補字、Kobo 與 WOFF2）',
    endpoint: '/api/v1/jobs/convert',
    submitLabel: '送出轉換任務',
  },
  rotate90: {
    heading: '90° 直排字形旋轉工具',
    subtitle: '將漢字與注音符號字形順/逆時針旋轉 90° 並鎖定統一字寬度量',
    endpoint: '/api/v1/jobs/rotate90',
    submitLabel: '送出旋轉任務',
  },
  webfont: {
    heading: 'Webfont WOFF2 與 CSS 樣式表打包',
    subtitle: '將 TTF / OTF 壓縮為 WOFF2 並產生標準 @font-face fonts.css 壓縮包',
    endpoint: '/api/v1/jobs/webfont',
    submitLabel: '開始打包 Webfont',
  },
  'static-family': {
    heading: '靜態多字重字型家族批次建置',
    subtitle: '一次上傳多個字重（或 ZIP 壓縮包），自動配對備用字型字重並輸出完整家族 ZIP',
    endpoint: '/api/v1/jobs/static-family',
    submitLabel: '批次編譯靜態家族',
  },
  'variable-family': {
    heading: '可變字型（Variable Font）實例化家族',
    subtitle: '依 wght 軸切出指定字重靜態實例，結合備用字型補全並編譯 OpenCC 規則',
    endpoint: '/api/v1/jobs/variable-family',
    submitLabel: '實例化並編譯家族',
  },
};

const PHASE_PROGRESS = {
  queued: 12,
  initializing: 25,
  compiling_opencc_font: 68,
  rotating_glyphs_90: 68,
  converting_woff2: 72,
  building_static_family: 68,
  instantiating_variable_family: 68,
  packaging_bundle: 90,
  completed: 100,
  timed_out: 100,
  interrupted: 100,
  failed: 100,
};

const PHASE_LABELS = {
  queued: '排隊等待 Worker',
  initializing: '啟動獨立編譯環境',
  compiling_opencc_font: '編譯 OpenCC GSUB 字型',
  rotating_glyphs_90: '旋轉漢字/注音字形 90°',
  converting_woff2: '壓縮 WOFF2 與產生 CSS',
  building_static_family: '批次編譯靜態多字重家族',
  instantiating_variable_family: '切分 Variable Font 字重與編譯',
  packaging_bundle: '打包輸出壓縮檔',
  completed: '編譯完成',
  timed_out: '執行逾時中止',
  interrupted: '伺服器重啟中斷',
  failed: '編譯失敗',
};

const STATUS_LABELS = {
  queued: '排隊中',
  running: '編譯中',
  completed: '已完成',
  failed: '失敗',
  cancelled: '已取消',
};

const state = {
  activeMode: 'convert',
  droppedFiles: new Map(),
  jobIds: loadStoredJobIds(),
  jobs: [],
  pollTimer: null,
  pollBackoffMs: 1500,
  previewTimer: null,
  previewSeq: 0,
  previewAbort: null,
  submitting: false,
  capabilities: null,
};

function quoteShellArg(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`;
}

function loadStoredJobIds() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((id) => typeof id === 'string') : [];
  } catch {
    return [];
  }
}

function saveStoredJobIds() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.jobIds.slice(0, 30)));
  } catch {
    // Ignore storage quota errors
  }
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatTTL(seconds) {
  if (seconds === 0) return '0 秒';
  if (!seconds) return '--';
  if (seconds >= 3600) return `${Math.round(seconds / 3600)} 小時`;
  return `${Math.round(seconds / 60)} 分鐘`;
}

function getDropKeyFiles(dropKey, inputEl) {
  if (state.droppedFiles.has(dropKey)) {
    return state.droppedFiles.get(dropKey);
  }
  return inputEl?.files ? Array.from(inputEl.files) : [];
}

function updateDropzoneDisplay(dropzone) {
  const dropKey = dropzone.dataset.drop;
  const input = dropzone.querySelector('input[type="file"]');
  const label = dropzone.querySelector('.dropzone-info p');
  const clearBtn = dropzone.querySelector('[data-clear]');
  const files = getDropKeyFiles(dropKey, input);

  if (!label.dataset.defaultText) {
    label.dataset.defaultText = label.textContent;
  }

  if (files.length === 0) {
    dropzone.classList.remove('has-file');
    label.textContent = label.dataset.defaultText;
    if (clearBtn) clearBtn.hidden = true;
  } else if (files.length === 1) {
    dropzone.classList.add('has-file');
    label.textContent = `已選擇：${files[0].name}（${formatBytes(files[0].size)}）`;
    if (clearBtn) clearBtn.hidden = false;
  } else {
    dropzone.classList.add('has-file');
    const total = files.reduce((acc, f) => acc + f.size, 0);
    label.textContent = `已選擇 ${files.length} 個檔案（合計 ${formatBytes(total)}）：${files.slice(0, 3).map((f) => f.name).join('、')}${files.length > 3 ? '…' : ''}`;
    if (clearBtn) clearBtn.hidden = false;
  }
}

function setupDropzones() {
  document.querySelectorAll('.dropzone').forEach((dropzone) => {
    const dropKey = dropzone.dataset.drop;
    const input = dropzone.querySelector('input[type="file"]');
    const clearBtn = dropzone.querySelector('[data-clear]');

    const labelEl = dropzone.querySelector('.dropzone-info p');
    if (labelEl && !labelEl.dataset.defaultText) {
      labelEl.dataset.defaultText = labelEl.textContent;
    }

    input.addEventListener('change', () => {
      state.droppedFiles.delete(dropKey);
      updateDropzoneDisplay(dropzone);
      updateCurlPreview();
    });

    dropzone.addEventListener('dragover', (event) => {
      event.preventDefault();
      dropzone.classList.add('is-dragover');
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('is-dragover');
    });

    dropzone.addEventListener('drop', (event) => {
      event.preventDefault();
      dropzone.classList.remove('is-dragover');
      const files = Array.from(event.dataTransfer?.files || []);
      if (!files.length) return;
      state.droppedFiles.set(dropKey, input.multiple ? files : [files[0]]);
      updateDropzoneDisplay(dropzone);
      updateCurlPreview();
    });

    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        state.droppedFiles.delete(dropKey);
        input.value = '';
        updateDropzoneDisplay(dropzone);
        updateCurlPreview();
      });
    }
  });
}

function syncDrawerInert() {
  const rail = document.getElementById('nav-rail');
  const isMobile = window.matchMedia('(max-width: 900px)').matches;
  const isOpen = rail.classList.contains('is-open');
  rail.inert = isMobile && !isOpen;
}

function switchMode(mode) {
  state.activeMode = mode;
  document.querySelectorAll('.mode-btn').forEach((btn) => {
    const active = btn.dataset.mode === mode;
    btn.classList.toggle('is-active', active);
    if (active) {
      btn.setAttribute('aria-current', 'page');
    } else {
      btn.removeAttribute('aria-current');
    }
  });

  document.querySelectorAll('.mode-form').forEach((form) => {
    form.hidden = form.dataset.mode !== mode;
  });

  const meta = MODE_META[mode];
  document.getElementById('mode-heading').textContent = meta.heading;
  document.getElementById('mode-subtitle').textContent = meta.subtitle;
  document.getElementById('submit-btn').textContent = meta.submitLabel;

  hideFeedback();
  closeMobileDrawer(false);
  refreshSpecimen();
  updateCurlPreview();
}

function openMobileDrawer() {
  document.getElementById('nav-rail').classList.add('is-open');
  document.getElementById('nav-backdrop').hidden = false;
  document.getElementById('mobile-nav-btn').setAttribute('aria-expanded', 'true');
  syncDrawerInert();
}

function closeMobileDrawer(restoreFocus = false) {
  const rail = document.getElementById('nav-rail');
  const wasOpen = rail.classList.contains('is-open');
  rail.classList.remove('is-open');
  document.getElementById('nav-backdrop').hidden = true;
  const navBtn = document.getElementById('mobile-nav-btn');
  navBtn.setAttribute('aria-expanded', 'false');
  syncDrawerInert();
  if (restoreFocus && wasOpen) {
    navBtn.focus();
  }
}

function getActiveForm() {
  return document.getElementById(`form-${state.activeMode}`);
}

function getActivePreviewParams() {
  const form = getActiveForm();
  const configEl = form?.querySelector('[data-preview-config]');
  const noPuncEl = form?.querySelector('[data-preview-nopunc]');
  return {
    supportsOpenCC: Boolean(configEl),
    config: configEl ? configEl.value : 's2t',
    noPunc: noPuncEl ? noPuncEl.checked : false,
  };
}

async function refreshSpecimen() {
  const pairsEl = document.getElementById('specimen-pairs');
  const metaEl = document.getElementById('specimen-meta');
  const customInput = document.getElementById('specimen-custom-input');
  const customOut = document.getElementById('specimen-custom-output');
  const { supportsOpenCC, config, noPunc } = getActivePreviewParams();

  if (state.previewAbort) {
    state.previewAbort.abort();
    state.previewAbort = null;
  }
  const reqSeq = ++state.previewSeq;

  if (!supportsOpenCC) {
    pairsEl.innerHTML = '';
    const notice = document.createElement('div');
    notice.className = 'specimen-pair';
    const desc = state.activeMode === 'rotate90'
      ? '模式說明：保留既有編碼表並將漢字 / 注音字形旋轉 90° 鎖定 1000 unit 等寬度量'
      : '模式說明：不修改 OpenType GSUB 轉換表，專注壓縮 WOFF2 並生成 @font-face fonts.css';
    notice.textContent = desc;
    pairsEl.appendChild(notice);
    customInput.parentElement.hidden = true;
    metaEl.textContent = `MODE: ${state.activeMode.toUpperCase()}`;
    return;
  }

  customInput.parentElement.hidden = false;
  const text = customInput.value.trim();
  const qs = new URLSearchParams({ config, no_punc: String(noPunc) });
  if (text) qs.set('text', text);

  const controller = new AbortController();
  state.previewAbort = controller;

  try {
    const resp = await fetch(`/api/v1/preview?${qs.toString()}`, { signal: controller.signal });
    if (!resp.ok || reqSeq !== state.previewSeq) return;
    const data = await resp.json();
    if (reqSeq !== state.previewSeq) return;

    pairsEl.innerHTML = '';
    for (const item of data.pairs.slice(0, 5)) {
      const pair = document.createElement('div');
      pair.className = 'specimen-pair';
      const src = document.createElement('span');
      src.className = 'specimen-src';
      src.textContent = item.source;
      const arr = document.createElement('span');
      arr.className = 'specimen-arrow';
      arr.textContent = '→';
      const dst = document.createElement('span');
      dst.className = 'specimen-dst';
      dst.setAttribute('lang', 'zh-Hant');
      dst.textContent = item.converted;
      pair.append(src, arr, dst);
      pairsEl.appendChild(pair);
    }

    if (text && data.sample_converted !== null) {
      customOut.setAttribute('lang', 'zh-Hant');
      customOut.textContent = data.sample_converted;
      customOut.hidden = false;
    } else {
      customOut.hidden = true;
      customOut.textContent = '';
    }

    metaEl.textContent = `CONFIG: ${config} · NO_PUNC: ${noPunc ? 'TRUE' : 'FALSE'}`;
  } catch (err) {
    if (err?.name !== 'AbortError') {
      // Ignore transient preview errors while keeping UI responsive
    }
  }
}

function buildFormDataForActiveMode() {
  const mode = state.activeMode;
  const form = getActiveForm();
  const fd = new FormData();

  if (mode === 'convert') {
    const srcFiles = getDropKeyFiles('convert-source', form.querySelector('#convert-source-input'));
    if (!srcFiles.length) throw new Error('請先選擇來源字型檔案。');
    fd.append('source_font', srcFiles[0]);

    const fbFiles = getDropKeyFiles('convert-fallback', form.querySelector('#convert-fallback-input'));
    if (fbFiles.length) fd.append('fallback_font', fbFiles[0]);

    const jsonInput = form.querySelector('#convert-name-json');
    if (jsonInput?.files?.length) fd.append('name_header_file', jsonInput.files[0]);

    appendFormFields(fd, form, ['source_font', 'fallback_font', 'name_header_file']);
    return fd;
  }

  if (mode === 'rotate90') {
    const srcFiles = getDropKeyFiles('rotate-source', form.querySelector('#rotate-source-input'));
    if (!srcFiles.length) throw new Error('請先選擇要旋轉的來源字型檔。');
    fd.append('source_font', srcFiles[0]);
    appendFormFields(fd, form, ['source_font']);
    return fd;
  }

  if (mode === 'webfont') {
    const srcFiles = getDropKeyFiles('webfont-source', form.querySelector('#webfont-source-input'));
    if (!srcFiles.length) throw new Error('請先選擇來源字型檔 (.ttf / .otf)。');
    fd.append('source_font', srcFiles[0]);
    appendFormFields(fd, form, ['source_font']);
    return fd;
  }

  if (mode === 'static-family') {
    const srcFiles = getDropKeyFiles('static-sources', form.querySelector('#static-sources-input'));
    if (!srcFiles.length) throw new Error('請至少上傳一個來源靜態字型檔或 ZIP 壓縮包。');
    srcFiles.forEach((f) => fd.append('source_files', f));

    const fbFiles = getDropKeyFiles('static-fallbacks', form.querySelector('#static-fallbacks-input'));
    fbFiles.forEach((f) => fd.append('fallback_files', f));

    appendFormFields(fd, form, ['source_files', 'fallback_files']);
    return fd;
  }

  if (mode === 'variable-family') {
    const srcFiles = getDropKeyFiles('vf-source', form.querySelector('#vf-source-input'));
    if (!srcFiles.length) throw new Error('請選擇來源 Variable Font 主檔。');
    fd.append('source_font', srcFiles[0]);

    const fbFiles = getDropKeyFiles('vf-fallbacks', form.querySelector('#vf-fallbacks-input'));
    if (!fbFiles.length) throw new Error('可變字型家族模式必須上傳對應字重的備用字型群（多檔或 ZIP）。');
    fbFiles.forEach((f) => fd.append('fallback_files', f));

    const checkedWeights = Array.from(form.querySelectorAll('#vf-weights-grid input:checked')).map((el) => el.value);
    if (checkedWeights.length > 0) {
      fd.append('weights', checkedWeights.join(','));
    }

    appendFormFields(fd, form, ['source_font', 'fallback_files']);
    return fd;
  }

  throw new Error('未知的轉換模式。');
}

function appendFormFields(fd, form, skipNames) {
  const skip = new Set(skipNames);
  form.querySelectorAll('input, select').forEach((el) => {
    if (!el.name || el.type === 'hidden' || skip.has(el.name)) return;
    if (el.type === 'checkbox') {
      fd.append(el.name, el.checked ? 'true' : 'false');
    } else if (el.value !== '') {
      fd.append(el.name, el.value);
    }
  });
}

function updateCurlPreview() {
  const mode = state.activeMode;
  const form = getActiveForm();
  const origin = window.location.origin;
  const endpoint = MODE_META[mode].endpoint;
  const parts = [`curl -X POST ${quoteShellArg(`${origin}${endpoint}`)}`];

  if (mode === 'convert') {
    parts.push('  -F \'source_font=@/path/to/SourceFont.ttf\'');
    const fb = getDropKeyFiles('convert-fallback', form.querySelector('#convert-fallback-input'));
    if (fb.length) parts.push(`  -F ${quoteShellArg(`fallback_font=@/path/to/${fb[0].name}`)}`);
  } else if (mode === 'rotate90') {
    parts.push('  -F \'source_font=@/path/to/SourceFont.ttf\'');
  } else if (mode === 'webfont') {
    parts.push('  -F \'source_font=@/path/to/SourceFont.ttf\'');
  } else if (mode === 'static-family') {
    parts.push('  -F \'source_files=@/path/to/fonts_static.zip\'');
    const fb = getDropKeyFiles('static-fallbacks', form.querySelector('#static-fallbacks-input'));
    if (fb.length) parts.push('  -F \'fallback_files=@/path/to/fallback_fonts.zip\'');
  } else if (mode === 'variable-family') {
    parts.push('  -F \'source_font=@/path/to/VariableFont.ttf\'');
    parts.push('  -F \'fallback_files=@/path/to/NotoSansTC.zip\'');
    const weights = Array.from(form.querySelectorAll('#vf-weights-grid input:checked')).map((el) => el.value);
    if (weights.length) parts.push(`  -F ${quoteShellArg(`weights=${weights.join(',')}`)}`);
  }

  form.querySelectorAll('input, select').forEach((el) => {
    if (!el.name || el.type === 'file' || el.type === 'hidden') return;
    if (el.type === 'checkbox') {
      if (el.checked) parts.push(`  -F ${quoteShellArg(`${el.name}=true`)}`);
    } else if (el.value !== '') {
      parts.push(`  -F ${quoteShellArg(`${el.name}=${el.value}`)}`);
    }
  });

  document.getElementById('curl-preview').textContent = parts.join(' \\\n');
}

function showFeedback(message, isOk = false) {
  const el = document.getElementById('form-feedback');
  el.textContent = message;
  el.classList.toggle('is-ok', isOk);
  el.hidden = false;
}

function hideFeedback() {
  const el = document.getElementById('form-feedback');
  el.hidden = true;
  el.textContent = '';
}

function setSubmitting(submitting, progressPct = 0) {
  state.submitting = submitting;
  const btn = document.getElementById('submit-btn');
  const wrap = document.getElementById('upload-progress-wrap');
  const text = document.getElementById('upload-progress-text');
  const fill = document.getElementById('upload-progress-fill');
  const hint = document.getElementById('submit-hint');

  btn.disabled = submitting;
  wrap.hidden = !submitting;
  hint.hidden = submitting;
  text.textContent = `上傳至伺服器中 ${progressPct}%`;
  fill.style.width = `${progressPct}%`;
}

function submitActiveJob() {
  if (state.submitting) return;
  hideFeedback();

  let formData;
  try {
    formData = buildFormDataForActiveMode();
  } catch (err) {
    showFeedback(err.message);
    return;
  }

  const endpoint = MODE_META[state.activeMode].endpoint;
  const xhr = new XMLHttpRequest();
  xhr.open('POST', endpoint, true);

  setSubmitting(true, 0);

  xhr.upload.onprogress = (event) => {
    if (!event.lengthComputable) return;
    const pct = Math.min(100, Math.round((event.loaded / event.total) * 100));
    setSubmitting(true, pct);
  };

  xhr.onload = () => {
    setSubmitting(false);
    let payload = null;
    try {
      payload = JSON.parse(xhr.responseText);
    } catch {
      payload = null;
    }

    if (xhr.status >= 200 && xhr.status < 300 && payload?.job_id) {
      state.jobIds = [payload.job_id, ...state.jobIds.filter((id) => id !== payload.job_id)].slice(0, 30);
      saveStoredJobIds();
      upsertJobRecord(payload);
      renderJobs();
      schedulePolling();
      showFeedback(`已建立任務 ${payload.job_id}，背景編譯開始。`, true);
      refreshStatusBanner();
    } else {
      const detail = payload?.detail || `提交失敗（HTTP ${xhr.status}）`;
      showFeedback(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
  };

  xhr.onerror = () => {
    setSubmitting(false);
    showFeedback('網路連線異常，無法上傳至伺服器。');
  };

  xhr.send(formData);
}

function upsertJobRecord(job) {
  const idx = state.jobs.findIndex((item) => item.job_id === job.job_id);
  if (idx >= 0) {
    state.jobs[idx] = job;
  } else {
    state.jobs.unshift(job);
  }
}

async function fetchStoredJobs() {
  if (!state.jobIds.length) {
    state.jobs = [];
    state.pollBackoffMs = 1500;
    renderJobs();
    return;
  }

  let shouldKeepPolling = state.jobs.some((j) => j.status === 'queued' || j.status === 'running') || !state.jobs.length;
  try {
    const qs = new URLSearchParams({ ids: state.jobIds.join(',') });
    const resp = await fetch(`/api/v1/jobs?${qs.toString()}`);
    if (!resp.ok) {
      state.pollBackoffMs = Math.min(10000, state.pollBackoffMs * 2);
      if (shouldKeepPolling) schedulePolling(state.pollBackoffMs);
      return;
    }
    const data = await resp.json();
    state.pollBackoffMs = 1500;
    const byId = new Map(data.map((j) => [j.job_id, j]));
    // Keep user's submission order while pruning expired IDs
    const validIds = state.jobIds.filter((id) => byId.has(id));
    if (validIds.length !== state.jobIds.length) {
      state.jobIds = validIds;
      saveStoredJobIds();
    }
    state.jobs = validIds.map((id) => byId.get(id));
    renderJobs();
    if (state.jobs.some((j) => j.status === 'queued' || j.status === 'running')) {
      schedulePolling(state.pollBackoffMs);
    }
  } catch {
    state.pollBackoffMs = Math.min(10000, state.pollBackoffMs * 2);
    if (shouldKeepPolling) {
      schedulePolling(state.pollBackoffMs);
    }
  }
}

function schedulePolling(delayMs = 1500) {
  if (state.pollTimer) return;
  state.pollTimer = setTimeout(async () => {
    state.pollTimer = null;
    await fetchStoredJobs();
    await refreshStatusBanner();
  }, delayMs);
}

function describeJobTitle(job) {
  const s = job.summary || {};
  if (s.source_filename) return `${s.source_filename}`;
  if (s.source_count) return `靜態家族批次（${s.source_count} 個來源字型）`;
  return `任務 (${job.mode})`;
}

function renderJobs() {
  const listEl = document.getElementById('job-list');
  const emptyEl = document.getElementById('queue-empty');
  emptyEl.hidden = state.jobs.length > 0;
  listEl.innerHTML = '';

  for (const job of state.jobs) {
    const card = document.createElement('article');
    card.className = 'job-card';

    const head = document.createElement('div');
    head.className = 'job-head';

    const titleWrap = document.createElement('div');
    const title = document.createElement('div');
    title.className = 'job-title';
    title.textContent = describeJobTitle(job);
    const idLine = document.createElement('div');
    idLine.className = 'job-id';
    idLine.textContent = `${job.job_id} · ${job.mode}`;
    titleWrap.append(title, idLine);

    const statusBadge = document.createElement('span');
    statusBadge.className = `job-status is-${job.status}`;
    statusBadge.textContent = job.status === 'queued' && job.queue_position > 0
      ? `排隊 #${job.queue_position}`
      : (STATUS_LABELS[job.status] || job.status);

    head.append(titleWrap, statusBadge);

    const line = document.createElement('div');
    line.className = `job-line is-${job.status}`;
    const lineFill = document.createElement('div');
    lineFill.className = 'job-line-fill';
    if (job.status === 'running') {
      lineFill.style.width = `${PHASE_PROGRESS[job.phase] || 55}%`;
    }
    line.appendChild(lineFill);

    const metaRow = document.createElement('div');
    metaRow.className = 'job-meta-row';
    const phaseSpan = document.createElement('span');
    phaseSpan.textContent = PHASE_LABELS[job.phase] || job.phase;
    const elapsedSpan = document.createElement('span');
    elapsedSpan.textContent = job.elapsed_seconds !== null ? `${job.elapsed_seconds.toFixed(1)}s` : '等待中';
    metaRow.append(phaseSpan, elapsedSpan);

    card.append(head, line, metaRow);

    if (job.error) {
      const errBox = document.createElement('div');
      errBox.className = 'job-error';
      errBox.textContent = job.error;
      card.appendChild(errBox);
    }

    if (job.log_tail && job.log_tail.length > 0) {
      const details = document.createElement('details');
      details.className = 'job-log-details';
      if (job.status === 'running' || job.status === 'failed') {
        details.open = true;
      }
      const summary = document.createElement('summary');
      summary.textContent = `Worker 編譯日誌 (${job.log_tail.length} 行)`;
      const pre = document.createElement('pre');
      pre.className = 'job-log';
      pre.textContent = job.log_tail.join('\n');
      details.append(summary, pre);
      card.appendChild(details);
    }

    const actions = document.createElement('div');
    actions.className = 'job-actions';

    if (job.status === 'completed' && job.download_url) {
      const primaryArt = job.artifacts.find((a) => a.primary) || job.artifacts[0];
      const dlBtn = document.createElement('a');
      dlBtn.className = 'btn-download';
      dlBtn.href = job.download_url;
      dlBtn.textContent = `下載主要檔案 (${formatBytes(primaryArt?.size_bytes || 0)})`;
      actions.appendChild(dlBtn);

      for (const art of job.artifacts) {
        if (art.primary) continue;
        const extra = document.createElement('a');
        extra.className = 'btn-artifact';
        extra.href = art.download_url;
        extra.textContent = `${art.filename} (${formatBytes(art.size_bytes)})`;
        actions.appendChild(extra);
      }
    }

    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'btn-delete-job';
    delBtn.textContent = job.status === 'running' || job.status === 'queued' ? '中止任務' : '刪除';
    delBtn.addEventListener('click', () => removeJob(job.job_id));
    actions.appendChild(delBtn);

    card.appendChild(actions);
    listEl.appendChild(card);
  }
}

async function removeJob(jobId) {
  try {
    await fetch(`/api/v1/jobs/${jobId}`, { method: 'DELETE' });
  } catch {
    // Remove locally even if already expired
  }
  state.jobIds = state.jobIds.filter((id) => id !== jobId);
  state.jobs = state.jobs.filter((j) => j.job_id !== jobId);
  saveStoredJobIds();
  renderJobs();
  refreshStatusBanner();
}

async function refreshStatusBanner() {
  try {
    const [capResp, healthResp] = await Promise.all([
      fetch('/api/v1/capabilities'),
      fetch('/healthz'),
    ]);
    if (capResp.ok) {
      const cap = await capResp.json();
      state.capabilities = cap;
      document.getElementById('brand-version').textContent =
        `OpenCC ${cap.opencc_data_version || '1.4.2'} · OpenType GSUB`;
      document.getElementById('cap-max-file').textContent = `${cap.max_file_mb} MB`;
      document.getElementById('cap-max-total').textContent = `${cap.max_total_upload_mb} MB`;
      document.getElementById('cap-workers').textContent = `${cap.running_jobs}/${cap.max_concurrent_jobs}`;
      document.getElementById('cap-rate').textContent =
        cap.rate_limit_per_min > 0 ? `${cap.rate_limit_per_min} 次/分` : '無限制';
      document.getElementById('cap-ttl').textContent = formatTTL(cap.job_ttl_seconds);
    }

    if (healthResp.ok || healthResp.status === 503) {
      const health = await healthResp.json();
      const pill = document.getElementById('health-pill');
      pill.classList.remove('is-ok', 'is-busy', 'is-err');
      if (health.status !== 'ok') {
        pill.classList.add('is-err');
        pill.textContent = '環境異常 (缺少 otfcc 或快取)';
      } else if (health.running_jobs > 0 || health.queued_jobs > 0) {
        pill.classList.add('is-busy');
        pill.textContent = `運行 ${health.running_jobs} · 排隊 ${health.queued_jobs}`;
      } else {
        pill.classList.add('is-ok');
        pill.textContent = 'Worker Ready';
      }
    }
  } catch {
    const pill = document.getElementById('health-pill');
    pill.classList.remove('is-ok', 'is-busy');
    pill.classList.add('is-err');
    pill.textContent = '無法連線伺服器';
  }
}

function init() {
  setupDropzones();

  document.querySelectorAll('.mode-btn').forEach((btn) => {
    btn.addEventListener('click', () => switchMode(btn.dataset.mode));
  });

  document.getElementById('mobile-nav-btn').addEventListener('click', openMobileDrawer);
  document.getElementById('nav-backdrop').addEventListener('click', () => closeMobileDrawer(true));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeMobileDrawer(true);
    }
  });
  window.addEventListener('resize', syncDrawerInert);

  document.querySelectorAll('[data-preview-config], [data-preview-nopunc]').forEach((el) => {
    el.addEventListener('change', () => {
      refreshSpecimen();
      updateCurlPreview();
    });
  });

  document.querySelectorAll('.mode-form input, .mode-form select').forEach((el) => {
    el.addEventListener('input', updateCurlPreview);
    el.addEventListener('change', updateCurlPreview);
  });

  document.getElementById('specimen-custom-input').addEventListener('input', () => {
    clearTimeout(state.previewTimer);
    state.previewTimer = setTimeout(() => {
      state.previewTimer = null;
      refreshSpecimen();
    }, 180);
  });

  document.getElementById('submit-btn').addEventListener('click', submitActiveJob);

  document.getElementById('copy-curl-btn').addEventListener('click', async () => {
    const text = document.getElementById('curl-preview').textContent;
    const btn = document.getElementById('copy-curl-btn');
    try {
      await navigator.clipboard.writeText(text);
      btn.textContent = '已複製';
      setTimeout(() => { btn.textContent = '複製 cURL'; }, 1500);
    } catch {
      btn.textContent = '請手動複製';
    }
  });

  document.getElementById('clear-history-btn').addEventListener('click', () => {
    const activeOnly = state.jobs.filter((j) => j.status === 'queued' || j.status === 'running');
    state.jobIds = activeOnly.map((j) => j.job_id);
    state.jobs = activeOnly;
    saveStoredJobIds();
    renderJobs();
  });

  switchMode('convert');
  refreshStatusBanner();
  fetchStoredJobs();
  setInterval(refreshStatusBanner, 15000);
}

init();
