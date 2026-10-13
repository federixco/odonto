import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js';

const scalarSizes = { char:1, int8:1, uchar:1, uint8:1, short:2, int16:2, ushort:2, uint16:2, int:4, int32:4, uint:4, uint32:4, float:4, float32:4, double:8, float64:8 };

function validatePly(buffer, head, limits) {
  const end = head.match(/end_header\r?\n/);
  if (!head.startsWith('ply') || !end) throw new Error('formato');
  const header = head.slice(0, end.index);
  const format = header.match(/format (\S+) 1\.0/)?.[1];
  if (!['ascii', 'binary_little_endian', 'binary_big_endian'].includes(format)) throw new Error('formato');
  let section, vertices = 0, faces = 0, stride = 0, countType, indexType;
  const vertexProps = [];
  for (const line of header.split(/\r?\n/)) {
    const p = line.trim().split(/\s+/);
    if (p[0] === 'element') {
      section = p[1];
      if (!['vertex', 'face'].includes(section)) throw new Error('formato');
      if (section === 'vertex') vertices = Number(p[2]); else faces = Number(p[2]);
    } else if (p[0] === 'property') {
      if (section === 'vertex') {
        if (!scalarSizes[p[1]]) throw new Error('formato');
        stride += scalarSizes[p[1]]; vertexProps.push(p[2]);
      } else {
        if (p[1] !== 'list' || !['vertex_indices','vertex_index'].includes(p[4]) || countType || !scalarSizes[p[2]] || !scalarSizes[p[3]]) throw new Error('formato');
        countType=p[2]; indexType=p[3];
      }
    }
  }
  if (!Number.isSafeInteger(vertices) || vertices < 1 || vertices > limits.vertices || !Number.isSafeInteger(faces) || faces < 0 || faces * 3 > limits.vertices) throw new Error('memoria');
  if (!['x','y','z'].every(p => vertexProps.includes(p)) || (faces && !countType)) throw new Error('formato');
  let triangles = 0;
  if (format === 'ascii') {
    const lines = new TextDecoder().decode(buffer).slice(end.index+end[0].length).trim().split(/\r?\n/);
    if (lines.length !== vertices+faces) throw new Error('formato');
    for (let i=0; i<vertices; i++) {
      const values=lines[i].trim().split(/\s+/);
      if (values.length !== vertexProps.length || values.some(v=>!Number.isFinite(Number(v)))) throw new Error('formato');
    }
    for (const line of lines.slice(vertices)) {
      const values=line.trim().split(/\s+/).map(Number), count=values[0];
      if (![3,4].includes(count) || values.length!==count+1 || values.slice(1).some(v=>!Number.isSafeInteger(v)||v<0||v>=vertices)) throw new Error('formato');
      triangles += count-2;
    }
  } else {
    let offset = new TextEncoder().encode(head.slice(0,end.index+end[0].length)).byteLength + vertices*stride;
    const view = new DataView(buffer), little = format==='binary_little_endian';
    const readInteger = type => {
      const size=scalarSizes[type];
      if (![1,2,4].includes(size) || /float|double/.test(type) || offset+size>buffer.byteLength) throw new Error('formato');
      const signed=!type.startsWith('u');
      const value=view[`get${signed?'Int':'Uint'}${size*8}`](offset,little); offset+=size; return value;
    };
    if (offset > buffer.byteLength) throw new Error('formato');
    for (let f=0; f<faces; f++) {
      const count=readInteger(countType);
      if (![3,4].includes(count)) throw new Error('formato');
      triangles+=count-2;
      for (let n=0;n<count;n++) { const v=readInteger(indexType); if(v<0||v>=vertices) throw new Error('formato'); }
    }
    if (offset!==buffer.byteLength) throw new Error('formato');
  }
  if (triangles*3>limits.vertices) throw new Error('memoria');
  return faces > 0;
}

/** Límites previos al loader: no confiar en conteos declarados por un archivo. */
export function parseMesh(buffer, formato, limits) {
  if (buffer.byteLength > limits.meshBytes || buffer.byteLength < 15) throw new Error('memoria');
  const head = new TextDecoder().decode(buffer.slice(0, Math.min(buffer.byteLength, 65536)));
  let faces = true;
  if (formato === 'STL') {
    const count = buffer.byteLength >= 84 ? new DataView(buffer).getUint32(80, true) : 0;
    if (84 + count * 50 === buffer.byteLength) {
      if (count * 3 > limits.vertices || count < 1) throw new Error('memoria');
    } else {
      if (!/^\s*solid\b/i.test(head)) throw new Error('formato');
      const text = new TextDecoder().decode(buffer);
      let vertices = 0, triangles = 0;
      for (const _ of text.matchAll(/\bvertex\s/gi)) { if (++vertices > limits.vertices) throw new Error('memoria'); }
      for (const _ of text.matchAll(/\bendfacet\b/gi)) triangles++;
      if (!vertices || vertices !== triangles * 3 || !/\bendsolid\b/i.test(text)) throw new Error('formato');
      if (vertices > limits.vertices) throw new Error('memoria');
    }
  } else if (formato === 'PLY') {
    faces = validatePly(buffer, head, limits);
  } else throw new Error('formato');
  let geometry;
  try { geometry = formato === 'STL' ? new STLLoader().parse(buffer) : new PLYLoader().parse(buffer); }
  catch { throw new Error('formato'); }
  const positions = geometry.getAttribute('position');
  if (!positions?.count || positions.count > limits.vertices || (geometry.index?.count || 0) > limits.vertices) {
    geometry.dispose(); throw new Error('memoria');
  }
  for (const value of positions.array) {
    if (!Number.isFinite(value) || Math.abs(value) > 1e9) { geometry.dispose(); throw new Error('formato'); }
  }
  geometry.computeBoundingBox();
  if (geometry.boundingBox.isEmpty()) { geometry.dispose(); throw new Error('formato'); }
  return { geometry, faces };
}
