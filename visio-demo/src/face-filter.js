// Texture warp on the measured facial mesh. This is a 2D mask, not a neural swap.
export function createFaceFilter({ image, points, triangles, oval }) {
  const canvas = document.createElement('canvas');
  const gl = canvas.getContext('webgl', { alpha: true, premultipliedAlpha: false, preserveDrawingBuffer: true });
  if (!gl) throw new Error('Le filtre nécessite WebGL. Essayez Chrome ou Edge avec l’accélération graphique.');
  const shader = (type, source) => {
    const value = gl.createShader(type); gl.shaderSource(value, source); gl.compileShader(value);
    if (!gl.getShaderParameter(value, gl.COMPILE_STATUS)) throw new Error('Impossible de préparer le filtre graphique.');
    return value;
  };
  const vertex = shader(gl.VERTEX_SHADER, `
    attribute vec2 position; attribute vec2 uv; attribute float opacity;
    varying vec2 tex; varying float alpha;
    void main() { gl_Position = vec4(position.x * 2.0 - 1.0, 1.0 - position.y * 2.0, 0.0, 1.0); tex = uv; alpha = opacity; }
  `);
  const fragment = shader(gl.FRAGMENT_SHADER, `
    precision mediump float; varying vec2 tex; varying float alpha; uniform sampler2D portrait;
    void main() { gl_FragColor = vec4(texture2D(portrait, tex).rgb, alpha); }
  `);
  const program = gl.createProgram(); gl.attachShader(program, vertex); gl.attachShader(program, fragment); gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Impossible de démarrer le filtre graphique.');
  gl.useProgram(program);
  const buffers = [];
  const attribute = (name, values, size, dynamic = false) => {
    const buffer = gl.createBuffer(); buffers.push(buffer); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(values), dynamic ? gl.DYNAMIC_DRAW : gl.STATIC_DRAW);
    const location = gl.getAttribLocation(program, name); gl.enableVertexAttribArray(location); gl.vertexAttribPointer(location, size, gl.FLOAT, false, 0, 0);
    return buffer;
  };
  const positions = attribute('position', points.flatMap(p => [p.x, p.y]), 2, true);
  attribute('uv', points.flatMap(p => [p.x, p.y]), 2);
  const edge = new Set(oval);
  attribute('opacity', points.map((_, i) => edge.has(i) ? 0 : 1), 1);
  const indices = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indices);
  gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(triangles), gl.STATIC_DRAW);
  const texture = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
  gl.clearColor(0, 0, 0, 0);
  return {
    draw(context, landmarks, width, height) {
      if (gl.isContextLost()) throw new Error('Le filtre graphique a été interrompu. Relancez la caméra.');
      if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
      gl.viewport(0, 0, width, height); gl.clear(gl.COLOR_BUFFER_BIT);
      gl.bindBuffer(gl.ARRAY_BUFFER, positions);
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, new Float32Array(landmarks.slice(0, points.length).flatMap(p => [p.x, p.y])));
      gl.drawElements(gl.TRIANGLES, triangles.length, gl.UNSIGNED_SHORT, 0);
      context.drawImage(canvas, 0, 0);
    },
    close() {
      buffers.forEach(buffer => gl.deleteBuffer(buffer)); gl.deleteBuffer(indices); gl.deleteTexture(texture);
      gl.deleteProgram(program); gl.deleteShader(vertex); gl.deleteShader(fragment);
      gl.getExtension('WEBGL_lose_context')?.loseContext(); canvas.width = canvas.height = 0;
    },
  };
}
