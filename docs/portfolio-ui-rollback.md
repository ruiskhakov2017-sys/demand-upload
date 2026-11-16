# Portfolio interface V4

V4 is on `feature/axyro-portfolio-design-v4`. The previous source is tagged
`portfolio-ui-before-refinement-20261116` (commit `312ba62`).

## Compare the interfaces

Both presentations are available simultaneously:

- Previous: `https://axyro.tech/portfolio/control-center?design=previous`
- New: `https://axyro.tech/portfolio/control-center?design=new`

The design parameter is kept when navigating between sections and when signing
in. Review links show a switch in the top bar. Each tab uses its own URL choice;
the selection is not saved in shared local storage or cookies. API and export
URLs do not receive this presentation parameter. Both interfaces use the same
portfolio data and authenticated session. The URL without `design` opens V4.

Before deployment the running frontend image was tagged on the server as
`axyro-portfolio-frontend:before-v4`; its original image ID is recorded in
`~/axyro-portfolio/ui-rollback/before-v4.image`. Keep this image while the design
is under review.

## Restore the previous interface

From the deployed V4 release directory under `~/axyro-portfolio/releases/`:

```sh
sudo docker compose \
  --env-file ../../.env.portfolio --env-file ../../.env.path \
  -f docker-compose.portfolio.yml \
  -f infrastructure/portfolio/compose.ingress.yml \
  -f infrastructure/portfolio/compose.ui-rollback.yml \
  up -d --no-deps --no-build frontend
```

This replaces only the frontend container. It keeps the database, backend,
sessions, public landing page and HTTPS routing intact. Reload the browser after
the container starts. Do not run `down`, initialize the database, or prune the
saved image as part of a visual rollback.

To return to V4, build the frontend from the V4 release and run the same command
without `compose.ui-rollback.yml`, still targeting only `frontend` with
`--no-deps`. The default Compose frontend has no explicit image name, so Compose
will use the newly built `axyro-portfolio-frontend` image.
