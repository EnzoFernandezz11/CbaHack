import {ThreeCanvas} from '@remotion/three';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {Color, Fog, SRGBColorSpace} from 'three';
import {AudioDesign} from './audio/AudioDesign';
import {CameraRig} from './scene/CameraRig';
import {Field} from './scene/Field';
import {Harvester} from './scene/Harvester';
import {Robot} from './scene/Robot';
import {PALETTE} from './scene/palette';
import {MACHINE_SPEED} from './timeline';

export const PeanutHarvestIntro: React.FC = () => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const machineZ = -frame * MACHINE_SPEED;
  const lensTransition = interpolate(
    frame,
    [399, 409, 414, 420],
    [0, 0.45, 0.9, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );

  return (
    <AbsoluteFill style={{backgroundColor: PALETTE.skyTop}}>
      <ThreeCanvas
        width={width}
        height={height}
        shadows
        gl={{antialias: true, outputColorSpace: SRGBColorSpace}}
        onCreated={({scene}) => {
          scene.background = new Color(PALETTE.skyTop);
          scene.fog = new Fog(PALETTE.skyHorizon, 45, 165);
        }}
      >
        <ambientLight intensity={0.72} color="#9fb5d1" />
        <hemisphereLight intensity={1.05} color="#ffd4a0" groundColor="#4c3023" />
        <directionalLight
          castShadow
          color="#ffc27d"
          intensity={3.4}
          position={[-28, 24, 18]}
          shadow-mapSize-width={1536}
          shadow-mapSize-height={1536}
          shadow-camera-far={120}
          shadow-camera-left={-35}
          shadow-camera-right={35}
          shadow-camera-top={35}
          shadow-camera-bottom={-35}
        />
        <Field frame={frame} />
        <group position={[0, 0, machineZ]}>
          <Harvester frame={frame} />
          <Robot frame={frame} />
        </group>
        <CameraRig frame={frame} machineZ={machineZ} />
      </ThreeCanvas>
      <AudioDesign />
      <AbsoluteFill
        style={{
          pointerEvents: 'none',
          background:
            'radial-gradient(circle at 50% 48%, transparent 44%, rgba(15, 11, 10, 0.34) 100%)',
          mixBlendMode: 'multiply',
        }}
      />
      <AbsoluteFill
        style={{
          pointerEvents: 'none',
          opacity: lensTransition,
          background:
            'radial-gradient(circle at 50% 50%, rgba(2, 5, 6, 0.25) 0%, rgba(2, 5, 6, 0.86) 42%, #010202 100%)',
        }}
      />
    </AbsoluteFill>
  );
};
