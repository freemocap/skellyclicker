import hashlib,json,tempfile,unittest
from io import BytesIO
from pathlib import Path
from PIL import Image
from skellyclicker_app.training_images import epoch_files,render_preview
class TrainingImageTests(unittest.TestCase):
 def test_saved_epochs_original_crop_annotations_and_identity(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);run=root/'run';data=root/'data';data.mkdir();run.mkdir()
   image=data/'image.png';Image.new('RGB',(160,100),'white').save(image)
   original=image.read_bytes();digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
   (data/'manifest.json').write_text('{}')
   (run/'dataset.json').write_text(json.dumps({'path':'data','manifest_sha256':digest(data/'manifest.json')}))
   row={'image_id':'a','path':'image.png','bytes':image.stat().st_size,'sha256':digest(image),'xy':[[40,40],[60,60]],'valid':[True,True]}
   (run/'worker-request.json').write_text(json.dumps({'images':[row]}))
   for epoch in [2,10]:
    out=run/'previews'/f'epoch-{epoch:06d}';out.mkdir(parents=True)
    (out/'predictions.json').write_text(json.dumps({'samples':[{'image_id':'a','keypoints':[[45,45,.9],[65,65,.9]]}]}))
   (run/'previews'/'epoch-000011').mkdir()
   self.assertEqual([e for e,p in epoch_files(run)],[2,10])
   raw=Image.open(BytesIO(render_preview(run,root,2,'a',False,False,0)))
   annotated=Image.open(BytesIO(render_preview(run,root,2,'a',False,True,0)))
   crop=Image.open(BytesIO(render_preview(run,root,2,'a',True,False,0)))
   self.assertEqual(raw.size,(160,100));self.assertEqual(crop.size,(60,60));self.assertNotEqual(raw.tobytes(),annotated.tobytes())
   self.assertEqual(image.read_bytes(),original)
   with self.assertRaises(ValueError):render_preview(run,root,2,'other',False,False,0)
   image.write_bytes(b'changed')
   with self.assertRaises(ValueError):render_preview(run,root,2,'a',False,False,0)
if __name__=='__main__':unittest.main()
