import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

describe('Runtime: NDW Frontend Library', () => {
    // Try to find the file relative to the execution root
    const ndwPath = './static/ts-src/ndw.ts';
    const content = fs.readFileSync(ndwPath, 'utf8');

    it('validates loop callback parameter', () => {
        // Matches test_ndw_runtime_has_loop_validation
        const hasValidation = /typeof.*fn.*!==.*['"]function['"]/.test(content) || 
                             /typeof.*fn.*===.*['"]function['"]/.test(content);
        expect(hasValidation).toBe(true);
    });

    it('warns about missing dt parameter in loop', () => {
        // Matches test_ndw_runtime_warns_about_dt_parameter
        expect(content).toContain('fn.length');
        expect(content.toLowerCase()).toContain('warn');
        expect(content).toContain('dt');
    });

    it('integrates with error overlay in _frame', () => {
        // Matches test_ndw_runtime_has_error_overlay_integration
        expect(content).toContain('try');
        expect(content).toContain('catch');
        expect(content).toContain('__NDW_showSnippetErrorOverlay');
    });

    it('provides backward-compatible canvas aliases', () => {
        // Matches test_ndw_makecanvas_has_compatibility_aliases
        const hasAliases = content.includes('.element = c') || content.includes('element: c') ||
                          content.includes('.canvas = c') || content.includes('canvas: c');
        expect(hasAliases).toBe(true);
    });

    it('sets ctx and dpr on canvas objects', () => {
        // Matches test_ndw_makecanvas_sets_ctx_and_dpr
        expect(content).toMatch(/ctx:|c\.ctx\s*=/);
        expect(content).toMatch(/dpr:|c\.dpr\s*=/);
    });

    it('handles keyboard and pointer tracking', () => {
        // Matches test_ndw_has_keyboard_tracking and test_ndw_has_pointer_tracking
        expect(content).toContain('_keys');
        expect(content.toLowerCase()).toContain('keydown');
        expect(content).toMatch(/isDown\s*\(.*key/i);
        expect(content.toLowerCase()).toContain('pointer');
        expect(content.toLowerCase()).toContain('pointerdown');
    });

    it('calculates dt and passes it to loop frames', () => {
        // Matches test_ndw_frame_passes_dt_to_callback
        const hasDtCalc = /dt\s*=.*now.*-.*last/i.test(content) || 
                          /const\s+dt.*=.*\(.*now.*-/i.test(content);
        expect(hasDtCalc).toBe(true);
    });
});
