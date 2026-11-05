// Project original-STL poses through the recovered dense mesh/BVH projector.
// Input assets are typed binary data, never executable project files.
const fs=require('node:fs'),path=require('node:path'),readline=require('node:readline');
const request=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const bytes=fs.readFileSync(request.asset),length=bytes.readUInt32LE(0);
const header=JSON.parse(bytes.subarray(4,4+length).toString('utf8'));
const base=(4+length+7)&~7,types={Float64Array,Float32Array,Int32Array,Uint32Array,Uint8Array};
const owned=Uint8Array.from(bytes).buffer;
const asset={metadata:{feature_names:request.names}};
for(const [key,v] of Object.entries(header.arrays)){
 const Type=types[v.type];if(!Type)throw Error('Unsupported dense array type');
 asset[key]=new Type(owned,base+v.offset,v.length);
}
asset.featurePositions=Float64Array.from(request.points_mm.flatMap(p=>p.map((v,i)=>v-request.origin_mm[i])));
globalThis.PoseGeometryAsset=asset;require('./authored_outline.cjs');
const lines=readline.createInterface({input:fs.createReadStream(request.poses),crlfDelay:Infinity});
const output=fs.createWriteStream(request.output);
(async()=>{for await(const line of lines){
 const row=JSON.parse(line),T=row.pose;
 if(!T){output.write(JSON.stringify({...row,projection:null})+'\n');continue;}
 const R=T.slice(0,3).map(r=>r.slice(0,3));
 // Asset vertices are original STL millimeters minus origin; FP translation is meters.
 const t=R.map((r,i)=>T[i][3]*1000+r.reduce((s,v,j)=>s+v*request.origin_mm[j],0));
 const projection=PoseGeometry.project({rotation_object_to_camera:R,translation_object_to_camera_mm:t,
  camera_intrinsics:request.cameras[row.camera],distortion:[],feature_names:request.names});
 if(!output.write(JSON.stringify({source_frame:row.source_frame,camera:row.camera,projection})+'\n'))
  await new Promise(resolve=>output.once('drain',resolve));
}output.end();})();
