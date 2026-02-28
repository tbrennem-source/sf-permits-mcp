## Sprint 84-B: Static Asset Caching
- Added Cache-Control headers for CSS/JS (max-age=86400, stale-while-revalidate=604800) and images/fonts (max-age=604800)
- HTML pages excluded from caching
