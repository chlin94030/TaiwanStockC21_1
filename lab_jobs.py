"""Disk-checkpointed finite job, observable start/error states, OS single-writer lock.

Important: a daemon thread is NOT a durable cloud worker. If Streamlit restarts,
resume requires a new click and preserved cache bytes. An app reboot is observable,
not automatically mistaken for a completed job.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import threading
import traceback
import pandas as pd
from lab_config import Config, VERSION
from lab_io import Store, JobLock, PauseRequested, SourceBlocked, DataError, atomic_json, read_json, code_hash, sha, frame_write
from lab_data import build_dataset
from lab_candidates import candidate_registry
from lab_backtest import build_cases, evaluate_grid
from lab_search import nested_study
from lab_report import write_report

_THREADS = {}
_THREAD_LOCK = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def input_hash(directory):
    if not directory:
        return ''
    root = Path(directory)
    h = hashlib.sha256()
    for p in sorted(root.iterdir()):
        if p.is_file():
            h.update(p.name.encode())
            h.update(sha(p).encode())
    return h.hexdigest()


def identifier(cfg, idir=None):
    key = {'config': cfg.to_dict(), 'code_hash': code_hash(), 'input_hash': input_hash(idir), 'version': VERSION}
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:20]


def _state(path, **updates):
    old = read_json(path)
    old.update(updates)
    old['updated_at'] = now()
    atomic_json(path, old)
    return old


def run_pipeline(root, cfg, token=None, input_dir=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    job = identifier(cfg, input_dir)
    run = root / 'runs' / job
    run.mkdir(parents=True, exist_ok=True)
    statefile = run / 'state.json'
    pause = run / 'PAUSE'
    if read_json(statefile).get('status') == 'COMPLETE':
        return run

    def check():
        if pause.exists():
            raise PauseRequested('已暫停；快取保留，可按「繼續」恢復。')

    def progress(**kw):
        # Retain start time, a diagnostic trace and the latest successfully
        # committed index. Do not leak the API token into the status file.
        updates = dict(kw)
        updates.setdefault('wait_seconds', 0)
        updates.update(status='RUNNING', job_id=job, pid=os.getpid(),
                       active_thread=threading.get_ident())
        _state(statefile, **updates)

    try:
        # The lock can fail BEFORE any API request. Catch it and publish a
        # visible, actionable BLOCKED status instead of silently dying.
        with JobLock(root / 'worker.lock'):
            protocol = read_json(run / 'protocol.json')
            if not protocol:
                protocol = {'version': VERSION, 'registered_at': now(), 'code_hash': code_hash(),
                            'config': cfg.to_dict(), 'input_hash': input_hash(input_dir),
                            'run_id': job, 'finite_search': True,
                            'automatic_orders_authorized': False,
                            'scope_is_not_reconstructed_from_successfully_downloaded_symbols': True}
                atomic_json(run / 'protocol.json', protocol)
            candidates = candidate_registry(cfg)
            atomic_json(run / 'candidates.json', candidates)
            atomic_json(root / 'latest.json', {
                'job_id': job, 'run': str(run), 'config': cfg.to_dict(),
                'input_dir': str(input_dir) if input_dir else None,
            })
            progress(phase='START', message='背景工作已啟動，確認資料來源與快取。',
                     done=0, total=None)

            store_root = run / 'import_cache' if cfg.source_mode == 'import' else root / 'cache'
            store = Store(store_root)
            ready = read_json(run / 'prepared.json')
            cachefiles = ['features.csv.gz', 'labels.csv.gz', 'monthly_pools.csv.gz',
                          'calendar.json', 'source_scope.json']
            usable = bool(ready) and all((run / p).is_file() and sha(run / p) == ready.get(p)
                                         for p in cachefiles)
            if usable:
                snap = pd.read_csv(run / 'features.csv.gz', parse_dates=['date'])
                labels = pd.read_csv(run / 'labels.csv.gz', parse_dates=['date', 'entry', 'exit'])
                pools = pd.read_csv(run / 'monthly_pools.csv.gz', parse_dates=['date'])
                cal = pd.DatetimeIndex(read_json(run / 'calendar.json'))
                source = read_json(run / 'source_scope.json')
                progress(phase='CACHE', message='已驗證並恢復特徵／報酬快取。')
            else:
                snap, labels, pools, cal, source = build_dataset(
                    store, cfg, run, progress, check, token, input_dir)
                atomic_json(run / 'prepared.json', {p: sha(run / p) for p in cachefiles})
            check()
            cov = [{'factor': c.removeprefix('rank_'), 'coverage': float(snap[c].notna().mean())}
                   for c in snap if c.startswith('rank_')]
            frame_write(run / 'feature_coverage.csv', pd.DataFrame(cov))
            progress(phase='CASES', message='建立共享比較日曆與同池基準。', done=0, total=None)
            cases = build_cases(snap, labels, pools, cfg)
            grids = evaluate_grid(cases, candidates, cfg, progress, check)
            result = nested_study(grids, cases, candidates, cal, cfg, run, source,
                                  progress, check)
            check()
            progress(phase='EXPORT', message='製作研究報告與完整性檢查。')
            write_report(result, run)
            _state(statefile, status='COMPLETE', phase='DONE', job_id=job,
                   message='本次有限研究已完成，請檢查資料涵蓋率及保留期結果。',
                   run=str(run), verdicts={h: x['verdict'] for h, x in result['models'].items()},
                   done=1, total=1, wait_seconds=0)
    except PauseRequested as e:
        _state(statefile, status='PAUSED', job_id=job, wait_seconds=0, message=str(e))
    except (DataError, SourceBlocked) as e:
        _state(statefile, status='BLOCKED', job_id=job, wait_seconds=0,
               message=f'{type(e).__name__}: {e}', results_approved=False,
               cached_work_retained=True)
    except Exception as e:
        # File traceback stays server-side. Never include a request URL or token
        # in user-facing state. A traceback may contain external source details;
        # restrict the UI to exception class and a short, sanitized message.
        (run / 'error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        _state(statefile, status='ERROR', job_id=job, wait_seconds=0,
               message=f'{type(e).__name__}: 背景工作失敗，請查看Streamlit管理頁面日誌。',
               error_type=type(e).__name__, results_approved=False,
               cached_work_retained=True)
    return run


def start(root, cfg, token=None, input_dir=None):
    root = Path(root)
    job = identifier(cfg, input_dir)
    run = root / 'runs' / job
    with _THREAD_LOCK:
        current = _THREADS.get(str(root.resolve()))
        if current and current.is_alive():
            active = read_json(root / 'latest.json')
            return Path(active['run']) if active.get('run') else run
        if read_json(run / 'state.json').get('status') == 'COMPLETE':
            atomic_json(root / 'latest.json', {
                'job_id': job, 'run': str(run), 'config': cfg.to_dict(),
                'input_dir': str(input_dir) if input_dir else None,
            })
            return run
        run.mkdir(parents=True, exist_ok=True)
        (run / 'PAUSE').unlink(missing_ok=True)
        prior = read_json(run / 'state.json')
        # Commit a durable pointer and observable QUEUED state SYNCHRONOUSLY,
        # BEFORE scheduling any worker. This eliminates the invisible startup.
        atomic_json(root / 'latest.json', {
            'job_id': job, 'run': str(run), 'config': cfg.to_dict(),
            'input_dir': str(input_dir) if input_dir else None,
        })
        _state(run / 'state.json', status='QUEUED', phase='QUEUE', job_id=job,
               started_at=prior.get('started_at') or now(),
               message='已排入背景工作；資料量大時仍可即時查看進度。',
               done=0, total=None, wait_seconds=0)
        thread = threading.Thread(target=run_pipeline,
                                  args=(root, cfg, token, input_dir),
                                  daemon=True, name='alpha-v21-research')
        _THREADS[str(root.resolve())] = thread
        thread.start()
    return run


def alive(root):
    t = _THREADS.get(str(Path(root).resolve()))
    return bool(t and t.is_alive())


def request_pause(run):
    p = Path(run)
    p.mkdir(parents=True, exist_ok=True)
    (p / 'PAUSE').write_text('pause', encoding='ascii')
