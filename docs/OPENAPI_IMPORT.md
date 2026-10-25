# OpenAPI Import (V0.2)

Regression Firewall can derive its HTTP probes from an **OpenAPI 3.x**
document (YAML or JSON), so an API with dozens of endpoints does not need a
hand-written probe list.

## Configure

```yaml
surfaces:
  http:
    base_url: "http://127.0.0.1:{port}"
    server:
      command: ["python", "serve.py"]
    openapi:
      file: openapi.yaml          # resolved relative to this config file
      set: {userId: "1", slug: "example"}   # values for {path} parameters
      methods: [get, post]        # optional filter (default: all found)
```

At config load time the document is read and one probe per operation is
appended to `surfaces.http.probes`. Explicitly listed probes always win on
id conflicts (a warning says so). The generated probes are part of the
config hash: if the OpenAPI document changes between `baseline` and
`check`, the standard config-changed warning fires — re-baseline only if
that was intended.

## Preview before committing

```bash
regression-firewall import-openapi openapi.yaml --set userId=1 --methods get,post
```

prints exactly the probes that would be generated (plus notes). Prefer the
config section over copy-pasting the output — the config stays in sync with
the document.

## Generation rules (deterministic)

- **Order:** document order of `paths`, then GET, POST, PUT, PATCH, DELETE.
- **Probe id:** `"<METHOD> <concrete-path>"`.
- **Path parameters:** `{name}` is replaced by the `set` value for `name`,
  else the literal `1` and a warning is emitted. Parameterized paths that
  collapse to the same concrete path (e.g. `/users/{id}` and
  `/users/{name}` both → `/users/1`) keep the first probe; a warning notes
  the collision. Set realistic values — an endpoint that validates its
  inputs may 404/422 on the default.
- **Request body** (`application/json` only): the media type's `example`,
  else the first named `examples.*.value`, else a minimal skeleton derived
  from the schema (objects recurse; arrays get one item; `string → ""`,
  `integer → 0`, `number → 0.0`, `boolean → false`, enums take the first
  value; `example`/`default` in the schema win). Non-JSON media types
  produce no body.
- **Not imported:** header/query parameters, authentication, servers,
  callbacks. Add header-bearing probes by hand.

## Not supported

- Swagger/OpenAPI **2.x** documents (convert first).
- Documents with no `paths`, or no operations left after the `methods`
  filter — both are loud config errors, never silent empty probe lists.
