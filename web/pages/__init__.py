from web.navigation import (
    PAGE_ANALYSIS,
    PAGE_DASHBOARD,
    PAGE_PORTFOLIO,
    PAGE_SCREENER,
    PAGE_STOCK_DETAIL,
    PAGE_STRATEGY,
)
from web.pages.analysis_tasks import render_analysis_tasks
from web.pages.dashboard import render_dashboard
from web.pages.portfolio import render_portfolio
from web.pages.stock_detail import render_stock_detail
from web.pages.stock_screener import render_stock_screener
from web.pages.strategy import render_strategy

PAGES = {
    PAGE_DASHBOARD: render_dashboard,
    PAGE_ANALYSIS: render_analysis_tasks,
    PAGE_STRATEGY: render_strategy,
    PAGE_SCREENER: render_stock_screener,
    PAGE_STOCK_DETAIL: render_stock_detail,
    PAGE_PORTFOLIO: render_portfolio,
}
