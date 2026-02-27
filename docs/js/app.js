// 全球新闻 24H - Inoreader 风格
let allArticles = [];
let filteredArticles = [];
let enabledCategories = [];  // 空数组表示全选
let enabledSources = [];     // 空数组表示全选
let currentLang = 'zh';
let isDarkMode = false;

const categoryNames = {
    world:'国际', politics:'政治', business:'商业', finance:'财经',
    technology:'科技', science:'科学', sports:'体育', entertainment:'娱乐',
    asia:'亚洲', china:'中国', us:'美国', uk:'英国', europe:'欧洲', 
    startups:'创业'
};

function init() {
    const saved = localStorage.getItem('newsSettings');
    if (saved) {
        const s = JSON.parse(saved);
        // 如果保存了空数组或 undefined，表示全选
        enabledCategories = s.categories !== undefined ? s.categories : [];
        enabledSources = s.sources !== undefined ? s.sources : [];
    }
    const theme = localStorage.getItem('theme');
    if (theme === 'dark') {
        isDarkMode = true;
        document.body.classList.add('dark-mode');
        document.getElementById('theme-btn').textContent = '☀️';
    }
    setupEventListeners();
    fetchNews();
    setInterval(fetchNews, 300000);
}

function setupEventListeners() {
    const settingsBtn = document.getElementById('settings-btn');
    const closeBtn = document.getElementById('close-settings');
    const themeBtn = document.getElementById('theme-btn');
    const langBtn = document.getElementById('lang-btn');
    const applyBtn = document.getElementById('apply-settings');
    const resetBtn = document.getElementById('reset-settings');
    
    if (settingsBtn) settingsBtn.addEventListener('click', toggleSettings);
    if (closeBtn) closeBtn.addEventListener('click', toggleSettings);
    if (themeBtn) themeBtn.addEventListener('click', toggleTheme);
    if (langBtn) langBtn.addEventListener('click', toggleLang);
    if (applyBtn) applyBtn.addEventListener('click', applySettings);
    if (resetBtn) resetBtn.addEventListener('click', resetSettings);
}

function toggleSettings() {
    const panel = document.getElementById('settings-panel');
    if (!panel) return;
    panel.classList.toggle('hidden');
    if (!panel.classList.contains('hidden')) {
        syncSettingsUI();
        populateSourceFilters();
    }
}

function populateSourceFilters() {
    const container = document.getElementById('source-filters');
    if (!container) return;
    const sources = [...new Set(allArticles.map(a => a.source))];
    if (sources.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无来源</div>';
        return;
    }
    
    container.innerHTML = sources.map(source => {
        // 空数组表示全选，所以 checked
        const checked = enabledSources.length === 0 || enabledSources.includes(source) ? 'checked' : '';
        return `<label class="source-item">
            <input type="checkbox" value="${source}" ${checked}>
            <span>${source}</span>
        </label>`;
    }).join('');
}

function toggleTheme() {
    isDarkMode = !isDarkMode;
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
    const themeBtn = document.getElementById('theme-btn');
    if (themeBtn) themeBtn.textContent = isDarkMode ? '☀️' : '🌙';
}

function toggleLang() {
    currentLang = currentLang === 'zh' ? 'en' : 'zh';
    localStorage.setItem('lang', currentLang);
    const langBtn = document.getElementById('lang-btn');
    if (langBtn) langBtn.textContent = currentLang === 'zh' ? '🇨🇳' : '🇺🇸';
    // 重新渲染，语言切换时新闻文本也要跟着变
    renderNews();
}

function syncSettingsUI() {
    // 获取所有可用的分类
    const allCategories = [...new Set(allArticles.map(a => a.category))];
    document.querySelectorAll('#category-filters input').forEach(cb => {
        // 空数组表示全选
        const isChecked = enabledCategories.length === 0 || enabledCategories.includes(cb.value);
        cb.checked = isChecked;
    });
    document.querySelectorAll('#source-filters input').forEach(cb => {
        const isChecked = enabledSources.length === 0 || enabledSources.includes(cb.value);
        cb.checked = isChecked;
    });
}

function applySettings() {
    enabledCategories = Array.from(document.querySelectorAll('#category-filters input:checked')).map(cb => cb.value);
    enabledSources = Array.from(document.querySelectorAll('#source-filters input:checked')).map(cb => cb.value);
    localStorage.setItem('newsSettings', JSON.stringify({ categories: enabledCategories, sources: enabledSources }));
    toggleSettings();
    filterAndRender();
}

function resetSettings() {
    // 重置为全选（空数组）
    enabledCategories = [];
    enabledSources = [];
    syncSettingsUI();
    filterAndRender();
}

function filterAndRender() {
    filteredArticles = allArticles.filter(a => {
        // 空数组表示全选
        const catMatch = enabledCategories.length === 0 || enabledCategories.includes(a.category);
        const srcMatch = enabledSources.length === 0 || enabledSources.includes(a.source);
        return catMatch && srcMatch;
    });
    renderNews();
}

function formatTime(dateStr) {
    try {
        const dt = new Date(dateStr);
        return dt.toLocaleTimeString(currentLang === 'zh' ? 'zh-CN' : 'en-US', {
            hour: '2-digit', minute: '2-digit'
        });
    } catch { return '--:--'; }
}

function getNewsText(article) {
    // 中文模式：显示翻译后的摘要
    if (currentLang === 'zh') {
        if (article.one_line && article.one_line !== article.title) return article.one_line;
        if (article.translated_title) return article.translated_title;
    }
    // 英文模式：显示原标题
    return article.title;
}

function renderNews() {
    const container = document.getElementById('news-container');
    if (!container) return;
    
    if (filteredArticles.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无新闻，请调整筛选条件</div>';
        return;
    }
    
    container.innerHTML = filteredArticles.map(a => {
        const time = a.time || formatTime(a.published);
        const text = getNewsText(a);
        const catName = categoryNames[a.category] || a.category;
        
        return `
            <div class="news-item">
                <span class="news-time">${time}</span>
                <div class="news-source-wrap">
                    <span class="news-source">${a.source}</span>
                </div>
                <span class="news-text">${text}</span>
                <span class="news-category">${catName}</span>
            </div>
        `;
    }).join('');
    
    const statTotal = document.getElementById('stat-total');
    const updateTime = document.getElementById('update-time');
    const lastUpdated = document.getElementById('last-updated');
    
    if (statTotal) statTotal.textContent = filteredArticles.length;
    if (updateTime) updateTime.textContent = allArticles.length > 0 ? formatTime(allArticles[0].published) : '--:--';
    if (lastUpdated) lastUpdated.textContent = allArticles.length > 0 ? `${formatTime(allArticles[0].published)} 更新` : '';
}

async function fetchNews() {
    try {
        const resp = await fetch('data/news.json?t=' + Date.now());
        const data = await resp.json();
        allArticles = data.articles || [];
        filterAndRender();
    } catch (e) {
        console.error('Fetch error:', e);
        const container = document.getElementById('news-container');
        if (container) {
            container.innerHTML = '<div class="empty-state">加载失败，请刷新页面</div>';
        }
    }
}

// 确保 DOM 加载完成后初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
