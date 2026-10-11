import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'package.json'));
let ts;
const candidates = [process.env.TYPESCRIPT_PATH, path.resolve(path.dirname(process.execPath), '../lib/node_modules/typescript'), 'typescript'].filter(Boolean);
for (const candidate of candidates) { try { ts = require(candidate); break; } catch {} }
if (!ts) throw new Error('TypeScript is required. Set TYPESCRIPT_PATH or install the repository dev dependencies.');
const nodeTypesCandidates = [process.env.NODE_TYPES_PATH,
  path.resolve(path.dirname(process.execPath), '../lib/node_modules/ts-node/node_modules/@types'),
  path.resolve(process.cwd(), 'node_modules/@types')].filter(Boolean);
const typeRoots = nodeTypesCandidates.filter((p) => fs.existsSync(path.join(p, 'node')));
if (!typeRoots.length) throw new Error('Node type declarations unavailable; set NODE_TYPES_PATH to an @types directory.');
const build = path.join(root, '.offline-build');
fs.mkdirSync(path.join(build, 'src'), { recursive: true });
const hashes = {
  'fixed.ts':'dcd8a1d88e1642e73fe55f7ae08187f8c0f7617a',
  'identity.ts':'da06c22cdb8509e541977365d55e7ee6ce5ad6d5',
  'types.ts':'626bb830ac241a2140bdc9db488374120c72832d',
  'verifier.ts':'5bf79b1d6622be36ffeec44ccb5600adc3ddc3e7',
};
for (const [name, expected] of Object.entries(hashes)) {
  const bytes = fs.readFileSync(path.join(root, 'evidence', name));
  const hash = createHash('sha1').update(Buffer.from(`blob ${bytes.length}\0`)).update(bytes).digest('hex');
  if (hash !== expected) throw new Error(`Retained original source hash mismatch: ${name}`);
  fs.writeFileSync(path.join(build, 'src', name), bytes);
}
fs.copyFileSync(path.join(root, 'overlay/packages/execution/src/buy-order-budget.ts'), path.join(build, 'src/buy-order-budget.ts'));
const test = fs.readFileSync(path.join(root, 'overlay/packages/execution/test/buy-order-budget.test.ts'), 'utf8')
  .replace('from "vitest"', 'from "node:test"')
  .replace('from "../src/buy-order-budget.js"', 'from "./buy-order-budget.js"');
fs.writeFileSync(path.join(build, 'src/buy-order-budget.test.ts'), test);
fs.writeFileSync(path.join(build, 'src/domain-index.ts'), 'export * from "./fixed.js";\nexport * from "./identity.js";\n');
fs.writeFileSync(path.join(build, 'src/opportunity-index.ts'), 'export * from "./verifier.js";\nexport * from "./types.js";\n');
fs.writeFileSync(path.join(build, 'package.json'), '{"type":"module"}\n');
const config = {
  compilerOptions: {
    target:'ES2022', module:'NodeNext', moduleResolution:'NodeNext', strict:true,
    noUncheckedIndexedAccess:true, noUnusedLocals:true, noUnusedParameters:true,
    esModuleInterop:true, skipLibCheck:true, outDir:'dist', rootDir:'src',
    baseUrl:'.', paths:{'@pmh/domain':['src/domain-index.ts'],'@pmh/opportunity':['src/opportunity-index.ts']},
    typeRoots, types:['node']
  }, include:['src/**/*.ts']
};
fs.writeFileSync(path.join(build, 'tsconfig.json'), JSON.stringify(config, null, 2));
const parsed = ts.parseJsonConfigFileContent(config, ts.sys, build);
const program = ts.createProgram(parsed.fileNames, parsed.options);
const diagnostics = ts.getPreEmitDiagnostics(program);
const log = ts.formatDiagnosticsWithColorAndContext(diagnostics, {
  getCurrentDirectory: () => build, getCanonicalFileName: (f) => f, getNewLine: () => '\n'
});
fs.writeFileSync(path.join(root,'evidence/typecheck.log'), log || `PASS: focused source + identical test bodies; TypeScript ${ts.version}\n`);
if (diagnostics.length) { console.error(log); process.exit(1); }
program.emit();
for (const name of ['domain','opportunity']) {
  const moduleDir = path.join(build, 'dist/node_modules/@pmh', name);
  fs.mkdirSync(moduleDir, { recursive:true });
  fs.writeFileSync(path.join(moduleDir, 'package.json'), '{"type":"module","exports":"./index.js"}');
  fs.writeFileSync(path.join(moduleDir, 'index.js'), `export * from '../../../${name}-index.js';\n`);
}
const results = spawnSync(process.execPath, ['--test','--test-reporter=tap',path.join(build,'dist/buy-order-budget.test.js'),path.join(root,'offline/payoff-selection.test.mjs')], { encoding:'utf8', timeout:120000 });
fs.writeFileSync(path.join(root,'evidence/native-tests.tap'), (results.stdout || '') + (results.stderr || ''));
process.stdout.write(results.stdout || ''); process.stderr.write(results.stderr || '');
const count = (key) => Number(new RegExp(`# ${key} (\\d+)`).exec(results.stdout || '')?.[1] || 0);
const status = { scope:'focused TypeScript sources + retained original fixed-point/verifier + extracted production selection blocks',
  node: process.version, typescript:ts.version, original_source_blobs:hashes,
  full_repository_vitest:'NOT_RUN', full_workspace_typecheck:'NOT_RUN', remote_commit:'NOT_MEASURED_BY_OFFLINE_RUNNER',
  tests:count('tests'), pass:count('pass'), fail:count('fail'), exit_code:results.status,
  error:results.error?.message || null,
  runner_adaptation:'Only vitest describe/it import changed to node:test; test bodies and production helper unchanged.' };
fs.writeFileSync(path.join(root,'evidence/validation-results.json'),JSON.stringify(status,null,2)+'\n');
process.exit(results.status ?? 1);
