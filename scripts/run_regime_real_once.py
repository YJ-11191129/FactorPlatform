import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

from app.services import regime_engine as re

ROOT = Path('D:/Kaggle/Data/wind_data')
ohlcv_path = ROOT / '02_daily_stock' / 'stock_daily_ohlcv.parquet'

print('[INFO] loading', ohlcv_path)
df = pd.read_parquet(ohlcv_path, columns=['date','wind_code','close','volume','amt'])
df['trade_date'] = pd.to_datetime(df['date'])
df = df.sort_values(['wind_code','trade_date'])
df['ret'] = df.groupby('wind_code')['close'].pct_change()

agg = (
    df.groupby('trade_date')
    .apply(lambda g: pd.Series({
        'mkt_ret': float(g['ret'].mean(skipna=True)),
        'mkt_close': float(g['close'].mean(skipna=True)),
        'mkt_volume': float(g['volume'].sum(skipna=True)),
        'mkt_turnover': float(g['amt'].sum(skipna=True)),
        'dispersion': float(g['ret'].std(skipna=True)),
        'breadth_stress_raw': float((g['ret'] < 0).mean() - g['ret'].median(skipna=True)),
        'illiq_raw': float((g['ret'].abs() / g['amt'].replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan).mean(skipna=True)),
    }))
    .reset_index()
    .dropna(subset=['mkt_ret'])
)

state = re._build_state_vector(agg)
merged = state.merge(agg[['trade_date', 'mkt_ret']], on='trade_date', how='left')

params = re.RegimeParams(min_size=20, jump=1, penalty=8.0, eps=1.0, min_samples=10, pca_dim=5, scope='A_SHARE_ALL_REAL')
x_scaled, x_emb = re._scale_and_embed(state, params.pca_dim)
bkps = re._detect_breakpoints(x_emb, params)

state_scaled = state.copy()
state_scaled[re.STATE_COLS] = x_scaled
sev = re._compute_severity(state_scaled, bkps, params)
max_sev = max(sev.values()) if sev else 1.0

cluster = DBSCAN(eps=params.eps, min_samples=params.min_samples)
cids = cluster.fit_predict(x_emb)

snapshot = merged.copy()
snapshot['date'] = pd.to_datetime(snapshot['trade_date']).dt.date
snapshot['scope'] = params.scope
snapshot['cluster_id'] = cids.astype(int)
snapshot['cpd_boundary_flag'] = False
snapshot['severity_score'] = 0.0
for b in bkps:
    if b >= len(snapshot):
        continue
    snapshot.loc[b, 'cpd_boundary_flag'] = True
    snapshot.loc[b, 'severity_score'] = float(sev.get(b, 0.0))
snapshot['cpd_score'] = snapshot['severity_score'] / max(1e-6, max_sev)
snapshot['regime_label'] = re._map_regime_labels(snapshot)

bp_dates = pd.to_datetime([snapshot.loc[b, 'date'] for b in bkps if b < len(snapshot)])
if len(bp_dates) > 0:
    prox = []
    for d in pd.to_datetime(snapshot['date']):
        dist = int(np.min(np.abs((bp_dates - d).days)))
        if dist <= 5:
            prox.append('WITHIN_5_BARS')
        elif dist <= 20:
            prox.append('WITHIN_20_BARS')
        else:
            prox.append('OUTSIDE_EVENT_WINDOW')
else:
    prox = ['OUTSIDE_EVENT_WINDOW'] * len(snapshot)
snapshot['shock_proximity'] = prox
snapshot['computed_at'] = pd.Timestamp.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
snapshot['model_version'] = params.model_version + '_real_ohlcv'
snapshot['volatility_state'] = pd.cut(snapshot['rv_20'], bins=[-np.inf, 0.15, 0.22, 0.30, np.inf], labels=['LOW_VOL','NORMAL_VOL','HIGH_VOL','EXTREME_VOL']).astype(str)
snapshot['tail_risk_state'] = pd.cut(snapshot['tailloss_5_20'], bins=[-np.inf, 0.006, 0.012, 0.020, np.inf], labels=['NORMAL','ELEVATED','STRESSED','EXTREME']).astype(str)
snapshot['liquidity_state'] = pd.cut(snapshot['illiq_20'], bins=[-np.inf, snapshot['illiq_20'].quantile(0.5), snapshot['illiq_20'].quantile(0.8), np.inf], labels=['EASY','TIGHT','STRESSED'], include_lowest=True).astype(str)
q40 = float(np.quantile(snapshot['severity_score'], 0.4)); q75 = float(np.quantile(snapshot['severity_score'], 0.75));
if q75 <= q40: q75 = q40 + 1e-6
snapshot['market_risk_level'] = pd.cut(snapshot['severity_score'], bins=[-np.inf, q40, q75, np.inf], labels=['LOW','MEDIUM','HIGH'], include_lowest=True).astype(str)

snapshot_out = snapshot[[
    'date','scope','regime_label','cluster_id','cpd_boundary_flag','cpd_score','severity_score',
    'rv_20','tailloss_5_20','illiq_20','vix_z','vrp_z','breadth_stress',
    'volatility_state','tail_risk_state','liquidity_state','shock_proximity','market_risk_level',
    'computed_at','model_version'
]].sort_values('date').reset_index(drop=True)

ranges = re._segment_ranges(snapshot_out['date'], bkps)
b_rows = []
for idx, (l, r) in enumerate(ranges):
    if r >= len(snapshot_out):
        continue
    b_rows.append({
        'breakpoint_date': snapshot_out.loc[r, 'date'],
        'segment_left_start': snapshot_out.loc[l, 'date'],
        'segment_left_end': snapshot_out.loc[r-1, 'date'] if r-1 >= l else snapshot_out.loc[l, 'date'],
        'segment_right_start': snapshot_out.loc[r, 'date'],
        'segment_right_end': snapshot_out.loc[min(len(snapshot_out)-1, ranges[idx+1][1]-1), 'date'] if idx+1 < len(ranges) else snapshot_out.loc[len(snapshot_out)-1, 'date'],
        'penalty': params.penalty,
        'min_size': params.min_size,
        'jump': params.jump,
        'severity_score': float(sev.get(r, 0.0)),
        'event_hit_flag': False,
        'model_version': snapshot_out.loc[0, 'model_version'],
    })
breakpoints = pd.DataFrame(b_rows)

out_root = Path('D:/FactorPlatform/data/exports/regime_engine')
out_root.mkdir(parents=True, exist_ok=True)
snapshot_out.to_parquet(out_root / 'regime_snapshot_daily_real.parquet', index=False)
breakpoints.to_parquet(out_root / 'regime_breakpoints_real.parquet', index=False)

summary = {
    'rows_input_daily': int(agg.shape[0]),
    'rows_snapshot': int(snapshot_out.shape[0]),
    'rows_breakpoints': int(breakpoints.shape[0]),
    'date_min': str(snapshot_out['date'].min()),
    'date_max': str(snapshot_out['date'].max()),
    'latest': snapshot_out.iloc[-1].to_dict(),
    'regime_counts': snapshot_out['regime_label'].value_counts().to_dict(),
    'vol_state_counts': snapshot_out['volatility_state'].value_counts().to_dict(),
    'top_breakpoints': breakpoints.sort_values('severity_score', ascending=False).head(10).to_dict(orient='records'),
}
(out_root / 'regime_run_real_summary.json').write_text(json.dumps(summary, ensure_ascii=False, default=str, indent=2), encoding='utf-8')
print(json.dumps({
    'rows_snapshot': summary['rows_snapshot'],
    'rows_breakpoints': summary['rows_breakpoints'],
    'date_min': summary['date_min'],
    'date_max': summary['date_max'],
    'latest_regime': summary['latest']['regime_label'],
    'latest_cpd_score': summary['latest']['cpd_score'],
}, ensure_ascii=False))
