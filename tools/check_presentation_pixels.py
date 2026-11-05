"""Compare visible playback screenshots with an independently decoded reference."""
import json
from pathlib import Path
import numpy as np
from PIL import Image

root=Path(__file__).resolve().parents[1]/'.test-artifacts'
data=json.loads((root/'presentation-pixels.json').read_text(encoding='utf-8'))
checks=[]
for row in data['results']:
    actual=np.asarray(Image.open(row['actualPath']).convert('RGB'),dtype=float)
    expected=np.asarray(Image.open(row['expectedPath']).convert('RGB'),dtype=float)
    if actual.shape!=expected.shape:raise AssertionError('Screenshots must use identical display dimensions')
    error=np.abs(actual-expected)
    checks.append({key:row[key] for key in ('mode','frame','camera')}|{
        'max':float(error.max()),'mean':float(error.mean()),'different':int(np.count_nonzero(error))})
result={'checks':checks,'post_ready_cloud_requests':data['postReadyCloudRequests']}
(root/'presentation-pixel-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
assert len(checks)==20 and max(row['max'] for row in checks)==0,result
assert data['postReadyCloudRequests']==0,result
print('PASS: 20 pixel-identical camera frames; no cloud requests after readiness')
