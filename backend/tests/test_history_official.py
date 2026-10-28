from datetime import date
import io
import zipfile
import pandas as pd
import pytest
import app.history_cache as cache
import app.history_official as official


def test_official_archive_requires_exact_session_schema_and_cash_series():
    text = ('TradDt,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol\n'
            '2026-10-27,STOCK,EQ,100,101,99,100,1000\n'
            '2026-10-27,OTHER,BE,100,101,99,100,1000\n')
    def archive(text):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as output:
            output.writestr('cash.csv', text)
        return buffer.getvalue()
    assert set(official.archive_rows(archive(text), date(2026, 10, 27))) == {'STOCK'}
    with pytest.raises(ValueError, match='session'):
        official.archive_rows(archive(text), date(2026, 10, 26))
    with pytest.raises(ValueError, match='schema'):
        official.archive_rows(archive('bad,header\n1,2'), date(2026, 10, 27))


def test_official_fallback_rejects_adjustment_mismatch_and_preserves_data(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, 'CACHE_DIR', tmp_path)
    index = pd.bdate_range(end='2026-10-26', periods=400)
    def frame(price):
        return pd.DataFrame({'open': price, 'high': price+1, 'low': price-1, 'close': price, 'volume': 1000}, index=index)
    cache.save_history('GOOD', frame(100.))
    cache.save_history('SPLIT', frame(50.))
    row = {'open': 100., 'high': 101., 'low': 99., 'close': 100., 'volume': 1000}
    monkeypatch.setattr(official, 'download_session', lambda day: {'GOOD': row, 'SPLIT': row})
    monkeypatch.setattr(official, 'corporate_actions', lambda day: set())
    result = official.repair_from_nse(['GOOD', 'SPLIT'], date(2026, 10, 27))
    assert result['recovered'] == ['GOOD']
    assert result['rejected'][0]['symbol'] == 'SPLIT'
    assert cache.load_history('GOOD').index.max() == pd.Timestamp('2026-10-27')
    assert cache.load_history('SPLIT').index.max() == pd.Timestamp('2026-10-26')


def test_ex_date_is_rejected_even_when_prior_ohlc_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, 'CACHE_DIR', tmp_path)
    index = pd.bdate_range(end='2026-10-26', periods=400)
    row = {'open': 100., 'high': 101., 'low': 99., 'close': 100., 'volume': 1000}
    cache.save_history('EXDIV', pd.DataFrame(row, index=index))
    monkeypatch.setattr(official, 'download_session', lambda day: {'EXDIV': row})
    monkeypatch.setattr(official, 'corporate_actions', lambda day: {'EXDIV'})
    result = official.repair_from_nse(['EXDIV'], date(2026, 10, 27))
    assert result['recovered'] == []
    assert 'Corporate action' in result['rejected'][0]['reason']
    assert cache.load_history('EXDIV').index.max() == pd.Timestamp('2026-10-26')


def test_constant_adjustment_factor_preserves_existing_history_and_basis(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, 'CACHE_DIR', tmp_path)
    index = pd.bdate_range(end='2026-10-26', periods=400)
    row = {'open': 100., 'high': 101., 'low': 99., 'close': 100., 'volume': 1000}
    previous = pd.DataFrame(row, index=index)
    columns = ['open', 'high', 'low', 'close']
    previous.loc[:, columns] *= .997
    cache.save_history('ADJUSTED', previous)
    monkeypatch.setattr(official, 'download_session', lambda day: {'ADJUSTED': row})
    monkeypatch.setattr(official, 'corporate_actions', lambda day: set())
    result = official.repair_from_nse(['ADJUSTED'], date(2026, 10, 27))
    assert result['recovered'] == ['ADJUSTED']
    assert result['basisFactors']['ADJUSTED'] == pytest.approx(.997)
    actual = cache.load_history('ADJUSTED')
    pd.testing.assert_frame_equal(actual.loc[index], previous, check_freq=False, check_names=False)
    assert actual.iloc[-1]['close'] == pytest.approx(99.7)
    assert actual.iloc[-1]['volume'] == 1000


def test_unverified_corporate_actions_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, 'CACHE_DIR', tmp_path)
    monkeypatch.setattr(official, 'download_session', lambda day: {})
    def unavailable(day):
        raise ValueError('Unavailable actions manifest')
    monkeypatch.setattr(official, 'corporate_actions', unavailable)
    assert official.repair_from_nse(['STOCK'], date(2026, 10, 27))['status'] == 'UNAVAILABLE'


def test_official_source_unavailability_never_alters_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, 'CACHE_DIR', tmp_path)
    def unavailable(day):
        raise OSError('offline')
    monkeypatch.setattr(official, 'download_session', unavailable)
    result = official.repair_from_nse(['STOCK'], date(2026, 10, 27))
    assert result['status'] == 'UNAVAILABLE'
    assert not list(tmp_path.iterdir())
