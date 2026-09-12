import React, {useMemo} from 'react';
import {PALETTE} from './palette';
import {range, seededRandom} from './seeded';

type FieldProps = {frame: number};

type Straw = {x: number; z: number; scale: number; lean: number};
type Dust = {x: number; y: number; z: number; size: number; phase: number};

/** A deliberately low-poly Córdoba peanut field: the repetition is geometric,
 * while the small irregularities come from a stable seed (never Math.random()). */
export const Field: React.FC<FieldProps> = ({frame}) => {
  const straw = useMemo<Straw[]>(
    () =>
      range(82).map((index) => {
        const row = index % 9;
        const column = Math.floor(index / 9);
        return {
          x: (row - 4) * 2.28 + (seededRandom(index + 7) - 0.5) * 0.32,
          z: 18 - column * 5.1 + (seededRandom(index + 31) - 0.5) * 2.2,
          scale: 0.55 + seededRandom(index + 61) * 0.55,
          lean: (seededRandom(index + 91) - 0.5) * 0.5,
        };
      }),
    [],
  );
  const dust = useMemo<Dust[]>(
    () =>
      range(18).map((index) => ({
        x: (seededRandom(index + 120) - 0.5) * 5.5,
        y: 0.35 + seededRandom(index + 150) * 1.5,
        z: 1 + seededRandom(index + 180) * 10,
        size: 0.12 + seededRandom(index + 210) * 0.28,
        phase: seededRandom(index + 240),
      })),
    [],
  );
  const dustTime = frame * 0.018;

  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[150, 180]} />
        <meshStandardMaterial color={PALETTE.soil} roughness={1} />
      </mesh>
      {/* Long, inverted peanut windrows. */}
      {range(11).map((row) => (
        <group key={`ridge-${row}`} position={[(row - 5) * 2.28, 0.08, 0]}>
          <mesh scale={[0.62, 0.18, 72]} receiveShadow>
            <boxGeometry args={[1, 1, 1]} />
            <meshStandardMaterial color={row % 2 ? PALETTE.straw : '#8b5b34'} roughness={1} />
          </mesh>
          <mesh position={[0, 0.16, 0]} scale={[0.23, 0.09, 72]}>
            <boxGeometry args={[1, 1, 1]} />
            <meshStandardMaterial color={PALETTE.soilDark} roughness={1} />
          </mesh>
        </group>
      ))}
      {straw.map((blade, index) => (
        <mesh key={`straw-${index}`} position={[blade.x, 0.34, blade.z]} rotation={[0, blade.lean, blade.lean]} scale={[blade.scale, blade.scale, blade.scale]}>
          <coneGeometry args={[0.2, 0.72, 5]} />
          <meshStandardMaterial color={index % 3 ? PALETTE.leaf : PALETTE.straw} roughness={1} />
        </mesh>
      ))}
      {/* Distant tree line and warm sun provide the horizon read. */}
      <mesh position={[0, 2.5, -48]} scale={[65, 5, 1]}>
        <coneGeometry args={[1, 1, 8]} />
        <meshStandardMaterial color={PALETTE.soilDark} roughness={1} />
      </mesh>
      {range(10).map((index) => (
        <mesh key={`tree-${index}`} position={[(index - 4.5) * 11, 5 + (index % 3), -46]} scale={[5, 5 + (index % 2) * 2, 3]}>
          <coneGeometry args={[1, 1, 7]} />
          <meshStandardMaterial color={index % 2 ? '#3e3c2e' : '#2b342b'} roughness={1} />
        </mesh>
      ))}
      <mesh position={[-18, 24, -65]}>
        <sphereGeometry args={[4.2, 20, 12]} />
        <meshBasicMaterial color={PALETTE.sun} />
      </mesh>
      {dust.map((particle, index) => {
        const drift = ((dustTime + particle.phase) % 1) * 2.4;
        return (
          <mesh key={`dust-${index}`} position={[particle.x + drift * 0.35, particle.y + Math.sin((dustTime + particle.phase) * Math.PI * 2) * 0.08, particle.z + drift]}>
            <sphereGeometry args={[particle.size, 7, 5]} />
            <meshBasicMaterial color="#d9ad7c" transparent opacity={0.1 + particle.size * 0.22} depthWrite={false} />
          </mesh>
        );
      })}
    </group>
  );
};
