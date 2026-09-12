import React from 'react';
import {Audio} from '@remotion/media';
import {interpolate, Sequence, staticFile, useCurrentFrame} from 'remotion';

const fadeOut = (frame: number, start: number, end: number) => frame < start ? 1 : frame >= end ? 0 : 1 - (frame - start) / (end - start);

export const AudioDesign: React.FC = () => {
  const frame = useCurrentFrame();
  const opticalFade = fadeOut(frame, 420, 450);
  return <>
    <Audio src={staticFile('audio/wind.wav')} volume={() => 0.16 * opticalFade} />
    <Audio src={staticFile('audio/engine.wav')} volume={() => 0.28 * opticalFade} />
    <Audio src={staticFile('audio/machinery.wav')} volume={() => 0.2 * opticalFade} />
    <Sequence from={390} durationInFrames={60}>
      <Audio
        src={staticFile('audio/transition.wav')}
        volume={(audioFrame) =>
          interpolate(audioFrame, [0, 12, 30, 60], [0, 0.32, 0.24, 0], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          })
        }
      />
    </Sequence>
  </>;
};
