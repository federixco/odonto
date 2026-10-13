import test from 'node:test';
import assert from 'node:assert/strict';
import { parseMesh } from '../mesh-parser.js';

const limits = { meshBytes: 100000, vertices: 1000 };
const bytes = text => new TextEncoder().encode(text).buffer;
const stl = 'solid test\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid test';
test('STL ASCII', () => { const { geometry, faces } = parseMesh(bytes(stl), 'STL', limits); assert.equal(geometry.attributes.position.count,3); assert.ok(faces); geometry.dispose(); });
test('STL binario', () => {
  const a = new ArrayBuffer(134), v = new DataView(a); v.setUint32(80,1,true);
  v.setFloat32(84+12+12,1,true); v.setFloat32(84+12+24+4,1,true);
  const {geometry} = parseMesh(a,'STL',limits); assert.equal(geometry.attributes.position.count,3); geometry.dispose();
});
test('PLY con color, malla y nube de puntos', () => {
  for (const face of ['', 'element face 1\nproperty list uchar int vertex_indices\n']) {
    const a = bytes(`ply\nformat ascii 1.0\nelement vertex 3\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\n${face}end_header\n0 0 0 255 0 0\n1 0 0 0 255 0\n0 1 0 0 0 255\n${face ? '3 0 1 2' : ''}`);
    const { geometry, faces } = parseMesh(a, 'PLY', limits);
    assert.equal(faces, !!face); assert.ok(geometry.hasAttribute('color')); geometry.dispose();
  }
});
test('límites, truncamiento y valores no finitos', () => {
  assert.throws(() => parseMesh(bytes(stl),'STL',{...limits,vertices:2}), /memoria/);
  assert.throws(() => parseMesh(bytes('esto no es un archivo válido'),'STL',limits));
  assert.throws(() => parseMesh(bytes(stl.replace('endsolid test','')),'STL',limits), /formato/);
  assert.throws(() => parseMesh(bytes('ply\nformat ascii 1.0\nelement vertex 999999999\nend_header\n'),'PLY',limits), /memoria/);
});

test('PLY binario little/big endian conserva geometría y colores', () => {
  for (const little of [true, false]) {
    const header = new TextEncoder().encode(`ply\nformat binary_${little ? 'little' : 'big'}_endian 1.0\nelement vertex 3\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nelement face 1\nproperty list uchar int vertex_indices\nend_header\n`);
    const buffer = new ArrayBuffer(header.length + 3*15 + 13);
    new Uint8Array(buffer).set(header);
    const view = new DataView(buffer);
    let offset = header.length;
    for (const [x,y,z,r,g,b] of [[0,0,0,255,0,0],[1,0,0,0,255,0],[0,1,0,0,0,255]]) {
      for (const value of [x,y,z]) { view.setFloat32(offset,value,little); offset+=4; }
      for (const value of [r,g,b]) view.setUint8(offset++,value);
    }
    view.setUint8(offset++,3);
    for (const value of [0,1,2]) { view.setInt32(offset,value,little); offset+=4; }
    const {geometry,faces} = parseMesh(buffer,'PLY',limits);
    assert.ok(faces); assert.equal(geometry.attributes.position.count,3);
    assert.equal(geometry.attributes.color.getX(0),1);
    assert.equal(geometry.attributes.color.getY(0),0);
    geometry.dispose();
    assert.throws(()=>parseMesh(buffer.slice(0,-1),'PLY',limits), /formato/);
  }
});
