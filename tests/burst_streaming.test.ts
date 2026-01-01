import { describe, it, expect } from 'vitest';
import { extractCompletedObjects } from '../src/utils';

describe('Logic: Burst Streaming Parser', () => {
    it('extracts completed objects from array', () => {
        // Test 1: Full array at once
        let text = '[{"id": 1}, {"id": 2}, {"id": 3}]';
        let objs = extractCompletedObjects(text);
        expect(objs).toHaveLength(3);
        expect(objs[0].id).toBe(1);
        expect(objs[2].id).toBe(3);

        // Test 2: Partial array (first object complete)
        text = '[{"id": 1}, {"id": 2}, {"id":';
        objs = extractCompletedObjects(text);
        expect(objs).toHaveLength(2);
        expect(objs[1].id).toBe(2);

        // Test 3: Array with nested objects
        text = '[{"a": {"b": 1}}, {"c": 2}]';
        objs = extractCompletedObjects(text);
        expect(objs).toHaveLength(2);
        expect(objs[0].a.b).toBe(1);

        // Test 4: String with escaped braces
        text = '[{"msg": "hello } world"}, {"id": 1}]';
        objs = extractCompletedObjects(text);
        expect(objs).toHaveLength(2);
        expect(objs[0].msg).toBe("hello } world");
    });
});
