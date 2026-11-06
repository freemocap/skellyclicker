"""Publish an immutable image-inclusion revision; the caller commits its project pointer."""
from uuid import uuid4
import pyarrow as pa
import pyarrow.parquet as pq
from freemocap_sdk.storage import atomic_json,file_digest,publish_directory
from .projects import recording_structure

def write_selection(root,recording_id,label_result,label_hash,rows,previous=None,reason='manual'):
    revision='selection-'+uuid4().hex[:12]
    extension=recording_structure(root,recording_id).application_dir('skellyclicker')
    staged=extension/'working'/'reviews'/revision;staged.mkdir(parents=True)
    schema=pa.schema([('image_id',pa.string()),('camera_id',pa.string()),('moment_id',pa.string()),('source_frame',pa.int64()),('timestamp_ns',pa.int64())])
    values=[{**{key:r[key] for key in ('image_id','camera_id','moment_id','source_frame')},'timestamp_ns':int(r['timestamp_ns'])} for r in rows]
    pq.write_table(pa.Table.from_pylist(values,schema=schema),staged/'selection.parquet')
    atomic_json(staged/'manifest.json',{'schema_version':2,'label_result':label_result,'label_manifest_sha256':label_hash,
        'previous_selection_sha256':previous,'review_state':'unreviewed','initialization':reason,
        'meaning':'Image inclusion draft; not approved labels; moment_id preserves stereo grouping',
        'files':{'selection.parquet':{'sha256':file_digest(staged/'selection.parquet'),'bytes':(staged/'selection.parquet').stat().st_size}}})
    destination=extension/'reviews'/revision;destination.parent.mkdir(parents=True,exist_ok=True)
    publish_directory(staging=staged,destination=destination)
    return destination.relative_to(root).as_posix()
