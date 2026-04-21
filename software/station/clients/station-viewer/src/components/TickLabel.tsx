import { useEffect, useState, memo } from 'react';
import Long from 'long';
import webSocketManager from '../api/websocket';
import { inference } from '../api/proto.js';

interface TickLabelProps {
  frame: number;
  framePercent: number;
}

interface TickData {
  timestamp: Date | null;
}

/**
 * Memoized tick label component that fetches its own data.
 * This prevents re-renders of the parent Timeline when data arrives.
 */
const TickLabel = memo(function TickLabel({
  frame,
  framePercent,
}: TickLabelProps) {
  const [data, setData] = useState<TickData>({ timestamp: null });

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      if (!webSocketManager.isConnected()) return;

      try {
        const entryId = Uint8Array.from(Long.fromNumber(frame).toBytesLE());
        const entry = await webSocketManager.normFs.readSingleEntry(
          'inference-states',
          entryId,
        );

        if (cancelled || !entry.data) return;

        const inferenceState = inference.InferenceRx.decode(entry.data);

        // Extract timestamp
        let timestamp: Date | null = null;
        if (inferenceState.localStampNs) {
          const timestampMs = Long.fromValue(inferenceState.localStampNs)
            .div(1000000)
            .toNumber();
          timestamp = new Date(timestampMs);
        }

        if (!cancelled) {
          setData({ timestamp });
        }
      } catch (error) {
        console.error(`Failed to fetch data for frame ${frame}:`, error);
      }
    };

    // Reset state when frame changes
    setData({ timestamp: null });
    fetchData();

    return () => {
      cancelled = true;
    };
  }, [frame]);

  const getTransform = () => {
    if (framePercent <= 1) return 'translateX(0)';
    if (framePercent >= 99) return 'translateX(-100%)';
    return 'translateX(-50%)';
  };

  return (
    <div
      className="absolute text-xs text-text-label"
      style={{ left: `${Math.max(0, Math.min(100, framePercent))}%`, transform: getTransform() }}
    >
      <div>{frame.toLocaleString()}</div>
      {data.timestamp && (
        <div className="text-text-muted text-[10px] mt-1">
          <div>{data.timestamp.toLocaleDateString()}</div>
          <div>{data.timestamp.toLocaleTimeString()}</div>
        </div>
      )}
    </div>
  );
});

export default TickLabel;
