import React, {useMemo} from 'react';
import {PALETTE} from './palette';
import {seededRandom} from './seeded';

type RobotProps = {frame: number};

const Panel: React.FC<{position: [number, number, number]; scale: [number, number, number]; rotation?: [number, number, number]}> = ({position, scale, rotation = [0, 0, 0]}) => (
  <mesh position={position} rotation={rotation} scale={scale} castShadow receiveShadow>
    <boxGeometry args={[1, 1, 1]} />
    <meshStandardMaterial color={PALETTE.white} roughness={0.36} metalness={0.28} />
  </mesh>
);

const Tire: React.FC<{position: [number, number, number]; spin: number}> = ({position, spin}) => (
  <group position={position} rotation={[spin, 0, 0]}>
    <mesh rotation={[0, 0, Math.PI / 2]} castShadow receiveShadow>
      <cylinderGeometry args={[1.18, 1.18, 0.62, 20]} />
      <meshStandardMaterial color={PALETTE.rubber} roughness={0.9} />
    </mesh>
    <mesh rotation={[0, 0, Math.PI / 2]} position={[0.32, 0, 0]}>
      <cylinderGeometry args={[0.62, 0.62, 0.035, 20]} />
      <meshStandardMaterial color={PALETTE.metal} roughness={0.27} metalness={0.8} />
    </mesh>
    <mesh rotation={[0, 0, Math.PI / 2]} position={[0.35, 0, 0]}>
      <cylinderGeometry args={[0.28, 0.28, 0.045, 16]} />
      <meshStandardMaterial color={PALETTE.graphite} roughness={0.6} />
    </mesh>
  </group>
);

const PeanutLoad: React.FC = () => {
  const peanuts = useMemo(() => Array.from({length: 44}, (_, i) => {
    const x = (seededRandom(i + 1) - 0.5) * 3.7;
    const z = (seededRandom(i + 19) - 0.5) * 2.05;
    const y = 2.1 + seededRandom(i + 37) * 0.55;
    return {position: [x, y, z] as [number, number, number], rotation: [seededRandom(i) * 2, seededRandom(i + 4) * 2, seededRandom(i + 8) * 2] as [number, number, number]};
  }), []);
  return <group>{peanuts.map((peanut, i) => <mesh key={i} position={peanut.position} rotation={peanut.rotation} scale={[0.16, 0.1, 0.24]}>
    <sphereGeometry args={[1, 8, 6]} />
    <meshStandardMaterial color={i % 3 === 0 ? '#c99558' : '#b9834b'} roughness={0.92} />
  </mesh>)}</group>;
};

export const Robot: React.FC<RobotProps> = ({frame}) => {
  const bob = Math.sin(frame * 0.13) * 0.025;
  const wheelSpin = frame * 0.042;
  return <group position={[0, bob, 13]}>
    <group position={[0, 1.65, 0]}>
      <Panel position={[0, 0, 0]} scale={[4.6, 1.55, 2.7]} />
      <mesh position={[0, 0.87, 0.05]} castShadow>
        <boxGeometry args={[4.35, 0.16, 2.45]} />
        <meshStandardMaterial color={PALETTE.graphite} roughness={0.42} metalness={0.5} />
      </mesh>
      <mesh position={[0, 1.12, 0.05]} rotation={[0, 0, 0]}>
        <boxGeometry args={[4.05, 0.08, 2.25]} />
        <meshStandardMaterial color={PALETTE.graphite} roughness={0.5} />
      </mesh>
      <PeanutLoad />
      {[-2.05, 2.05].map((x) => <mesh key={x} position={[x, 0.94, 0]}>
        <boxGeometry args={[0.12, 1.55, 2.55]} />
        <meshStandardMaterial color={PALETTE.metal} metalness={0.75} roughness={0.3} />
      </mesh>)}
    </group>
    <mesh position={[0, 0.78, 0]} castShadow>
      <boxGeometry args={[4.2, 1.4, 2.5]} />
      <meshStandardMaterial color={PALETTE.graphite} roughness={0.5} metalness={0.45} />
    </mesh>
    <Panel position={[0, 1.05, -1.27]} scale={[3.5, 0.85, 0.12]} />
    <mesh position={[0, 1.13, -1.35]}>
      <boxGeometry args={[2.7, 0.08, 0.05]} />
      <meshStandardMaterial color={PALETTE.green} emissive={PALETTE.green} emissiveIntensity={1.8} />
    </mesh>
    {[-1.72, 1.72].map((x) => <Tire key={x} position={[x, 0.95, -0.92]} spin={wheelSpin} />)}
    {[-1.72, 1.72].map((x) => <Tire key={x} position={[x, 0.95, 1.02]} spin={wheelSpin} />)}
    <group position={[0, 0.05, -1.7]}>
      <mesh position={[0, 0.12, 0]} castShadow><boxGeometry args={[3.45, 0.2, 0.28]} /><meshStandardMaterial color={PALETTE.metal} metalness={0.7} roughness={0.35} /></mesh>
      <mesh position={[0, -0.18, 0.18]} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.48, 0.48, 3.25, 20]} /><meshStandardMaterial color={PALETTE.rubber} roughness={0.8} /></mesh>
      {[-1.25, -0.62, 0, 0.62, 1.25].map((x) => <mesh key={x} position={[x, -0.18, 0.2]} rotation={[0, Math.PI / 2, 0]}><torusGeometry args={[0.35, 0.075, 8, 16]} /><meshStandardMaterial color={PALETTE.graphite} roughness={0.7} /></mesh>)}
    </group>
    <group position={[0, 2.65, 0.15]}>
      <mesh position={[0, 1.65, 0]}><cylinderGeometry args={[0.12, 0.12, 3.25, 12]} /><meshStandardMaterial color={PALETTE.graphite} metalness={0.75} roughness={0.3} /></mesh>
      <mesh position={[0, 3.35, 0]} castShadow><boxGeometry args={[0.72, 0.55, 0.62]} /><meshStandardMaterial color={PALETTE.white} roughness={0.3} metalness={0.5} /></mesh>
      <mesh position={[0, 3.35, -0.33]}><cylinderGeometry args={[0.17, 0.17, 0.025, 20]} /><meshStandardMaterial color={PALETTE.glass} emissive={PALETTE.green} emissiveIntensity={0.5} /></mesh>
      <mesh position={[0, 3.72, 0]}><cylinderGeometry args={[0.22, 0.22, 0.12, 16]} /><meshStandardMaterial color={PALETTE.graphite} metalness={0.8} /></mesh>
      <mesh position={[0, 3.79, 0]}><cylinderGeometry args={[0.16, 0.16, 0.025, 16]} /><meshStandardMaterial color={PALETTE.green} emissive={PALETTE.green} emissiveIntensity={2} /></mesh>
    </group>
    <mesh position={[0, 2.35, -1.35]}><boxGeometry args={[2.4, 0.08, 0.08]} /><meshStandardMaterial color={PALETTE.green} emissive={PALETTE.green} emissiveIntensity={1.6} /></mesh>
  </group>;
};
