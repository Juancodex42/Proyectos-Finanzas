import io
import os
import tempfile
import zipfile
import tarfile

try:
    import py7zr
except ImportError:
    py7zr = None
    
try:
    import rarfile
except ImportError:
    rarfile = None

MAX_ARCHIVE_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # 200 MB


def process_archive(file_obj, filename, depth=0, state=None, process_func=None):
    """
    Recursively process files inside an archive (ZIP/TAR/7z/RAR).
    Returns aggregated processed transactions and raw samples.
    """
    if process_func is None:
        import processor_lib
        process_func = processor_lib.process_uploaded_file

    if state is None:
        state = {"extracted_size": 0, "declared_uncompressed": 0}
    else:
        state.setdefault("extracted_size", 0)
        state.setdefault("declared_uncompressed", 0)
    if depth > 3:
        raise ValueError("Excedida la profundidad máxima de descompresión permitida (límite: 3).")
        
    MAX_EXTRACT_SIZE = 100 * 1024 * 1024  # 100 MB
    print(f"Processing Archive: {filename} (depth={depth})")
    processed = []
    raw_sample = []
    
    try:
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        if zipfile.is_zipfile(file_obj):
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            temp_dir = tempfile.gettempdir()
            with zipfile.ZipFile(file_obj, 'r') as zf:
                real_temp = os.path.realpath(temp_dir)
                for member in zf.infolist():
                    target_path = os.path.realpath(os.path.join(temp_dir, member.filename))
                    if not target_path.startswith(real_temp + os.sep) and target_path != real_temp:
                        raise ValueError(f"Ruta insegura detectada en archivo comprimido: {member.filename}")
                    member_size = getattr(member, 'file_size', 0) or 0
                    state["declared_uncompressed"] += member_size
                    if state["declared_uncompressed"] > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                        raise ValueError("El archivo comprimido supera el límite de seguridad de tamaño descomprimido acumulado (200MB).")
                for member_name in zf.namelist():
                    if member_name.endswith('/') or '__MACOSX' in member_name or member_name.startswith('.'):
                        continue
                        
                    with zf.open(member_name) as f:
                        remaining = MAX_EXTRACT_SIZE - state["extracted_size"]
                        if remaining <= 0:
                            raise ValueError("El archivo comprimido supera el tamaño límite de extracción de 100MB.")
                        content = f.read(remaining + 1)
                        state["extracted_size"] += len(content)
                        if state["extracted_size"] > MAX_EXTRACT_SIZE:
                            raise ValueError("El archivo de extracción excede el límite permitido de 100MB.")
                            
                        sub_file = io.BytesIO(content)
                        p, r = process_func(sub_file, member_name, depth + 1, state)
                        processed.extend(p)
                        if len(raw_sample) < 5:
                            raw_sample.extend(r)
        else:
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            if py7zr and (py7zr.is_7zfile(file_obj) or filename.endswith('.7z')):
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
                try:
                    with tempfile.TemporaryDirectory() as temp_dir:
                        real_temp = os.path.realpath(temp_dir)
                        with py7zr.SevenZipFile(file_obj, mode='r') as zf:
                            info_7z = zf.archiveinfo()
                            total_uncompressed = getattr(info_7z, 'uncompressed', 0) or 0
                            state["declared_uncompressed"] += total_uncompressed
                            if state["declared_uncompressed"] > MAX_ARCHIVE_UNCOMPRESSED_BYTES or total_uncompressed > (MAX_EXTRACT_SIZE - state["extracted_size"]):
                                raise ValueError("El archivo comprimido supera el tamaño límite de extracción de 100MB.")
                            for fname in zf.getnames():
                                target_path = os.path.realpath(os.path.join(temp_dir, fname))
                                if not target_path.startswith(real_temp + os.sep) and target_path != real_temp:
                                    raise ValueError(f"Ruta insegura detectada en archivo comprimido: {fname}")
                            zf.extractall(path=temp_dir)
                            
                        for root, dirs, files in os.walk(temp_dir):
                            for fname in files:
                                if fname.startswith('.') or '__MACOSX' in fname:
                                    continue
                                file_path = os.path.realpath(os.path.join(root, fname))
                                if not file_path.startswith(os.path.realpath(temp_dir)):
                                    continue
                                with open(file_path, 'rb') as f:
                                    remaining = MAX_EXTRACT_SIZE - state["extracted_size"]
                                    if remaining <= 0:
                                        raise ValueError("El archivo comprimido supera el tamaño límite de extracción de 100MB.")
                                    content = f.read(remaining + 1)
                                    state["extracted_size"] += len(content)
                                    if state["extracted_size"] > MAX_EXTRACT_SIZE:
                                        raise ValueError("El archivo de extracción excede el límite permitido de 100MB.")
                                    sub_file = io.BytesIO(content)
                                    p, r = process_func(sub_file, fname, depth + 1, state)
                                    processed.extend(p)
                                    if len(raw_sample) < 5:
                                        raw_sample.extend(r)
                except Exception as e:
                    print(f"7z Extraction Error: {e}")
                    raise e
            else:
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
                if rarfile and (rarfile.is_rarfile(file_obj) or filename.endswith('.rar')):
                    if hasattr(file_obj, 'seek'):
                        file_obj.seek(0)
                    temp_dir = tempfile.gettempdir()
                    real_temp = os.path.realpath(temp_dir)
                    with rarfile.RarFile(file_obj) as rf:
                        for f in rf.infolist():
                            target_path = os.path.realpath(os.path.join(temp_dir, f.filename))
                            if not target_path.startswith(real_temp + os.sep) and target_path != real_temp:
                                raise ValueError(f"Ruta insegura detectada en archivo comprimido: {f.filename}")
                            f_size = getattr(f, 'file_size', 0) or 0
                            state["declared_uncompressed"] += f_size
                            if state["declared_uncompressed"] > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                                raise ValueError("El archivo comprimido supera el límite de seguridad de tamaño descomprimido acumulado (200MB).")
                            if f.isdir():
                                continue
                            with rf.open(f) as rfo:
                                remaining = MAX_EXTRACT_SIZE - state["extracted_size"]
                                if remaining <= 0:
                                    raise ValueError("El archivo comprimido supera el tamaño límite de extracción de 100MB.")
                                content = rfo.read(remaining + 1)
                                state["extracted_size"] += len(content)
                                if state["extracted_size"] > MAX_EXTRACT_SIZE:
                                    raise ValueError("El archivo de extracción excede el límite permitido de 100MB.")
                                sub_file = io.BytesIO(content)
                                p, r = process_func(sub_file, f.filename, depth + 1, state)
                                processed.extend(p)
                                if len(raw_sample) < 5:
                                    raw_sample.extend(r)
                else:
                    if hasattr(file_obj, 'seek'):
                        file_obj.seek(0)
                    if tarfile.is_tarfile(file_obj):
                        if hasattr(file_obj, 'seek'):
                            file_obj.seek(0)
                        temp_dir = tempfile.gettempdir()
                        real_temp = os.path.realpath(temp_dir)
                        with tarfile.open(fileobj=file_obj, mode='r:*') as t:
                            for member in t.getmembers():
                                target_path = os.path.realpath(os.path.join(temp_dir, member.name))
                                if not target_path.startswith(real_temp + os.sep) and target_path != real_temp:
                                    raise ValueError(f"Ruta insegura detectada en archivo comprimido: {member.name}")
                                member_size = getattr(member, 'size', 0) or 0
                                state["declared_uncompressed"] += member_size
                                if state["declared_uncompressed"] > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                                    raise ValueError("El archivo comprimido supera el límite de seguridad de tamaño descomprimido acumulado (200MB).")
                                if not member.isfile():
                                    continue
                                f = t.extractfile(member)
                                if f:
                                    remaining = MAX_EXTRACT_SIZE - state["extracted_size"]
                                    if remaining <= 0:
                                        raise ValueError("El archivo comprimido supera el tamaño límite de extracción de 100MB.")
                                    content = f.read(remaining + 1)
                                    state["extracted_size"] += len(content)
                                    if state["extracted_size"] > MAX_EXTRACT_SIZE:
                                        raise ValueError("El archivo de extracción excede el límite permitido de 100MB.")
                                    sub_file = io.BytesIO(content)
                                    p, r = process_func(sub_file, member.name, depth + 1, state)
                                    processed.extend(p)
                                    if len(raw_sample) < 5:
                                        raw_sample.extend(r)
                            
    except Exception as e:
        print(f"Error processing archive {filename}: {e}")
        err_msg = str(e).lower()
        if "rar" in err_msg or "unrar" in err_msg:
            raise ValueError("Para procesar archivos .RAR se requiere instalar UnRAR en Windows. Por favor extrae los archivos o conviértelos a .ZIP antes de subirlos.")
        raise e

    return processed, raw_sample

extract_and_process_archive = process_archive

