"""Separate ranked-out candidates from deliberate human label rejections."""
import json
import pyarrow.parquet as pq
from freemocap_sdk.storage import file_digest,resolve_relative
from .projects import Project,read_model
from .label_inputs import checked


def rejected_image_ids(manifest):
    project=read_model(manifest,Project)
    if not project.active_review:return set()
    active=resolve_relative(manifest.parent,project.active_review)
    revisions={file_digest(p):p for p in active.parent.glob('*/manifest.json')}
    chain=[];current=active/'manifest.json';seen=set()
    while current:
        digest=file_digest(current)
        if digest in seen:raise ValueError('Selection history contains a cycle')
        seen.add(digest);meta=json.loads(current.read_text(encoding='utf-8'))
        checked(current.parent/'selection.parquet',meta['files']['selection.parquet'])
        rows=pq.read_table(current.parent/'selection.parquet').to_pylist()
        if meta.get('schema_version',1)==1:
            labels=resolve_relative(manifest.parent,meta['label_result'])
            if file_digest(labels/'manifest.json')!=meta['label_manifest_sha256']:raise ValueError('Historical labels changed')
            label_meta=json.loads((labels/'manifest.json').read_text(encoding='utf-8'))
            checked(labels/'images.parquet',label_meta['files']['images.parquet'])
            moments={r['moment_id'] for r in rows}
            rows=[{'image_id':r['moment_id']+':'+r['camera_id']} for r in pq.read_table(labels/'images.parquet').to_pylist() if r['moment_id'] in moments]
        elif meta.get('schema_version')!=2:raise ValueError('Unsupported selection history version')
        chain.append((meta,{r['image_id'] for r in rows}))
        previous=meta.get('previous_selection_sha256')
        if previous and previous not in revisions:raise ValueError('Selection history is incomplete; cannot distinguish rejected labels from unused candidates')
        current=revisions.get(previous)
    rejected=set();before=set()
    for meta,after in reversed(chain):
        # Best-N is a budget/coverage choice, not a rejection of every other label.
        ranked=meta.get('initialization')=='bulk_keep' and bool((meta.get('membership_change') or {}).get('ranking'))
        if not ranked:rejected.update(before-after)
        rejected.difference_update(after-before)
        before=after
    return rejected
