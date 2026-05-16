import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { HealthGauge } from '../HealthGauge';

describe('HealthGauge', () => {
  it('renders the score', () => {
    render(<HealthGauge score={72} />);
    expect(screen.getByText('72')).toBeInTheDocument();
  });

  it('renders em-dash for null', () => {
    render(<HealthGauge score={null} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('clamps above 100', () => {
    render(<HealthGauge score={150} />);
    expect(screen.getByText('100')).toBeInTheDocument();
  });

  it('clamps below 0', () => {
    render(<HealthGauge score={-5} />);
    expect(screen.getByText('0')).toBeInTheDocument();
  });

  it('rounds to integer for the displayed text', () => {
    render(<HealthGauge score={72.6} />);
    expect(screen.getByText('73')).toBeInTheDocument();
  });
});
