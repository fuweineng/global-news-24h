// 全球新闻 24H - Inoreader 风格
let allArticles = [];
let filteredArticles = [];
let enabledCategories = ['world','politics','business','finance','technology','science'];
let enabledSources = ['Reuters','BBC','CNN','NHK','DW','France24'];
let currentLang = 'zh';
let isDarkMode = false;

// 初始化
function init() {
    const saved = localStorage.getItem('newsSettings');
    if (saved) {
        const s = JSON.parse(saved);
        enabledCategories = s.categories || enabledCategories;
        enabledSources = s.sources || enabledSources;
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
    document.getElementById('settings-btn').addEventListener('click', toggleSettings);
    document.getElementById('close-settings').addEventListener('click', toggleSettings);
    document.getElementById('theme-btn').addEventListener('click', toggleTheme);
    document.getElementById('lang-btn').addEventListener('click', toggleLang);
    document.getElementById('apply-settings').addEventListener('click', applySettings);
    document.getElementById('reset-settings').addEventListener('click', resetSettings);
}

function toggleSettings() {
    const panel = document.getElementById('settings-panel');
    panel.classList.toggle('hidden');
    if (!panel.classList.contains('hidden')) {
        syncSettingsUI();
    }
}

function toggleTheme() {
    isDarkMode = !isDarkMode;
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
    document.getElementById('theme-btn').textContent = isDarkMode ? '☀️' : '🌙';
}

function toggleLang() {
    currentLang = currentLang === 'zh' ? 'en' : 'zh';
    localStorage.setItem('lang', currentLang);
    document.getElementById('lang-btn').textContent = currentLang === 'zh' ? '🇨🇳' : '🇺🇸';
    renderNews();
}

function syncSettingsUI() {
    document.querySelectorAll('#category-filters input').forEach(cb => {
        cb.checked = enabledCategories.includes(cb.value);
    });
    document.querySelectorAll('#source-filters input').forEach(cb => {
        cb.checked = enabledSources.includes(cb.value);
    });
}

function applySettings() {
    enabledCategories = Array.from(document.querySelectorAll('#category-filters input:checked'))
        .map(cb => cb.value);
    enabledSources = Array.from(document.querySelectorAll('#source-filters input:checked'))
        .map(cb => cb.value);
    localStorage.setItem('newsSettings', JSON.stringify({
        categories: enabledCategories,
        sources: enabledSources
    }));
    toggleSettings();
    filterAndRender();
}

function resetSettings() {
    enabledCategories = ['world','politics','business','finance','technology','science'];
    enabledSources = ['Reuters','BBC','CNN','NHK','DW','France24'];
    syncSettingsUI();
}

function filterAndRender() {
    filteredArticles = allArticles.filter(a => 
        enabledCategories.includes(a.category) && 
        enabledSources.includes(a.source)
    );
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

function renderNews() {
    const container = document.getElementById('news-container');
    if (filteredArticles.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无新闻，请调整筛选条件</div>';
        return;
    }
    container.innerHTML = filteredArticles.map(a => {
        const time = a.time || formatTime(a.published);
        const text = (currentLang === 'zh' && a.one_line) ? a.one_line : a.title;
        const catName = {
            world:'国际',politics:'政治',business:'商业',finance:'财经',
            technology:'科技',science:'科学',sports:'体育',entertainment:'娱乐',
            asia:'亚洲',china:'中国',us:'美国',uk:'英国',europe:'欧洲'
        }[a.category] || a.category;
        return `
            <div class="news-item">
                <span class="news-time">${time}</span>
                <span class="news-source">${a.source}</span>
                <span class="news-text">${text}</span>
                <span class="news-category">${catName}</span>
            </div>
        `;
    }).join('');
    document.getElementById('stat-total').textContent = filteredArticles.length;
    document.getElementById('update-time').textContent = 
        allArticles.length > 0 ? formatTime(allArticles[0].published) : '--:--';
    document.getElementById('last-updated').textContent = 
        allArticles.length > 0 ? `${formatTime(allArticles[0].published)} 更新` : '';
}

async function fetchNews() {
    try {
        const resp = await fetch('data/news.json?t=' + Date.now());
        const data = await resp.json();
        allArticles = data.articles || [];
        filterAndRender();
    } catch (e) {
        console.error('Fetch error:', e);
        document.getElementById('news-container').innerHTML = 
            '<div class="empty-state">加载失败，请刷新</div>';
    }
}

document.addEventListener('DOMContentLoaded', init);
