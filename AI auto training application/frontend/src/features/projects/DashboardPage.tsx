import { Link } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Card, CardBody } from '../../components/Card';
import { FullSpinner } from '../../components/Spinner';
import { PageHeader } from '../../components/PageHeader';
import { StatusPill } from '../../components/StatusPill';
import { timeAgo } from '../../lib/format';
import { useProjects } from './api';

export function DashboardPage() {
  const { data, isLoading, error } = useProjects();

  return (
    <div>
      <PageHeader
        title="Projects"
        subtitle="All training projects in one place."
        action={
          <Link to="/projects/new">
            <Button>New project</Button>
          </Link>
        }
      />

      {isLoading && <FullSpinner label="Loading projects" />}
      {error && (
        <Card>
          <CardBody>
            <p className="text-sm text-red-700">Failed to load projects: {String(error)}</p>
          </CardBody>
        </Card>
      )}

      {data && data.items.length === 0 && (
        <Card>
          <CardBody className="text-center">
            <p className="text-sm text-slate-600">No projects yet.</p>
            <Link to="/projects/new" className="mt-3 inline-block">
              <Button>Create your first project</Button>
            </Link>
          </CardBody>
        </Card>
      )}

      {data && data.items.length > 0 && (
        <Card>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr className="text-left text-[11px] font-medium uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-2">Name</th>
                  <th className="px-4 py-2">Model</th>
                  <th className="px-4 py-2">Task</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Created</th>
                  <th className="px-4 py-2">Updated</th>
                  <th className="px-4 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {data.items.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link
                        to={`/projects/${p.id}`}
                        className="font-medium text-slate-900 hover:text-blue-600 hover:underline"
                      >
                        {p.name}
                      </Link>
                      {p.description ? (
                        <div className="mt-0.5 line-clamp-1 text-xs text-slate-500">
                          {p.description}
                        </div>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-xs uppercase tracking-wider text-slate-600">
                      {p.model_family}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600">{p.task_type}</td>
                    <td className="px-4 py-3">
                      <StatusPill status={p.status} />
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">{timeAgo(p.created_at)}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{timeAgo(p.updated_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to={`/projects/${p.id}`}
                        className="text-xs font-medium text-blue-600 hover:underline"
                      >
                        Open →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
