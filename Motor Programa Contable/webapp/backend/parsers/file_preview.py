import datetime
import re
import unicodedata
import pandas as pd


def _normalize_text(s):
    """Lowercases, strips whitespace/BOM, and removes accents/diacritics."""
    if s is None:
        return ""
    s = unicodedata.normalize('NFKD', str(s).replace('\ufeff', '').strip().lower())
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return s.replace('_', ' ').replace('-', ' ').strip()


def _extract_header_like_cells(values):
    """Returns normalized cell strings if the row looks like a header row (>=3 non-numeric text cells <=40 chars)."""
    text_cells = []
    for val in values:
        if val is None or pd.isna(val):
            continue
        if isinstance(val, (int, float, datetime.date, datetime.datetime, pd.Timestamp)):
            return []
        s = str(val).strip()
        if not s:
            continue
        if len(s) > 40:
            return []
        s_num = s.replace('.', '', 1).replace(',', '', 1).lstrip('+-')
        if s_num.isdigit():
            return []
        if re.match(r'^\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{1,4}', s):
            return []
        text_cells.append(s)
    if len(text_cells) >= 3:
        return [_normalize_text(c) for c in text_cells if _normalize_text(c)]
    return []


def extract_preview_columns(file_obj, filename):
    """Sniffs preview column names and cell content from an uploaded CSV or Excel file."""
    file_obj.seek(0)
    cols_set = set()
    fn = filename.lower()
    if fn.endswith(('.xlsx', '.xls')):
        try:
            preview_df = pd.read_excel(file_obj, nrows=25, header=None)
            if preview_df is not None and not preview_df.empty:
                for _, p_row in preview_df.iterrows():
                    header_cells = _extract_header_like_cells(p_row.values)
                    if header_cells:
                        cols_set.update(header_cells)
        except Exception:
            pass
    else:
        for enc in ['utf-8-sig', 'utf-8', 'latin1', 'cp1252']:
            for sep in [None, ',', ';', '\t']:
                try:
                    file_obj.seek(0)
                    kwargs = {'encoding': enc, 'nrows': 2, 'on_bad_lines': 'skip'}
                    if sep is not None:
                        kwargs['sep'] = sep
                    preview_df = pd.read_csv(file_obj, **kwargs)
                    if preview_df is not None and not preview_df.empty and len(preview_df.columns) > 1:
                        cols_set = {_normalize_text(c) for c in preview_df.columns}
                        break
                except Exception:
                    pass
            if cols_set:
                break
    file_obj.seek(0)
    return cols_set

