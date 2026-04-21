import { useEffect, useRef, useState, useCallback, memo } from 'react';

interface FullscreenImageViewerProps {
  src: string;
  alt: string;
  onClose: () => void;
}

const FullscreenImageViewerComponent = function FullscreenImageViewer({ src, alt, onClose }: FullscreenImageViewerProps) {
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0, posX: 0, posY: 0 });
  const positionRef = useRef({ x: 0, y: 0 });
  const isDraggingRef = useRef(false);
  const imgRef = useRef<HTMLImageElement>(null);

  const MIN_SCALE = 0.5;
  const MAX_SCALE = 4;

  const handleZoomIn = useCallback(() => {
    setScale((s) => Math.min(s + 0.5, MAX_SCALE));
  }, []);

  const handleZoomOut = useCallback(() => {
    setScale((s) => {
      const newScale = Math.max(s - 0.5, MIN_SCALE);
      if (newScale === 1) {
        setPosition({ x: 0, y: 0 });
        positionRef.current = { x: 0, y: 0 };
      }
      return newScale;
    });
  }, []);

  const handleReset = useCallback(() => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
    positionRef.current = { x: 0, y: 0 };
  }, []);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
    }
  }, [onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    isDraggingRef.current = true;
    setIsDragging(true);
    dragStart.current = {
      x: e.clientX,
      y: e.clientY,
      posX: positionRef.current.x,
      posY: positionRef.current.y,
    };
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - dragStart.current.x;
    const dy = e.clientY - dragStart.current.y;
    const newPos = {
      x: dragStart.current.posX + dx,
      y: dragStart.current.posY + dy,
    };
    positionRef.current = newPos;
    setPosition(newPos);
  }, []);

  const handleMouseUp = useCallback(() => {
    isDraggingRef.current = false;
    setIsDragging(false);
  }, []);

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;

    const onTouchStart = (e: TouchEvent) => {
      if (e.touches.length !== 1) return;
      const touch = e.touches[0];
      isDraggingRef.current = true;
      setIsDragging(true);
      dragStart.current = {
        x: touch.clientX,
        y: touch.clientY,
        posX: positionRef.current.x,
        posY: positionRef.current.y,
      };
    };

    const onTouchMove = (e: TouchEvent) => {
      if (!isDraggingRef.current || e.touches.length !== 1) return;
      e.preventDefault();
      const touch = e.touches[0];
      const dx = touch.clientX - dragStart.current.x;
      const dy = touch.clientY - dragStart.current.y;
      const newPos = {
        x: dragStart.current.posX + dx,
        y: dragStart.current.posY + dy,
      };
      positionRef.current = newPos;
      setPosition(newPos);
    };

    const onTouchEnd = () => {
      isDraggingRef.current = false;
      setIsDragging(false);
    };

    img.addEventListener('touchstart', onTouchStart, { passive: false });
    img.addEventListener('touchmove', onTouchMove, { passive: false });
    img.addEventListener('touchend', onTouchEnd);

    return () => {
      img.removeEventListener('touchstart', onTouchStart);
      img.removeEventListener('touchmove', onTouchMove);
      img.removeEventListener('touchend', onTouchEnd);
    };
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 bg-surface-overlay-light backdrop-blur-sm flex items-center justify-center"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <img
        ref={imgRef}
        src={src}
        alt={alt}
        className="max-w-full max-h-full select-none"
        style={{
          transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
          cursor: isDragging ? 'grabbing' : 'grab',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        draggable={false}
      />

      <div className="fixed bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2 bg-surface-primary border border-border-default px-4 py-3 rounded md:px-3 md:py-2">
        <button
          type="button"
          onClick={handleZoomOut}
          className="px-3 py-2 text-sm bg-surface-tertiary hover:bg-surface-elevated active:bg-surface-active active:scale-95 text-text-primary rounded transition-transform cursor-pointer md:px-2 md:py-1 md:text-xs"
          title="Zoom out"
        >
          −
        </button>
        <button
          type="button"
          onClick={handleReset}
          className="px-3 py-2 text-sm bg-surface-tertiary hover:bg-surface-elevated active:bg-surface-active active:scale-95 text-text-primary rounded transition-transform cursor-pointer min-w-14 text-center md:px-2 md:py-1 md:text-xs md:min-w-10"
        >
          {Math.round(scale * 100)}%
        </button>
        <button
          type="button"
          onClick={handleZoomIn}
          className="px-3 py-2 text-sm bg-surface-tertiary hover:bg-surface-elevated active:bg-surface-active active:scale-95 text-text-primary rounded transition-transform cursor-pointer md:px-2 md:py-1 md:text-xs"
          title="Zoom in"
        >
          +
        </button>
        <div className="w-px h-6 bg-surface-elevated mx-1 md:h-4" />
        <button
          type="button"
          onClick={onClose}
          className="px-3 py-2 text-sm bg-surface-tertiary hover:bg-surface-elevated active:bg-surface-active active:scale-95 text-text-primary rounded transition-transform cursor-pointer md:px-2 md:py-1 md:text-xs"
          title="Close (Esc)"
        >
          ✕
        </button>
      </div>
    </div>
  );
};

const FullscreenImageViewer = memo(FullscreenImageViewerComponent);
FullscreenImageViewer.displayName = 'FullscreenImageViewer';

export default FullscreenImageViewer;
