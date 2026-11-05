// Reused authored mesh projector from benchy/automation/geometry/pose_geometry.js.
// Original algorithm and tolerances retained; asset injection remains generic.
/* Shared dense STL geometry. Camera X right, Y down, Z forward; millimeters and right-handed degrees. */
globalThis.PoseGeometry = (() => {
  'use strict';
  const A = globalThis.PoseGeometryAsset;
  if (!A) throw new Error('Load geometry.js before pose_geometry.js');
  const V=A.vertices,T=A.triangles,E=A.edges,N=A.normals,C=A.centers;
  const stack=new Int32Array(128),facing=new Uint8Array(T.length/3);
  const projectedVertices=new Float64Array(V.length/3*2),vertexDepth=new Float64Array(V.length/3);
  const zero={translation_mm:[0,0,0],rotation_deg:[0,0,0]};
  function multiply(a,b){const r=Array.from({length:3},()=>[0,0,0]);for(let i=0;i<3;i++)for(let j=0;j<3;j++)for(let k=0;k<3;k++)r[i][j]+=a[i][k]*b[k][j];return r;}
  function poseFromOffsets(candidate, offsets=zero){
    const translation=offsets.translation_mm||zero.translation_mm,angles=offsets.rotation_deg||zero.rotation_deg;
    if(translation.length!==3||angles.length!==3||![...translation,...angles].every(Number.isFinite))throw new TypeError('Three finite translation millimeters and rotation degrees required');
    const [x,y,z]=angles.map(v=>v*Math.PI/180),cx=Math.cos(x),sx=Math.sin(x),cy=Math.cos(y),sy=Math.sin(y),cz=Math.cos(z),sz=Math.sin(z);
    const rx=[[1,0,0],[0,cx,-sx],[0,sx,cx]],ry=[[cy,0,sy],[0,1,0],[-sy,0,cy]],rz=[[cz,-sz,0],[sz,cz,0],[0,0,1]];
    return {rotation_object_to_camera:multiply(multiply(multiply(rz,ry),rx),candidate.rotation_object_to_camera),translation_object_to_camera_mm:candidate.translation_object_to_camera_mm.map((v,i)=>v+translation[i])};
  }
  function pointProjection(x,y,z,K,d){
    x/=z;y/=z;const r2=x*x+y*y,r4=r2*r2,r6=r4*r2;
    const radial=(1+(d[0]||0)*r2+(d[1]||0)*r4+(d[4]||0)*r6)/(1+(d[5]||0)*r2+(d[6]||0)*r4+(d[7]||0)*r6);
    const xd=x*radial+2*(d[2]||0)*x*y+(d[3]||0)*(r2+2*x*x),yd=y*radial+(d[2]||0)*(r2+2*y*y)+2*(d[3]||0)*x*y;
    return [K[0][0]*xd+K[0][2],K[1][1]*yd+K[1][2]];
  }
  function projectPoints(candidate,pose,points=A.featurePositions){
    const R=pose.rotation_object_to_camera,t=pose.translation_object_to_camera_mm,K=candidate.camera_intrinsics,d=candidate.distortion;
    if(![0,4,5,8].includes(d.length))throw new RangeError('Only OpenCV zero/4/5/8 coefficient distortion is supported');
    const result=[];
    for(let i=0;i<points.length;i+=3){const x=points[i],y=points[i+1],z=points[i+2];const px=R[0][0]*x+R[0][1]*y+R[0][2]*z+t[0],py=R[1][0]*x+R[1][1]*y+R[1][2]*z+t[1],pz=R[2][0]*x+R[2][1]*y+R[2][2]*z+t[2];if(!(pz>1e-6))throw new RangeError('Edited mesh crosses or lies behind the camera');result.push(pointProjection(px,py,pz,K,d));}
    return result;
  }
  // A segment query stops before its surface endpoint, matching Forge's explicit millimeter tolerance.
  function visible(ox,oy,oz,px,py,pz,tolerance){
    const dx=px-ox,dy=py-oy,dz=pz-oz,length=Math.hypot(dx,dy,dz);if(length<=tolerance)return false;
    const maxT=1-tolerance/length,B=A.bvhBounds,Q=A.bvhNodes;let count=1;stack[0]=0;
    while(count){const node=stack[--count],b=node*6;let near=0,far=maxT;
      for(let axis=0;axis<3;axis++){const o=axis===0?ox:axis===1?oy:oz,d=axis===0?dx:axis===1?dy:dz;if(Math.abs(d)<1e-15){if(o<B[b+axis]||o>B[b+axis+3]){far=-1;break;}}else{let a=(B[b+axis]-o)/d,c=(B[b+axis+3]-o)/d;if(a>c){const swap=a;a=c;c=swap;}near=Math.max(near,a);far=Math.min(far,c);if(far<near)break;}}
      if(far<near)continue;
      const q=node*4;if(Q[q]>=0){stack[count++]=Q[q];stack[count++]=Q[q+1];continue;}
      for(let j=Q[q+2],end=j+Q[q+3];j<end;j++){
        const tri=A.triangleOrder[j]*3,ia=T[tri]*3,ib=T[tri+1]*3,ic=T[tri+2]*3;
        const e1x=V[ib]-V[ia],e1y=V[ib+1]-V[ia+1],e1z=V[ib+2]-V[ia+2],e2x=V[ic]-V[ia],e2y=V[ic+1]-V[ia+1],e2z=V[ic+2]-V[ia+2];
        const hx=dy*e2z-dz*e2y,hy=dz*e2x-dx*e2z,hz=dx*e2y-dy*e2x,det=e1x*hx+e1y*hy+e1z*hz;if(Math.abs(det)<1e-14)continue;
        const inv=1/det,sx=ox-V[ia],sy=oy-V[ia+1],sz=oz-V[ia+2],u=(sx*hx+sy*hy+sz*hz)*inv;if(u< -1e-10||u>1+1e-10)continue;
        const qx=sy*e1z-sz*e1y,qy=sz*e1x-sx*e1z,qz=sx*e1y-sy*e1x,v=(dx*qx+dy*qy+dz*qz)*inv;if(v< -1e-10||u+v>1+1e-10)continue;
        const distance=(e2x*qx+e2y*qy+e2z*qz)*inv;if(distance>1e-10&&distance<maxT)return false;
      }
    }
    return true;
  }
  function project(candidate,edit=zero){
    const started=performance.now();const pose=edit.rotation_object_to_camera?edit:poseFromOffsets(candidate,edit);
    const R=pose.rotation_object_to_camera,t=pose.translation_object_to_camera_mm,K=candidate.camera_intrinsics,d=candidate.distortion;
    if(candidate.feature_names.length!==A.metadata.feature_names.length||candidate.feature_names.some((v,i)=>v!==A.metadata.feature_names[i]))throw new Error('Feature identities do not match shared mesh geometry');
    const xy=projectPoints(candidate,pose),camera=[-(R[0][0]*t[0]+R[1][0]*t[1]+R[2][0]*t[2]),-(R[0][1]*t[0]+R[1][1]*t[1]+R[2][1]*t[2]),-(R[0][2]*t[0]+R[1][2]*t[1]+R[2][2]*t[2])];
    let minimumDepth=Infinity;
    for(let i=0;i<V.length;i+=3){const x=V[i],y=V[i+1],z=V[i+2],cx=R[0][0]*x+R[0][1]*y+R[0][2]*z+t[0],cy=R[1][0]*x+R[1][1]*y+R[1][2]*z+t[1],cz=R[2][0]*x+R[2][1]*y+R[2][2]*z+t[2];minimumDepth=Math.min(minimumDepth,cz);if(!(cz>1e-6))throw new RangeError('Edited mesh crosses or lies behind the camera');const p=pointProjection(cx,cy,cz,K,d),index=i/3;projectedVertices[index*2]=p[0];projectedVertices[index*2+1]=p[1];vertexDepth[index]=cz;}
    for(let i=0;i<facing.length;i++){const j=i*3;facing[i]=(N[j]*(camera[0]-C[j])+N[j+1]*(camera[1]-C[j+1])+N[j+2]*(camera[2]-C[j+2]))>0?1:0;}
    const visibility=[];for(let i=0;i<A.featurePositions.length;i+=3)visibility.push(visible(...camera,A.featurePositions[i],A.featurePositions[i+1],A.featurePositions[i+2],.02));
    const segments=[],edgeIds=[];
    for(let e=0;e<E.length/2;e++){
      if(!A.creases[e]&&facing[A.firstFaces[e]]===facing[A.lastFaces[e]])continue;
      const ia=E[e*2],ib=E[e*2+1],a=ia*3,b=ib*3;
      if(!visible(...camera,(V[a]+V[b])*.5,(V[a+1]+V[b+1])*.5,(V[a+2]+V[b+2])*.5,.03))continue;
      segments.push([[projectedVertices[ia*2],projectedVertices[ia*2+1]],[projectedVertices[ib*2],projectedVertices[ib*2+1]]]);edgeIds.push(e);
    }
    return {...pose,keypoints_xy:xy,visibility,mesh_wireframe_segments_xy:segments,mesh_edge_ids:edgeIds,positive_depth:true,coordinate_convention:'opencv_integer_pixel_centres',diagnostics:{elapsed_ms:performance.now()-started,minimum_mesh_depth_mm:minimumDepth,visible_edge_count:segments.length,visibility_semantics:'Recomputed mesh self-visibility; external occlusion unknown'}};
  }
  return Object.freeze({poseFromOffsets,project,projectPoints,metadata:A.metadata});
})();

