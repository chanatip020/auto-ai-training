import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from '../Button';

describe('Button', () => {
  it('renders its children', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
  });

  it('calls onClick when clicked', async () => {
    const fn = vi.fn();
    render(<Button onClick={fn}>Tap</Button>);
    await userEvent.click(screen.getByRole('button'));
    expect(fn).toHaveBeenCalledOnce();
  });

  it('is disabled when loading', () => {
    const fn = vi.fn();
    render(<Button loading onClick={fn}>Saving…</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it("doesn't fire onClick while disabled", async () => {
    const fn = vi.fn();
    render(<Button disabled onClick={fn}>No</Button>);
    await userEvent.click(screen.getByRole('button'));
    expect(fn).not.toHaveBeenCalled();
  });

  it('applies the danger variant class', () => {
    render(<Button variant="danger">Delete</Button>);
    const btn = screen.getByRole('button');
    expect(btn.className).toMatch(/red/);
  });
});
