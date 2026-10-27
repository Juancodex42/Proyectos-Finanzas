"""
Funciones de saneamiento y parseo de fechas y números para extractores PDF/OCR.
Higieniza artefactos de escaneo y corrige fechas malformadas en dictámenes.
Referencia de diseño: docs/contratos_io_transacciones.md
"""

import re
from datetime import datetime


def clean_num(s):
    if not s:
        return 0.0
    orig_str = str(s)
    has_fiat_symbol = ('$' in orig_str) or any(c in orig_str.upper() for c in ['ARS', 'USD', 'EUR', 'PESOS'])
    s = orig_str.replace('$', '').replace('ARS', '').replace('ars', '').replace('USD', '').replace('usd', '').replace('Completed', '').replace('Cancelled', '').strip()
    if '.' in s and ',' in s:
        s = s.replace('.', '').replace(',', '.') if s.rfind(',') > s.rfind('.') else s.replace(',', '')
    elif ',' in s and '.' not in s:
        s = s.replace(',', '.')
    elif '.' in s and s.count('.') > 1:
        parts = s.split('.')
        if has_fiat_symbol:
            s = ''.join(parts)
        elif len(parts[-1]) <= 2:
            s = ''.join(parts[:-1]) + '.' + parts[-1]
        else:
            try:
                first_int = int(parts[0])
                s = (parts[0] + '.' + ''.join(parts[1:])) if first_int < 50000 else ''.join(parts)
            except Exception:
                s = ''.join(parts)
    try:
        return float(s)
    except Exception:
        return 0.0


def _sanitize_and_build_date(y, m, d, hh='00', mm='00', ss='00'):
    hh, mm = hh or '00', mm or '00'
    ss = '00' if not ss else (ss.zfill(2) if len(ss) == 1 else ss)
    curr_year = datetime.now().year

    if len(y) == 2:
        y = '20' + y
    elif len(y) == 3 and y.startswith('02'):
        y = '2' + y

    if len(y) == 4 and y.startswith('2'):
        try:
            yi = int(y)
            if yi > curr_year + 1 or yi < 2015:
                if y.startswith('207') and y[3] in '0123456789':
                    y = '202' + y[3]
                elif y[1] in '689' and y[2] == '2':
                    y = '20' + y[2:]
                elif y.endswith('24'):
                    y = '2024'
                elif y.endswith('25'):
                    y = '2025'
                elif y.endswith('26'):
                    y = '2026'
        except ValueError:
            return ''

    try:
        yi = int(y)
        mi = int(m)
        di = int(d)
        if yi < 2015 or yi > curr_year + 1:
            return ''

        # Common OCR digit misreads in scanned certificates
        if mi in (42, 92):
            mi = 12
        elif mi in (61, 91):
            mi = 1
        elif mi == 0:
            mi = 1

        if di == 0:
            di = 1
        elif di == 41:
            di = 24

        if mi > 12 and di <= 12:
            mi, di = di, mi

        m, d = str(mi), str(di)
        if mi < 1 or mi > 12 or di < 1 or di > 31:
            return ''
        # Days per month validation
        max_days = 31
        if mi in (4, 6, 9, 11):
            max_days = 30
        elif mi == 2:
            is_leap = (yi % 4 == 0 and yi % 100 != 0) or (yi % 400 == 0)
            max_days = 29 if is_leap else 28
        if di > max_days:
            di = max_days
            d = str(di)
    except ValueError:
        return ''
    return f'{y}-{m.zfill(2)}-{d.zfill(2)} {hh}:{mm}:{ss}'


def parse_date_str(s):
    if not s:
        return ''
    s = str(s).strip().replace('T', ' ')
    if '+' in s:
        s = s.split('+')[0].strip()

    m1 = re.search(r'(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{2}):(\d{2})(?::(\d{1,2}))?)?', s)
    if m1:
        y, m, d, hh, mm, ss = m1.groups()
        res = _sanitize_and_build_date(y, m, d, hh, mm, ss)
        if res:
            return res

    m1_rev = re.search(r'(\d{2})-(\d{2})-(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{1,2}))?)?', s)
    if m1_rev:
        d, m, y, hh, mm, ss = m1_rev.groups()
        res = _sanitize_and_build_date(y, m, d, hh, mm, ss)
        if res:
            return res

    m1_2d = re.search(r'(\d{2})-(\d{2})-(\d{2})(?:\s+(\d{2}):(\d{2})(?::(\d{1,2}))?)?', s)
    if m1_2d:
        p1, m, p2, hh, mm, ss = m1_2d.groups()
        y, d = ('20' + p2, p1) if int(p1) > 12 or int(p2) <= 31 else ('20' + p1, p2)
        res = _sanitize_and_build_date(y, m, d, hh, mm, ss)
        if res:
            return res

    m2 = re.search(r'(\d{2})/(\d{2})/(\d{2,4})(?:\s+(\d{2}):(\d{2})(?::(\d{1,2}))?)?', s)
    if m2:
        d, m, y, hh, mm, ss = m2.groups()
        res = _sanitize_and_build_date(y, m, d, hh, mm, ss)
        if res:
            return res
    return ''
