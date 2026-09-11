import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Build output and the Python venv are not lintable source.
  globalIgnores([
    '.next/**', 'out/**', 'build/**', 'dist/**', 'next-env.d.ts',
    '.venv/**', '.pytest-tmp*/**', '.pytest_cache/**', '.wrangler/**', '.vinext/**',
  ]),
]);

export default eslintConfig;
