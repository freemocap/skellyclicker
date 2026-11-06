import unittest
from skellyclicker_app.target_crops import projection_bounds

class TargetCropTests(unittest.TestCase):
 def test_padding_and_edge_clamp(self):
  value=projection_bounds({'positive_depth':True,'keypoints_xy':[[2,5],[20,30]],'mesh_wireframe_segments_xy':[[[1,2],[25,32]]]},100,80)
  self.assertEqual(value,dict(x=0.,y=0.,width=28.,height=35.))
 def test_unavailable_does_not_show_unrelated_pixels(self):
  for value in (None,{'positive_depth':False,'keypoints_xy':[[2,3]]},{'positive_depth':True,'keypoints_xy':[[-30,5],[-1,30]]},{'positive_depth':True,'keypoints_xy':[[float('nan'),2]]}):
   self.assertIsNone(projection_bounds(value,100,80))

 def test_thumbnail_preserves_outline_and_keypoints_without_letterbox(self):
  import tempfile,json
  from io import BytesIO
  from pathlib import Path
  from PIL import Image
  from freemocap_sdk.storage import file_digest
  from skellyclicker_app.label_routes import image_thumbnail
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/'source.png';Image.new('RGB',(120,80),'white').save(source)
   projection=root/'projection.jsonl';projection.write_text(json.dumps({'projection':{'mesh_wireframe_segments_xy':[[[10,10],[80,10]]]}})+'\n')
   data=image_thumbnail(source,file_digest(source),source.stat().st_size,source.stat().st_mtime_ns,(0,0,100,60),((40,40,True),),projection,0,file_digest(projection))
   output=Image.open(BytesIO(data));self.assertEqual(output.size,(100,60));self.assertEqual(output.format,'PNG')
   self.assertEqual(output.getpixel((40,10)),(55,234,255));self.assertEqual(output.getpixel((40,40)),(255,69,230));self.assertEqual(output.getpixel((0,0)),(255,255,255))

 def test_raw_and_annotated_views_share_crop_and_preserve_source(self):
  import tempfile,json
  from io import BytesIO
  from pathlib import Path
  from PIL import Image
  from freemocap_sdk.storage import file_digest
  from skellyclicker_app.label_routes import image_thumbnail
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/'source.png';Image.new('RGB',(120,80),(21,42,63)).save(source);original=source.read_bytes()
   projection=root/'projection.jsonl';projection.write_text(json.dumps({'projection':{'mesh_wireframe_segments_xy':[[[10,10],[80,10]]]}})+'\n')
   args=(source,file_digest(source),source.stat().st_size,source.stat().st_mtime_ns,(10,10,50,40),((40,40,True),),projection,0,file_digest(projection))
   annotated=Image.open(BytesIO(image_thumbnail(*args,True,320)));raw=Image.open(BytesIO(image_thumbnail(*args,False,320)))
   self.assertEqual(raw.size,annotated.size);self.assertEqual(raw.size,(50,40));self.assertEqual(raw.getpixel((30,30)),(21,42,63));self.assertEqual(annotated.getpixel((30,30)),(255,69,230))
   full=Image.open(BytesIO(image_thumbnail(*args[:4],None,*args[5:],True,0)));self.assertEqual(full.size,(120,80))
   small=Image.open(BytesIO(image_thumbnail(*args[:4],None,*args[5:],False,64)));self.assertEqual(small.size,(64,43));self.assertEqual(source.read_bytes(),original)

 def test_image_http_identity_resolution_and_raw_pixels(self):
  import tempfile,json
  from pathlib import Path
  from types import SimpleNamespace
  from unittest.mock import patch
  from io import BytesIO
  from fastapi import FastAPI
  import asyncio
  from urllib.parse import urlencode
  from PIL import Image
  from freemocap_sdk.storage import file_digest
  from skellyclicker_app.label_routes import router
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/'image.png';Image.new('RGB',(120,80),(10,20,30)).save(source)
   projection=root/'projection.jsonl';projection.write_text(json.dumps({'projection':{'mesh_wireframe_segments_xy':[]}})+'\n')
   row={'path':'image.png','sha256':file_digest(source),'bytes':source.stat().st_size,'camera_id':'left','source_frame':1,'moment_id':'moment'}
   context=('label-hash',{'moment:left':row},{('moment','left'):((40,40,True),)},{'cameras':{'left':{'1':{'x':10,'y':10,'width':50,'height':40}}},'width':120,'height':80})
   app=FastAPI();app.include_router(router);query={'project_path':str(root/'project.json'),'label_manifest_sha256':'label-hash','image_id':'moment:left'}
   with patch('skellyclicker_app.label_routes.read_model',return_value=SimpleNamespace(label_result='labels',sample_result='poses',playback_result='playback')),patch('skellyclicker_app.label_routes.thumbnail_fingerprint',return_value=()),patch('skellyclicker_app.label_routes.thumbnail_context',return_value=context),patch('skellyclicker_app.label_routes.projection_offset',return_value=(projection,0,file_digest(projection))):
    async def get_async(path,params):
     messages=[]
     scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'GET','scheme':'http','path':path,'raw_path':path.encode(),'query_string':urlencode(params).encode(),'headers':[],'client':('test',1),'server':('test',80),'root_path':''}
     async def receive():await asyncio.Event().wait()
     async def send(message):messages.append(message)
     await app(scope,receive,send)
     start=next(m for m in messages if m['type']=='http.response.start')
     return SimpleNamespace(status_code=start['status'],headers={k.decode():v.decode() for k,v in start['headers']},content=b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body'))
    client=SimpleNamespace(get=lambda path,params:asyncio.run(get_async(path,params)))
    raw=client.get('/api/labels/image',params={**query,'annotated':False});self.assertEqual(raw.status_code,200);self.assertEqual(raw.content,source.read_bytes());self.assertEqual(raw.headers['x-image-id'],'moment:left')
    annotated=client.get('/api/labels/image',params=query);self.assertEqual(Image.open(BytesIO(annotated.content)).getpixel((40,40)),(255,69,230))
    crop=client.get('/api/labels/thumbnail',params={**query,'annotated':False});self.assertEqual(Image.open(BytesIO(crop.content)).size,(50,40))
    full=client.get('/api/labels/thumbnail',params={**query,'crop':False,'annotated':False,'max_size':64});self.assertEqual(Image.open(BytesIO(full.content)).size,(64,43))
    self.assertEqual(client.get('/api/labels/image',params={**query,'label_manifest_sha256':'stale'}).status_code,409)
    self.assertEqual(client.get('/api/labels/thumbnail',params={**query,'max_size':0}).status_code,422)
