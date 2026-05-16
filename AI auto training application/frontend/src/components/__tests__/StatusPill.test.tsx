import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusPill } from '../StatusPill';

describe('StatusPill', () => {
  it('renders the human label for a project status', () => {
    render(<StatusPill status="dataset_uploaded" />);
    expect(screen.getByText('Uploaded')).toBeInTheDocument();
  });

  it('renders the human label for a job status', () => {
    render(<StatusPill status="running" />);
    expect(screen.getByText('Running')).toBeInTheDocument();
  });

  it('applies the right colour class for ready', () => {
    render(<StatusPill status="ready_for_training" />);
    const pill = screen.getByText('Ready');
    expect(pill.className).toMatch(/green/);
  });

  it('applies the right colour class for failed', () => {
    render(<StatusPill status="failed" />);
    const pill = screen.getByText('Failed');
    expect(pill.className).toMatch(/red/);
  });

  it('falls back to the raw value for unknown status', () => {
    // @ts-expect-error testing fallback
    render(<StatusPill status="some_future_status" />);
    expect(screen.getByText('some_future_status')).toBeInTheDocument();
  });
});
