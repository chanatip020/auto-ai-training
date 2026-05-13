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
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((p) => (
            <Link key={p.id} to={`/projects/${p.id}`} className="group">
              <Card className="transition group-hover:border-blue-400 group-hover:shadow-md">
                <CardBody>
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="truncate text-sm font-semibold text-slate-900">
                      {p.name}
                    </h3>
                    <StatusPill status={p.status} />
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs text-slate-500">
                    {p.description || '— no description —'}
                  </p>
                  <div className="mt-4 flex items-center justify-between text-[11px] text-slate-500">
                    <span className="uppercase tracking-wider">{p.model_family} / {p.task_type}</span>
                    <span>Created {timeAgo(p.created_at)}</span>
                  </div>
                </CardBody>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
