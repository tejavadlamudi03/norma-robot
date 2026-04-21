import { forwardRef, memo, useImperativeHandle, useRef } from 'react';
import { TimelineActions, TimelineState } from '../hooks/useTimelineState';
import { TimelineControlsRef } from '../hooks';
import GotoFrameInput, { GotoFrameInputRef } from './GotoFrameInput';

interface TimelineControlsProps {
  state: TimelineState;
  actions: TimelineActions;
  frameStep?: number;
  largeFrameStep?: number;
}

const TimelineControlsComponent = forwardRef<TimelineControlsRef, TimelineControlsProps>(
  function TimelineControls({
    state,
    actions,
    frameStep = 1,
    largeFrameStep = 10,
  }: TimelineControlsProps, ref) {
    const gotoInputRef = useRef<GotoFrameInputRef>(null);

    useImperativeHandle(ref, () => ({
      focusGotoInput: () => gotoInputRef.current?.focus(),
    }));

    return (
      <div className="flex items-center gap-2">
        <button
          onClick={() => actions.jumpToStart()}
          className="px-2 py-1 text-xs bg-surface-tertiary hover:bg-surface-elevated active:bg-surface-active active:scale-95 text-text-primary rounded transition-transform cursor-pointer"
          title="Jump to start (Home)"
        >
          |◀
        </button>
        <button
          onClick={() => actions.prevFrame(largeFrameStep)}
          className="px-2 py-1 text-xs bg-surface-tertiary hover:bg-surface-elevated active:bg-surface-active active:scale-95 text-text-primary rounded transition-transform cursor-pointer"
          title={`Previous ${largeFrameStep} frames (Shift+←)`}
        >
          ◀◀
        </button>
        <button
          onClick={() => actions.prevFrame(frameStep)}
          className="px-2 py-1 text-xs bg-surface-tertiary hover:bg-surface-elevated active:bg-surface-active active:scale-95 text-text-primary rounded transition-transform cursor-pointer"
          title="Previous frame (←)"
        >
          ◀
        </button>
        <GotoFrameInput
          ref={gotoInputRef}
          currentFrame={state.currentFrame}
          range={state.originalRange}
          onSelectFrame={actions.selectFrame}
          className="min-w-36 max-w-48"
          title="Jump to frame (G key) - Enter frame # or ±offset"
        />
        <button
          onClick={() => actions.nextFrame(frameStep)}
          className="px-2 py-1 text-xs bg-surface-tertiary hover:bg-surface-elevated active:bg-surface-active active:scale-95 text-text-primary rounded transition-transform cursor-pointer"
          title="Next frame (→)"
        >
          ▶
        </button>
        <button
          onClick={() => actions.nextFrame(largeFrameStep)}
          className="px-2 py-1 text-xs bg-surface-tertiary hover:bg-surface-elevated active:bg-surface-active active:scale-95 text-text-primary rounded transition-transform cursor-pointer"
          title={`Next ${largeFrameStep} frames (Shift+→)`}
        >
          ▶▶
        </button>
        <button
          onClick={() => actions.jumpToEnd()}
          className="px-2 py-1 text-xs bg-surface-tertiary hover:bg-surface-elevated active:bg-surface-active active:scale-95 text-text-primary rounded transition-transform cursor-pointer"
          title="Jump to end (End)"
        >
          ▶|
        </button>
      </div>
    );
  }
);

const TimelineControls = memo(TimelineControlsComponent);
TimelineControls.displayName = 'TimelineControls';

export default TimelineControls;
