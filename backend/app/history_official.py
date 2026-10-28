"""Optional official NSE settled cash data, with price-basis consistency checks."""
import csv
from datetime import date, datetime
import io
import json
import urllib.request
import zipfile
import pandas as pd
import numpy as np

from .history_cache import load_history, save_history
from .history_quality import merge_recent_history, validated_frame
from .reliability import previous_trading_session


def archive_rows(payload, session):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        files = [item for item in archive.infolist() if item.filename.lower().endswith('.csv')]
        if len(files) != 1 or files[0].file_size > 100_000_000:
            raise ValueError('Unexpected NSE archive structure')
        text = archive.read(files[0]).decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    required = {'TradDt', 'TckrSymb', 'SctySrs', 'OpnPric', 'HghPric', 'LwPric', 'ClsPric', 'TtlTradgVol'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('Unexpected NSE cash schema')
    rows = {}
    for row in reader:
        if row['SctySrs'].strip() != 'EQ':
            continue
        if date.fromisoformat(row['TradDt'].strip()) != session:
            raise ValueError('Archive session does not match requested date')
        symbol = row['TckrSymb'].strip()
        if symbol in rows:
            raise ValueError('Duplicate NSE symbol/session')
        try:
            rows[symbol] = {key: float(row[column]) for key, column in [
                ('open', 'OpnPric'), ('high', 'HghPric'), ('low', 'LwPric'),
                ('close', 'ClsPric'), ('volume', 'TtlTradgVol')]}
        except (TypeError, ValueError):
            continue
    return rows


def download_session(session):
    url = ('https://nsearchives.nseindia.com/content/cm/'
           f'BhavCopy_NSE_CM_0_0_0_{session:%Y%m%d}_F_0000.csv.zip')
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0', 'Accept': 'application/zip,application/octet-stream'})
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = response.read(20_000_001)
    if len(payload) > 20_000_000:
        raise ValueError('NSE archive exceeds size limit')
    return archive_rows(payload, session)


def corporate_actions(session):
    # Raw bhavcopy bars cannot extend adjusted histories on an unverified ex-date.
    clock = session.strftime('%d-%m-%Y')
    url = ('https://www.nseindia.com/api/corporates-corporateActions'
           f'?index=equities&from_date={clock}&to_date={clock}')
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = response.read(5_000_001)
    if len(payload) > 5_000_000:
        raise ValueError('Corporate action response exceeds size limit')
    records = json.loads(payload)
    if not isinstance(records, list):
        raise ValueError('Unverified corporate action manifest')
    affected = set()
    for row in records:
        if not isinstance(row, dict) or not row.get('symbol') or not row.get('exDate'):
            raise ValueError('Incomplete corporate action manifest')
        try:
            ex_date = datetime.strptime(row['exDate'], '%d-%b-%Y').date()
        except ValueError:
            ex_date = date.fromisoformat(row['exDate'])
        if ex_date != session:
            raise ValueError('Corporate action manifest date mismatch')
        affected.add(row['symbol'].strip())
    return affected


def repair_from_nse(symbols, expected):
    report = {'source': 'NSE_OFFICIAL_CASH_BHAVCOPY', 'status': 'NOT_NEEDED',
              'attempted': len(symbols), 'recovered': [], 'rejected': [], 'basisFactors': {}}
    if not symbols:
        return report
    sessions = [expected]
    for _ in range(3):
        sessions.append(previous_trading_session(sessions[-1]))
    try:
        archives = {session: download_session(session) for session in sessions}
        actions = corporate_actions(expected)
    except Exception as error:
        # Public source failure never bypasses validation or fabricates a bar.
        report.update(status='UNAVAILABLE', reason=type(error).__name__)
        if isinstance(getattr(error, 'code', None), int):
            report['httpStatus'] = error.code
        return report
    for symbol in symbols:
        if symbol in actions:
            report['rejected'].append({'symbol': symbol, 'reason': 'Corporate action requires full adjusted history'})
            continue
        records = [(session, archives[session][symbol]) for session in sessions if symbol in archives[session]]
        if len(records) != 4:
            report['rejected'].append({'symbol': symbol, 'reason': 'Missing cash-equity sessions'})
            continue
        frame = pd.DataFrame([row for _, row in records], index=pd.to_datetime([day for day, _ in records]))
        recent = validated_frame(frame, expected)
        previous = validated_frame(load_history(symbol), expected)
        # Yahoo adjusted bars and official raw bars may use a different constant
        # basis. Verify all 12 OHLC values over three sessions, not close alone.
        # Corporate actions on the appended session were already excluded above.
        if previous is not None:
            overlap = previous.index.intersection(recent.index).sort_values()[-3:]
            if len(overlap) == 3:
                columns = ['open', 'high', 'low', 'close']
                prior = previous.loc[overlap, columns].to_numpy(dtype=float)
                raw = recent.loc[overlap, columns].to_numpy(dtype=float)
                factor = float(np.median(prior / raw))
                if np.isfinite(factor) and factor > 0 and np.allclose(prior, raw * factor, rtol=1e-5, atol=1e-6):
                    recent.loc[:, columns] *= factor
                    report['basisFactors'][symbol] = factor
        combined = merge_recent_history(previous, recent, expected)
        if combined is None:
            report['rejected'].append({'symbol': symbol, 'reason': 'Adjusted historical OHLC mismatch'})
            continue
        save_history(symbol, combined)
        report['recovered'].append(symbol)
    report.update(status='COMPLETE' if len(report['recovered']) == len(symbols) else 'PARTIAL',
                  sessions=[str(day) for day in sorted(sessions)])
    return report
