import React from 'react';
import {Composition} from 'remotion';
import {PriceStory} from './PriceStory';
// config.ts 由 voice-animation/build_render.py 从 timeline.json 自动生成
import {FPS, WIDTH, HEIGHT, DURATION_IN_FRAMES} from './config';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="PriceStory"
    component={PriceStory}
    durationInFrames={DURATION_IN_FRAMES}
    fps={FPS}
    width={WIDTH}
    height={HEIGHT}
  />
);
