import { formatBytes, formatBytesAsText } from '@/components/history/history-utils';

interface RawBytesExpandedProps {
  data: Uint8Array;
}

export default function RawBytesExpanded({ data }: RawBytesExpandedProps) {
  return (
    <>
      <div>
        <div className="text-xs text-text-label mb-1">Hex ({data.length} bytes):</div>
        <div className="bg-surface-primary p-2 rounded font-mono text-xs text-accent-success overflow-x-auto max-h-64 overflow-y-auto">
          {formatBytes(data, data.length)}
        </div>
      </div>

      <div>
        <div className="text-xs text-text-label mb-1">ASCII ({Math.min(data.length, 256)} chars):</div>
        <div className="bg-surface-primary p-2 rounded font-mono text-xs text-accent-info overflow-x-auto">
          {formatBytesAsText(data, 256)}
          {data.length > 256 && '...'}
        </div>
      </div>
    </>
  );
}
