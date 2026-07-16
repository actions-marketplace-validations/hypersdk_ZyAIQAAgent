/**
 * API contract runner — validate REST endpoints against their OpenAPI schema,
 * and run multi-step API workflows (create → poll-until-state → delete).
 *
 * Uses Playwright's APIRequestContext (auth headers, cookies, TLS) plus a
 * self-contained JSON-Schema validator (the OpenAPI subset real APIs use) —
 * no external npm deps, matching the repo's Pillow-over-pixelmatch philosophy.
 *
 * Usage: node api-contract.mjs <configJsonFile> <outDir>
 *   config: { base, spec (url | inline object), mode: 'spec'|'workflow',
 *             auth: {type, token, apiKey, header, login:{url,body,tokenPath,userField,passField,user,pass}},
 *             workflow: [step...], include_writes, insecure, path_params, selected_paths, max_endpoints }
 * Progress → stderr, result JSON → stdout.
 */

import { request } from '@playwright/test';
import fs from 'fs';

const cfgFile = process.argv[2];
const outDir = process.argv[3];
if (!cfgFile) { console.error('Usage: node api-contract.mjs <configJsonFile> <outDir>'); process.exit(2); }
const cfg = JSON.parse(fs.readFileSync(cfgFile, 'utf-8'));
const base = (cfg.base || '').replace(/\/$/, '');
const emit = (m) => console.error(m);

// ── minimal JSON-Schema validator (OpenAPI 3 subset) ──
function resolveRef(ref, root) {
  if (!ref.startsWith('#/')) return null;
  let node = root;
  for (const part of ref.slice(2).split('/')) {
    node = node?.[decodeURIComponent(part.replace(/~1/g, '/').replace(/~0/g, '~'))];
    if (node == null) return null;
  }
  return node;
}
function typeOf(v) {
  if (v === null) return 'null';
  if (Array.isArray(v)) return 'array';
  if (Number.isInteger(v)) return 'integer';
  return typeof v === 'number' ? 'number' : typeof v;
}
function typeOk(want, got) {
  if (want === 'number') return got === 'number' || got === 'integer';
  return want === got;
}
function validate(schema, data, root, path = '$', errs = [], depth = 0) {
  if (!schema || depth > 25) return errs;
  if (schema.$ref) {
    const r = resolveRef(schema.$ref, root);
    if (!r) { errs.push(`${path}: unresolved $ref ${schema.$ref}`); return errs; }
    return validate(r, data, root, path, errs, depth + 1);
  }
  for (const key of ['allOf']) if (schema[key]) schema[key].forEach((s) => validate(s, data, root, path, errs, depth + 1));
  for (const key of ['oneOf', 'anyOf']) {
    if (schema[key]) {
      const ok = schema[key].some((s) => validate(s, data, root, path, [], depth + 1).length === 0);
      if (!ok) errs.push(`${path}: matches none of ${key}`);
    }
  }
  if (data === null) {
    if (schema.nullable) return errs;
    if (schema.type && schema.type !== 'null') errs.push(`${path}: null but expected ${schema.type}`);
    return errs;
  }
  const t = typeOf(data);
  if (schema.type && !typeOk(schema.type, t)) { errs.push(`${path}: expected ${schema.type}, got ${t}`); return errs; }
  if (schema.enum && !schema.enum.some((e) => JSON.stringify(e) === JSON.stringify(data)))
    errs.push(`${path}: ${JSON.stringify(data)} not in enum`);
  if (t === 'object' && schema.properties) {
    for (const req of schema.required || []) if (!(req in data)) errs.push(`${path}.${req}: required property missing`);
    for (const [k, v] of Object.entries(data)) if (schema.properties[k]) validate(schema.properties[k], v, root, `${path}.${k}`, errs, depth + 1);
  }
  if (t === 'array' && schema.items) data.forEach((it, i) => validate(schema.items, it, root, `${path}[${i}]`, errs, depth + 1));
  return errs;
}

function dotGet(obj, dotted) {
  return dotted.split('.').reduce((o, k) => (o == null ? o : o[/^\d+$/.test(k) ? Number(k) : k]), obj);
}
function interpolate(str, vars) {
  return typeof str === 'string' ? str.replace(/\{\{(\w+)\}\}/g, (_, k) => (k in vars ? vars[k] : `{{${k}}}`)) : str;
}
function interpolateDeep(v, vars) {
  if (typeof v === 'string') return interpolate(v, vars);
  if (Array.isArray(v)) return v.map((x) => interpolateDeep(x, vars));
  if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, val]) => [k, interpolateDeep(val, vars)]));
  return v;
}

async function buildAuthHeaders(ctx, auth) {
  const headers = {};
  if (!auth) return headers;
  if (auth.token) headers['Authorization'] = `Bearer ${auth.token}`;
  if (auth.apiKey) headers[auth.header || 'x-api-key'] = auth.apiKey;
  if (auth.login && auth.login.url) {
    // POST credentials, extract the token from the response (apiKey-first then user/pass shape)
    const body = auth.login.body || { [auth.login.userField || 'username']: auth.login.user, [auth.login.passField || 'password']: auth.login.pass };
    try {
      const resp = await ctx.post(auth.login.url, { data: body });
      const json = await resp.json().catch(() => ({}));
      const token = dotGet(json, auth.login.tokenPath || 'token') || json.access_token || json.token;
      if (token) { headers['Authorization'] = `Bearer ${token}`; emit(`api: logged in, token acquired`); }
      else emit(`api: login returned no token (status ${resp.status()})`);
    } catch (e) { emit(`api: login failed — ${e}`); }
  }
  return headers;
}

function concretizeParams(path, map) {
  // OpenAPI {param} and colon :param both supported
  return path.replace(/\{(\w+)\}|:(\w+)/g, (_, a, b) => {
    const name = a || b;
    return map[name] || defaultParam(name);
  });
}
function defaultParam(name) {
  const n = name.toLowerCase();
  if (/ns|namespace/.test(n)) return 'default';
  if (/id/.test(n)) return 'x';
  return 'test';
}

async function loadSpec(spec, ctx) {
  if (typeof spec === 'object') return spec;
  if (typeof spec === 'string' && /^https?:/.test(spec)) {
    const resp = await ctx.get(spec);
    return resp.json();
  }
  throw new Error('spec must be an OpenAPI object or an http(s) URL');
}

const SAFE = ['get'];
const WRITE = ['post', 'put', 'patch', 'delete'];

async function runSpecMode(ctx, spec, root) {
  const methods = cfg.include_writes ? [...SAFE, ...WRITE] : SAFE;
  const paramMap = cfg.path_params || {};
  const results = [];
  const paths = spec.paths || {};
  const wanted = cfg.selected_paths && cfg.selected_paths.length ? new Set(cfg.selected_paths) : null;
  let count = 0;
  const cap = cfg.max_endpoints || 60;
  for (const [rawPath, ops] of Object.entries(paths)) {
    if (wanted && !wanted.has(rawPath)) continue;
    for (const [method, op] of Object.entries(ops)) {
      if (!methods.includes(method.toLowerCase())) continue;
      if (count >= cap) { emit(`api: endpoint cap ${cap} reached`); break; }
      count++;
      const path = concretizeParams(rawPath, paramMap);
      const t0 = Date.now();
      let status = 0, ok = false, schemaErrs = [], note = '';
      try {
        const resp = await ctx.fetch(base + path, { method: method.toUpperCase() });
        status = resp.status();
        const declared = op.responses || {};
        const codeKey = String(status);
        const matchKey = declared[codeKey] ? codeKey : declared[`${String(status)[0]}XX`] ? `${String(status)[0]}XX` : declared.default ? 'default' : null;
        ok = matchKey != null || (status >= 200 && status < 300);
        const schema = matchKey && declared[matchKey]?.content?.['application/json']?.schema;
        if (schema && status >= 200 && status < 300) {
          const bodyJson = await resp.json().catch(() => undefined);
          if (bodyJson !== undefined) {
            schemaErrs = validate(schema, bodyJson, root).slice(0, 8);
            if (schemaErrs.length) ok = false;
          }
        } else if (!matchKey) {
          note = `status ${status} not declared`;
        }
      } catch (e) { note = String(e).slice(0, 120); }
      const r = { method: method.toUpperCase(), path, status, ok, schema_errors: schemaErrs, note, latency_ms: Date.now() - t0 };
      results.push(r);
      emit(`${ok ? '✓' : '✗'} ${r.method} ${path} → ${status}${schemaErrs.length ? ` (${schemaErrs.length} schema err)` : ''}`);
    }
  }
  return results;
}

async function runWorkflowMode(ctx) {
  const vars = {};
  const steps = [];
  for (let i = 0; i < (cfg.workflow || []).length; i++) {
    const raw = cfg.workflow[i];
    const step = interpolateDeep(raw, vars);
    const method = (step.method || 'GET').toUpperCase();
    const path = step.path;
    const desc = step.name || `${method} ${path}`;
    emit(`▶ step ${i + 1}: ${desc}`);
    const t0 = Date.now();
    let status = 0, ok = true, error = '';
    try {
      if (step.poll) {
        // repeat until json_path === value, or timeout
        const deadline = Date.now() + (step.poll.timeout_ms || 30000);
        let last;
        for (;;) {
          const resp = await ctx.fetch(base + path, { method });
          status = resp.status();
          last = await resp.json().catch(() => ({}));
          const cur = dotGet(last, step.poll.json_path);
          if (String(cur) === String(step.poll.equals)) break;
          if (Date.now() > deadline) { ok = false; error = `poll timeout: ${step.poll.json_path}=${cur}, wanted ${step.poll.equals}`; break; }
          await new Promise((r) => setTimeout(r, step.poll.interval_ms || 2000));
        }
        Object.assign(vars, extractVars(step.extract, last));
      } else {
        const opts = { method };
        if (step.body != null) opts.data = step.body;
        if (step.headers) opts.headers = step.headers;
        const resp = await ctx.fetch(base + path, opts);
        status = resp.status();
        const json = await resp.json().catch(() => undefined);
        if (step.expect) {
          if (step.expect.status != null && status !== step.expect.status) { ok = false; error = `expected status ${step.expect.status}, got ${status}`; }
          if (ok && step.expect.json_path != null) {
            const got = dotGet(json, step.expect.json_path);
            if (String(got) !== String(step.expect.equals)) { ok = false; error = `${step.expect.json_path}=${got}, wanted ${step.expect.equals}`; }
          }
          if (ok && step.expect.schema) {
            const errs = validate(step.expect.schema, json, step.expect.schema).slice(0, 8);
            if (errs.length) { ok = false; error = `schema: ${errs.join('; ')}`; }
          }
        } else if (status >= 400) { ok = false; error = `status ${status}`; }
        if (json !== undefined) Object.assign(vars, extractVars(step.extract, json));
      }
    } catch (e) { ok = false; error = String(e).slice(0, 200); }
    steps.push({ n: i + 1, desc, method, path, status, ok, error, latency_ms: Date.now() - t0 });
    emit(`${ok ? '✓' : '✗'} step ${i + 1}: ${desc} → ${status}${error ? ` — ${error}` : ''}`);
    if (!ok && cfg.stop_on_fail !== false) break;
  }
  return steps;
}
function extractVars(extract, json) {
  const out = {};
  for (const [k, jp] of Object.entries(extract || {})) out[k] = dotGet(json, jp);
  return out;
}

async function main() {
  if (outDir) fs.mkdirSync(outDir, { recursive: true });
  const ctx = await request.newContext({ ignoreHTTPSErrors: cfg.insecure === true || process.env.ZYVOR_IGNORE_HTTPS_ERRORS === 'true' });
  const authHeaders = await buildAuthHeaders(ctx, cfg.auth);
  const authedCtx = await request.newContext({
    ignoreHTTPSErrors: cfg.insecure === true || process.env.ZYVOR_IGNORE_HTTPS_ERRORS === 'true',
    extraHTTPHeaders: authHeaders,
  });

  let out;
  if (cfg.mode === 'workflow') {
    const steps = await runWorkflowMode(authedCtx);
    const passed = steps.filter((s) => s.ok).length;
    out = { mode: 'workflow', base, steps, passed, failed: steps.length - passed, total: steps.length };
  } else {
    const spec = await loadSpec(cfg.spec, authedCtx);
    const endpoints = await runSpecMode(authedCtx, spec, spec);
    const passed = endpoints.filter((e) => e.ok).length;
    out = { mode: 'spec', base, endpoints, passed, failed: endpoints.length - passed, total: endpoints.length };
  }
  await ctx.dispose();
  await authedCtx.dispose();
  process.stdout.write(JSON.stringify(out));
}

main().catch((e) => { console.error(e); process.exit(1); });
