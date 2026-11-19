/** Decompiled Progress Bar fragment shader (Vizzy module 1376). */
export const PROGRESS_BAR_SHADER = /* glsl */ `
  #define PI 3.14159265359

  uniform int uBarType;
  uniform int uDirection;
  uniform float uProgress;
  uniform vec3 uFgColor;
  uniform vec3 uBgColor;
  uniform float uFgAlpha;
  uniform float uBgAlpha;
  uniform float uLength;
  uniform float uThickness;
  uniform float uRadius;
  uniform float uCornerRadius;
  uniform float uCircleStartAngle;
  uniform float uSegments;
  uniform float uGap;
  uniform float uContinuousSegments;
  uniform float uSkipSegmentGapsDuringProgress;
  uniform float uCircleConsistentGapThickness;
  uniform float uCanvasSize;

  varying vec2 vUv;

  float sdRoundRect(vec2 p, vec2 b, float r) {
    vec2 d = abs(p) - b + vec2(r);
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - r;
  }
  
  float segmentMaskCircle(float angle, float numSegments, float gapAngle, float dist) {
    if (numSegments <= 1.0 || gapAngle < 0.0001) return 1.0;
    float segmentAngle = (2.0 * PI) / numSegments;
    float m = mod(angle, segmentAngle);
    float shifted = m - segmentAngle * 0.5;
    float sd_rad = (segmentAngle - gapAngle) * 0.5 - abs(shifted);
    float sd_pixels = sd_rad * dist;
    return smoothstep(-0.5, 0.5, sd_pixels);
  }

  float segmentMaskLine(float pos, float totalLength, float numSegments, float gapDist) {
    if (numSegments <= 1.0 || gapDist < 0.001) return 1.0;
    float segmentPitch = totalLength / numSegments;
    float visibleSegmentLength = max(segmentPitch - gapDist, 0.0001);
    float clampedPos = clamp(pos, 0.0, totalLength - 0.0001);
    float localPos = mod(clampedPos, segmentPitch);
    
    float shifted = localPos - visibleSegmentLength * 0.5;
    float wrapped = mod(shifted + segmentPitch * 0.5, segmentPitch) - segmentPitch * 0.5;
    float sd = visibleSegmentLength * 0.5 - abs(wrapped);
    
    if (clampedPos < visibleSegmentLength * 0.5 && shifted < 0.0) {
      sd = 100.0;
    }
    if (clampedPos > totalLength - gapDist - visibleSegmentLength * 0.5 && shifted > 0.0) {
      sd = 100.0;
    }
    
    return smoothstep(-0.5, 0.5, sd);
  }

  float getSegmentCount(float rawSegments) {
    return max(floor(rawSegments + 0.5), 1.0);
  }

  float getLitSegments(float progress, float segmentCount) {
    float p = clamp(progress, 0.0, 1.0);
    if (p <= 0.0) return 0.0;
    // Ceil-style quantization ensures the last segment can light before exact 1.0 progress.
    return min(segmentCount, ceil(p * segmentCount - 0.0001));
  }

  void main() {
    // vUv is 0 to 1
    vec2 uv = vUv - 0.5; // -0.5 to 0.5
    
    // Pixel coordinates based on the backing progress canvas size.
    vec2 p = uv * uCanvasSize;
    
    float alpha = 0.0;
    vec3 color = uBgColor;
    float isFg = 0.0;
    float segmentCount = getSegmentCount(uSegments);

    if (uBarType == 0) {
      // LINE
      bool isVertical = uDirection == 2 || uDirection == 3 || uDirection == 5;
      bool isCenterDirection = uDirection == 4 || uDirection == 5;
      float halfLength = uLength * 0.5;
      float axis = isVertical ? p.y : p.x;
      vec2 b = isVertical ? vec2(uThickness / 2.0, halfLength) : vec2(halfLength, uThickness / 2.0);
      float d = sdRoundRect(p, b, uCornerRadius);
      
      // fill base
      alpha = smoothstep(1.0, 0.0, d);
      
      if (alpha > 0.0) {
        float progressVal = 0.0;
        float pos = 0.0;
        
        if (uDirection == 0) { // L2R
          pos = axis + halfLength;
          progressVal = pos / uLength;
        } else if (uDirection == 1) { // R2L
          pos = halfLength - axis;
          progressVal = pos / uLength;
        } else if (uDirection == 2) { // T2B
          pos = halfLength - axis;
          progressVal = pos / uLength;
        } else if (uDirection == 3) { // B2T
          pos = axis + halfLength;
          progressVal = pos / uLength;
        } else if (uDirection == 4) { // CenterH
          pos = axis + halfLength;
          progressVal = abs(axis) / max(halfLength, 0.0001);
        } else if (uDirection == 5) { // CenterV
          pos = axis + halfLength;
          progressVal = abs(axis) / max(halfLength, 0.0001);
        }

        progressVal = clamp(progressVal, 0.0, 1.0);
        pos = clamp(pos, 0.0, uLength);

        float lit = 0.0;
        if (segmentCount <= 1.0) {
          if (progressVal <= uProgress) {
            lit = 1.0;
          }
        } else {
          float gapDist = min(uGap, (uLength / segmentCount) * 0.9);
          // Model line segments as N equal segments + (N-1) equal gaps.
          // We pass (uLength + gapDist) to masking so the trailing gap lies outside visible range.
          float segmentModelLength = uLength + gapDist;
          float segmentPitch = segmentModelLength / segmentCount;
          float visibleSegmentLength = max(segmentPitch - gapDist, 0.0001);
          float segmentPos = clamp(pos, 0.0, uLength - 0.0001);

          // Use the unshifted coordinate for progress indexing too.
          // Shifting only the index coordinate can split a visual segment in half.
          float progressSegmentPos = segmentPos;

          float segmentIndex = floor(progressSegmentPos / segmentPitch);
          segmentIndex = min(segmentIndex, segmentCount - 1.0);

          if (uContinuousSegments > 0.5) {
            float litProgress = progressVal;
            if (uSkipSegmentGapsDuringProgress > 0.5) {
              float localInSegment = progressSegmentPos - segmentIndex * segmentPitch;
              float visibleAccum =
                segmentIndex * visibleSegmentLength + min(localInSegment, visibleSegmentLength);
              float totalVisibleLength = visibleSegmentLength * segmentCount;
              
              if (isCenterDirection) {
                litProgress = abs(visibleAccum - totalVisibleLength * 0.5) / (totalVisibleLength * 0.5);
              } else {
                litProgress = visibleAccum / totalVisibleLength;
              }
            }

            if (litProgress <= clamp(uProgress, 0.0, 1.0)) {
              lit = 1.0;
            }
          } else {
            float litSegments = getLitSegments(uProgress, segmentCount);

            if (isCenterDirection) {
              if (litSegments > 0.0) {
                float oddLitSegments = 1.0 + 2.0 * floor(max(litSegments - 1.0, 0.0) * 0.5);
                float centerIndex = floor(segmentCount * 0.5);
                float halfSpan = (oddLitSegments - 1.0) * 0.5;
                if (abs(segmentIndex - centerIndex) <= halfSpan + 0.0001) {
                  lit = 1.0;
                }
              }
            } else if (segmentIndex < litSegments) {
              lit = 1.0;
            }
          }

          alpha *= segmentMaskLine(segmentPos, segmentModelLength, segmentCount, gapDist);
        }
        
        isFg = lit;
      }

    } else {
      // CIRCLE
      float dist = length(p);
      float d = abs(dist - uRadius) - uThickness / 2.0;
      alpha = smoothstep(1.0, 0.0, d);
      
      if (alpha > 0.0) {
        float angle = atan(p.y, p.x); // -PI to PI
        if (angle < 0.0) angle += 2.0 * PI;
        
        // Normalize angle so that top starts at 0 and allow rotation offset.
        float a = mod(angle + PI / 2.0 + uCircleStartAngle, 2.0 * PI);
        if (a < 0.0) a += 2.0 * PI;

        float progressAngle = clamp(uProgress, 0.0, 1.0) * 2.0 * PI;
        float directionAngle = uDirection == 0 ? (2.0 * PI - a) : a;

        if (segmentCount <= 1.0) {
          if (uDirection == 0) { // CW
            float aCW = directionAngle;
            if (aCW >= 2.0 * PI) aCW -= 2.0 * PI;
            isFg = clamp((progressAngle - aCW) * dist + 0.5, 0.0, 1.0);
          } else if (uDirection == 1) { // CCW
            isFg = clamp((progressAngle - directionAngle) * dist + 0.5, 0.0, 1.0);
          } else if (uDirection == 2) { // Center Both Ways
            float distanceFromTop = min(a, 2.0 * PI - a);
            isFg = clamp((progressAngle / 2.0 - distanceFromTop) * dist + 0.5, 0.0, 1.0);
          }
        } else {
          float segmentAngle = (2.0 * PI) / segmentCount;
          // For center expand, shift so segment 0 is centered on top of the circle.
          if (uDirection == 2) {
            directionAngle = mod(directionAngle + segmentAngle * 0.5, 2.0 * PI);
          }
          float segmentIndex = floor(clamp(directionAngle, 0.0, 2.0 * PI - 0.0001) / segmentAngle);
          float progressRadius = max(uRadius, 0.0001);
          float maskRadius =
            uCircleConsistentGapThickness > 0.5 ? max(dist, 0.0001) : max(uRadius, 0.0001);
          float gapAngleForProgress = min(uGap / progressRadius, segmentAngle * 0.9);
          float gapAngleForMask = min(uGap / maskRadius, segmentAngle * 0.9);

          if (uContinuousSegments > 0.5) {
            float litProgress = 0.0;
            float visibleDist = dist * 2.0 * PI;
            
            if (uSkipSegmentGapsDuringProgress > 0.5) {
              float localAngle = mod(directionAngle, segmentAngle);
              float halfGap = gapAngleForProgress * 0.5;
              float visibleSegmentAngle = max(segmentAngle - gapAngleForProgress, 0.00001);
              float localVisible = clamp(localAngle - halfGap, 0.0, visibleSegmentAngle);
              float visibleAccum = segmentIndex * visibleSegmentAngle + localVisible;
              float totalVisibleAngle = visibleSegmentAngle * segmentCount;
              
              if (uDirection == 2) {
                float shiftedAccum = mod(visibleAccum - visibleSegmentAngle * 0.5 + totalVisibleAngle, totalVisibleAngle);
                float distanceAccum = min(shiftedAccum, totalVisibleAngle - shiftedAccum);
                litProgress = distanceAccum / (totalVisibleAngle * 0.5);
                visibleDist = dist * (totalVisibleAngle * 0.5);
              } else {
                litProgress = visibleAccum / totalVisibleAngle;
                visibleDist = dist * totalVisibleAngle;
              }
            } else {
              if (uDirection == 2) {
                float distanceFromTop = min(a, 2.0 * PI - a);
                litProgress = distanceFromTop / PI;
                visibleDist = dist * PI;
              } else {
                litProgress = directionAngle / (2.0 * PI);
                visibleDist = dist * 2.0 * PI;
              }
            }

            isFg = clamp((clamp(uProgress, 0.0, 1.0) - litProgress) * visibleDist + 0.5, 0.0, 1.0);
          } else {
            float litSegments = getLitSegments(uProgress, segmentCount);

            if (uDirection == 2) {
              if (litSegments > 0.0) {
                float oddLitSegments = 1.0 + 2.0 * floor(max(litSegments - 1.0, 0.0) * 0.5);
                float halfSpan = (oddLitSegments - 1.0) * 0.5;
                float circularDistance = min(segmentIndex, segmentCount - segmentIndex);
                if (circularDistance <= halfSpan + 0.0001) {
                  isFg = 1.0;
                }
              }
            } else if (segmentIndex < litSegments) {
              isFg = 1.0;
            }
          }

          alpha *= segmentMaskCircle(directionAngle, segmentCount, gapAngleForMask, dist);
        }
      }
    }

    color = mix(uBgColor, uFgColor, isFg);
    float mixedAlpha = mix(uBgAlpha, uFgAlpha, isFg);
    gl_FragColor = vec4(color, alpha * mixedAlpha);
  }
`;
