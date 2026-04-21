import { motors_mirroring } from '@/api/proto.js';

interface MirroringExpandedProps {
  data: motors_mirroring.RxEnvelope;
}

export default function MirroringExpanded({ data }: MirroringExpandedProps) {
  return (
    <div>
      <div className="text-xs text-text-label mb-1">Motors Mirroring RxEnvelope:</div>
      <div className="bg-surface-primary p-2 rounded text-xs space-y-1">
        <div className="text-accent-secondary">Type: Motors Mirroring</div>
        {data.state?.mirroring && data.state.mirroring.length > 0 && (
          <div className="text-accent-data">
            Mirroring Configurations: {data.state.mirroring.length}
          </div>
        )}
      </div>
    </div>
  );
}
