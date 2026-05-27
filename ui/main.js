import { invoke } from '@tauri-apps/api/core';
import { getCurrentWindow } from '@tauri-apps/api/window';


// STATE MANAGEMENT
let state = {
  modsFolder: '',
  mods: [],
  originalMods: [], // Deep copy to check for modifications
  searchQuery: '',
  showNative: false,
  activeConfigPath: '',
  configEntries: [],
  originalConfigEntries: [], // Deep copy to check for config modifications
  ue4ssSettingsEntries: [],
  originalUe4ssSettingsEntries: [], // Deep copy to check for settings modifications
};

// DOM ELEMENT REFERENCES
const el = {
  welcomeScreen: document.getElementById('welcome-screen'),
  managerScreen: document.getElementById('manager-screen'),
  btnPickFolder: document.getElementById('btn-pick-folder'),
  btnChangeFolder: document.getElementById('btn-change-folder'),
  btnOpenFolder: document.getElementById('btn-open-folder'),
  btnOpenFolderMain: document.getElementById('btn-open-folder-main'),
  txtActivePath: document.getElementById('txt-active-path'),
  
  inpSearch: document.getElementById('inp-search'),
  btnClearSearch: document.getElementById('btn-clear-search'),
  chkShowNative: document.getElementById('chk-show-native'),
  chkToggleAll: document.getElementById('chk-toggle-all'),
  
  btnRefresh: document.getElementById('btn-refresh'),
  btnUndo: document.getElementById('btn-undo'),
  btnLaunch: document.getElementById('btn-launch'),
  
  listContainer: document.getElementById('list-container'),
  txtListCount: document.getElementById('txt-list-count'),
  
  chkSaveEnabled: document.getElementById('chk-save-enabled'),
  chkSaveJson: document.getElementById('chk-save-json'),
  chkSaveTxt: document.getElementById('chk-save-txt'),
  btnSave: document.getElementById('btn-save'),
  
  // Config Modal
  modalConfig: document.getElementById('modal-config'),
  txtModalTitle: document.getElementById('txt-modal-title'),
  txtModalSubtitle: document.getElementById('txt-modal-subtitle'),
  modalFieldsContainer: document.getElementById('modal-fields-container'),
  btnModalClose: document.getElementById('btn-modal-close'),
  btnModalCancel: document.getElementById('btn-modal-cancel'),
  btnModalSave: document.getElementById('btn-modal-save'),
  
  // Confirm Modal
  modalConfirm: document.getElementById('modal-confirm'),
  txtConfirmTitle: document.getElementById('txt-confirm-title'),
  txtConfirmDesc: document.getElementById('txt-confirm-desc'),
  btnConfirmCancel: document.getElementById('btn-confirm-cancel'),
  btnConfirmOk: document.getElementById('btn-confirm-ok'),
  
  // Drag and Drop
  dndOverlay: document.getElementById('dnd-overlay'),
  toastContainer: document.getElementById('toast-container'),
  
  // UE4SS Settings Modal
  btnUe4ssSettings: document.getElementById('btn-ue4ss-settings'),
  modalUe4ssSettings: document.getElementById('modal-ue4ss-settings'),
  txtUe4ssSettingsSubtitle: document.getElementById('txt-ue4ss-settings-subtitle'),
  modalUe4ssSettingsFieldsContainer: document.getElementById('modal-ue4ss-settings-fields-container'),
  btnUe4ssSettingsClose: document.getElementById('btn-ue4ss-settings-close'),
  btnUe4ssSettingsCancel: document.getElementById('btn-ue4ss-settings-cancel'),
  btnUe4ssSettingsSave: document.getElementById('btn-ue4ss-settings-save'),
};

// --- TOAST NOTIFICATIONS ---
function showToast(message, type = 'success', duration = 4000) {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  let icon = '🔔';
  if (type === 'success') icon = '✅';
  else if (type === 'error') icon = '❌';
  else if (type === 'warning') icon = '⚠️';
  else if (type === 'info') icon = 'ℹ️';

  toast.innerHTML = `
    <span class="toast-icon">${icon}</span>
    <span class="toast-message">${message}</span>
    <button class="toast-close">×</button>
  `;
  
  el.toastContainer.appendChild(toast);
  
  // Animate progress bar (simulated via CSS transition or just timeout)
  const closeBtn = toast.querySelector('.toast-close');
  closeBtn.addEventListener('click', () => {
    toast.classList.add('toast-fadeout');
    setTimeout(() => toast.remove(), 300);
  });
  
  setTimeout(() => {
    if (toast.parentNode) {
      toast.classList.add('toast-fadeout');
      setTimeout(() => toast.remove(), 300);
    }
  }, duration);
}

// --- CONFIRMATION DIALOG ---
let confirmResolver = null;
function showConfirm(title, description) {
  el.txtConfirmTitle.textContent = title;
  el.txtConfirmDesc.textContent = description;
  el.modalConfirm.classList.remove('hidden');
  
  return new Promise((resolve) => {
    confirmResolver = resolve;
  });
}

el.btnConfirmOk.addEventListener('click', () => {
  el.modalConfirm.classList.add('hidden');
  if (confirmResolver) {
    confirmResolver(true);
    confirmResolver = null;
  }
});

el.btnConfirmCancel.addEventListener('click', () => {
  el.modalConfirm.classList.add('hidden');
  if (confirmResolver) {
    confirmResolver(false);
    confirmResolver = null;
  }
});

// --- STATE HELPERS ---
function hasChanges() {
  if (state.mods.length !== state.originalMods.length) return true;
  for (let i = 0; i < state.mods.length; i++) {
    const m = state.mods[i];
    const orig = state.originalMods.find(o => o.name === m.name);
    if (!orig || orig.enabled !== m.enabled) {
      return true;
    }
  }
  return false;
}

function updateSaveButton() {
  const modified = hasChanges();
  el.btnSave.disabled = !modified;
}

// --- CONTROLLER ACTIONS ---
async function saveAppConfig() {
  try {
    const config = {
      mods_folder: state.modsFolder || null,
      show_native: state.showNative,
      save_enabled: el.chkSaveEnabled.checked,
      save_json: el.chkSaveJson.checked,
      save_txt: el.chkSaveTxt.checked,
    };
    await invoke('save_app_config', { config });
  } catch (err) {
    console.error('Failed to save application config:', err);
  }
}

async function init() {
  try {
    // Load config from persistence file
    const config = await invoke('load_app_config');
    
    // Restore UI preferences & folder path
    state.modsFolder = config.mods_folder || '';
    state.showNative = config.show_native || false;
    
    el.chkShowNative.checked = state.showNative;
    el.chkSaveEnabled.checked = config.save_enabled;
    el.chkSaveJson.checked = config.save_json;
    el.chkSaveTxt.checked = config.save_txt;
    
    if (state.modsFolder) {
      showToast('Configuration loaded successfully.', 'success');
      await loadMods();
    } else {
      showWelcomeScreen();
    }
  } catch (err) {
    console.error(err);
    showToast(`Initialization failed: ${err}`, 'error');
    showWelcomeScreen();
  }
}

function showWelcomeScreen() {
  el.welcomeScreen.classList.remove('hidden');
  el.managerScreen.classList.add('hidden');
}

function showManagerScreen() {
  el.welcomeScreen.classList.add('hidden');
  el.managerScreen.classList.remove('hidden');
  el.txtActivePath.textContent = state.modsFolder;
}

async function pickFolder() {
  try {
    const selected = await invoke('pick_mods_folder');
    if (selected) {
      state.modsFolder = selected;
      showToast('Mods folder selected successfully.', 'success');
      await saveAppConfig(); // Persistent save!
      await loadMods();
    }
  } catch (err) {
    showToast(`Failed to select directory: ${err}`, 'error');
  }
}

async function loadMods() {
  if (!state.modsFolder) return;
  
  try {
    const modsList = await invoke('load_mods', { modsFolder: state.modsFolder });
    state.mods = modsList.map(m => ({ ...m }));
    state.originalMods = modsList.map(m => ({ ...m })); // Keep a deep copy
    
    showManagerScreen();
    renderMods();
    updateSaveButton();
    el.chkToggleAll.checked = state.mods.every(m => m.enabled);
  } catch (err) {
    showToast(`Failed to load mods: ${err}`, 'error');
  }
}

async function saveAllChanges() {
  try {
    el.btnSave.disabled = true;
    const saveEnabled = el.chkSaveEnabled.checked;
    const saveJson = el.chkSaveJson.checked;
    const saveTxt = el.chkSaveTxt.checked;
    
    if (!saveEnabled && !saveJson && !saveTxt) {
      showToast('Please select at least one saving format strategy!', 'warning');
      el.btnSave.disabled = false;
      return;
    }
    
    await invoke('save_changes', {
      modsFolder: state.modsFolder,
      mods: state.mods,
      saveEnabled,
      saveJson,
      saveTxt,
    });
    
    showToast('All modifications saved successfully!', 'success');
    state.originalMods = state.mods.map(m => ({ ...m })); // Reset pristine baseline
    updateSaveButton();
  } catch (err) {
    showToast(`Error saving changes: ${err}`, 'error');
    updateSaveButton();
  }
}

function undoChanges() {
  if (!hasChanges()) return;
  state.mods = state.originalMods.map(m => ({ ...m }));
  renderMods();
  updateSaveButton();
  el.chkToggleAll.checked = state.mods.every(m => m.enabled);
  showToast('Reverted all unsaved modifications.', 'info');
}

async function runGame() {
  try {
    showToast('Starting game execution in background...', 'info');
    const result = await invoke('launch_game', { modsFolder: state.modsFolder });
    showToast(`Game process launched: ${result}`, 'success');
  } catch (err) {
    showToast(`Failed to start game: ${err}`, 'error');
  }
}

async function deleteMod(mod) {
  const ok = await showConfirm(
    'Delete Mod Permanently?',
    `Are you sure you want to permanently delete "${mod.name}"?\n\nThis will delete all scripts and configuration files for this mod from your hard drive. This action cannot be undone!`
  );
  if (!ok) return;
  
  try {
    showToast(`Deleting "${mod.name}"...`, 'info');
    await invoke('uninstall_mod', {
      modsFolder: state.modsFolder,
      modName: mod.name,
    });
    showToast(`Mod "${mod.name}" was permanently deleted.`, 'success');
    await loadMods(); // Reload mods from disk to refresh the state & UI
  } catch (err) {
    showToast(`Failed to delete mod: ${err}`, 'error');
  }
}

// --- LUA CONFIG ACTIONS ---
async function openConfigModal(mod) {
  if (!mod.config_path) return;
  
  try {
    state.activeConfigPath = mod.config_path;
    el.txtModalTitle.textContent = `Configure: ${mod.name}`;
    el.txtModalSubtitle.textContent = mod.config_path;
    
    const entries = await invoke('load_mod_config', { configPath: mod.config_path });
    state.configEntries = entries.map(e => ({ ...e }));
    state.originalConfigEntries = entries.map(e => ({ ...e }));
    
    renderConfigFields();
    el.modalConfig.classList.remove('hidden');
  } catch (err) {
    showToast(`Failed to parse configuration: ${err}`, 'error');
  }
}

function closeConfigModal() {
  el.modalConfig.classList.add('hidden');
  state.activeConfigPath = '';
  state.configEntries = [];
  state.originalConfigEntries = [];
}

async function saveConfig() {
  if (!state.activeConfigPath) return;
  
  try {
    // Gather updates
    const updates = {};
    let hasChanges = false;
    
    for (const entry of state.configEntries) {
      const orig = state.originalConfigEntries.find(o => o.key === entry.key);
      const inputEl = document.getElementById(makeDomId('cfg-input', entry.key));
      
      let newValue = entry.value;
      if (entry.value_type === 'boolean') {
        newValue = inputEl.checked;
      } else if (entry.value_type === 'number') {
        newValue = parseFloat(inputEl.value);
        if (isNaN(newValue)) {
          showToast(`Invalid numeric value for field "${entry.key}"`, 'error');
          return;
        }
      } else if (entry.value_type === 'string') {
        newValue = inputEl.value;
      }
      
      if (!orig || orig.value !== newValue) {
        updates[entry.key] = newValue;
        hasChanges = true;
      }
    }
    
    if (hasChanges) {
      await invoke('save_mod_config', {
        configPath: state.activeConfigPath,
        updates,
      });
      showToast('Lua configuration written successfully!', 'success');
    } else {
      showToast('No configuration changes detected.', 'info');
    }
    
    closeConfigModal();
  } catch (err) {
    showToast(`Failed to save config: ${err}`, 'error');
  }
}

// --- UE4SS SETTINGS INI ACTIONS ---
async function openUe4ssSettingsModal() {
  if (!state.modsFolder) return;
  
  try {
    showToast('Loading UE4SS configuration...', 'info', 1000);
    const entries = await invoke('load_ue4ss_settings', { modsFolder: state.modsFolder });
    state.ue4ssSettingsEntries = entries.map(e => ({ ...e }));
    state.originalUe4ssSettingsEntries = entries.map(e => ({ ...e }));
    
    // Resolve the subtitle path: usually parent of Mods + UE4SS-settings.ini
    const parts = state.modsFolder.split(/[\\/]/);
    const parentPath = parts.slice(0, -1).join('/');
    el.txtUe4ssSettingsSubtitle.textContent = `${parentPath}/UE4SS-settings.ini`;
    
    renderUe4ssSettingsFields();
    el.modalUe4ssSettings.classList.remove('hidden');
  } catch (err) {
    showToast(`Failed to parse settings: ${err}`, 'error');
  }
}

function closeUe4ssSettingsModal() {
  el.modalUe4ssSettings.classList.add('hidden');
  state.ue4ssSettingsEntries = [];
  state.originalUe4ssSettingsEntries = [];
}

async function saveUe4ssSettings() {
  if (!state.modsFolder) return;
  
  try {
    const updates = {};
    let hasChanges = false;
    
    for (const entry of state.ue4ssSettingsEntries) {
      const orig = state.originalUe4ssSettingsEntries.find(o => o.section === entry.section && o.key === entry.key);
      const inputEl = document.getElementById(makeDomId('ini-input', entry.section, entry.key));
      
      let newValue = entry.value;
      const isBoolVal = entry.value.toLowerCase() === 'true' || entry.value.toLowerCase() === 'false' || entry.value === '0' || entry.value === '1';
      
      if (isBoolVal) {
        if (entry.value === '0' || entry.value === '1') {
          newValue = inputEl.checked ? '1' : '0';
        } else {
          newValue = inputEl.checked ? 'true' : 'false';
        }
      } else {
        newValue = inputEl.value;
      }
      
      if (!orig || orig.value !== newValue) {
        // Use the composite section/key key to ensure exact uniqueness
        updates[`${entry.section}/${entry.key}`] = newValue;
        hasChanges = true;
      }
    }
    
    if (hasChanges) {
      await invoke('save_ue4ss_settings', {
        modsFolder: state.modsFolder,
        updates,
      });
      showToast('UE4SS configuration saved successfully!', 'success');
    } else {
      showToast('No settings changes detected.', 'info');
    }
    
    closeUe4ssSettingsModal();
  } catch (err) {
    showToast(`Failed to save settings: ${err}`, 'error');
  }
}

function renderUe4ssSettingsFields() {
  el.modalUe4ssSettingsFieldsContainer.innerHTML = '';
  
  if (state.ue4ssSettingsEntries.length === 0) {
    el.modalUe4ssSettingsFieldsContainer.innerHTML = `
      <div class="empty-state" style="color: var(--text-muted); text-align: center; padding: 20px;">No settings extracted from UE4SS-settings.ini.</div>
    `;
    return;
  }
  
  // Group entries by Section
  const grouped = {};
  state.ue4ssSettingsEntries.forEach(entry => {
    if (!grouped[entry.section]) {
      grouped[entry.section] = [];
    }
    grouped[entry.section].push(entry);
  });
  
  for (const section in grouped) {
    const sectionWrapper = document.createElement('div');
    sectionWrapper.className = 'config-section-group';
    sectionWrapper.style.marginBottom = '20px';
    
    const sectionHeader = document.createElement('h3');
    sectionHeader.textContent = section;
    sectionHeader.style.fontFamily = 'var(--font-display)';
    sectionHeader.style.fontSize = '14px';
    sectionHeader.style.fontWeight = '700';
    sectionHeader.style.color = 'var(--accent-purple)';
    sectionHeader.style.borderBottom = '1px solid rgba(255, 255, 255, 0.05)';
    sectionHeader.style.paddingBottom = '6px';
    sectionHeader.style.marginBottom = '12px';
    
    sectionWrapper.appendChild(sectionHeader);
    
    grouped[section].forEach(entry => {
      const fieldWrapper = document.createElement('div');
      fieldWrapper.className = 'config-field-row';
      fieldWrapper.style.marginBottom = '8px';
      
      let inputHtml = '';
      const inputId = makeDomId('ini-input', entry.section, entry.key);
      const descText = entry.comment ? `<p class="field-description">${escapeHtml(entry.comment).replace(/\n/g, '<br>')}</p>` : '';
      
      // Determine field type
      const valLower = entry.value.toLowerCase();
      const isBool = valLower === 'true' || valLower === 'false' || entry.value === '0' || entry.value === '1';
      
      if (isBool) {
        const isChecked = valLower === 'true' || entry.value === '1';
        inputHtml = `
          <div class="field-input-wrapper">
            <label class="switch-container">
              <input type="checkbox" id="${inputId}" ${isChecked ? 'checked' : ''}>
              <span class="switch-slider"></span>
            </label>
          </div>
        `;
      } else {
        // Fallback text input
        inputHtml = `
          <div class="field-input-wrapper">
            <input type="text" class="input-text" id="${inputId}" value="${escapeHtml(entry.value)}">
          </div>
        `;
      }
      
      fieldWrapper.innerHTML = `
        <div class="field-info">
          <label class="field-label" for="${inputId}">${escapeHtml(entry.key)}</label>
          ${descText}
        </div>
        ${inputHtml}
      `;
      
      sectionWrapper.appendChild(fieldWrapper);
    });
    
    el.modalUe4ssSettingsFieldsContainer.appendChild(sectionWrapper);
  }
}

// --- RENDERING VIEWS ---
function renderMods() {
  el.listContainer.innerHTML = '';
  
  // Filter mods
  const filtered = state.mods.filter(mod => {
    // Native mods toggle
    if (!state.showNative && mod.is_native) return false;
    // Search query
    if (state.searchQuery) {
      const q = state.searchQuery.toLowerCase();
      const matchName = mod.name.toLowerCase().includes(q);
      const matchScript = mod.scripts.some(s => s.toLowerCase().includes(q));
      if (!matchName && !matchScript) return false;
    }
    return true;
  });
  
  // Update count
  el.txtListCount.textContent = `Showing ${filtered.length} of ${state.mods.length} mods`;
  
  if (filtered.length === 0) {
    el.listContainer.innerHTML = `
      <div class="list-empty">
        <span class="empty-icon">📂</span>
        <p>No matching mod folders found.</p>
      </div>
    `;
    return;
  }
  
  filtered.forEach(mod => {
    const card = document.createElement('div');
    card.className = `mod-card ${mod.enabled ? 'enabled' : 'disabled'}`;
    
    // Determine language badge
    let langBadge = '';
    if (mod.is_native) {
      langBadge = `<span class="badge badge-native">Native</span>`;
    } else if (mod.lang === 'cpp') {
      langBadge = `<span class="badge badge-cpp">C++ Mod</span>`;
    } else if (mod.lang === 'lua') {
      langBadge = `<span class="badge badge-lua">Lua Mod</span>`;
    }
    
    // Scripts list summary
    let scriptsInfo = '';
    if (mod.scripts && mod.scripts.length > 0) {
      scriptsInfo = `
        <div class="mod-scripts">
          <strong>Files:</strong> ${mod.scripts.map(escapeHtml).join(', ')}
        </div>
      `;
    }
    
    // Config trigger button
    const configBtn = mod.config_path
      ? `<button class="btn btn-secondary btn-small btn-config" data-name="${escapeHtml(mod.name)}">⚙️ Configure</button>`
      : '';
      
    // Uninstall/Delete Button
    const deleteBtn = `<button class="btn btn-danger btn-small btn-delete" data-name="${escapeHtml(mod.name)}">🗑️ Delete</button>`;
      
    card.innerHTML = `
      <div class="card-left">
        <label class="checkbox-container">
          <input type="checkbox" class="mod-toggle" data-name="${escapeHtml(mod.name)}" ${mod.enabled ? 'checked' : ''}>
          <span class="checkbox-checkmark"></span>
        </label>
        <div class="mod-details">
          <div class="mod-header-row">
            <span class="mod-name">${escapeHtml(mod.name)}</span>
            ${langBadge}
          </div>
          ${scriptsInfo}
        </div>
      </div>
      <div class="card-right" style="display: flex; gap: 8px; align-items: center;">
        ${configBtn}
        ${deleteBtn}
      </div>
    `;
    
    // Bind toggle
    const toggle = card.querySelector('.mod-toggle');
    toggle.addEventListener('change', (e) => {
      const targetName = e.target.getAttribute('data-name');
      const m = state.mods.find(x => x.name === targetName);
      if (m) {
        m.enabled = e.target.checked;
        if (m.enabled) {
          card.classList.remove('disabled');
          card.classList.add('enabled');
        } else {
          card.classList.remove('enabled');
          card.classList.add('disabled');
        }
        updateSaveButton();
        el.chkToggleAll.checked = state.mods.every(x => x.enabled);
      }
    });
    
    // Bind config button
    if (mod.config_path) {
      const btn = card.querySelector('.btn-config');
      btn.addEventListener('click', () => openConfigModal(mod));
    }
    
    // Bind delete button
    const deleteBtnEl = card.querySelector('.btn-delete');
    deleteBtnEl.addEventListener('click', () => deleteMod(mod));
    
    el.listContainer.appendChild(card);
  });
}

function renderConfigFields() {
  el.modalFieldsContainer.innerHTML = '';
  
  if (state.configEntries.length === 0) {
    el.modalFieldsContainer.innerHTML = `
      <div class="empty-state">No configurable fields extracted from config.lua.</div>
    `;
    return;
  }
  
  state.configEntries.forEach(entry => {
    const fieldWrapper = document.createElement('div');
    fieldWrapper.className = 'config-field-row';
    
    let inputHtml = '';
    const inputId = makeDomId('cfg-input', entry.key);
    const descText = entry.comment ? `<p class="field-description">${escapeHtml(entry.comment)}</p>` : '';
    
    if (entry.value_type === 'boolean') {
      inputHtml = `
        <div class="field-input-wrapper">
          <label class="switch-container">
            <input type="checkbox" id="${inputId}" ${entry.value ? 'checked' : ''}>
            <span class="switch-slider"></span>
          </label>
        </div>
      `;
    } else if (entry.value_type === 'number') {
      inputHtml = `
        <div class="field-input-wrapper">
          <input type="number" step="any" class="input-text" id="${inputId}" value="${escapeHtml(String(entry.value))}">
        </div>
      `;
    } else if (entry.value_type === 'string') {
      inputHtml = `
        <div class="field-input-wrapper">
          <input type="text" class="input-text" id="${inputId}" value="${escapeHtml(entry.value)}">
        </div>
      `;
    } else {
      // Fallback
      inputHtml = `
        <div class="field-input-wrapper">
          <input type="text" class="input-text" id="${inputId}" value="${escapeHtml(String(entry.value))}">
        </div>
      `;
    }
    
    fieldWrapper.innerHTML = `
      <div class="field-info">
        <label class="field-label" for="${inputId}">${escapeHtml(entry.key)}</label>
        ${descText}
      </div>
      ${inputHtml}
    `;
    
    el.modalFieldsContainer.appendChild(fieldWrapper);
  });
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function makeDomId(prefix, ...parts) {
  return [prefix, ...parts.map(part => encodeURIComponent(String(part)))].join('-');
}

// --- DRAG AND DROP HANDLERS ---
window.addEventListener('dragover', (e) => {
  e.preventDefault();
});

window.addEventListener('drop', (e) => {
  e.preventDefault();
});

async function handleDropPath(path) {
  if (!state.modsFolder) {
    showToast('Please pick a Mods folder first before installing mods.', 'warning');
    return;
  }
  
  if (!path) {
    showToast('Failed to retrieve absolute path of the dropped item.', 'error');
    return;
  }
  
  // Extract filename
  const parts = path.split(/[\\/]/);
  const nameWithExt = parts[parts.length - 1] || parts[parts.length - 2] || "";
  if (!nameWithExt) {
    showToast('Failed to determine name from path.', 'error');
    return;
  }
  
  // Instant frontend validation for unsupported file extensions
  const lastDotIdx = nameWithExt.lastIndexOf('.');
  if (lastDotIdx !== -1) {
    const ext = nameWithExt.substring(lastDotIdx + 1).toLowerCase();
    const blockedExtensions = ['txt', 'exe', 'png', 'jpg', 'jpeg', 'pdf', 'mp3', 'mp4', 'tar', 'gz', 'json', 'dll', 'lua'];
    if (blockedExtensions.includes(ext)) {
      showToast(`Unsupported file format (.${ext}). Please drag in a ZIP, 7-Zip, RAR archive or mod folder.`, 'error');
      return;
    }
  }
  
  const nameLower = nameWithExt.toLowerCase();
  const isArchive = nameLower.endsWith('.zip') || nameLower.endsWith('.7z') || nameLower.endsWith('.rar');
  let name = nameWithExt;
  if (isArchive) {
    name = name.substring(0, name.lastIndexOf('.'));
  }
  
  const exists = state.mods.some(m => m.name.toLowerCase() === name.toLowerCase());
  let replace = false;
  
  if (exists) {
    const ok = await showConfirm(
      'Overwrite Existing Mod?',
      `A mod named "${name}" is already installed. Do you want to replace it? Unsaved changes in config files will be lost!`
    );
    if (!ok) {
      showToast('Installation cancelled.', 'info');
      return;
    }
    replace = true;
  }
  
  try {
    showToast(`Installing "${name}"...`, 'info');
    const newMod = await invoke('install_mod', {
      modsFolder: state.modsFolder,
      sourcePath: path,
      replace,
    });
    
    showToast(`Installed "${newMod.name}" successfully!`, 'success');
    await loadMods(); // Reload mods to show newly added item
  } catch (err) {
    showToast(`Failed to install mod: ${err}`, 'error');
  }
}

// --- EVENT LISTENERS ---
if (!window.__initialized) {
  window.__initialized = true;

  // Native Tauri drag & drop listener
  try {
    const appWindow = getCurrentWindow();
    appWindow.onDragDropEvent((event) => {
      if (event.payload.type === 'enter' || event.payload.type === 'over') {
        el.dndOverlay.classList.remove('hidden');
      } else if (event.payload.type === 'drop') {
        el.dndOverlay.classList.add('hidden');
        const paths = event.payload.paths;
        if (paths && paths.length > 0) {
          handleDropPath(paths[0]);
        }
      } else if (event.payload.type === 'leave') {
        el.dndOverlay.classList.add('hidden');
      }
    });
  } catch (err) {
    console.error('Failed to bind native drag-drop event:', err);
  }

  el.btnPickFolder.addEventListener('click', pickFolder);
  el.btnChangeFolder.addEventListener('click', pickFolder);
  
  const handleOpenFolder = async () => {
    if (!state.modsFolder) return;
    try {
      await invoke('open_mods_folder', { modsFolder: state.modsFolder });
    } catch (err) {
      showToast(`Failed to open mods directory: ${err}`, 'error');
    }
  };

  if (el.btnOpenFolder) {
    el.btnOpenFolder.addEventListener('click', handleOpenFolder);
  }
  if (el.btnOpenFolderMain) {
    el.btnOpenFolderMain.addEventListener('click', handleOpenFolder);
  }

  el.inpSearch.addEventListener('input', (e) => {
    state.searchQuery = e.target.value;
    if (state.searchQuery) {
      el.btnClearSearch.classList.remove('hidden');
    } else {
      el.btnClearSearch.classList.add('hidden');
    }
    renderMods();
  });

  el.btnClearSearch.addEventListener('click', () => {
    el.inpSearch.value = '';
    state.searchQuery = '';
    el.btnClearSearch.classList.add('hidden');
    renderMods();
  });

  el.chkShowNative.addEventListener('change', (e) => {
    state.showNative = e.target.checked;
    renderMods();
    saveAppConfig();
  });

  el.chkSaveEnabled.addEventListener('change', saveAppConfig);
  el.chkSaveJson.addEventListener('change', saveAppConfig);
  el.chkSaveTxt.addEventListener('change', saveAppConfig);

  el.chkToggleAll.addEventListener('change', (e) => {
    const checkState = e.target.checked;
    state.mods.forEach(m => {
      m.enabled = checkState;
    });
    renderMods();
    updateSaveButton();
    el.chkToggleAll.checked = state.mods.every(m => m.enabled);
  });

  el.btnRefresh.addEventListener('click', async () => {
    if (hasChanges()) {
      const ok = await showConfirm(
        'Discard Unsaved Modifications?',
        'You have unsaved changes to mod states. Refreshing will revert them.'
      );
      if (!ok) return;
    }
    await loadMods();
    showToast('Reloaded all mods from disk.', 'success');
  });

  el.btnUndo.addEventListener('click', undoChanges);
  el.btnSave.addEventListener('click', saveAllChanges);
  el.btnLaunch.addEventListener('click', runGame);

  // Config modal events
  el.btnModalClose.addEventListener('click', closeConfigModal);
  el.btnModalCancel.addEventListener('click', closeConfigModal);
  el.btnModalSave.addEventListener('click', saveConfig);

  // UE4SS Settings modal events
  el.btnUe4ssSettings.addEventListener('click', openUe4ssSettingsModal);
  el.btnUe4ssSettingsClose.addEventListener('click', closeUe4ssSettingsModal);
  el.btnUe4ssSettingsCancel.addEventListener('click', closeUe4ssSettingsModal);
  el.btnUe4ssSettingsSave.addEventListener('click', saveUe4ssSettings);

  // ESC key listener for modals
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (!el.modalConfig.classList.contains('hidden')) {
        closeConfigModal();
      }
      if (!el.modalUe4ssSettings.classList.contains('hidden')) {
        closeUe4ssSettingsModal();
      }
      if (!el.modalConfirm.classList.contains('hidden')) {
        el.modalConfirm.classList.add('hidden');
        if (confirmResolver) {
          confirmResolver(false);
          confirmResolver = null;
        }
      }
    }
  });
}

// INITIALIZE APP
init();
