import React, { useRef } from 'react';

export interface Tick {
  frame: number;
  isMajor: boolean;
}

interface HistoryTimelineTrackProps {
  minFrame: number;
  maxFrame: number;
  ticks: Tick[];
  height?: string;
}

const HistoryTimelineTrack: React.FC<HistoryTimelineTrackProps> = ({
  minFrame,
  maxFrame,
  ticks,
  height = 'h-8',
}) => {
  const trackRef = useRef<HTMLDivElement>(null);
  const totalFrames = maxFrame - minFrame + 1;

  const frameToPercent = (frame: number) => {
    if (totalFrames <= 1) return 0;
    return ((frame - minFrame) / (totalFrames - 1)) * 100;
  };

  return (
    <div ref={trackRef} className={`w-full ${height} bg-timeline-track relative cursor-pointer rounded-md`}>
        {ticks.map((tick) => (
        <div
            key={tick.frame}
            className="absolute top-0 h-full pointer-events-none"
            style={{ left: `${frameToPercent(tick.frame)}%` }}
        >
            <div className={`w-px pointer-events-none ${tick.isMajor ? 'bg-timeline-tick-major h-full' : 'bg-timeline-tick-minor h-full'}`}></div>
        </div>
        ))}
    </div>
  );
};

export default HistoryTimelineTrack;