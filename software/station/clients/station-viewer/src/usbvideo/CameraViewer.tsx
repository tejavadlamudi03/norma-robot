import { memo, useEffect, useState, useRef } from 'react';
import Long from 'long';
import { usbvideo } from '../api/proto.js';

interface CameraViewerProps {
  inferenceState: usbvideo.IRxEnvelope;
  className?: string;
  imageClassName?: string;
  overlay?: 'none' | 'fps';
  fit?: 'contain' | 'cover';
}

const CameraViewer = memo(function CameraViewer({
  inferenceState,
  className = '',
  imageClassName = '',
  overlay = 'fps',
  fit = 'contain',
}: CameraViewerProps) {
  const [fps, setFps] = useState<number>(0);
  const [imageUrl, setImageUrl] = useState<string>('');
  const imageUrlRef = useRef<string>('');
  const previousIndexRef = useRef<Long | null>(null);
  const frameCount = useRef<number>(0);
  const lastFpsTime = useRef<number>(Date.now());

  useEffect(() => {
    if (!inferenceState || !inferenceState.frames) {
      return;
    }

    const { frames, stamp } = inferenceState;

    // Get frame data - try framesData first (single frame), then linearData (packed frames)
    const data = (frames.framesData && frames.framesData.length > 0)
      ? frames.framesData[0]
      : frames.linearData;

    if (!data || data.length === 0 || !stamp || !stamp.index) {
      return;
    }

    const newIndex = Long.fromValue(stamp.index);

    // Only create new blob URL if frame index has changed
    if (!previousIndexRef.current || !previousIndexRef.current.equals(newIndex)) {
      // FPS calculation
      frameCount.current++;
      const nowFps = Date.now();
      const timeDiff = nowFps - lastFpsTime.current;

      if (timeDiff >= 1000) { // Update every second
        const calculatedFps = (frameCount.current / timeDiff) * 1000;
        setFps(calculatedFps);
        frameCount.current = 0;
        lastFpsTime.current = nowFps;
      }

      const blob = new Blob([data.slice()], { type: 'image/jpeg' });
      const url = URL.createObjectURL(blob);
      if (imageUrlRef.current) {
        URL.revokeObjectURL(imageUrlRef.current);
      }
      imageUrlRef.current = url;
      setImageUrl(url);
      previousIndexRef.current = newIndex;
    }
  }, [inferenceState]);

  // Cleanup effect for component unmount
  useEffect(() => {
    return () => {
      if (imageUrlRef.current) {
        URL.revokeObjectURL(imageUrlRef.current);
        imageUrlRef.current = '';
      }
    };
  }, []);

  if (!inferenceState) {
    return <div className="text-text-primary p-4">Waiting for USB Video data...</div>;
  }

  const fitClassName = fit === 'cover' ? 'object-cover' : 'object-contain';

  return (
    <div className={`overflow-hidden h-full ${className}`}>
      <div className="relative flex justify-center items-center h-full w-full bg-black/20">
        {imageUrl && (
          <img
            src={imageUrl}
            alt="USB Camera Feed"
            className={`h-full w-full ${fitClassName} ${imageClassName}`}
          />
        )}
        {overlay === 'fps' && (
          <div className="absolute top-0 right-0 p-2 text-right bg-surface-secondary/70 rounded-bl-lg backdrop-blur-sm">
            <span className="text-xs text-text-label">FPS: </span>
            <span className="text-xs font-mono text-accent-data">{fps.toFixed(1)}</span>
          </div>
        )}
      </div>
    </div>
  );
});

export default CameraViewer;
