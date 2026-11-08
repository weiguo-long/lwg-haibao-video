import React, {useCallback, useLayoutEffect, useRef, useState} from 'react';
import {
  AbsoluteFill,
  Audio,
  continueRender,
  delayRender,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

type FrameWindow = Window & {__seekTo?: (t: number) => void; __frameReady?: boolean};

/**
 * 帧源是 public/render.html —— 与用户确认的 preview.html 共用同一批海报 DOM、
 * scoped CSS 与 timeline.json 渲染逻辑，只是去掉了播放器 UI 和音频。
 * 每帧用 frame/fps 同步调用 iframe 内的 __seekTo(t)（同源、同步、无重载），
 * 所以字幕切换与逐元素入场在成片里和预览完全一致，且可逐帧复现。
 */
export const PriceStory: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const ready = useRef(false);
  const [handle] = useState(() => delayRender('loading frame source'));

  const t = frame / fps;
  const tRef = useRef(t);
  tRef.current = t;

  const seek = useCallback((value: number) => {
    const win = iframeRef.current?.contentWindow as FrameWindow | null;
    if (win && win.__frameReady && win.__seekTo) {
      win.__seekTo(value);
      return true;
    }
    return false;
  }, []);

  const onLoad = useCallback(() => {
    ready.current = true;
    // 单帧渲染（remotion still）时组件只挂载一次，必须在 onLoad 里立即定位
    seek(tRef.current);
    continueRender(handle);
  }, [handle, seek]);

  // iframe 已就绪时，在 render 阶段同步驱动，避免合成器滞后一帧
  if (ready.current) seek(t);
  // 每次提交再兜底一次（useLayoutEffect 早于浏览器绘制与截图）
  useLayoutEffect(() => { seek(t); });

  return (
    <AbsoluteFill style={{backgroundColor: '#1A1614'}}>
      <iframe
        ref={iframeRef}
        src={staticFile('render.html')}
        onLoad={onLoad}
        title="frame source"
        style={{width, height, border: 0, display: 'block'}}
      />
      <Audio src={staticFile('voiceover-full.mp3')} />
    </AbsoluteFill>
  );
};
