import { Link, useParams } from 'react-router-dom';
import { Card, CardBody } from '../../components/Card';
import { PageHeader } from '../../components/PageHeader';

/**
 * Placeholder route reserved for Phase 6 (CVAT integration).
 *
 * Future shape:
 *   1. Pick a saved CVAT connection (from /settings).
 *   2. List the connection's projects / tasks (proxied through our backend).
 *   3. Choose one, click "Import" — our backend triggers a CVAT export +
 *      converts it to YOLO format, landing a new dataset version under
 *      this project.
 */
export function CvatComingSoonPage() {
  const { id = '' } = useParams();
  return (
    <div>
      <PageHeader
        title="Import from CVAT"
        subtitle="Coming in Phase 6"
      />
      <Card>
        <CardBody className="space-y-3 text-sm text-slate-600">
          <p>
            The CVAT import wizard is reserved for Phase 6. The frontend, backend,
            and database all already plan for it:
          </p>
          <ul className="list-disc space-y-1 pl-5 text-xs">
            <li><code>cvat_connections</code> + <code>cvat_imports</code> tables (per design doc).</li>
            <li><code>POST /cvat/connections</code>, <code>GET /cvat/.../projects</code>, <code>GET /cvat/.../tasks</code>, <code>POST /projects/{'{pid}'}/cvat-imports</code>.</li>
            <li>This route, plus type definitions in <code>src/lib/types.ts</code>.</li>
          </ul>
          <p className="text-xs">
            For now, use{' '}
            <Link to={`/projects/${id}/dataset`} className="text-blue-600 hover:underline">
              ZIP upload
            </Link>{' '}
            to ingest a dataset, or open <Link to="/settings" className="text-blue-600 hover:underline">Settings</Link> to see the planned connections UI.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
