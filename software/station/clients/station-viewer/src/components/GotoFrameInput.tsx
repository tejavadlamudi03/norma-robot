import { useState, useEffect, useRef, forwardRef, useImperativeHandle } from 'react';

interface GotoFrameInputProps {
  currentFrame: number;
  range: { min: number; max: number };
  onSelectFrame: (frame: number) => void;
  className?: string;
  title?: string;
}

export interface GotoFrameInputRef {
  focus: () => void;
}

function parseInput(value: string, currentFrame: number): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;

  if (trimmed.startsWith('+')) {
    const offset = parseInt(trimmed.slice(1), 10);
    if (isNaN(offset)) return null;
    return currentFrame + offset;
  } else if (trimmed.startsWith('-')) {
    const offset = parseInt(trimmed.slice(1), 10);
    if (isNaN(offset)) return null;
    return currentFrame - offset;
  } else {
    const frame = parseInt(trimmed, 10);
    return isNaN(frame) ? null : frame;
  }
}

const GotoFrameInput = forwardRef<GotoFrameInputRef, GotoFrameInputProps>(
  function GotoFrameInput({ currentFrame, range, onSelectFrame, className = '', title }, ref) {
    const inputRef = useRef<HTMLInputElement>(null);
    const [inputValue, setInputValue] = useState(currentFrame.toString());
    const [error, setError] = useState(false);
    const [isFocused, setIsFocused] = useState(false);

    useImperativeHandle(ref, () => ({
      focus: () => inputRef.current?.focus(),
    }));

    useEffect(() => {
      if (!isFocused) {
        setInputValue(currentFrame.toString());
        setError(false);
      }
    }, [currentFrame, isFocused]);

    const handleFocus = () => {
      setIsFocused(true);
      inputRef.current?.select();
    };

    const handleBlur = () => {
      setIsFocused(false);
      setInputValue(currentFrame.toString());
      setError(false);
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      setInputValue(e.target.value);
      setError(false);
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        const frame = parseInput(inputValue, currentFrame);
        if (frame !== null && frame >= range.min && frame <= range.max) {
          onSelectFrame(frame);
          setIsFocused(false);
          inputRef.current?.blur();
          setError(false);
        } else {
          setError(true);
        }
        e.preventDefault();
      } else if (e.key === 'Escape') {
        setInputValue(currentFrame.toString());
        setError(false);
        setIsFocused(false);
        inputRef.current?.blur();
        e.preventDefault();
      }
    };

    return (
      <input
        ref={inputRef}
        type="text"
        value={inputValue}
        onChange={handleChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        placeholder="Frame # or ±N"
        title={title}
        className={`px-2 py-1 text-xs bg-surface-tertiary text-text-primary rounded border border-border-subtle focus:border-accent-info-deep focus:outline-none font-mono text-center ${error ? 'border-accent-critical' : ''} ${className}`}
      />
    );
  }
);

export default GotoFrameInput;
