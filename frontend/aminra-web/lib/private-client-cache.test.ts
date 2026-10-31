import { beforeEach, expect, it } from 'vitest';
import { clearPrivateClientData, privateCacheKey } from './private-client-cache';
beforeEach(() => localStorage.clear());
it('separates identical filenames across actors and tenants, including filename normalization collisions', () => {
 const keys = [privateCacheKey('a','x','report','résumé.pdf'),privateCacheKey('b','x','report','résumé.pdf'),privateCacheKey('a','y','report','résumé.pdf'),privateCacheKey('a','x','report','r_sum_.pdf')];
 expect(new Set(keys).size).toBe(4);expect(privateCacheKey(undefined,'x','report')).toBeNull();expect(privateCacheKey('a',null,'report')).toBeNull();
});
it('purges private reports and unattributable legacy records while preserving unrelated preferences', () => {
 for (const key of [privateCacheKey('a','x','report','private.pdf')!, 'aminra_full_report_private.pdf','aminra_file_versions_private.pdf','aminra_eval_a']) localStorage.setItem(key,'synthetic secret');
 localStorage.setItem('aminra_lang','vi');localStorage.setItem('unrelated-app','retain');clearPrivateClientData(localStorage);
 expect(Object.keys(localStorage).sort()).toEqual(['aminra_lang','unrelated-app']);
});
