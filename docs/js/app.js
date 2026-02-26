// Global News App - 24inf.cn Style with Translation
let allArticles = [];
let currentFilter = 'all';
let currentLang = 'zh'; // 'zh' or 'en'
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
        filterTechnology: '💻 科技',
        filterScience: '🔬 科学',
        filterSports: '⚽ 体育',
        filterEntertainment: '🎬 娱乐',
        filterAsia: '🌏 亚洲',
        filterChina: '🇨🇳 中国',
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
        readMore: '阅读原文'
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
        filterTechnology: '💻 Tech',
        filterScience: '🔬 Science',
        filterSports: '⚽ Sports',
        filterEntertainment: '🎬 Entertainment',
        filterAsia: '🌏 Asia',
        filterChina: '🇨🇳 China',
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
        readMore: 'Read'
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
    const savedLang = localStorage.getItem('lang') || 'zh';
    setLanguage(savedLang);
}

// Toggle language (UI + content translation)
function toggleLanguage() {
    currentLang = currentLang === 'zh' ? 'en' : 'zh';
    localStorage.setItem('lang', currentLang);
    
    const t = translations[currentLang];
    document.getElementById('lang-icon').textContent = currentLang === 'zh' ? '🇨🇳' : '🇺🇸';
    document.getElementById('lang-text').textContent = t.langName;
    
    // Update UI translations
    updateUITranslations();
    
    // Re-render news with selected language
    renderNews(filterNews(allArticles, currentFilter));
}

// Update UI translations
function updateUITranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[currentLang][key]) {
            el.textContent = translations[currentLang][key];
        }
    });
    
    // Update theme text
    const t = translations[currentLang];
    document.getElementById('theme-text').textContent = isDarkMode ? t.lightMode : t.darkMode;
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
    
    const t = translations[lang];
    document.getElementById('lang-icon').textContent = lang === 'zh' ? '🇨🇳' : '🇺🇸';
    document.getElementById('lang-text').textContent = t.langName;
    
    updateUITranslations();
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
        const categories = article.categories || [article.category];
        if (category === 'asia') {
            return article.country && ['CN', 'JP', 'KR', 'HK', 'TW', 'SG'].includes(article.country);
        }
        return categories.includes(category);
    });
}

// Get article title based on language
function getArticleTitle(article) {
    if (currentLang === 'zh' && article.title_zh) {
        return article.title_zh;
    }
    return article.title;
}

// Get article summary based on language
function getArticleSummary(article) {
    if (currentLang === 'zh' && article.summary_zh) {
        return article.summary_zh;
    }
    return article.summary;
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

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    initSettings();
    
    // Language toggle
    document.getElementById('lang-toggle').addEventListener('click', toggleLanguage);
    
    // Theme toggle
    document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
    
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
