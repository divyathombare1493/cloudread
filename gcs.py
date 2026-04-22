import os
import uuid
from google.cloud import storage
from google.oauth2 import service_account

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.join(BASE_DIR, 'key.json')
BUCKET_NAME = 'bkt-cloud-read'

_credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
_client = storage.Client(credentials=_credentials, project=_credentials.project_id)
_bucket = _client.bucket(BUCKET_NAME)


def upload_file(file_storage, folder):
    ext = os.path.splitext(file_storage.filename)[1].lower()
    blob_name = f"{folder}/{uuid.uuid4().hex}{ext}"
    blob = _bucket.blob(blob_name)
    file_storage.stream.seek(0)
    blob.upload_from_file(file_storage.stream, content_type=file_storage.mimetype)
    return f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"
