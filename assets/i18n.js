/**
 * Client-Side Internationalization (i18n) System
 * 
 * Features:
 * - No server request needed to change language
 * - Auto-detect browser language on first visit
 * - Persist language choice in localStorage
 * - Easy to extend with new languages
 * 
 * Usage:
 * 1. Add data-i18n="key" to elements that need translation
 * 2. Add data-i18n-attr="key:attr" for attributes (e.g., placeholder, alt)
 * 3. Call I18n.init() on page load
 */

const I18n = {
  // All translations (injected by server)
  translations: {},
  
  // Current active language
  currentLang: 'en',
  
  /**
   * Initialize i18n system
   * Should be called once on page load
   */
  init() {
    // Get saved language or detect from browser
    this.currentLang = this.getPreferredLanguage();
    
    // Apply translations
    this.updatePage();
    
    // Setup language switcher events
    this.setupSwitcher();
    
    console.log(`[i18n] Initialized with language: ${this.currentLang}`);
  },
  
  /**
   * Get preferred language from localStorage or browser
   */
  getPreferredLanguage() {
    // Check localStorage first
    const saved = localStorage.getItem('preferred_lang');
    if (saved && this.translations[saved]) {
      return saved;
    }
    
    // Detect from browser
    const browserLang = navigator.language || navigator.userLanguage;
    const langCode = browserLang.toLowerCase().slice(0, 2);
    
    if (this.translations[langCode]) {
      return langCode;
    }
    
    // Fallback to English
    return 'en';
  },
  
  /**
   * Change language
   * @param {string} lang - Language code (e.g., 'en', 'id')
   */
  set(lang) {
    if (!this.translations[lang]) {
      console.warn(`[i18n] Language "${lang}" not found, falling back to English`);
      lang = 'en';
    }
    
    this.currentLang = lang;
    localStorage.setItem('preferred_lang', lang);
    
    this.updatePage();
    
    // Update dropdown state
    this.updateSwitcherState();
    
    console.log(`[i18n] Language changed to: ${lang}`);
  },
  
  /**
   * Update all translatable elements on page
   */
  updatePage() {
    const translations = this.translations[this.currentLang] || {};
    
    // Update text content
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      const text = translations[key];
      if (text !== undefined) {
        // Check if text contains HTML tags (for safe HTML content)
        if (el.dataset.i18nHtml === 'true') {
          el.innerHTML = text;
        } else {
          el.textContent = text;
        }
      }
    });
    
    // Update attributes (placeholder, title, alt, etc.)
    document.querySelectorAll('[data-i18n-attr]').forEach(el => {
      const parts = el.dataset.i18nAttr.split(':');
      const key = parts[0];
      const attr = parts[1] || 'textContent';
      const text = translations[key];
      if (text !== undefined) {
        el.setAttribute(attr, text);
      }
    });
    
    // Update HTML lang attribute
    document.documentElement.lang = this.currentLang;
  },
  
  /**
   * Setup language switcher dropdown
   */
  setupSwitcher() {
    const switcher = document.querySelector('.lang-switcher');
    if (!switcher) return;
    
    // Get available languages from translations object
    const availableLangs = Object.keys(this.translations);
    
    // Create language buttons
    switcher.innerHTML = availableLangs.map(lang => `
      <button 
        class="lang-btn ${lang === this.currentLang ? 'active' : ''}" 
        data-lang="${lang}"
        type="button"
      >
        ${this.getLangName(lang)}
      </button>
    `).join('');
    
    // Add click handlers
    switcher.querySelectorAll('.lang-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const lang = btn.dataset.lang;
        this.set(lang);
      });
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
      if (!switcher.contains(e.target)) {
        switcher.classList.remove('open');
      }
    });
    
    this.updateSwitcherState();
  },
  
  /**
   * Update switcher dropdown appearance
   */
  updateSwitcherState() {
    const switcher = document.querySelector('.lang-switcher');
    if (!switcher) return;
    
    // Update active button
    switcher.querySelectorAll('.lang-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.lang === this.currentLang);
    });
  },
  
  /**
   * Get human-readable language name
   */
  getLangName(code) {
    const names = {
      'en': 'English',
      'id': 'Indonesia',
      'ja': '日本語',
      'ko': '한국어',
      'zh': '中文',
      'es': 'Español',
      'fr': 'Français',
      'de': 'Deutsch'
    };
    return names[code] || code.toUpperCase();
  },
  
  /**
   * Get current language
   */
  getLang() {
    return this.currentLang;
  },
  
  /**
   * Get translation for a key
   */
  t(key) {
    return this.translations[this.currentLang]?.[key] || 
           this.translations['en']?.[key] || 
           key;
  }
};

// Make I18n available globally
window.I18n = I18n;
