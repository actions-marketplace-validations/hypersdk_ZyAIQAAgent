/**
 * Minimal JSON-Schema validator (OpenAPI 3 subset) — no external deps.
 * Handles: type, required, properties, items, enum, nullable, $ref
 * (local #/… pointers), allOf, oneOf, anyOf. Returns an array of error strings.
 */

export function resolveRef(ref, root) {
  if (!ref.startsWith('#/')) return null;
  let node = root;
  for (const part of ref.slice(2).split('/')) {
    node = node?.[decodeURIComponent(part.replace(/~1/g, '/').replace(/~0/g, '~'))];
    if (node == null) return null;
  }
  return node;
}

export function typeOf(v) {
  if (v === null) return 'null';
  if (Array.isArray(v)) return 'array';
  if (Number.isInteger(v)) return 'integer';
  return typeof v === 'number' ? 'number' : typeof v;
}

export function typeOk(want, got) {
  if (want === 'number') return got === 'number' || got === 'integer';
  return want === got;
}

export function validate(schema, data, root, path = '$', errs = [], depth = 0) {
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
  if (t === 'object') {
    // required must be enforced even when `properties` is absent
    for (const req of schema.required || []) if (!(req in data)) errs.push(`${path}.${req}: required property missing`);
    if (schema.properties) {
      for (const [k, v] of Object.entries(data)) if (schema.properties[k]) validate(schema.properties[k], v, root, `${path}.${k}`, errs, depth + 1);
    }
  }
  if (t === 'array' && schema.items) data.forEach((it, i) => validate(schema.items, it, root, `${path}[${i}]`, errs, depth + 1));
  return errs;
}
