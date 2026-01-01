import { describe, it, expect } from 'vitest';
import { isValidPage } from '../src/utils';

describe('Validation: Schema', () => {
    it('validates correct full_page_html', () => {
        const page = { kind: 'full_page_html', html: '<div></div>', title: 'Test' };
        expect(isValidPage(page)).toBe(true);
    });

    it('validates partial page as invalid', () => {
        const page = { kind: 'full_page_html' }; // missing html
        expect(isValidPage(page)).toBe(false);
    });

    it('validates garbage as invalid', () => {
        expect(isValidPage(null)).toBe(false);
        expect(isValidPage('string')).toBe(false);
        expect(isValidPage({})).toBe(false);
    });
});
