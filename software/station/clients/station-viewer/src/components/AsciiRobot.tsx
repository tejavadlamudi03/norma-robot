import { memo, useEffect, useState } from 'react';

const FRAMES = ['o_o', 'o_o', '-_-', 'o_o', '^_^', 'o_o', 'O_O', 'o_o'];

function AsciiRobotComponent() {
  const [frameIdx, setFrameIdx] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setFrameIdx(i => (i + 1) % FRAMES.length), 500);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex flex-col items-center gap-3 font-mono select-none">
      <pre className="text-text-muted text-sm leading-tight text-center">
        {`  ╭───╮\n  │${FRAMES[frameIdx]}│\n  ╰───╯\n  ─ │ ─\n  ─────`}
      </pre>
      <p className="empty-state-rainbow text-lg">
        connect a robot<span className="blink-cursor">▋</span>
      </p>
    </div>
  );
}

const AsciiRobot = memo(AsciiRobotComponent);
AsciiRobot.displayName = 'AsciiRobot';
export default AsciiRobot;
