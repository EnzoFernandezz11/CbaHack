import React, {useLayoutEffect} from 'react';
import {useThree} from '@react-three/fiber';
import {PerspectiveCamera, Vector3} from 'three';

type CameraRigProps = {frame: number; machineZ: number};
const ease = (t: number) => t * t * (3 - 2 * t);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export const CameraRig: React.FC<CameraRigProps> = ({frame, machineZ}) => {
  const {camera} = useThree();
  useLayoutEffect(() => {
    const t = frame;
    let x: number;
    let y: number;
    let z: number;
    let fov: number;
    let target: Vector3;

    if (t < 105) {
      const p = ease(t / 105);
      x = lerp(-22, 13, p);
      y = lerp(18, 10, p);
      z = machineZ + lerp(34, 26, p);
      fov = 42;
      target = new Vector3(0, lerp(1.8, 2.2, p), machineZ + lerp(2, 8, p));
    } else if (t < 240) {
      const p = ease((t - 105) / 135);
      x = lerp(13, 8, p);
      y = lerp(10, 7, p);
      z = machineZ + lerp(26, 24, p);
      fov = lerp(42, 46, p);
      target = new Vector3(0, lerp(2.2, 2.7, p), machineZ + lerp(8, 11, p));
    } else if (t < 399) {
      const p = ease((t - 240) / 159);
      x = lerp(8, 1.5, p);
      y = lerp(7, 6.5, p);
      z = machineZ + lerp(24, 16.4, p);
      fov = lerp(46, 50, p);
      target = new Vector3(0, lerp(2.7, 5.8, p), machineZ + lerp(11, 12.8, p));
    } else if (t < 420) {
      const p = ease((t - 399) / 21);
      x = lerp(1.5, 0, p);
      y = lerp(6.5, 5.95, p);
      z = machineZ + lerp(16.4, 12.5, p);
      fov = lerp(50, 56, p);
      target = new Vector3(
        0,
        lerp(5.8, 0.3, p),
        machineZ + lerp(12.8, 3, p),
      );
    } else {
      x = 0;
      y = 5.95;
      z = machineZ + 12.5;
      fov = 56;
      target = new Vector3(0, 0.3, machineZ + 3);
    }

    camera.position.set(x, y, z);
    camera.lookAt(target);
    if (camera instanceof PerspectiveCamera) {
      const focalLength =
        0.5 * camera.getFilmHeight() / Math.tan((fov * Math.PI) / 360);
      camera.setFocalLength(focalLength);
    }
    camera.updateProjectionMatrix();
  }, [camera, frame, machineZ]);
  return null;
};
