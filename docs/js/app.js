// Global News App - Enhanced with Search & Stats
let allArticles = [];
let filteredArticles = [];
let currentFilter = 'all';
let currentSearch = '';
let currentLang = 'zh';
let isDarkMode = false;

// Translations
const translations = {
    zh: {
        title: '24 小时全球新闻',
        darkMode: '暗黑',
        lightMode: '白天',
        langName: '中文',
        filterAll: '全部',
        filterWorld: '🌍 国际',
        filterPolitics: '🏛️ 政治',
        filterBusiness: '💼 商业',
        filterFinance: '📈 财经',
        filterTechnology: '💻 科技',
        filterStartups: '🚀 创业',
        filterScience: '🔬 科学',
        filterSports: '⚽ 体育',
        filterEntertainment: '🎬 娱乐',
        filterMusic: '🎵 音乐',
        filterAsia: '🌏 亚洲',
        filterChina: '🇨🇳 中国',
        filterJapan: '🇯🇵 日本',
        filterKorea: '🇰🇷 韩国',
        filterEurope: '🇪🇺 欧洲',
        filterUS: '🇺🇸 美国',
        filterUK: '🇬🇧 英国',
        updateFreq: '每 30 分钟更新',
        dataSource: '数据来自全球 RSS 源',
        viewOnGithub: '查看 GitHub',
        loading: '正在加载新闻...',
        error: '无法加载新闻',
        retry: '请稍后再试',
        noNews: '没有找到新闻',
        adjustFilters: '尝试调整筛选条件',
        justNow: '刚刚',
        minutesAgo: '{n}分钟前',
        hoursAgo: '{n}小时前',
        today: '今天',
        yesterday: '昨天',
        readMore: '阅读原文',
        searchPlaceholder: '搜索新闻...',
        search: '搜索',
        totalArticles: '总新闻数',
        sources: '新闻源',
        lastUpdate: '最后更新'
    },
    en: {
        title: '24Hr Global News',
        darkMode: 'Dark',
        lightMode: 'Light',
        langName: 'English',
        filterAll: 'All',
        filterWorld: '🌍 World',
        filterPolitics: '🏛️ Politics',
        filterBusiness: '💼 Business',
        filterFinance: '📈 Finance',
        filterTechnology: '💻 Tech',
        filterStartups: '🚀 Startups',
        filterScience: '🔬 Science',
        filterSports: '⚽ Sports',
        filterEntertainment: '🎬 Entertainment',
        filterMusic: '🎵 Music',
        filterAsia: '🌏 Asia',
        filterChina: '🇨🇳 China',
        filterJapan: '🇯🇵 Japan',
        filterKorea: '🇰🇷 Korea',
        filterEurope: '🇪🇺 Europe',
        filterUS: '🇺🇸 US',
        filterUK: '🇬🇧 UK',
        updateFreq: 'Updated every 30 minutes',
        dataSource: 'Data from global RSS feeds',
        viewOnGithub: 'View on GitHub',
        loading: 'Loading news...',
        error: 'Unable to load news',
        retry: 'Please check back in a few minutes',
        noNews: 'No news found',
        adjustFilters: 'Try adjusting your filters',
        justNow: 'Just now',
        minutesAgo: '{n}m ago',
        hoursAgo: '{n}h ago',
        today: 'Today',
        yesterday: 'Yesterday',
        readMore: 'Read',
        searchPlaceholder: 'Search news...',
        search: 'Search',
        totalArticles: 'Total Articles',
        sources: 'Sources',
        lastUpdate: 'Last Update'
    }
};

// Initialize
function initSettings() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        isDarkMode = true;
        document.body.classList.add('dark-mode');
        document.getElementById('theme-icon').textContent = '☀️';
        document.getElementById('theme-text').textContent = translations[currentLang].lightMode;
    }
    
    const savedLang = localStorage.getItem('lang') || 'zh';
    setLanguage(savedLang);
}

function toggleLanguage() {
    currentLang = currentLang === 'zh' ? 'en' : 'zh';
    localStorage.setItem('lang', currentLang);
    
    const t = translations[currentLang];
    document.getElementById('lang-icon').textContent = currentLang === 'zh' ? '🇨🇳' : '🇺🇸';
    document.getElementById('lang-text').textContent = t.langName;
    
    updateUITranslations();
    renderNews(filterArticles());
}

function updateUITranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[currentLang][key]) {
            el.textContent = translations[currentLang][key];
        }
    });
    
    const t = translations[currentLang];
    document.getElementById('theme-text').textContent = isDarkMode ? t.lightMode : t.darkMode;
    document.getElementById('search-input').placeholder = t.searchPlaceholder;
    document.querySelector('.search-btn').textContent = t.search;
}

function toggleTheme() {
    isDarkMode = !isDarkMode;
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
    
    const t = translations[currentLang];
    document.getElementById('theme-icon').textContent = isDarkMode ? '☀️' : '🌙';
    document.getElementById('theme-text').textContent = isDarkMode ? t.lightMode : t.darkMode;
}

function setLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('lang', lang);
    
    const t = translations[lang];
    document.getElementById('lang-icon').textContent = lang === 'zh' ? '🇨🇳' : '🇺🇸';
    document.getElementById('lang-text').textContent = t.langName;
    
    updateUITranslations();
}

async function fetchNews() {
    try {
        const response = await fetch('./data/news.json');
        if (!response.ok) throw new Error('Failed to load news data');
        
        const data = await response.json();
        allArticles = data.articles;
        
        const updateTime = new Date(data.updated);
        const t = translations[currentLang];
        document.getElementById('last-updated').textContent = `${t.lastUpdate}: ${formatUpdateTime(updateTime)}`;
        
        // Update stats
        document.getElementById('stat-total').textContent = data.total;
        document.getElementById('stat-sources').textContent = data.sources_count;
        
        filteredArticles = allArticles;
        renderNews(filteredArticles);
    } catch (error) {
        console.error('Error fetching news:', error);
        const t = translations[currentLang];
        document.getElementById('news-container').innerHTML = `
            <div class="error">
                <h3>😕 ${t.error}</h3>
                <p>${t.retry}</p>
            </div>
        `;
    }
}

function formatUpdateTime(date) {
    const now = new Date();
    const diff = Math.floor((now - date) / 60000);
    
    if (diff < 1) return translations[currentLang].justNow;
    if (diff < 60) return translations[currentLang].minutesAgo.replace('{n}', diff);
    if (diff < 1440) return translations[currentLang].hoursAgo.replace('{n}', Math.floor(diff / 60));
    
    return date.toLocaleTimeString(currentLang === 'zh' ? 'zh-CN' : 'en-US', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });
}

function formatRelativeTime(date) {
    const now = new Date();
    const diff = Math.floor((now - date) / 60000);
    const t = translations[currentLang];
    
    if (diff < 1) return { date: t.today, time: t.justNow };
    if (diff < 60) return { date: '', time: t.minutesAgo.replace('{n}', diff) };
    if (diff < 1440) return { date: '', time: t.hoursAgo.replace('{n}', Math.floor(diff / 60)) + 'h' };
    
    const isToday = date.toDateString() === now.toDateString();
    const isYesterday = date.toDateString() === new Date(now - 86400000).toDateString();
    
    if (isToday) return { date: t.today, time: date.toLocaleTimeString(currentLang === 'zh' ? 'zh-CN' : 'en-US', { hour: '2-digit', minute: '2-digit' }) };
    if (isYesterday) return { date: t.yesterday, time: date.toLocaleTimeString(currentLang === 'zh' ? 'zh-CN' : 'en-US', { hour: '2-digit', minute: '2-digit' }) };
    
    return { 
        date: date.toLocaleDateString(currentLang === 'zh' ? 'zh-CN' : 'en-US', { month: 'short', day: 'numeric' }),
        time: date.toLocaleTimeString(currentLang === 'zh' ? 'zh-CN' : 'en-US', { hour: '2-digit', minute: '2-digit' })
    };
}

function filterArticles() {
    let articles = allArticles;
    
    // Category filter
    if (currentFilter !== 'all') {
        if (currentFilter === 'asia') {
            articles = articles.filter(a => a.country && ['CN', 'JP', 'KR', 'HK', 'TW', 'SG', 'TH'].includes(a.country));
        } else if (['china', 'japan', 'korea', 'taiwan', 'singapore', 'thailand', 'europe', 'us', 'uk'].includes(currentFilter)) {
            const countryMap = {
                china: ['CN', 'HK'],
                japan: ['JP'],
                korea: ['KR'],
                taiwan: ['TW'],
                singapore: ['SG'],
                thailand: ['TH'],
                europe: ['GB', 'DE', 'FR'],
                us: ['US'],
                uk: ['GB']
            };
            const countries = countryMap[currentFilter] || [currentFilter.toUpperCase()];
            articles = articles.filter(a => a.country && countries.includes(a.country));
        } else {
            articles = articles.filter(a => {
                const categories = a.categories || [a.category];
                return categories.includes(currentFilter);
            });
        }
    }
    
    // Search filter
    if (currentSearch.trim()) {
        const searchLower = currentSearch.toLowerCase();
        articles = articles.filter(a => {
            const title = (a.title_zh || a.title).toLowerCase();
            const summary = (a.summary_zh || a.summary || '').toLowerCase();
            const source = (a.source || '').toLowerCase();
            return title.includes(searchLower) || summary.includes(searchLower) || source.includes(searchLower);
        });
    }
    
    return articles;
}

function getArticleTitle(article) {
    return (currentLang === 'zh' && article.title_zh) ? article.title_zh : article.title;
}

function getArticleSummary(article) {
    return (currentLang === 'zh' && article.summary_zh) ? article.summary_zh : article.summary;
}

function renderNews(articles) {
    const container = document.getElementById('news-container');
    const t = translations[currentLang];
    
    if (articles.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>${t.noNews}</h3>
                <p>${t.adjustFilters}</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = articles.map(article => {
        const pubDate = new Date(article.published);
        const timeInfo = formatRelativeTime(pubDate);
        const title = getArticleTitle(article);
        const summary = getArticleSummary(article);
        
        return `
            <article class="news-card">
                <div class="time-col">
                    ${timeInfo.date ? `<span class="time-date">${timeInfo.date}</span>` : ''}
                    <span class="time-clock">${timeInfo.time}</span>
                </div>
                <div class="content-col">
                    <div class="source-row">
                        <span class="source">${article.source}</span>
                        <span class="country">${article.country}</span>
                    </div>
                    <h3 class="title">
                        <a href="${article.link}" target="_blank" rel="noopener">${title}</a>
                    </h3>
                    ${summary ? `<p class="summary">${summary}</p>` : ''}
                </div>
                <div class="meta-col">
                    <span class="category-tag">${article.category}</span>
                    <a href="${article.link}" target="_blank" rel="noopener" class="external-link">
                        ↗ <span>${t.readMore}</span>
                    </a>
                </div>
            </article>
        `;
    }).join('');
}

function handleSearch() {
    currentSearch = document.getElementById('search-input').value;
    filteredArticles = filterArticles();
    renderNews(filteredArticles);
}

// Event listeners
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
    
    document.querySelector('.search-btn').addEventListener('click', handleSearch);
    document.getElementById('search-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSearch();
    });
    
    fetchNews();
    
    // Auto-refresh every 5 minutes
    setInterval(fetchNews, 300000);
});
