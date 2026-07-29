# Releases & Container Image

Tagged releases are published automatically by [`.github/workflows/release.yml`](../.github/workflows/release.yml).

## What happens on a release

Pushing a tag matching `v*.*.*` (e.g. `v0.1.0`) to the `hypersdk/ZyAIQAAgent` repo:

1. Builds the container image from [`docker/Dockerfile`](../docker/Dockerfile).
2. Pushes it to GHCR as `ghcr.io/hypersdk/zyaiqaagent:<tag>` and `:latest`.
3. Creates a GitHub Release on the tag with auto-generated notes.

## Pulling the image

```bash
docker pull ghcr.io/hypersdk/zyaiqaagent:latest
# or a specific version
docker pull ghcr.io/hypersdk/zyaiqaagent:v0.1.0

docker run --rm --env-file .env ghcr.io/hypersdk/zyaiqaagent:latest test
```

The image entrypoint is `zyvor-qa` (see [`docker/Dockerfile`](../docker/Dockerfile)); pass any `zyvor-qa` subcommand as the container command, e.g. `serve --port 8080 --host 0.0.0.0`.

No k3s/Kubernetes cluster is required to run it — it's a normal container. A single Pod works fine against any existing cluster too:

```bash
kubectl run zyvor-qa --image=ghcr.io/hypersdk/zyaiqaagent:latest \
  --env="ZYVOR_BASE_URL=https://zyvor.dev" \
  -- serve --port 8080 --host 0.0.0.0
```

The [`kubernetes/`](../kubernetes/README.md) manifests and the k3s path in [`docs/remote-deploy.md`](remote-deploy.md) are only for when you want a managed Deployment/Service, not a requirement.

GHCR packages inherit repo visibility by default — if the repo is private, `docker pull` requires `docker login ghcr.io` with a token that has `read:packages`.

## Cutting a release

```bash
git tag v0.1.1
git push hypersdk v0.1.1
# or, to also create the GitHub Release explicitly:
gh release create v0.1.1 --repo hypersdk/ZyAIQAAgent --generate-notes
```

Either the tag push or the `gh release create` triggers the workflow (it also accepts `workflow_dispatch` with an existing tag, for re-publishing an image without cutting a new release). Version numbers follow `pyproject.toml` / `package.json` (`0.1.0` today); bump those alongside the tag.
