"""Optional official NSE settled cash data, with price-basis consistency checks."""
import csv
from datetime import date
import io
import urllib.request
import zipfile
import pandas as pd

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


def repair_from_nse(symbols, expected):
    report = {'source': 'NSE_OFFICIAL_CASH_BHAVCOPY', 'status': 'NOT_NEEDED',
              'attempted': len(symbols), 'recovered': [], 'rejected': []}
    if not symbols:
        return report
    sessions = [expected]
    for _ in range(3):
        sessions.append(previous_trading_session(sessions[-1]))
    try:
        archives = {session: download_session(session) for session in sessions}
    except Exception as error:
        # Public source failure never bypasses validation or fabricates a bar.
        report.update(status='UNAVAILABLE', reason=type(error).__name__)
        if isinstance(getattr(error, 'code', None), int):
            report['httpStatus'] = error.code
        return report
    for symbol in symbols:
        records = [(session, archives[session][symbol]) for session in sessions if symbol in archives[session]]
        if len(records) != 4:
            report['rejected'].append({'symbol': symbol, 'reason': 'Missing cash-equity sessions'})
            continue
        frame = pd.DataFrame([row for _, row in records], index=pd.to_datetime([day for day, _ in records]))
        recent = validated_frame(frame, expected)
        previous = validated_frame(load_history(symbol), expected)
        combined = merge_recent_history(previous, recent, expected)
        if combined is None:
            report['rejected'].append({'symbol': symbol, 'reason': 'Adjusted historical OHLC mismatch'})
            continue
        save_history(symbol, combined)
        report['recovered'].append(symbol)
    report.update(status='COMPLETE' if len(report['recovered']) == len(symbols) else 'PARTIAL',
                  sessions=[str(day) for day in sorted(sessions)])
    return report
