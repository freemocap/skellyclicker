"""Read-only checkpoint views from frozen images and saved predictions."""
import json, math
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw
from freemocap_sdk.storage import resolve_relative,file_digest
from .label_inputs import checked


def epoch_files(folder):
    return sorted((int(p.parent.name.removeprefix('epoch-')), p) for p in (folder/'previews').glob('epoch-*/predictions.json') if p.parent.name.removeprefix('epoch-').isdigit())


def preview_rows(folder, epoch):
    path=folder/'previews'/f'epoch-{epoch:06d}'/'predictions.json'
    saved=json.loads(path.read_text(encoding='utf-8'))
    request=json.loads((folder/'worker-request.json').read_text(encoding='utf-8'))
    sources={row['image_id']:row for row in request['images']}
    return [(sources[s['image_id']],s) for s in saved['samples'] if s['image_id'] in sources]


def render_preview(folder, project_root, epoch, image_id, crop, annotated, max_size):
    pair=next(((r,s) for r,s in preview_rows(folder,epoch) if r['image_id']==image_id),None)
    if pair is None:raise ValueError('Image was not evaluated at this epoch')
    row,sample=pair
    frozen=json.loads((folder/'dataset.json').read_text(encoding='utf-8'))
    dataset=resolve_relative(project_root,frozen['path'])
    if file_digest(dataset/'manifest.json')!=frozen['manifest_sha256']:raise ValueError('Frozen dataset manifest changed')
    path=resolve_relative(dataset,row['path']);checked(path,row)
    with Image.open(path) as source:image=source.convert('RGB')
    points=[(float(x),float(y)) for (x,y),valid in zip(row['xy'],row['valid']) if valid and x is not None and y is not None and math.isfinite(x) and math.isfinite(y)]
    if annotated:
        draw=ImageDraw.Draw(image)
        for x,y in points:draw.ellipse((x-3,y-3,x+3,y+3),outline='#ff46ff',width=1)
        for x,y,*_ in sample['keypoints']:
            if x is not None and y is not None and math.isfinite(x) and math.isfinite(y):
                draw.line((x-3,y,x+3,y),fill='#46e6ff',width=1);draw.line((x,y-3,x,y+3),fill='#46e6ff',width=1)
    if crop:
        if not points:raise ValueError('No valid reference points for a target crop; choose Full image')
        left=max(0,math.floor(min(x for x,y in points)-20));top=max(0,math.floor(min(y for x,y in points)-20))
        right=min(image.width,math.ceil(max(x for x,y in points)+20));bottom=min(image.height,math.ceil(max(y for x,y in points)+20))
        if right<=left or bottom<=top:raise ValueError('Target crop is outside the source image')
        image=image.crop((left,top,right,bottom))
    if max_size:image.thumbnail((max_size,max_size))
    output=BytesIO();image.save(output,format='PNG');return output.getvalue()
