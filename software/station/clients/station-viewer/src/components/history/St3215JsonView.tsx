import React, { memo, useMemo } from 'react';
import { st3215 } from '@/api/proto.js';
import { getSt3215JsonData } from '@/components/history/history-utils';

interface St3215JsonViewProps {
  data: st3215.InferenceState;
}

const St3215JsonView = memo(function St3215JsonView({ data }: St3215JsonViewProps) {
  const { jsonString, hexdumps } = useMemo(() => getSt3215JsonData(data), [data]);

  const parts = useMemo(() => {
    const result: React.ReactNode[] = [];
    let lastIndex = 0;

    const placeholders = hexdumps
      .map((p) => ({
        placeholder: p.placeholder,
        index: jsonString.indexOf(`"${p.placeholder}"`)
      }))
      .filter((p) => p.index !== -1)
      .sort((a, b) => a.index - b.index);

    for (const p of placeholders) {
      result.push(jsonString.substring(lastIndex, p.index));
      const hexdump = hexdumps.find((h) => h.placeholder === p.placeholder);
      result.push(
        <span key={p.placeholder} className="text-accent-success">{hexdump?.content}</span>
      );
      lastIndex = p.index + `"${p.placeholder}"`.length;
    }
    result.push(jsonString.substring(lastIndex));
    return result;
  }, [jsonString, hexdumps]);

  return (
    <div>
      <div className="text-xs text-text-label mb-1">ST3215 InferenceState JSON:</div>
      <div className="bg-surface-primary p-2 rounded text-xs font-mono text-accent-danger overflow-x-auto max-h-64 overflow-y-auto">
        <pre>{parts}</pre>
      </div>
    </div>
  );
});

export default St3215JsonView;
