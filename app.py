"""V21.1: non-blocking Streamlit monitor for the independent research worker.

The page never performs the whole-market HTTP collection itself. This is a
research UI, not an order-entry or production investment application.
"""
from pathlib import Path
from dataclasses import replace
import hashlib
import importlib
import os
import streamlit as st

from lab_config import VERSION, Config, load_config
from lab_io import read_json, DataError
from lab_jobs import start, alive, request_pause
from lab_data import extract_dataset
from lab_runtime import estimated_hours, hours_message, progress_caption, seconds_since, rate

HERE = Path(__file__).resolve().parent
ROOT = HERE / 'data' / 'v21_universe_lab'


def secret_token():
    try:
        return str(st.secrets.get('FINMIND_TOKEN', os.getenv('FINMIND_TOKEN', ''))).strip()
    except Exception:
        return os.getenv('FINMIND_TOKEN', '').strip()


def quick_local_check(config):
    """Bounded no-network health check; not market-data validation."""
    config.validate()
    out = {'config': 'OK', 'file_write': 'NOT_CHECKED', 'requirements': {},
           'external_api_reachable': 'NOT_TESTED'}
    for name in ('numpy', 'pandas', 'requests', 'streamlit', 'yfinance'):
        m = importlib.import_module(name)
        out['requirements'][name] = str(getattr(m, '__version__', 'installed'))
    ROOT.mkdir(parents=True, exist_ok=True)
    tmp = ROOT / '.ui_write_test'
    tmp.write_text('ok', encoding='ascii')
    if tmp.read_text(encoding='ascii') != 'ok':
        raise DataError('Cache directory does not support file read/write')
    tmp.unlink(missing_ok=True)
    out['file_write'] = 'OK'
    return out


st.set_page_config(page_title='Alpha Radar V21.1 研究室', layout='wide')
st.title('Alpha Radar｜母池與因子權重研究室')
st.caption(VERSION + ' • 獨立研究程式，不會變更V20舊系統或自動下單')
st.write('同一日期比較過去一年日均成交金額前100／200／300／500檔；訓練期選因子及權重，後續分開驗證。')

cfg = load_config(HERE / 'config.json')
access_token = secret_token()
with st.expander('第一次使用前請看：執行時間與真實資料限制', expanded=True):
    st.warning('全市場首次逐檔取得多年歷史資料，不是10分鐘內能完成的工作。程式會先收集量值，之後才有母池與績效結果。')
    st.write(hours_message(2001, 0, bool(access_token)))
    st.caption('FinMind 限額只是理論請求節奏；資料來源停機、重試及後續Yahoo還原價下載另計。已有有效快取可節省時間。')
    st.write('**FinMind免費Token：' + ('已設定（不顯示內容）' if access_token else '未設定，使用更保守的免Token速率') + '**')
    st.caption('Streamlit Cloud可能會休眠或清除暫存資料。大量歷史初次建檔，建議在本機或有持久磁碟的主機上執行。')

mode = st.radio('資料模式', ['自動：官方現行名冊＋逐檔歷史成交額', '匯入：已整理的全市場資料ZIP'], horizontal=True)
input_dir = None
if mode.startswith('匯入'):
    cfg = replace(cfg, source_mode='import')
    upload = st.file_uploader('標準格式資料集，不是v19_results.json', type=['zip'])
    historical = st.checkbox('另附各月底歷史成分membership.csv')
    market_cap = st.checkbox('納入歷史市值Top-N（需market_caps.csv）')
    optional = st.checkbox('加入已標註公告時間的營收/EPS/法人因子（需evidence.csv）')
    cfg = replace(cfg,
                  requested_scope='HISTORICAL_MEMBERSHIP' if historical else 'CURRENT_OFFICIAL_SNAPSHOT',
                  include_market_cap_pools=market_cap, enable_optional_factors=optional)
    if upload:
        data = upload.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        input_dir = ROOT / 'inputs' / digest
        if not (input_dir / 'manifest.json').exists():
            archive = ROOT / 'uploads' / (digest + '.zip')
            archive.parent.mkdir(parents=True, exist_ok=True)
            archive.write_bytes(data)
            try:
                extract_dataset(archive, input_dir)
            except Exception as exc:
                st.error('資料格式檢查失敗：' + str(exc))
                st.stop()
    else:
        st.info('請參照 DATA_CONTRACT.md 匯入完整市場資料。以前的150檔研究報告不足以建立Top500。')
else:
    st.info('自動模式優先驗證來源完整性；無法拿到真實全市場歷史量值時會明確停止，不會用少數股票冒充全市場。')

with st.expander('查看固定研究設定與資料限制', expanded=False):
    st.json(cfg.to_dict())
    st.caption('預設使用現行名冊，不能宣稱已修正歷史下市股倖存者偏差。未驗證的財報/法人因子不會擅自加入。')

latest = read_json(ROOT / 'latest.json')
status = read_json(Path(latest['run']) / 'state.json') if latest.get('run') else {}
status_age = seconds_since(status.get('updated_at'))
active = status.get('status') in ('QUEUED', 'RUNNING') and (status_age is not None and status_age < 120)
cols = st.columns(3)
if cols[0].button('▶ 啟動／繼續', type='primary', disabled=active or (cfg.source_mode == 'import' and input_dir is None), use_container_width=True):
    try:
        old = read_json(ROOT / 'latest.json')
        oldstate = read_json(Path(old['run']) / 'state.json') if old.get('run') else {}
        if oldstate.get('status') in ('PAUSED', 'RUNNING', 'BLOCKED', 'QUEUED'):
            previous = old.get('config')
            if previous and old.get('run'):
                # Reuse the original freeze/end date, not a silently refreshed
                # new experiment when the calendar advances one day.
                prev_cfg = Config(**previous)
                if prev_cfg.source_mode == cfg.source_mode:
                    cfg = prev_cfg
                    input_dir = old.get('input_dir') or None
        cfg.validate()
        started = start(ROOT, cfg, access_token, input_dir)
        st.success('任務已建立：' + Path(started).name + '。下方會自動更新進度。')
    except Exception as exc:
        st.error('啟動失敗：' + str(exc))
if cols[1].button('暫停並保留快取', disabled=not active, use_container_width=True):
    request_pause(latest['run'])
    st.info('已提出暫停要求；會在下一個可安全中斷點停止。')
if cols[2].button('🔍 本機設定與寫入測試', use_container_width=True):
    try:
        st.json(quick_local_check(cfg))
        st.success('程式依賴與磁碟寫入正常（未測網路/API）。')
    except Exception as exc:
        st.error('本機檢查失敗：' + type(exc).__name__ + ': ' + str(exc))

@st.fragment(run_every='5s')
def monitor():
    item = read_json(ROOT / 'latest.json')
    if not item.get('run'):
        st.info('尚無任務。先閱讀上方的初次下載時間，再按「啟動／繼續」。')
        return
    run = Path(item['run'])
    state = read_json(run / 'state.json')
    code = state.get('status', 'QUEUED')
    phase = state.get('phase', 'QUEUE')
    age = seconds_since(state.get('updated_at'))
    st.subheader('目前狀態：' + str(code) + ' ｜ ' + str(phase))
    st.write(state.get('message') or '正在建立背景工作...')
    elapsed = seconds_since(state.get('started_at'))
    if elapsed is not None:
        st.caption('任務已開始約 ' + str(elapsed // 60) + ' 分鐘；最後一次狀態更新：' +
                   (str(age) + ' 秒前' if age is not None else '未知'))
    if state.get('current_symbol'):
        st.caption('目前股票：' + str(state['current_symbol']) +
                   ' ｜ 最後已儲存：' + str(state.get('last_committed_symbol') or '尚無'))
    total, done = state.get('total'), state.get('done')
    if isinstance(total, int) and total > 0 and isinstance(done, int):
        st.progress(max(0., min(1., done / total)), text=f'{min(done, total):,} / {total:,}（此階段）')
        # Use the frozen run's token availability only as a UI estimate;
        # secrets never appear in state files.
        note = progress_caption(state, bool(access_token))
        if note: st.caption(note)
    if state.get('wait_seconds'):
        st.warning('來源配額或限速等待：約 ' + str(state['wait_seconds']) + ' 秒，進度仍會每隔數秒更新。')
    if code == 'RUNNING' and age is not None and age > 120:
        st.error('狀態已超過兩分鐘沒有更新：背景工作可能已中斷／主機休眠。保留data/後按「繼續」，或查看主機日誌。')
    if code == 'QUEUED' and age is not None and age > 45:
        st.error('排隊超過45秒未進入工作，可能是背景執行緒或部署環境有問題。')
    if code in ('BLOCKED', 'ERROR'):
        st.error('資料／執行環境阻擋；不是研究結果失敗。不要刪掉data/，查看上方錯誤後再按繼續。')
    if code == 'COMPLETE':
        st.success('研究完成。下方報告是真實資料回測時才具有研究解讀價值。')
    report_path = run / 'REPORT.txt'
    if report_path.is_file():
        report = report_path.read_text(encoding='utf-8-sig')
        st.text(report)
        st.download_button('下載研究報告 TXT', report.encode('utf-8-sig'),
                           'LAB_REPORT.txt', 'text/plain', on_click='ignore')
        for name in ('selected_models.json', 'results.json', 'LAB_RESULTS.zip'):
            p = run / name
            if p.is_file() and p.stat().st_size < 30 * 1024 * 1024:
                st.download_button('下載 ' + name, p.read_bytes(), name,
                                   'application/zip' if name.endswith('.zip') else 'application/json',
                                   on_click='ignore')
    # Shareable status text, useful when a user reports "10 minutes nothing".
    if state and code != 'COMPLETE':
        lines = [f'version={VERSION}', f'status={code}', f'phase={phase}',
                 f'updated_at={state.get("updated_at", "")}',
                 f'progress={done}/{total}', f'message={state.get("message", "")}']
        st.download_button('下載執行診斷狀態 TXT', '\n'.join(lines).encode('utf-8'),
                           'V21_JOB_DIAGNOSTICS.txt', 'text/plain', on_click='ignore')

monitor()
