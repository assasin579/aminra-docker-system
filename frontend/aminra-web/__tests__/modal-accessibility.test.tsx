import React from 'react';
import { describe, test, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Modal from '@/components/Modal';
describe('Modal keyboard boundary', () => {
    test('names dialog, traps both Tab directions and restores the trigger', async () => {
        const trigger = document.createElement('button');
        document.body.append(trigger);
        trigger.focus();
        const { unmount } = render(<Modal ariaLabel="Gửi hồ sơ"><button>First</button><button>Last</button></Modal>);
        expect(await screen.findByRole('dialog', { name: 'Gửi hồ sơ' })).toBeInTheDocument();
        const first = screen.getByRole('button', { name: 'First' }), last = screen.getByRole('button', { name: 'Last' });
        expect(first).toHaveFocus();
        fireEvent.keyDown(window, { key: 'Tab', shiftKey: true });
        expect(last).toHaveFocus();
        fireEvent.keyDown(window, { key: 'Tab' });
        expect(first).toHaveFocus();
        trigger.focus();
        expect(first).toHaveFocus();
        unmount();
        expect(trigger).toHaveFocus();
        trigger.remove();
    });
    test('only top dialog handles Escape and restores focus to its parent', async () => {
        const parentClose = vi.fn(), childClose = vi.fn();
        const parent = render(<Modal ariaLabel="Parent" onClose={parentClose}><button>Parent button</button></Modal>);
        await screen.findByRole('dialog', { name: 'Parent' });
        const child = render(<Modal ariaLabel="Child" onClose={childClose}><button>Child button</button></Modal>);
        await screen.findByRole('dialog', { name: 'Child' });
        fireEvent.keyDown(window, { key: 'Escape' });
        expect(childClose).toHaveBeenCalledOnce();
        expect(parentClose).not.toHaveBeenCalled();
        child.unmount();
        expect(screen.getByRole('button', { name: 'Parent button' })).toHaveFocus();
        expect(document.body.style.overflow).toBe('hidden');
        parent.unmount();
    });
    test('pending mutation can disable backdrop and Escape dismissal', async () => {
        const close = vi.fn();
        const { rerender } = render(<Modal onClose={close}><button>Save</button></Modal>);
        await screen.findByRole('dialog');
        rerender(<Modal><button>Save</button></Modal>);
        fireEvent.keyDown(window, { key: 'Escape' });
        fireEvent.click(screen.getByRole('dialog'));
        expect(close).not.toHaveBeenCalled();
    });
});
