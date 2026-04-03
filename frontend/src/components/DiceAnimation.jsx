// DiceAnimation.jsx — 占星骰子 3D 动画组件
// 通过 jsDelivr CDN 加载 Three.js（无需 npm install three）
// 暴露 throwDice() 方法供父组件调用

import { useEffect, useRef, useImperativeHandle, forwardRef } from 'react'

const THREE_CDN = 'https://cdn.jsdelivr.net/npm/three@0.157.0/build/three.min.js'

function loadThree() {
  return new Promise((resolve, reject) => {
    if (window.THREE) { resolve(window.THREE); return }
    const s = document.createElement('script')
    s.src = THREE_CDN
    s.onload  = () => resolve(window.THREE)
    s.onerror = () => reject(new Error('THREE load failed'))
    document.head.appendChild(s)
  })
}

// ─── 骰子数据 ───────────────────────────────────────────────────
const FACE_DATA = [
  [['☉','太阳'],['☽','月亮'],['☿','水星'],['♀','金星'],['♂','火星'],['♃','木星'],
   ['♄','土星'],['♅','天王'],['♆','海王'],['♇','冥王'],['⊗','上升'],['☊','北交']],
  [['♈','白羊'],['♉','金牛'],['♊','双子'],['♋','巨蟹'],['♌','狮子'],['♍','处女'],
   ['♎','天秤'],['♏','天蝎'],['♐','射手'],['♑','摩羯'],['♒','水瓶'],['♓','双鱼']],
  [['Ⅰ','一宫'],['Ⅱ','二宫'],['Ⅲ','三宫'],['Ⅳ','四宫'],['Ⅴ','五宫'],['Ⅵ','六宫'],
   ['Ⅶ','七宫'],['Ⅷ','八宫'],['Ⅸ','九宫'],['Ⅹ','十宫'],['Ⅺ','十一宫'],['Ⅻ','十二宫']],
]
const DICE_CONFIG = [
  { baseColor:'#1e0e35', glowColor:'rgba(80,40,120,0.5)', matColor:0x2a1545, emissive:0x1a0a30, edgeColor:0xd4a840, glowLight:0x8855cc },
  { baseColor:'#0a1535', glowColor:'rgba(30,60,120,0.5)', matColor:0x0f2040, emissive:0x0a1530, edgeColor:0xd4a840, glowLight:0x4488cc },
  { baseColor:'#0a2518', glowColor:'rgba(30,100,60,0.5)', matColor:0x0d2a1a, emissive:0x0a200f, edgeColor:0xd4a840, glowLight:0x44aa66 },
]

// ─── 组件 ────────────────────────────────────────────────────────
const DiceAnimation = forwardRef(function DiceAnimation({ onSettled, height = 300 }, ref) {
  const canvasRef   = useRef(null)
  const stateRef    = useRef(null)  // 所有 Three.js 状态存在这里

  // 暴露 throwDice() 给父组件
  useImperativeHandle(ref, () => ({
    throwDice() {
      stateRef.current?.throwDice()
    }
  }))

  useEffect(() => {
    let cancelled = false
    let rafId = null

    loadThree().then(THREE => {
      if (cancelled || !canvasRef.current) return
      initScene(THREE, canvasRef.current, stateRef, onSettled, () => rafId)
    }).catch(err => console.warn('DiceAnimation:', err))

    return () => {
      cancelled = true
      if (rafId) cancelAnimationFrame(rafId)
      // 销毁 Three.js 资源
      const st = stateRef.current
      if (st) {
        st.renderer.dispose()
        st.destroyed = true
      }
      stateRef.current = null
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // canvas resize 响应
  useEffect(() => {
    const st = stateRef.current
    if (!st) return
    const { renderer, camera } = st
    const w = canvasRef.current.clientWidth
    renderer.setSize(w, height)
    camera.aspect = w / height
    camera.updateProjectionMatrix()
  }, [height])

  return (
    <canvas
      ref={canvasRef}
      style={{ display: 'block', width: '100%', height: `${height}px`, borderRadius: '12px' }}
    />
  )
})

export default DiceAnimation

// ─── Three.js 初始化（与 demo 完全一致）────────────────────────────
function initScene(THREE, canvas, stateRef, onSettled) {
  // ── 渲染器 ──
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.3
  if (THREE.SRGBColorSpace) renderer.outputColorSpace = THREE.SRGBColorSpace

  const W = canvas.clientWidth, H = canvas.clientHeight
  renderer.setSize(W, H)

  const scene  = new THREE.Scene()
  scene.background = new THREE.Color(0x080816)
  scene.fog = new THREE.FogExp2(0x080816, 0.028)

  const camera = new THREE.PerspectiveCamera(38, W / H, 0.1, 100)
  camera.position.set(0, 10, 9)
  camera.lookAt(0, 0, 0)

  // ── 环境贴图 ──
  const pmrem = new THREE.PMREMGenerator(renderer)
  pmrem.compileEquirectangularShader()
  const envCv = document.createElement('canvas')
  envCv.width = 512; envCv.height = 256
  const ec = envCv.getContext('2d')
  const grad = ec.createLinearGradient(0, 0, 0, 256)
  grad.addColorStop(0, '#1a1a3e'); grad.addColorStop(0.3, '#0d0d2a')
  grad.addColorStop(0.5, '#2a1a0a'); grad.addColorStop(1, '#050510')
  ec.fillStyle = grad; ec.fillRect(0, 0, 512, 256)
  ec.fillStyle = 'rgba(255,220,160,0.4)'
  ec.beginPath(); ec.arc(256, 50, 80, 0, Math.PI * 2); ec.fill()
  const envTex = new THREE.CanvasTexture(envCv)
  envTex.mapping = THREE.EquirectangularReflectionMapping
  const envMap = pmrem.fromEquirectangular(envTex).texture
  envTex.dispose(); pmrem.dispose()
  scene.environment = envMap

  // ── 灯光 ──
  scene.add(new THREE.AmbientLight(0x445577, 0.8))
  const keyLight = new THREE.DirectionalLight(0xffeedd, 2.5)
  keyLight.position.set(5, 12, 6); keyLight.castShadow = true
  keyLight.shadow.mapSize.set(1024, 1024)
  keyLight.shadow.camera.left = keyLight.shadow.camera.bottom = -8
  keyLight.shadow.camera.right = keyLight.shadow.camera.top = 8
  keyLight.shadow.bias = -0.001
  scene.add(keyLight)
  scene.add(Object.assign(new THREE.DirectionalLight(0x8888cc, 0.9), { position: new THREE.Vector3(-6, 5, -3) }))
  scene.add(Object.assign(new THREE.PointLight(0xffffff, 0.8, 20), { position: new THREE.Vector3(0, 8, 0) }))
  const spotLight = new THREE.SpotLight(0xffeedd, 0, 15, Math.PI / 6, 0.5, 1)
  spotLight.position.set(0, 10, 2); scene.add(spotLight); scene.add(spotLight.target)

  // ── 桌面纹理 ──
  function makeAstroTableTexture(size) {
    const cv = document.createElement('canvas'); cv.width = cv.height = size
    const ctx = cv.getContext('2d'); const cx = size/2, cy = size/2, maxR = size/2
    const bg = ctx.createRadialGradient(cx,cy,0,cx,cy,maxR)
    bg.addColorStop(0,'#111838'); bg.addColorStop(0.4,'#0c1030')
    bg.addColorStop(0.75,'#080c22'); bg.addColorStop(1,'#040614')
    ctx.fillStyle = bg; ctx.fillRect(0,0,size,size)
    for (let si=0; si<600; si++) {
      const sx=Math.random()*size, sy=Math.random()*size
      const d=Math.sqrt((sx-cx)**2+(sy-cy)**2)
      if (d>maxR*0.93) continue
      ctx.fillStyle=`rgba(200,190,240,${Math.random()*0.12})`
      ctx.beginPath(); ctx.arc(sx,sy,Math.random()*1.2+0.3,0,Math.PI*2); ctx.fill()
    }
    ctx.save(); ctx.translate(cx,cy)
    ctx.beginPath(); ctx.arc(0,0,maxR*0.92,0,Math.PI*2)
    ctx.strokeStyle='rgba(190,165,90,0.35)'; ctx.lineWidth=2; ctx.stroke()
    const zodiac=['♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓']
    ctx.font=`bold ${Math.round(size*0.055)}px "Segoe UI Symbol",serif`
    ctx.textAlign='center'; ctx.textBaseline='middle'
    zodiac.forEach((sym,idx) => {
      const a=(idx*Math.PI*2/12)+Math.PI/12-Math.PI/2
      const r=maxR*0.82, tx=Math.cos(a)*r, ty=Math.sin(a)*r
      ctx.save(); ctx.shadowColor='rgba(210,180,90,0.6)'; ctx.shadowBlur=15
      ctx.fillStyle='rgba(210,185,100,0.5)'; ctx.fillText(sym,tx,ty); ctx.restore()
      ctx.fillStyle='rgba(210,185,100,0.35)'; ctx.fillText(sym,tx,ty)
    })
    for (let li=0; li<12; li++) {
      const a=(li*Math.PI*2/12)-Math.PI/2
      ctx.beginPath()
      ctx.moveTo(Math.cos(a)*maxR*0.35, Math.sin(a)*maxR*0.35)
      ctx.lineTo(Math.cos(a)*maxR*0.72, Math.sin(a)*maxR*0.72)
      ctx.strokeStyle='rgba(180,160,90,0.15)'; ctx.lineWidth=1; ctx.stroke()
    }
    ctx.beginPath(); ctx.arc(0,0,maxR*0.72,0,Math.PI*2)
    ctx.strokeStyle='rgba(190,165,90,0.25)'; ctx.lineWidth=1.5; ctx.stroke()
    ctx.beginPath(); ctx.arc(0,0,maxR*0.35,0,Math.PI*2)
    ctx.strokeStyle='rgba(190,165,90,0.2)'; ctx.lineWidth=1; ctx.stroke()
    const houseNums=['Ⅰ','Ⅱ','Ⅲ','Ⅳ','Ⅴ','Ⅵ','Ⅶ','Ⅷ','Ⅸ','Ⅹ','Ⅺ','Ⅻ']
    ctx.font=`bold ${Math.round(size*0.028)}px serif`
    houseNums.forEach((num,idx) => {
      const a=(idx*Math.PI*2/12)+Math.PI/12-Math.PI/2
      const r=maxR*0.54
      ctx.fillStyle='rgba(190,170,110,0.3)'; ctx.fillText(num,Math.cos(a)*r,Math.sin(a)*r)
    })
    function drawTri(r,off,style,w) {
      ctx.beginPath()
      for (let t=0;t<3;t++) { const a=t*Math.PI*2/3+off; t===0?ctx.moveTo(Math.cos(a)*r,Math.sin(a)*r):ctx.lineTo(Math.cos(a)*r,Math.sin(a)*r) }
      ctx.closePath(); ctx.strokeStyle=style; ctx.lineWidth=w; ctx.stroke()
    }
    drawTri(maxR*0.32,-Math.PI/2,'rgba(190,165,90,0.25)',1.5)
    drawTri(maxR*0.32,Math.PI/2,'rgba(190,165,90,0.25)',1.5)
    ctx.beginPath(); ctx.arc(0,0,maxR*0.05,0,Math.PI*2)
    ctx.strokeStyle='rgba(210,185,100,0.3)'; ctx.lineWidth=1.5; ctx.stroke()
    ctx.restore()
    const vigGrad=ctx.createRadialGradient(cx,cy,maxR*0.5,cx,cy,maxR)
    vigGrad.addColorStop(0,'rgba(0,0,0,0)'); vigGrad.addColorStop(0.75,'rgba(0,0,0,0.15)'); vigGrad.addColorStop(1,'rgba(0,0,0,0.6)')
    ctx.fillStyle=vigGrad; ctx.fillRect(0,0,size,size)
    const tex=new THREE.CanvasTexture(cv)
    if (THREE.SRGBColorSpace) tex.colorSpace=THREE.SRGBColorSpace
    tex.anisotropy=renderer.capabilities.getMaxAnisotropy()
    return tex
  }

  const tableMesh = new THREE.Mesh(
    new THREE.CylinderGeometry(6,6,0.15,80),
    new THREE.MeshStandardMaterial({ map: makeAstroTableTexture(1024), roughness:0.85, metalness:0.05, envMap, envMapIntensity:0.08 })
  )
  tableMesh.position.y = -0.075; tableMesh.receiveShadow = true; scene.add(tableMesh)

  // 金边
  const rimGroup = new THREE.Group()
  const rimMat = c => new THREE.MeshStandardMaterial({ color:c, metalness:0.95, roughness:0.15, envMap, envMapIntensity:1.5, emissive:c, emissiveIntensity:0.15 })
  const r1 = new THREE.Mesh(new THREE.TorusGeometry(6,0.018,8,150), rimMat(0xd4a840)); r1.rotation.x=Math.PI/2; rimGroup.add(r1)
  const r2 = new THREE.Mesh(new THREE.TorusGeometry(5.88,0.01,8,150), new THREE.MeshStandardMaterial({ color:0xc9a84c, metalness:0.9, roughness:0.2, transparent:true, opacity:0.5, emissive:0xc9a84c, emissiveIntensity:0.1 })); r2.rotation.x=Math.PI/2; r2.position.y=0.01; rimGroup.add(r2)
  const glowDotMat = new THREE.MeshBasicMaterial({ color:0xd4a840, transparent:true, opacity:0.4 })
  for (let ci=0; ci<12; ci++) {
    const a=ci*Math.PI*2/12, cr=6
    const dot=new THREE.Mesh(new THREE.SphereGeometry(0.025,8,8), glowDotMat); dot.position.set(Math.cos(a)*cr,0.02,Math.sin(a)*cr); rimGroup.add(dot)
    const g=new THREE.Mesh(new THREE.SphereGeometry(0.06,8,8), new THREE.MeshBasicMaterial({color:0xd4a840,transparent:true,opacity:0.1})); g.position.copy(dot.position); rimGroup.add(g)
  }
  scene.add(rimGroup)

  // 星光粒子
  const starPos=[],starColors=[]
  for (let si=0;si<500;si++) {
    const sr=Math.random()*5.6, sa=Math.random()*Math.PI*2
    starPos.push(sr*Math.cos(sa),0.005+Math.random()*0.01,sr*Math.sin(sa))
    const isWarm=Math.random()>0.5
    if (isWarm) starColors.push(0.8+Math.random()*0.2,0.7+Math.random()*0.15,0.3+Math.random()*0.2)
    else starColors.push(0.5+Math.random()*0.2,0.5+Math.random()*0.2,0.8+Math.random()*0.2)
  }
  const sGeo=new THREE.BufferGeometry()
  sGeo.setAttribute('position',new THREE.Float32BufferAttribute(starPos,3))
  sGeo.setAttribute('color',new THREE.Float32BufferAttribute(starColors,3))
  scene.add(new THREE.Points(sGeo,new THREE.PointsMaterial({size:0.02,transparent:true,opacity:0.3,vertexColors:true,sizeAttenuation:true})))

  // ── 自定义十二面体（带 UV 每面独立材质）──
  function createDodecahedronWithUV(radius) {
    const baseGeo = new THREE.DodecahedronGeometry(radius,0)
    const posAttr = baseGeo.getAttribute('position')
    const normalAttr = baseGeo.getAttribute('normal')
    const triCount = posAttr.count/3
    const faces=[]; const eps=0.01
    for (let t=0;t<triCount;t++) {
      const i0=t*3; const nx=normalAttr.getX(i0),ny=normalAttr.getY(i0),nz=normalAttr.getZ(i0)
      let found=false
      for (let fi=0;fi<faces.length;fi++) {
        const fn=faces[fi].normal
        if (Math.abs(fn.x-nx)<eps&&Math.abs(fn.y-ny)<eps&&Math.abs(fn.z-nz)<eps){ faces[fi].triangles.push(t); found=true; break }
      }
      if (!found) faces.push({normal:new THREE.Vector3(nx,ny,nz),triangles:[t]})
    }
    const vertices=[],normals=[],uvs=[],groups=[]
    let vertexOffset=0
    faces.forEach((face,faceIndex) => {
      const faceNormal=face.normal; const center=new THREE.Vector3(); const allVerts=[]
      face.triangles.forEach(triIdx => { for (let v=0;v<3;v++) { const vi=triIdx*3+v; allVerts.push(new THREE.Vector3(posAttr.getX(vi),posAttr.getY(vi),posAttr.getZ(vi))); center.add(allVerts[allVerts.length-1]) } })
      center.divideScalar(allVerts.length)
      const uAxis=new THREE.Vector3().subVectors(allVerts[0],center); uAxis.sub(faceNormal.clone().multiplyScalar(uAxis.dot(faceNormal))); uAxis.normalize()
      const vAxis=new THREE.Vector3().crossVectors(faceNormal,uAxis).normalize()
      const coords2d=allVerts.map(v => { const rel=new THREE.Vector3().subVectors(v,center); return{u:rel.dot(uAxis),v:rel.dot(vAxis)} })
      let maxRad=0; coords2d.forEach(c => { const r=Math.sqrt(c.u*c.u+c.v*c.v); if(r>maxRad)maxRad=r })
      const scale=0.45/maxRad; const groupStart=vertexOffset
      face.triangles.forEach(triIdx => {
        for (let v=0;v<3;v++) {
          const vi=triIdx*3+v; const vx=posAttr.getX(vi),vy=posAttr.getY(vi),vz=posAttr.getZ(vi)
          vertices.push(vx,vy,vz); normals.push(faceNormal.x,faceNormal.y,faceNormal.z)
          const rel=new THREE.Vector3(vx-center.x,vy-center.y,vz-center.z)
          uvs.push(rel.dot(uAxis)*scale+0.5, rel.dot(vAxis)*scale+0.5)
          vertexOffset++
        }
      })
      groups.push({start:groupStart,count:face.triangles.length*3,materialIndex:faceIndex})
    })
    const geo=new THREE.BufferGeometry()
    geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3))
    geo.setAttribute('normal',new THREE.Float32BufferAttribute(normals,3))
    geo.setAttribute('uv',new THREE.Float32BufferAttribute(uvs,2))
    groups.forEach(g => geo.addGroup(g.start,g.count,g.materialIndex))
    return{geometry:geo,faceNormals:faces.map(f=>f.normal)}
  }

  function makeFaceTexture(symbol,label,baseColor,glowColor) {
    const size=512; const cv=document.createElement('canvas'); cv.width=cv.height=size
    const ctx=cv.getContext('2d'); const cx=size/2,cy=size/2
    ctx.fillStyle=baseColor; ctx.fillRect(0,0,size,size)
    ctx.beginPath()
    for (let pi=0;pi<5;pi++) { const a=pi*2*Math.PI/5-Math.PI/2; const px=cx+Math.cos(a)*size*0.42,py=cy+Math.sin(a)*size*0.42; pi===0?ctx.moveTo(px,py):ctx.lineTo(px,py) }
    ctx.closePath()
    const grad=ctx.createRadialGradient(cx,cy,0,cx,cy,size*0.4); grad.addColorStop(0,glowColor); grad.addColorStop(1,baseColor)
    ctx.fillStyle=grad; ctx.fill(); ctx.strokeStyle='rgba(201,168,76,0.5)'; ctx.lineWidth=3; ctx.stroke()
    ctx.save(); ctx.shadowColor='#d4a840'; ctx.shadowBlur=20; ctx.fillStyle='#f0d870'
    ctx.textAlign='center'; ctx.textBaseline='middle'
    ctx.font=`bold ${Math.round(size*0.32)}px "Segoe UI Symbol","Apple Color Emoji","Noto Sans Symbols",serif`
    ctx.fillText(symbol,cx,cy-size*0.06); ctx.fillText(symbol,cx,cy-size*0.06); ctx.restore()
    ctx.fillStyle='rgba(220,200,140,0.9)'
    ctx.font=`600 ${Math.round(size*0.1)}px "Segoe UI","PingFang SC","Microsoft YaHei",sans-serif`
    ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.fillText(label,cx,cy+size*0.18)
    const tex=new THREE.CanvasTexture(cv)
    if (THREE.SRGBColorSpace) tex.colorSpace=THREE.SRGBColorSpace
    tex.anisotropy=renderer.capabilities.getMaxAnisotropy()
    return tex
  }

  const R=0.45
  const {geometry:diceGeo, faceNormals:actualFaceNormals}=createDodecahedronWithUV(R)
  const meshes=[]; const diceGroups=[]
  DICE_CONFIG.forEach((config,dieIdx) => {
    const group=new THREE.Group()
    const materials=[]
    for (let fi=0;fi<12;fi++) {
      const fd=FACE_DATA[dieIdx][fi]
      const tex=makeFaceTexture(fd[0],fd[1],config.baseColor,config.glowColor)
      materials.push(new THREE.MeshPhysicalMaterial({ map:tex, roughness:0.25, metalness:0.08, clearcoat:0.7, clearcoatRoughness:0.2, reflectivity:0.5, emissive:config.emissive, emissiveIntensity:0.15, envMap, envMapIntensity:1.2, flatShading:true }))
    }
    const bodyMesh=new THREE.Mesh(diceGeo.clone(),materials); bodyMesh.castShadow=true; bodyMesh.receiveShadow=true; group.add(bodyMesh)
    const edgesGeo=new THREE.EdgesGeometry(new THREE.DodecahedronGeometry(R*1.001,0),8)
    const edgeMesh=new THREE.LineSegments(edgesGeo,new THREE.LineBasicMaterial({color:config.edgeColor,transparent:true,opacity:0.8})); group.add(edgeMesh)
    scene.add(group); meshes.push(group); diceGroups.push(group)
    group.userData={bodyMesh,materials,edgeMesh,config,glowIntensity:0,targetGlow:0}
  })

  // ── 物理 ──
  const GRAVITY=22,FLOOR=R,WALL=5.2,BOUNCE=0.38,FRICTION=0.82,LDAMP=0.994,ADAMP=0.992
  const SETTLE_DAMP=0.97,ROLL_FRICTION=0.0012,SPIN_TRANSFER=0.6
  const phys=meshes.map(()=>({pos:new THREE.Vector3(0,R,0),vel:new THREE.Vector3(),angVel:new THREE.Vector3(),quat:new THREE.Quaternion(),onFloor:false,settled:false,bounceCount:0}))
  const initPositions=[new THREE.Vector3(-1.6,R,0),new THREE.Vector3(0,R,0),new THREE.Vector3(1.6,R,0)]
  const initRotations=[new THREE.Euler(0.3,0.5,0.1),new THREE.Euler(0.2,-0.3,0.15),new THREE.Euler(-0.1,0.4,-0.2)]
  phys.forEach((p,i)=>{ p.pos.copy(initPositions[i]); p.quat.setFromEuler(initRotations[i]) })

  function getTopFaceIndex(dieIndex) {
    const q=phys[dieIndex].quat; const up=new THREE.Vector3(0,1,0)
    let bestDot=-Infinity,bestIdx=0
    for (let fi=0;fi<actualFaceNormals.length;fi++) {
      const n=actualFaceNormals[fi].clone().applyQuaternion(q); const d=n.dot(up)
      if (d>bestDot){bestDot=d;bestIdx=fi}
    }
    return bestIdx
  }

  let rolling=false,checkT=null,throwTime=0,cameraShake=0

  function throwDice() {
    if (rolling) return
    rolling=true; diceGroups.forEach(g=>{g.userData.targetGlow=0}); spotLight.intensity=0
    cameraShake=0.3; throwTime=performance.now()
    const startX=[-1.0,0.5,1.8]
    phys.forEach((p,i)=>{
      p.settled=false; p.bounceCount=0; p.onFloor=false
      p.pos.set(startX[i]+(Math.random()-0.5)*0.8, 4+Math.random()*2.5, -3+(Math.random()-0.5)*1)
      p.vel.set((Math.random()-0.5)*6, 0.5+Math.random()*1.5, 3+Math.random()*4)
      p.angVel.set((Math.random()-0.5)*40,(Math.random()-0.5)*40,(Math.random()-0.5)*40)
      p.quat.set(Math.random()-0.5,Math.random()-0.5,Math.random()-0.5,Math.random()-0.5).normalize()
    })
    clearInterval(checkT)
    checkT=setInterval(checkSettled,200)
  }

  function checkSettled() {
    if (performance.now()-throwTime<2200) return
    const done=phys.every(p=>p.vel.lengthSq()<0.01&&p.angVel.lengthSq()<0.01&&p.pos.y<=FLOOR+0.05)
    if (!done) return
    clearInterval(checkT)
    const faceIndices=[0,1,2].map(i=>getTopFaceIndex(i))
    diceGroups.forEach(g=>{g.userData.targetGlow=1}); spotLight.intensity=3
    rolling=false
    onSettled?.(faceIndices)
  }

  // 物理步进
  const _ax=new THREE.Vector3(),_dq=new THREE.Quaternion(),_cross=new THREE.Vector3()
  function step(dt) {
    const dtc=Math.min(dt,0.033); if(dtc<=0)return
    const subSteps=3,subDt=dtc/subSteps
    for (let s=0;s<subSteps;s++) {
      phys.forEach((p,i)=>{
        if(p.settled)return
        p.vel.y-=GRAVITY*subDt; p.pos.addScaledVector(p.vel,subDt)
        if(p.pos.y<=FLOOR){
          p.pos.y=FLOOR
          if(p.vel.y<-0.4){
            p.vel.y*=-BOUNCE; p.bounceCount++
            const impSpeed=Math.abs(p.vel.y)
            p.vel.x+=(Math.random()-0.5)*impSpeed*0.5; p.vel.z+=(Math.random()-0.5)*impSpeed*0.5
            const hSpeed=Math.sqrt(p.vel.x**2+p.vel.z**2)
            if(hSpeed>0.1){
              _cross.set(-p.vel.z,0,p.vel.x).normalize()
              p.angVel.x+=_cross.x*hSpeed*SPIN_TRANSFER*(3+Math.random()*4)
              p.angVel.y+=(Math.random()-0.5)*hSpeed*2
              p.angVel.z+=_cross.z*hSpeed*SPIN_TRANSFER*(3+Math.random()*4)
            }
            const decay=Math.max(0.2,1-p.bounceCount*0.12)
            p.vel.x*=FRICTION*decay; p.vel.z*=FRICTION*decay; p.angVel.multiplyScalar(0.85*decay)
            if(p.bounceCount<=3)cameraShake=Math.max(cameraShake,0.08/p.bounceCount)
          } else if(p.vel.y<0) {
            p.vel.y=0; p.onFloor=true
            const gSpeed=Math.sqrt(p.vel.x**2+p.vel.z**2)
            if(gSpeed>0.05){
              const rollAS=gSpeed/R; const moveDir=new THREE.Vector3(p.vel.x,0,p.vel.z).normalize()
              _cross.set(-moveDir.z,0,moveDir.x)
              p.angVel.lerp(new THREE.Vector3(_cross.x*rollAS,p.angVel.y*0.95,_cross.z*rollAS),subDt*3)
              p.vel.x*=(1-ROLL_FRICTION); p.vel.z*=(1-ROLL_FRICTION)
            } else {
              p.vel.x*=SETTLE_DAMP; p.vel.z*=SETTLE_DAMP; p.angVel.multiplyScalar(SETTLE_DAMP)
              if(gSpeed<0.02&&p.angVel.length()>0.1&&p.angVel.length()<2){
                const down=new THREE.Vector3(0,-1,0); let bd=-Infinity,bn=null
                for(let fi=0;fi<actualFaceNormals.length;fi++){const n=actualFaceNormals[fi].clone().applyQuaternion(p.quat);const d=n.dot(down);if(d>bd){bd=d;bn=n}}
                if(bn&&bd>0.8){const cor=new THREE.Vector3().crossVectors(bn,down);p.angVel.addScaledVector(cor,subDt*8);p.angVel.multiplyScalar(0.92)}
              }
            }
          }
        }
        const hr=Math.sqrt(p.pos.x**2+p.pos.z**2)
        if(hr>WALL){const wnx=p.pos.x/hr,wnz=p.pos.z/hr;p.pos.x=wnx*WALL;p.pos.z=wnz*WALL;const vd=p.vel.x*wnx+p.vel.z*wnz;if(vd>0){p.vel.x-=(1+BOUNCE)*vd*wnx;p.vel.z-=(1+BOUNCE)*vd*wnz;p.angVel.y+=vd*3*(Math.random()>0.5?1:-1)}}
        for(let j=i+1;j<phys.length;j++){
          const q=phys[j]; if(q.settled)continue
          const dx=p.pos.x-q.pos.x,dy=p.pos.y-q.pos.y,dz=p.pos.z-q.pos.z
          const d=Math.sqrt(dx**2+dy**2+dz**2),mn=R*2.15
          if(d<mn&&d>0.001){
            const cnx=dx/d,cny=dy/d,cnz=dz/d,ov=(mn-d)*0.52
            p.pos.x+=cnx*ov;p.pos.y+=cny*ov;p.pos.z+=cnz*ov;q.pos.x-=cnx*ov;q.pos.y-=cny*ov;q.pos.z-=cnz*ov
            const rv=(p.vel.x-q.vel.x)*cnx+(p.vel.y-q.vel.y)*cny+(p.vel.z-q.vel.z)*cnz
            if(rv<0){const imp=rv*0.9;p.vel.x-=imp*cnx;p.vel.y-=imp*cny;p.vel.z-=imp*cnz;q.vel.x+=imp*cnx;q.vel.y+=imp*cny;q.vel.z+=imp*cnz;p.angVel.x+=(Math.random()-0.5)*5;p.angVel.z+=(Math.random()-0.5)*5;q.angVel.x+=(Math.random()-0.5)*5;q.angVel.z+=(Math.random()-0.5)*5}
          }
        }
        p.vel.multiplyScalar(LDAMP); p.angVel.multiplyScalar(ADAMP)
        if(p.onFloor&&p.vel.lengthSq()<0.0003&&p.angVel.lengthSq()<0.003){p.vel.set(0,0,0);p.angVel.set(0,0,0);p.settled=true}
        const spd=p.angVel.length()
        if(spd>0.0001){_ax.copy(p.angVel).divideScalar(spd);_dq.setFromAxisAngle(_ax,spd*subDt);p.quat.premultiply(_dq).normalize()}
      })
    }
    phys.forEach((p,i)=>{meshes[i].position.copy(p.pos);meshes[i].quaternion.copy(p.quat)})
  }

  // 相机抖动 & 空闲动画
  const baseCamPos=new THREE.Vector3(0,10,9)
  function updateCamera(){
    if(cameraShake>0.001){cameraShake*=0.92;camera.position.set(baseCamPos.x+(Math.random()-0.5)*cameraShake,baseCamPos.y+(Math.random()-0.5)*cameraShake,baseCamPos.z)}
    else{camera.position.lerp(baseCamPos,0.05)}
    camera.lookAt(0,0,0)
  }
  function updateDiceVisuals(time,dt){
    diceGroups.forEach((g,i)=>{
      const ud=g.userData; ud.glowIntensity+=(ud.targetGlow-ud.glowIntensity)*dt*3
      if(ud.glowIntensity>0.01){const pulse=0.5+0.5*Math.sin(time*2+i*2.1);ud.materials.forEach(m=>{m.emissiveIntensity=0.15+ud.glowIntensity*(0.4+pulse*0.3)});ud.edgeMesh.material.opacity=0.8+ud.glowIntensity*0.2*pulse}
    })
  }
  function idleAnimation(time){
    if(rolling)return
    phys.forEach((p,i)=>{
      meshes[i].position.y=p.pos.y+Math.sin(time*1.2+i*2)*0.018
      meshes[i].position.x=p.pos.x+Math.sin(time*0.8+i*1.5)*0.008
      meshes[i].rotation.y+=0.003
    })
  }
  function updateCrystalGlow(time){
    rimGroup.children.forEach((child,idx)=>{
      if(child.material?.transparent&&child.geometry?.type==='SphereGeometry'){
        const phase=time*1.5+idx*0.52; const big=child.geometry.parameters.radius>0.04
        child.material.opacity=(big?0.06:0.3)+(big?0.08:0.15)*Math.sin(phase)
        if(big)child.scale.setScalar(1+0.2*Math.sin(phase))
      }
    })
  }

  // 存入 stateRef
  stateRef.current = { renderer, camera, throwDice }

  // 主循环
  let last=performance.now()
  ;(function loop(){
    if(stateRef.current?.destroyed)return
    requestAnimationFrame(loop)
    const now=performance.now(); let dt=(now-last)/1000; last=now
    if(dt>0.1)dt=0.033; const time=now/1000
    if(rolling)step(dt)
    idleAnimation(time); updateCamera(); updateDiceVisuals(time,dt); updateCrystalGlow(time)
    renderer.render(scene,camera)
  })()
}
