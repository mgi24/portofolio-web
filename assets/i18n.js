/**
 * Client-Side Internationalization (i18n) System
 * 
 * Features:
 * - No server request needed to change language
 * - Default language is English
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
  
  // Default language
  defaultLang: 'en',
  
  // Current active language
  currentLang: 'en',
  
  /**
   * Initialize i18n system
   * Should be called once on page load
   */
  init() {
    // Get saved language or fallback to English
    this.currentLang = this.getPreferredLanguage();
    
    // Apply translations
    this.updatePage();
    
    // Setup language switcher events
    this.setupSwitcher();
    
    console.log(`[i18n] Initialized with language: ${this.currentLang}`);
  },
  
  /**
   * Get preferred language from localStorage or fallback to English
   */
  getPreferredLanguage() {
    // Check localStorage first
    const saved = localStorage.getItem('preferred_lang');
    if (saved && this.translations[saved]) {
      return saved;
    }
    
    // Fallback to English (default)
    return this.defaultLang;
  },
  
  /**
   * Change language
   * @param {string} lang - Language code (e.g., 'en', 'id')
   */
  set(lang) {
    if (!this.translations[lang]) {
      console.warn(`[i18n] Language "${lang}" not found, falling back to English`);
      lang = this.defaultLang;
    }
    
    this.currentLang = lang;
    
    // Save to localStorage for persistence
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
    const dropdown = document.querySelector('.dropdown');
    if (!dropdown) return;
    
    // Get available languages from translations object
    const availableLangs = Object.keys(this.translations);
    
    // Update dropdown button with current language
    const dropbtn = dropdown.querySelector('.dropbtn');
    if (dropbtn) {
      dropbtn.textContent = this.getLangName(this.currentLang) + ' ▼';
    }
    
    // Update dropdown content with language options
    const dropdownContent = dropdown.querySelector('.dropdown-content');
    if (dropdownContent) {
      dropdownContent.innerHTML = availableLangs.map(lang => `
        <a href="#" class="lang-link" data-lang="${lang}">${this.getLangName(lang)}</a>
      `).join('');
      
      // Add click handlers
      dropdownContent.querySelectorAll('.lang-link').forEach(link => {
        link.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          const lang = link.dataset.lang;
          this.set(lang);
        });
      });
    }
    
    this.updateSwitcherState();
  },
  
  /**
   * Update dropdown button state
   */
  updateSwitcherState() {
    const dropdown = document.querySelector('.dropdown');
    if (!dropdown) return;
    
    const dropbtn = dropdown.querySelector('.dropbtn');
    if (dropbtn) {
      dropbtn.textContent = this.getLangName(this.currentLang) + ' ▼';
    }
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
           this.translations[this.defaultLang]?.[key] || 
           key;
  }
};

// Make I18n available globally
window.I18n = I18n;
