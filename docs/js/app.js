// Global News App
let allArticles = [];
let currentFilter = 'all';

// Fetch news data
async function fetchNews() {
    try {
        const response = await fetch('../data/news.json');
        if (!response.ok) {
            throw new Error('Failed to load news data');
        }
        const data = await response.json();
        allArticles = data.articles;
        
        // Update last updated time
        const updateTime = new Date(data.updated);
        document.getElementById('last-updated').textContent = 
            `Last updated: ${updateTime.toLocaleString('en-US', { 
                month: 'short', 
                day: 'numeric', 
                hour: '2-digit', 
                minute: '2-digit',
                timeZoneName: 'short'
            })}`;
        
        renderNews(allArticles);
    } catch (error) {
        console.error('Error fetching news:', error);
        document.getElementById('news-container').innerHTML = `
            <div class="error">
                <h3>😕 Unable to load news</h3>
                <p>${error.message}</p>
                <p style="margin-top: 1rem; font-size: 0.9rem;">
                    The news feed is being generated. Please check back in a few minutes.
                </p>
            </div>
        `;
    }
}

// Render news cards
function renderNews(articles) {
    const container = document.getElementById('news-container');
    
    if (articles.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No news found</h3>
                <p>Try adjusting your filters</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = articles.map(article => `
        <article class="news-card" data-category="${article.category}">
            <div>
                <span class="source">${article.source}</span>
                <span class="source country">${article.country}</span>
            </div>
            <h2 class="title">
                <a href="${article.link}" target="_blank" rel="noopener noreferrer">
                    ${article.title}
                </a>
            </h2>
            <p class="summary">${article.summary || 'No summary available'}</p>
            <div class="meta">
                <span class="category">${article.category}</span>
                <span class="time">${formatTime(article.published)}</span>
            </div>
        </article>
    `).join('');
}

// Format time to relative format
function formatTime(isoString) {
    if (!isoString) return 'Unknown';
    
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric'
    });
}

// Filter news by category
function filterNews(category) {
    currentFilter = category;
    
    // Update active button
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.category === category);
    });
    
    if (category === 'all') {
        renderNews(allArticles);
    } else {
        const filtered = allArticles.filter(article => article.category === category);
        renderNews(filtered);
    }
}

// Set up event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Fetch news on load
    fetchNews();
    
    // Set up filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            filterNews(btn.dataset.category);
        });
    });
    
    // Auto-refresh every 5 minutes
    setInterval(fetchNews, 5 * 60 * 1000);
});

// Service Worker registration for PWA (optional)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch(() => {
            // Service worker registration failed, continue without it
        });
    });
}
