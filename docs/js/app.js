// Global News App - 客观一句话新闻
let allArticles = [];
let filteredArticles = [];
let currentFilter = 'all';
let currentSearch = '';
let currentLang = 'zh';
let isDarkMode = false;

const translations = {
    zh: {
        title: '24 小时全球新闻',
        darkMode: '暗黑',
        lightMode: '白天',
        langName: '中文',
        filterAll: '全部',
        loading: '加载中...',
        error: '无法加载新闻',
        noNews: '没有新闻',
        searchPlaceholder: '搜索...',
        search: '搜索',
        totalArticles: '总数',
        sources: '来源'
    },
    en: {
        title: '24Hr Global News',
        darkMode: 'Dark',
        lightMode: 'Light',
        langName: 'English',
        filterAll: 'All',
        loading: 'Loading...',
        error: 'Unable to load',
        noNews: 'No news',
        searchPlaceholder: 'Search...',
        search: 'Search',
        totalArticles: 'Total',
        sources: 'Sources'
    }
};

function initSettings() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        isDarkMode = true;
        document.body.classList.add('dark-mode');
        document.getElementById('theme-icon').textContent = '☀️';
    }
    currentLang = localStorage.getItem('lang') || 'zh';
    updateUILang();
}

function toggleLanguage() {
    currentLang = currentLang === 'zh' ? 'en' : 'zh';
    localStorage.setItem('lang', currentLang);
    updateUILang();
    renderNews(filterArticles());
}

function updateUILang() {
    const t = translations[currentLang];
    document.getElementById('lang-icon').textContent = currentLang === 'zh' ? '🇨🇳' : '🇺🇸';
    document.getElementById('lang-text').textContent = t.langName;
    document.getElementById('search-input').placeholder = t.searchPlaceholder;
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t[key]) el.textContent = t[key];
    });
}

function toggleTheme() {
    isDarkMode = !isDarkMode;
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
    document.getElementById('theme-icon').textContent = isDarkMode ? '☀️' : '🌙';
}

function filterArticles() {
    let articles = allArticles;
    if (currentFilter !== 'all') {
        articles = articles.filter(a => a.category === currentFilter);
    }
    if (currentSearch) {
        const q = currentSearch.toLowerCase();
        articles = articles.filter(a => 
            a.title.toLowerCase().includes(q) || 
            (a.one_line && a.one_line.toLowerCase().includes(q))
        );
    }
    return articles;
}

function formatTime(dateStr) {
    try {
        const dt = new Date(dateStr);
        return dt.toLocaleTimeString(currentLang === 'zh' ? 'zh-CN' : 'en-US', {
            hour: '2-digit', minute: '2-digit'
        });
    } catch { return '--:--'; }
}

function renderNews(articles) {
    const container = document.getElementById('news-container');
    const t = translations[currentLang];
    
    if (articles.length === 0) {
        container.innerHTML = `<div class="empty-state">${t.noNews}</div>`;
        return;
    }
    
    // 单行格式：时间，新闻来源 新闻浓缩一句话
    container.innerHTML = articles.map(article => {
        const time = article.time || formatTime(article.published);
        const source = article.source;
        const text = (currentLang === 'zh' && article.one_line) ? article.one_line : article.title;
        
        return `
            <a href="${article.link}" target="_blank" rel="noopener" class="news-line">
                <span class="news-time">${time}</span>
                <span class="news-source">${source}</span>
                <span class="news-text">${text}</span>
            </a>
        `;
    }).join('');
    
    // 更新统计
    document.getElementById('stat-total').textContent = articles.length;
    document.getElementById('stat-sources').textContent = allArticles.length > 0 ? 
        new Set(allArticles.map(a => a.source)).size : 0;
    document.getElementById('last-update-stat').textContent = 
        allArticles.length > 0 ? formatTime(allArticles[0].published) : '-';
}

async function fetchNews() {
    try {
        const resp = await fetch('data/news.json?t=' + Date.now());
        const data = await resp.json();
        allArticles = data.articles || [];
        filteredArticles = filterArticles();
        renderNews(filteredArticles);
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('news-container').innerHTML = 
            `<div class="error">${translations[currentLang].error}</div>`;
    }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    initSettings();
    document.getElementById('lang-toggle').addEventListener('click', toggleLanguage);
    document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
    
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.getAttribute('data-category');
            filteredArticles = filterArticles();
            renderNews(filteredArticles);
        });
    });
    
    document.querySelector('.search-btn').addEventListener('click', () => {
        currentSearch = document.getElementById('search-input').value;
        filteredArticles = filterArticles();
        renderNews(filteredArticles);
    });
    
    document.getElementById('search-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            currentSearch = e.target.value;
            filteredArticles = filterArticles();
            renderNews(filteredArticles);
        }
    });
    
    fetchNews();
    setInterval(fetchNews, 300000); // 5 分钟刷新
});
