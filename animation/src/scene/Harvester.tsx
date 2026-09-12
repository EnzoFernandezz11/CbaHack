import React from 'react';
import {PALETTE} from './palette';

type HarvesterProps = {frame: number};

const Wheel: React.FC<{x: number; z: number; radius?: number; rotation: number}> = ({x, z, radius = 0.72, rotation}) => (
  <group position={[x, radius, z]} rotation={[rotation, 0, 0]}>
    <mesh rotation={[0, 0, Math.PI / 2]} castShadow>
      <cylinderGeometry args={[radius, radius, 0.42, 12]} />
      <meshStandardMaterial color={PALETTE.rubber} roughness={0.95} />
    </mesh>
    <mesh rotation={[0, 0, Math.PI / 2]} position={[x < 0 ? 0.22 : -0.22, 0, 0]}>
      <cylinderGeometry args={[radius * 0.48, radius * 0.48, 0.44, 12]} />
      <meshStandardMaterial color={PALETTE.metal} roughness={0.8} />
    </mesh>
  </group>
);

/** Tractor-led peanut digger/windrower, facing down local -Z. */
export const Harvester: React.FC<HarvesterProps> = ({frame}) => {
  const wheelRotation = frame * 0.18;
  const reelRotation = frame * 0.32;
  const shaker = Math.sin(frame * 0.35) * 0.035;

  return (
    <group>
      {/* Tractor, the forward (negative-Z) unit. */}
      <group position={[0, 0, -2.5]}>
        <mesh position={[0, 1.15, -0.35]} castShadow>
          <boxGeometry args={[2.35, 0.7, 2.2]} />
          <meshStandardMaterial color={PALETTE.green} roughness={0.72} />
        </mesh>
        <mesh position={[0, 1.8, 0.32]} castShadow>
          <boxGeometry args={[1.65, 1.35, 1.28]} />
          <meshStandardMaterial color={PALETTE.graphite} roughness={0.65} />
        </mesh>
        <mesh position={[0, 1.86, -0.34]}>
          <boxGeometry args={[1.42, 0.82, 0.06]} />
          <meshStandardMaterial color={PALETTE.glass} metalness={0.15} roughness={0.25} />
        </mesh>
        <mesh position={[0, 1.26, -1.55]} castShadow>
          <boxGeometry args={[1.7, 0.5, 0.65]} />
          <meshStandardMaterial color={PALETTE.green} roughness={0.75} />
        </mesh>
        <mesh position={[0.72, 2.2, 0.84]}>
          <cylinderGeometry args={[0.06, 0.06, 0.9, 8]} />
          <meshStandardMaterial color={PALETTE.graphite} metalness={0.7} />
        </mesh>
        <Wheel x={-1.18} z={-1.4} radius={0.52} rotation={wheelRotation} />
        <Wheel x={1.18} z={-1.4} radius={0.52} rotation={wheelRotation} />
        <Wheel x={-1.27} z={0.46} radius={0.78} rotation={wheelRotation} />
        <Wheel x={1.27} z={0.46} radius={0.78} rotation={wheelRotation} />
      </group>
      {/* Drawbar and the trailing peanut digger. */}
      <mesh position={[0, 0.72, -0.72]} rotation={[0, 0, shaker]}>
        <boxGeometry args={[0.28, 0.2, 2.2]} />
        <meshStandardMaterial color={PALETTE.metal} metalness={0.7} roughness={0.55} />
      </mesh>
      <group position={[0, shaker, 1.45]}>
        <mesh position={[0, 1.6, 0]} castShadow>
          <boxGeometry args={[2.8, 1.45, 2.7]} />
          <meshStandardMaterial color={PALETTE.straw} roughness={0.78} />
        </mesh>
        <mesh position={[0, 2.55, 0.15]} castShadow>
          <boxGeometry args={[2.45, 0.45, 2.0]} />
          <meshStandardMaterial color={PALETTE.green} roughness={0.7} />
        </mesh>
        <mesh position={[0, 2.8, 0.18]} rotation={[0.08, 0, 0]}>
          <boxGeometry args={[2.25, 0.1, 1.8]} />
          <meshStandardMaterial color={PALETTE.metal} metalness={0.6} roughness={0.55} />
        </mesh>
        <mesh position={[0, 0.45, -1.42]} castShadow>
          <boxGeometry args={[3.25, 0.25, 0.28]} />
          <meshStandardMaterial color={PALETTE.metal} metalness={0.75} roughness={0.48} />
        </mesh>
        <mesh position={[0, 0.33, -1.63]} rotation={[0, 0, reelRotation]}>
          <torusGeometry args={[1.05, 0.07, 6, 14]} />
          <meshStandardMaterial color={PALETTE.metal} metalness={0.75} roughness={0.5} />
        </mesh>
        {[-0.9, -0.3, 0.3, 0.9].map((x) => (
          <mesh key={`pickup-${x}`} position={[x, 0.45, -1.75]} rotation={[0, 0, Math.sin(reelRotation + x) * 0.18]}>
            <boxGeometry args={[0.08, 0.55, 0.16]} />
            <meshStandardMaterial color={PALETTE.metal} metalness={0.8} roughness={0.42} />
          </mesh>
        ))}
        <Wheel x={-1.35} z={0.7} radius={0.45} rotation={wheelRotation} />
        <Wheel x={1.35} z={0.7} radius={0.45} rotation={wheelRotation} />
      </group>
    </group>
  );
};
