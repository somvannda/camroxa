/** Decompiled Logo fragment shader (Vizzy module 1366). */
export const LOGO_SHADER = /* glsl */ `
varying vec2 vUv;
uniform sampler2D tDiffuse;
uniform vec2 resolution;

// x posx, y posy, z scalex, w scaley 
uniform vec4 transform1;

// x: rotation, y: aspect, z: cutoff, w: wrapping
uniform vec4 transform2;

vec2 rotate(vec2 v, float a) {
  float s = sin(a);
  float c = cos(a);
  mat2 m = mat2(c, -s, s, c);
  return m * v;
}

vec4 getColor(vec2 p, float r, vec2 s) {
  // Translate
  vec2 transformedUv =  vec2( (vUv.x - 0.5) * transform2.y, vUv.y - 0.5)  * 2.0 + p.xy;
  float radius = transform2.z * length(s);
  // Antialias
  float alpha = smoothstep(radius, radius - 2./ resolution.y, length(transformedUv));
  
  // Rotate
  transformedUv = rotate(transformedUv, r);
  transformedUv.x *= 1. / transform2.y;
  // Scale
  transformedUv /=  s;
  transformedUv = (transformedUv + 1.) / 2.0;

  vec2 pos = transformedUv;
  int wrapping = int(transform2.w);
  vec4 col;
  if(wrapping == 0) {
    col = texture2D(tDiffuse, pos);
  } else  if(wrapping == 1) {
    col = texture2D(tDiffuse, mod(pos, 1.0));
  } else if(wrapping == 2) {
    if(pos.x > 1.0 || pos.y > 1.0 || pos.x < 0. || pos.y < 0.) discard;
    col = texture2D(tDiffuse, pos);
  }

  return vec4(col.rgb, col.a * alpha);
}

void main() {
  //gl_FragColor = texture2D(tDiffuse, vUv);
  gl_FragColor = getColor(transform1.xy, transform2.x, transform1.zw);
}`;
