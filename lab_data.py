"""Two-pass data pipeline: whole-roster actual amount -> monthly union -> price factors."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import zipfile
import numpy as np
import pandas as pd
from lab_io import Store,DataError,atomic_json,read_json,frame_write,sha
from lab_sources import Client
from lab_universe import signal_calendar,turnover_snapshots,make_pools
from lab_features import raw_adjusted_frame,features,attach_evidence,percentile_reference,return_record,label_records

BENCHMARK='0050.TW'
ALLOWED_IMPORT={'prices.csv','prices.csv.gz','calendar.csv','catalog.json','manifest.json',
                'membership.csv','market_caps.csv','evidence.csv'}

def extract_dataset(path,destination):
    dest=Path(destination);dest.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path) as z:
        infos=z.infolist()
        if sum(i.file_size for i in infos)>1_000_000_000:raise DataError('Dataset expands beyond 1GB')
        for i in infos:
            if i.filename not in ALLOWED_IMPORT or i.is_dir():raise DataError('Unexpected input archive member: '+i.filename)
            if (i.external_attr>>16)&0o170000==0o120000:raise DataError('Symlinks forbidden')
        if len({i.filename for i in infos})!=len(infos):raise DataError('Duplicate archive names')
        if z.testzip():raise DataError('Input ZIP CRC failed')
        for i in infos:
            with z.open(i) as src,open(dest/i.filename,'wb') as dst:shutil.copyfileobj(src,dst)
    return dest


def import_prices(directory,store,cfg,progress,check):
    root=Path(directory)
    manifest=read_json(root/'manifest.json')
    cat=read_json(root/'catalog.json',[])
    if not manifest or not cat:raise DataError('Import requires manifest.json and catalog.json')
    if manifest.get('amount_unit')!='TWD' or manifest.get('volume_unit')!='SHARES':raise DataError('Declare actual TWD amount and share volume units')
    if manifest.get('price_basis')!='ADJUSTED_PROVIDER':raise DataError('Comparable adjusted OHLC required')
    if manifest.get('amount_kind')!='ACTUAL_TRADED_VALUE':raise DataError('Estimated close x volume is not annual actual amount')
    if not manifest.get('source'):raise DataError('Input source required')
    tickers=[r['ticker'] for r in cat]
    if len(set(tickers))!=len(tickers):raise DataError('Duplicate catalog')
    if any(not re.fullmatch(r'[1-9][0-9]{3}\.(TW|TWO)',s) for s in tickers):raise DataError('Catalog must contain common-equity symbols, not ETFs/warrants')
    synthetic=manifest.get('data_kind')=='SYNTHETIC'
    if not synthetic and len(cat)<cfg.min_current_roster:raise DataError('Partial catalog cannot represent the requested all-market universe')
    if cfg.requested_scope=='HISTORICAL_MEMBERSHIP':
        if not (root/'membership.csv').exists():raise DataError('Historical membership.csv absent')
        if manifest.get('membership_scope')!='HISTORICAL_MEMBERSHIP':raise DataError('Historical scope not declared')
    c=pd.read_csv(root/'calendar.csv')
    calendar=sorted(pd.to_datetime(c['date']).dt.strftime('%Y-%m-%d').unique())
    calendar=[d for d in calendar if cfg.start<=d<=cfg.end]
    path=root/'prices.csv.gz'
    if not path.exists():path=root/'prices.csv'
    if not path.exists():raise DataError('prices.csv(.gz) absent; a v19_results report is not market-price input')
    fingerprint=sha(path)
    if store.meta('imported_sha')!=fingerprint:
        if store.meta('import_in_progress_sha')!=fingerprint:
            with store.connect() as conn:
                for t in ('raw','adj','downloads'):conn.execute('DELETE FROM '+t)
            store.set_meta('import_in_progress_sha',fingerprint)
            store.set_meta('import_rows_done',0)
        done=int(store.meta('import_rows_done',0))
        rows=0
        required=['ticker','date']+['raw_'+c for c in ('open','high','low','close')]+['volume','amount']+['adj_'+c for c in ('open','high','low','close')]
        for chunk in pd.read_csv(path,chunksize=100000,dtype={'ticker':str}):
            check()
            rows+=len(chunk)
            if rows<=done:continue
            if not set(required).issubset(chunk):raise DataError('Normalized input fields missing: '+str(set(required)-set(chunk)))
            if not chunk.ticker.isin(tickers+[BENCHMARK]).all():raise DataError('Input symbol absent from catalog')
            chunk['date']=pd.to_datetime(chunk.date,errors='raise').dt.strftime('%Y-%m-%d')
            if chunk[['ticker','date']].duplicated().any():raise DataError('Duplicate input (ticker,date)')
            for col in required[2:]:chunk[col]=pd.to_numeric(chunk[col],errors='raise')
            if (chunk[['volume','amount']].dropna()<0).any().any():raise DataError('Negative volume/amount')
            raw_cols=['ticker','date','raw_open','raw_high','raw_low','raw_close','volume','amount']
            adj_cols=['ticker','date','adj_open','adj_high','adj_low','adj_close']
            # One transaction per 100k-row chunk, not two connections per stock.
            # Primary keys detect duplicates across chunks. The resume marker is
            # committed atomically with both raw and adjusted records.
            raw_vals=[tuple(None if pd.isna(v) else v for v in r) for r in chunk[raw_cols].itertuples(index=False,name=None)]
            adj_vals=[tuple(None if pd.isna(v) else v for v in r) for r in chunk[adj_cols].itertuples(index=False,name=None)]
            try:
                with store.connect() as conn:
                    conn.executemany('INSERT INTO raw VALUES(?,?,?,?,?,?,?,?)',raw_vals)
                    conn.executemany('INSERT INTO adj VALUES(?,?,?,?,?,?)',adj_vals)
                    conn.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('import_rows_done',str(rows)))
            except Exception as e:raise DataError('Input transaction failed; possible duplicate (ticker,date). Completed chunks are retained.') from e
            progress(message='Importing canonical rows',done=rows,total=None)
        store.set_meta('imported_sha',fingerprint)
    scope='SYNTHETIC' if synthetic else ('USER_SUPPLIED_HISTORICAL_MEMBERSHIP' if cfg.requested_scope=='HISTORICAL_MEMBERSHIP' else 'CURRENT_SNAPSHOT_DIAGNOSTIC')
    return cat,calendar,{'scope':scope,'data_kind':manifest.get('data_kind','PROVIDER_HISTORY'),
            'manifest':manifest,'import_file_sha':fingerprint,'source_independently_audited':False}


def build_dataset(store,cfg,run,progress,check,token=None,input_dir=None):
    run=Path(run);run.mkdir(parents=True,exist_ok=True)
    if cfg.source_mode=='import':
        if not input_dir:raise DataError('An input directory is required')
        cat,calendar,source=import_prices(input_dir,store,cfg,progress,check)
        client=None
    else:
        client=Client(store,cfg,progress,check,token)
        cat=read_json(run/'roster.json',[])
        if not cat:
            progress(phase='ROSTER',message='讀取臺灣證交所與櫃買中心現行公司名冊',done=0,total=2)
            cat=client.catalog();atomic_json(run/'roster.json',cat)
        progress(phase='CALENDAR',message=f'名冊 {len(cat)} 檔，確認交易日與起迄期間', done=0,total=1,roster_count=len(cat))
        calendar=read_json(run/'calendar.json',[])
        if not calendar:
            calendar=client.calendar();atomic_json(run/'calendar.json',calendar)
        source={'scope':'CURRENT_SNAPSHOT_DIAGNOSTIC','data_kind':'PROVIDER_HISTORY',
                'whole_current_roster_count':len(cat),'historical_membership_verified':False,
                'amount_source':'FinMind TaiwanStockPrice Trading_money',
                'adjusted_price_source':'Yahoo via yfinance','source_independently_audited':False}
        requested=cat+[{'ticker':BENCHMARK}]
        for i,row in enumerate(requested):
            check()
            t=row['ticker']
            progress(phase='AMOUNT',done=i,total=len(requested),current_symbol=t,
                     message=f'全市場歷史成交金額：正在檢查／取得 {t} （{i}/{len(requested)}）',
                     roster_count=len(cat))
            cached=store.cached('raw:'+t,cfg.start,cfg.end)
            if not cached:
                covered=store.covered_range('raw:'+t)
                start=cfg.start
                if covered and covered[0]<=cfg.start and covered[1]<cfg.end:
                    start=max(cfg.start,str((pd.Timestamp(covered[1])-pd.Timedelta(days=7)).date()))
                f=client.raw(t,start=start)
                store.put('raw',t,f,cfg.start,cfg.end,'FinMind_TaiwanStockPrice_ACTUAL_AMOUNT')
            # IMPORTANT: only display progress once cache/DB has actually committed.
            progress(phase='AMOUNT',done=i+1,total=len(requested),current_symbol=t,
                     last_committed_symbol=t,roster_count=len(cat),
                     message=f'已儲存 {i+1}/{len(requested)} 檔歷史量值（{t}；'+
                             ('已使用快取）' if cached else '新取得資料）'))
    atomic_json(run/'source_scope.json',source);atomic_json(run/'roster.json',cat);atomic_json(run/'calendar.json',calendar)
    cal=pd.DatetimeIndex(calendar)
    signals=signal_calendar(cal,cfg)
    minimum=cfg.min_train_months+cfg.min_outer_folds*cfg.outer_test_months+cfg.holdout_months+4
    if len(signals)<minimum:raise DataError(f'Only {len(signals)} matured monthly dates; protocol needs at least {minimum}. Extend actual history, do not recycle dates.')
    amt=[];empty=[]
    for i,row in enumerate(cat):
        check();t=row['ticker'];raw=store.get('raw',t,cfg.start,cfg.end)
        if raw.empty:empty.append(t);continue
        s=turnover_snapshots(raw,cal,signals,cfg);s['ticker']=t;amt.append(s)
        if i%30==0:progress(phase='POOL',done=i+1,total=len(cat),message='Computing monthly trailing-252 turnover ranks')
    # An absent current security could be a high-turnover security. Do not silently
    # describe successful downloads as the full requested market.
    if empty:raise DataError('No raw history for requested symbols: '+','.join(empty[:20])+'; full-market ranking is blocked')
    turnover=pd.concat(amt,ignore_index=True)
    members=caps=evidence=None
    if input_dir:
        root=Path(input_dir)
        if (root/'membership.csv').exists():members=pd.read_csv(root/'membership.csv')
        if (root/'market_caps.csv').exists():caps=pd.read_csv(root/'market_caps.csv')
        if cfg.enable_optional_factors:
            if not (root/'evidence.csv').exists():raise DataError('PIT evidence.csv missing')
            evidence=pd.read_csv(root/'evidence.csv')
    pools,pool_diag=make_pools(turnover,signals,cfg,members,caps)
    frame_write(run/'monthly_pools.csv.gz',pools);frame_write(run/'pool_coverage.csv',pool_diag)
    union=sorted(set(pools.ticker))
    if client:
        for i,t in enumerate(union+[BENCHMARK]):
            check()
            progress(phase='ADJUSTED',done=i,total=len(union)+1,current_symbol=t,
                     message=f'取得入選股票還原價格：{i}/{len(union)+1}（{t}）')
            if not store.cached('adj:'+t,cfg.start,cfg.end):
                a=client.adjusted(t)
                store.put('adj',t,a,cfg.start,cfg.end,'YAHOO_ADJUSTED_PROVIDER')
                client.wait(.5,'Adjusted price pacing')
            progress(phase='ADJUSTED',done=i+1,total=len(union)+1,last_committed_symbol=t,
                     message=f'已儲存 {i+1}/{len(union)+1} 檔還原價格')
    snapshots=[];labels=[]
    for i,t in enumerate(union+[BENCHMARK]):
        check();r=store.get('raw',t,cfg.start,cfg.end);a=store.get('adj',t,cfg.start,cfg.end)
        f=raw_adjusted_frame(r,a,cal)
        if t!=BENCHMARK:
            z=features(f).loc[signals].copy();z['date']=z.index;z['ticker']=t
            # Each month's normalization reference is the union of registered pools.
            valid_dates=set(pools.loc[pools.ticker==t,'date'])
            snapshots.append(z[z.date.isin(valid_dates)].reset_index(drop=True))
        used=signals if t==BENCHMARK else pd.DatetimeIndex([d for d in signals if d in valid_dates])
        for h in cfg.horizons:
            batch=label_records(f,used,h,cfg,t==BENCHMARK)
            for q in batch:q['ticker']=t
            labels.extend(batch)
        if i%10==0:progress(phase='FEATURES',done=i+1,total=len(union)+1,message='Computing features and immutable outcome labels once')
    snap=pd.concat(snapshots,ignore_index=True)
    snap=snap.merge(turnover[['date','ticker','amount20']],on=['date','ticker'],how='left')
    names={r['ticker']:r.get('name',r['ticker']) for r in cat}
    sectors={r['ticker']:r.get('sector','UNKNOWN') for r in cat}
    snap['name']=snap.ticker.map(names);snap['sector']=snap.ticker.map(sectors)
    if evidence is not None:snap=attach_evidence(snap,evidence)
    snap=percentile_reference(snap,cfg)
    progress(phase='SAVE',message='Saving compact monthly feature checkpoint')
    frame_write(run/'features.csv.gz',snap)
    progress(phase='SAVE',message='Saving shared outcome checkpoint')
    lab=pd.DataFrame(labels);frame_write(run/'labels.csv.gz',lab)
    source['monthly_union_count']=len(union)
    source['feature_reference']='SAME_DATE_UNION_OF_ALL_PREREGISTERED_POOLS'
    source['price_revision_vintages_verified']=False
    atomic_json(run/'source_scope.json',source)
    progress(phase='HASH',message='Hashing consistent input database')
    atomic_json(run/'data_manifest.json',{'canonical_data_hash':store.data_hash(),'downloads':store.manifest(),
                    'source':source,'input_rows_are_not_trade_evidence':True})
    return snap,lab,pools,cal,source
