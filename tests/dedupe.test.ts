import { describe, it, expect } from 'vitest';
import { KVDedupe } from '../src/dedupe';

describe('Integrity: KVDedupe', () => {
    it('skeletonize strips non-structural content', () => {
        // Logic ported from test_structural_dedupe.py
        const dedupe = new KVDedupe({} as any); // Mock KV not needed for this method
        const html = `
        <div class="p-6 bg-slate-100">
            <!-- Comment -->
            <h1 id="title" style="color:red">Hello World</h1>
            <p class="mt-2 text-slate-700">This is a test paragraph.</p>
            <script>console.log('hi');</script>
            <style>.foo { color: blue; }</style>
        </div>
        `;
        const skeleton = dedupe.skeletonize(html);
        
        // Structural elements should remain (whitespace stripped)
        expect(skeleton).toContain('<div');
        expect(skeleton).toContain('class="p-6bg-slate-100"'); // Whitespace stripped
        expect(skeleton).toContain('<h1');
        expect(skeleton).toContain('<p');
        
        // Non-structural content should be gone
        expect(skeleton).not.toContain('Comment');
        expect(skeleton).not.toContain('Hello World');
        expect(skeleton).not.toContain('paragraph');
        expect(skeleton).not.toContain('console.log');
        expect(skeleton).not.toContain('.foo');
    });

    it('signature identical for layout twins', async () => {
        const dedupe = new KVDedupe({} as any);
        const doc1 = {
            "kind": "full_page_html",
            "html": '<div class="card"><h1>Title 1</h1><p>Text 1</p></div>'
        };
        const doc2 = {
            "kind": "full_page_html",
            "html": '<div class="card"><h1>Different Title</h1><p>Other text</p></div>'
        };
        const sig1 = await dedupe.signatureFor(doc1);
        const sig2 = await dedupe.signatureFor(doc2);
        expect(sig1).toBe(sig2);
        expect(sig1.length).toBe(64); // SHA-256 hex
    });

    it('signature different for distinct layouts', async () => {
        const dedupe = new KVDedupe({} as any);
        const doc1 = { kind: "full_page_html", html: '<div class="card"><h1>Title</h1></div>' };
        const doc2 = { kind: "full_page_html", html: '<section class="hero"><h1>Title</h1></section>' };
        const sig1 = await dedupe.signatureFor(doc1);
        const sig2 = await dedupe.signatureFor(doc2);
        expect(sig1).not.toBe(sig2);
    });
});
