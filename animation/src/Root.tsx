import {Composition} from 'remotion';
import {PeanutHarvestIntro} from './PeanutHarvestIntro';
import {VIDEO} from './timeline';

export const Root: React.FC = () => {
  return (
    <Composition
      id="PeanutHarvestIntro"
      component={PeanutHarvestIntro}
      durationInFrames={VIDEO.durationInFrames}
      fps={VIDEO.fps}
      width={VIDEO.width}
      height={VIDEO.height}
    />
  );
};
