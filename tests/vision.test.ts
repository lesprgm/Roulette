import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as llm from '../src/llm';
import * as utils from '../src/utils';

// We mock utils to override getDesignMatrixB64
vi.mock('../src/utils', async (importOriginal) => {
    const actual = await importOriginal<typeof import('../src/utils')>();
    return {
        ...actual,
        getDesignMatrixB64: vi.fn(),
    };
});

describe('Logic: Vision Grounding', () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;

    beforeEach(() => {
        mockFetch.mockReset();
        vi.clearAllMocks();
    });

    const mockEnv = {
        GEMINI_API_KEY: 'gemini-key',
        DEDUPE_KV: { get: async () => null, put: async () => {} } as any,
        ASSETS_KV: { get: async () => '0', put: async () => {} } as any
    };

    it('callGemini includes image part when design matrix is available', async () => {
        // Mock getDesignMatrixB64 from utils
        vi.mocked(utils.getDesignMatrixB64).mockResolvedValue('fake-base64-data');

        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({
                candidates: [{ content: { parts: [{ text: '{"kind": "full_page_html", "html": "OK"}' }] } }]
            })
        });

        await llm.generatePage(mockEnv as any, 123);

        expect(mockFetch).toHaveBeenCalled();
        const init = JSON.parse(mockFetch.mock.calls[0][1].body);
        const parts = init.contents[0].parts;

        // Verify multimodal payload
        expect(parts).toHaveLength(2);
        expect(parts[1].inlineData.data).toBe('fake-base64-data');
    });

    it('callGemini omits image part when design matrix is missing', async () => {
        vi.mocked(utils.getDesignMatrixB64).mockResolvedValue(null);

        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({
                candidates: [{ content: { parts: [{ text: '{"kind": "full_page_html", "html": "OK"}' }] } }]
            })
        });

        await llm.generatePage(mockEnv as any, 456);

        const init = JSON.parse(mockFetch.mock.calls[0][1].body);
        const parts = init.contents[0].parts;

        expect(parts).toHaveLength(1);
    });
});
