import io
from typing import Any, Union
import pandas as pd
from werkzeug.datastructures import FileStorage

from backend.utils.error_handlers import CSVLoadError


def load_csv(file_stream: Union[FileStorage, io.BytesIO, io.StringIO, bytes, str]) -> pd.DataFrame:
    """
    Read an uploaded CSV stream, byte buffer, or file path into a pandas DataFrame.
    
    Raises:
        CSVLoadError: If the file is empty, unreadable, or corrupted.
    """
    if file_stream is None:
        raise CSVLoadError("No file stream provided.")

    try:
        # If it is a Werkzeug FileStorage object
        if isinstance(file_stream, FileStorage):
            file_stream.stream.seek(0, io.SEEK_END)
            size = file_stream.stream.tell()
            file_stream.stream.seek(0)
            if size == 0:
                raise CSVLoadError("Uploaded CSV file is empty (0 bytes).")
            # Read into DataFrame
            df = pd.read_csv(file_stream.stream)

        # If raw bytes
        elif isinstance(file_stream, (bytes, bytearray)):
            if len(file_stream) == 0:
                raise CSVLoadError("Provided CSV byte stream is empty.")
            df = pd.read_csv(io.BytesIO(file_stream))

        # If BytesIO or StringIO
        elif isinstance(file_stream, (io.BytesIO, io.StringIO)):
            file_stream.seek(0, io.SEEK_END)
            size = file_stream.tell()
            file_stream.seek(0)
            if size == 0:
                raise CSVLoadError("Provided file buffer is empty.")
            df = pd.read_csv(file_stream)

        # If string file path
        elif isinstance(file_stream, str):
            df = pd.read_csv(file_stream)

        else:
            df = pd.read_csv(file_stream)

    except pd.errors.EmptyDataError:
        raise CSVLoadError("Uploaded CSV contains no readable columns or data rows.")
    except pd.errors.ParserError as pe:
        raise CSVLoadError(f"Malformed or corrupted CSV file structure: {str(pe)}")
    except UnicodeDecodeError as ue:
        raise CSVLoadError(f"CSV file encoding error: {str(ue)}. Please upload UTF-8 encoded CSV.")
    except CSVLoadError:
        raise
    except Exception as e:
        raise CSVLoadError(f"Failed to read CSV dataset: {str(e)}")

    if df.empty or len(df) == 0:
        raise CSVLoadError("Uploaded CSV contains headers but zero data records.")

    return df
