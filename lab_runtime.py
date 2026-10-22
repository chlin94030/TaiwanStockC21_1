"""Pure progress / duration diagnostics. No data collection or Streamlit dependency."""
from datetime import datetime, timezone

FREE_PER_HOUR = 260
TOKEN_PER_HOUR = 520


def rate(token_present=False):
    return TOKEN_PER_HOUR if token_present else FREE_PER_HOUR


def estimated_hours(requests_remaining, token_present=False):
    """Planning estimate at the application's deliberately conservative API rate.

    Not a promise of end-to-end latency. Cached requests, provider waits, adjusted
    prices and computation are not captured in this number.
    """
    return max(0, int(requests_remaining)) / rate(token_present)


def hours_message(total, completed=0, token_present=False):
    remaining = max(0, int(total) - int(completed))
    hours = estimated_hours(remaining, token_present)
    if remaining == 0:
        return '逐檔歷史量值收集已到目前階段的最後一檔。'
    return (f'如剩餘 {remaining:,} 檔均需向 FinMind 請求，依本程式每小時約 '
            f'{rate(token_present)} 次的保守速率，純請求節奏約 {hours:.1f} 小時；'
            '已有快取會更快，額外的網路重試及後續還原價格處理可能更久。')


def seconds_since(iso_value, now=None):
    if not iso_value:
        return None
    try:
        parsed = datetime.fromisoformat(str(iso_value))
        if parsed.tzinfo is None:
            return None
        delta = (now or datetime.now(timezone.utc)) - parsed
        return max(0, int(delta.total_seconds()))
    except (ValueError, TypeError, OverflowError):
        return None


def progress_caption(state, token_present=False):
    """State-only presentation; NEVER downloads history or probes a remote API."""
    if state.get('phase') != 'AMOUNT':
        return ''
    total = state.get('total')
    done = state.get('done', 0)
    if not isinstance(total, int) or not isinstance(done, int) or total <= 0:
        return ''
    return hours_message(total, done, token_present)
