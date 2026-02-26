// Global News App - 24inf.cn Style
let allArticles = [];
let currentFilter = 'all';
let currentLang = 'en';
let isDarkMode = false;

// Translations
const translations = {
    en: {
        title: '24Hr Global News',
        darkMode: 'Dark',
        lightMode: 'Light',
        filterAll: 'All News',
        filterGeneral: 'General',
        filterBusiness: 'Business',
        filterAsia: 'Asia',
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
        yesterday: 'Yesterday'
    },
    zh: {
        title: '24 小时全球新闻',
        darkMode: '暗黑',
        lightMode: '白天',
        filterAll: '全部新闻',
        filterGeneral: '综合',
        filterBusiness: '商业',
        filterAsia: '亚洲',
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
        yesterday: '昨天'
    }
};

// Initialize theme and language
function initSettings() {
    // Load theme preference
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        isDarkMode = true;
        document.body.classList.add('dark-mode');
        document.getElementById('theme-icon').textContent = '☀️';
        document.getElementById('theme-text').textContent = translations[currentLang].lightMode;
    }
    
    // Load language preference
    const savedLang = localStorage.getItem('lang') || 'en';
    setLanguage(savedLang);
}

// Toggle dark/light mode
function toggleTheme() {
    isDarkMode = !isDarkMode;
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
    
    const t = translations[currentLang];
    document.getElementById('theme-icon').textContent = isDarkMode ? '☀️' : '🌙';
    document.getElementById('theme-text').textContent = isDarkMode ? t.lightMode : t.darkMode;
}

// Set language
function setLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('lang', lang);
    document.getElementById('lang-select').value = lang;
    
    // Update all translated elements
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[lang][key]) {
            el.textContent = translations[lang][key];
        }
    });
    
    // Re-render news with new language
    renderNews(filterNews(allArticles, currentFilter));
}

// Fetch news data
async function fetchNews() {
    try {
        const response = await fetch('./data/news.json');
        if (!response.ok) {
            throw new Error('Failed to load news data');
        }
        const data = await response.json();
        allArticles = data.articles;
        
        // Update last updated time
        const updateTime = new Date(data.updated);
        const t = translations[currentLang];
        document.getElementById('last-updated').textContent = 
            `${t.updateFreq.split(' ')[0]}: ${formatUpdateTime(updateTime)}`;
        
        renderNews(allArticles);
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

// Format update time
function formatUpdateTime(date) {
    const now = new Date();
    const diff = Math.floor((now - date) / 60000); // minutes
    
    if (diff < 1) return translations[currentLang].justNow;
    if (diff < 60) return translations[currentLang].minutesAgo.replace('{n}', diff);
    if (diff < 1440) return translations[currentLang].hoursAgo.replace('{n}', Math.floor(diff / 60));
    
    return date.toLocaleTimeString(currentLang === 'zh' ? 'zh-CN' : 'en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Format relative time for cards
function formatRelativeTime(date) {
    const now = new Date();
    const diff = Math.floor((now - date) / 60000); // minutes
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

// Filter news
function filterNews(articles, category) {
    if (category === 'all') return articles;
    return articles.filter(article => {
        if (category === 'asia') {
            return article.country && ['CN', 'JP', 'KR', 'IN', 'SG', 'HK', 'TW'].includes(article.country);
        }
        return article.category === category;
    });
}

// Render news cards
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
        const countryName = getCountryName(article.country);
        
        return `
            <article class="news-card">
                <div class="time-col">
                    ${timeInfo.date ? `<span class="time-date">${timeInfo.date}</span>` : ''}
                    <span class="time-clock">${timeInfo.time}</span>
                </div>
                <div class="content-col">
                    <div class="source-row">
                        <span class="source">${article.source}</span>
                        ${countryName ? `<span class="country">${countryName}</span>` : ''}
                    </div>
                    <h3 class="title">
                        <a href="${article.link}" target="_blank" rel="noopener">${article.title}</a>
                    </h3>
                    ${article.summary ? `<p class="summary">${article.summary}</p>` : ''}
                </div>
                <div class="meta-col">
                    ${article.category ? `<span class="category-tag">${article.category}</span>` : ''}
                    <a href="${article.link}" target="_blank" rel="noopener" class="external-link">
                        ↗ <span>${currentLang === 'zh' ? '阅读原文' : 'Read'}</span>
                    </a>
                </div>
            </article>
        `;
    }).join('');
}

// Get country name
function getCountryName(code) {
    const names = {
        US: 'US', GB: 'UK', CN: 'CN', JP: 'JP', KR: 'KR',
        IN: 'IN', SG: 'SG', HK: 'HK', TW: 'TW', DE: 'DE',
        FR: 'FR', IT: 'IT', ES: 'ES', RU: 'RU', BR: 'BR',
        CA: 'CA', AU: 'AU', QA: 'QA', AE: 'AE'
    };
    return names[code] || code;
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    initSettings();
    
    // Theme toggle
    document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
    
    // Language select
    document.getElementById('lang-select').addEventListener('change', (e) => {
        setLanguage(e.target.value);
    });
    
    // Filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.getAttribute('data-category');
            renderNews(filterNews(allArticles, currentFilter));
        });
    });
    
    // Fetch news
    fetchNews();
});
